import asyncio
import inspect
import json
import sys
from typing import Callable, Optional, List

import websockets

from nexus_sdk.message import MessageType, NexusMessage
from nexus_sdk.identity import AgentIdentity
from nexus_sdk.task import NexusTask, TaskStatus
from nexus_sdk.crypto import generate_keypair, get_public_key_pem, encrypt_for, decrypt_with


class NexusAgent:
    def __init__(
        self,
        name: str,
        org_id: str = "default",
        api_key: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
        hub_url: str = "ws://localhost:8765",
        encrypt: bool = True
    ):
        self.org_id = org_id
        self.name = name
        self.api_key = api_key
        self.hub_url = hub_url
        self.ws = None
        self.token: Optional[str] = None
        self.encrypt = encrypt
        self._message_handler: Optional[Callable] = None
        self._request_handler: Optional[Callable] = None
        self._task_handler: Optional[Callable] = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._pending_tasks: dict[str, asyncio.Future] = {}
        self._public_key_cache: dict[str, str] = {}

        self._private_key = generate_keypair()
        self._public_key_pem = get_public_key_pem(self._private_key)

        self.identity = AgentIdentity(
            name=name,
            org_id=org_id,
            capabilities=capabilities or [],
            roles=roles or ["standard"],
            permissions=permissions or [],
            metadata=metadata or {},
            public_key=self._public_key_pem
        )
        self.qualified_name = self.identity.qualified_name

    def on_message(self, handler: Callable): self._message_handler = handler
    def on_request(self, handler: Callable): self._request_handler = handler
    def on_task(self, handler: Callable): self._task_handler = handler

    async def connect(self):
        self.ws = await websockets.connect(self.hub_url)
        
        reg_payload = self.identity.to_dict()
        if self.api_key:
            reg_payload["api_key"] = self.api_key

        reg_msg = NexusMessage(type=MessageType.REGISTER, sender=self.name, content=reg_payload)
        await self.ws.send(reg_msg.to_json())
        res = NexusMessage.from_json(await self.ws.recv())

        if res.type == MessageType.REGISTERED:
            self.token = res.content.get("token")
            self.qualified_name = res.content.get("qualified_name", self.name)
            
            # Synchronisation des privilèges certifiés par le Hub
            if "roles" in res.content:
                self.identity.roles = res.content["roles"]
            if "permissions" in res.content:
                self.identity.permissions = res.content["permissions"]
            if "org_id" in res.content:
                self.identity.org_id = res.content["org_id"]
                self.org_id = res.content["org_id"]

            print(f"✅ [{self.qualified_name}] Connecté sur {self.hub_url} | E2E: {'🔒 ON' if self.encrypt else '🔓 OFF'}")
        elif res.type == MessageType.ERROR:
            print(f"❌ [{self.name}] Refusé : {res.content}")
            await self.ws.close()
            raise PermissionError(res.content)

        asyncio.create_task(self._listen_loop())

    async def _fetch_public_key(self, agent_name: str) -> Optional[str]:
        if agent_name in self._public_key_cache:
            return self._public_key_cache[agent_name]
        try:
            data = await self.who_is(agent_name, timeout=3.0)
            pk = data.get("public_key")
            if pk:
                self._public_key_cache[agent_name] = pk
                return pk
        except Exception:
            pass
        return None

    def _encrypt_content(self, recipient_pk: str, content) -> str:
        plaintext = json.dumps(content) if not isinstance(content, str) else content
        return encrypt_for(recipient_pk, plaintext)

    def _decrypt_content(self, encrypted_content: str):
        try:
            decrypted = decrypt_with(self._private_key, encrypted_content)
            try: return json.loads(decrypted)
            except json.JSONDecodeError: return decrypted
        except Exception:
            try: return json.loads(encrypted_content)
            except json.JSONDecodeError: return encrypted_content

    async def _listen_loop(self):
        try:
            async for raw in self.ws:
                msg = NexusMessage.from_json(raw)

                if msg.type in (MessageType.RESPONSE, MessageType.IDENTITY, MessageType.DISCOVER_RESULT, MessageType.ADMIN_RESULT) and msg.reply_to in self._pending_requests:
                    future = self._pending_requests.pop(msg.reply_to)
                    if not future.done():
                        content = msg.content
                        if self.encrypt and msg.type == MessageType.RESPONSE and isinstance(content, str):
                            content = self._decrypt_content(content)
                        future.set_result(content)

                elif msg.type == MessageType.TASK_ASSIGN:
                    task = NexusTask.from_dict(msg.content)
                    asyncio.create_task(self._execute_assigned_task(task))

                elif msg.type == MessageType.TASK_UPDATE:
                    task = NexusTask.from_dict(msg.content)
                    if task.task_id in self._pending_tasks:
                        future = self._pending_tasks[task.task_id]
                        if task.status == TaskStatus.COMPLETED:
                            self._pending_tasks.pop(task.task_id)
                            output = task.output_data
                            if self.encrypt and isinstance(output, str):
                                output = self._decrypt_content(output)
                            if not future.done(): future.set_result(output)
                        elif task.status == TaskStatus.FAILED:
                            self._pending_tasks.pop(task.task_id)
                            if not future.done(): future.set_exception(RuntimeError(task.error_message))

                elif msg.type == MessageType.REQUEST:
                    content = msg.content
                    if self.encrypt and isinstance(content, str):
                        content = self._decrypt_content(content)
                    msg.content = content
                    if self._request_handler:
                        reply = await self._request_handler(msg) if inspect.iscoroutinefunction(self._request_handler) else self._request_handler(msg)
                        if self.encrypt:
                            pk = await self._fetch_public_key(msg.sender)
                            if pk: reply = self._encrypt_content(pk, reply)
                        await self.ws.send(NexusMessage(type=MessageType.RESPONSE, sender=self.qualified_name, to=msg.sender, reply_to=msg.id, content=reply, token=self.token).to_json())

                elif msg.type == MessageType.MESSAGE:
                    content = msg.content
                    if self.encrypt and isinstance(content, str): content = self._decrypt_content(content)
                    msg.content = content
                    if self._message_handler:
                        if inspect.iscoroutinefunction(self._message_handler): await self._message_handler(msg)
                        else: self._message_handler(msg)

                elif msg.type == MessageType.ERROR:
                    print(f"❌ [{self.qualified_name}] {msg.content}")
                    if msg.reply_to and msg.reply_to in self._pending_requests:
                        future = self._pending_requests.pop(msg.reply_to)
                        if not future.done(): future.set_exception(RuntimeError(msg.content))
                    for tid, fut in list(self._pending_tasks.items()):
                        if not fut.done():
                            fut.set_exception(RuntimeError(msg.content))
                            self._pending_tasks.pop(tid)

        except websockets.ConnectionClosed:
            print(f"⚠️  [{self.qualified_name}] Déconnecté.")

    async def _execute_assigned_task(self, task: NexusTask):
        print(f"⚙️  [{self.qualified_name}] Tâche: '{task.title}' de {task.orchestrator}")
        task.update_status(TaskStatus.RUNNING)
        await self.ws.send(NexusMessage(type=MessageType.TASK_UPDATE, sender=self.qualified_name, content=task.to_dict(), token=self.token).to_json())

        decrypted_input = task.input_data
        if self.encrypt and isinstance(decrypted_input, str):
            decrypted_input = self._decrypt_content(decrypted_input)

        try:
            if self._task_handler:
                output = await self._task_handler(decrypted_input, task) if inspect.iscoroutinefunction(self._task_handler) else self._task_handler(decrypted_input, task)
            else:
                raise NotImplementedError("Aucun handler.")
            encrypted_output = output
            if self.encrypt:
                pk = await self._fetch_public_key(task.orchestrator)
                if pk: encrypted_output = self._encrypt_content(pk, output)
            task.update_status(TaskStatus.COMPLETED, output_data=encrypted_output)
        except Exception as e:
            task.update_status(TaskStatus.FAILED, error_message=str(e))

        await self.ws.send(NexusMessage(type=MessageType.TASK_UPDATE, sender=self.qualified_name, content=task.to_dict(), token=self.token).to_json())
        print(f"✅ [{self.qualified_name}] Tâche terminée: {task.status.value.upper()}")

    async def send(self, to: str, content):
        ec = content
        if self.encrypt:
            pk = await self._fetch_public_key(to)
            if pk: ec = self._encrypt_content(pk, content)
        await self.ws.send(NexusMessage(type=MessageType.MESSAGE, sender=self.qualified_name, to=to, content=ec, token=self.token).to_json())

    async def ask(self, to: str, content, timeout: float = 10.0):
        ec = content
        if self.encrypt:
            pk = await self._fetch_public_key(to)
            if pk: ec = self._encrypt_content(pk, content)
        msg = NexusMessage(type=MessageType.REQUEST, sender=self.qualified_name, to=to, content=ec, token=self.token)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_requests[msg.id] = future
        await self.ws.send(msg.to_json())
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(msg.id, None)
            raise TimeoutError(f"Timeout {timeout}s.")

    async def submit_task(self, title: str, assignee: str, input_data, timeout: float = 15.0):
        ei = input_data
        if self.encrypt:
            pk = await self._fetch_public_key(assignee)
            if pk: ei = self._encrypt_content(pk, input_data)
        task = NexusTask(title=title, orchestrator=self.qualified_name, assignee=assignee, input_data=ei)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_tasks[task.task_id] = future
        await self.ws.send(NexusMessage(type=MessageType.TASK_SUBMIT, sender=self.qualified_name, to=assignee, content=task.to_dict(), token=self.token).to_json())
        print(f"📝 [{self.qualified_name}] Tâche ➜ {assignee}")
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_tasks.pop(task.task_id, None)
            raise TimeoutError(f"Tâche '{title}' expirée ({timeout}s).")

    async def admin(self, command: str, timeout: float = 10.0, **params):
        """
        Exécute une commande d'administration sur le Hub.

        Exige une identité authentifiée par clé d'API avec le rôle admin :
        des rôles déclarés à la connexion sont refusés par le Hub.

            agent = NexusAgent(name="console", api_key="nx_live_...")
            await agent.connect()
            info = await agent.admin("hub.info")

        Raises:
            PermissionError: administration refusée.
            RuntimeError:    commande rejetée par le Hub.
        """
        msg = NexusMessage(
            type=MessageType.ADMIN_REQUEST, sender=self.qualified_name,
            content={"command": command, "params": params}, token=self.token,
        )
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_requests[msg.id] = future
        await self.ws.send(msg.to_json())

        try:
            reply = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(msg.id, None)
            raise TimeoutError(f"Commande '{command}' expirée ({timeout}s).")

        if not reply.get("ok"):
            error = reply.get("error", "commande refusée")
            if "ADMIN_DENIED" in error:
                raise PermissionError(error)
            raise RuntimeError(error)
        return reply.get("result")

    async def who_is(self, agent_name: str, timeout: float = 5.0) -> dict:
        msg = NexusMessage(type=MessageType.WHO_IS, sender=self.qualified_name, content=agent_name, token=self.token)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_requests[msg.id] = future
        await self.ws.send(msg.to_json())
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            if isinstance(result, dict) and result.get("public_key"):
                self._public_key_cache[agent_name] = result["public_key"]
            return result
        except asyncio.TimeoutError:
            self._pending_requests.pop(msg.id, None)
            raise TimeoutError("Who_is timeout.")

    async def discover(
        self,
        capabilities: Optional[List[str]] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
        name_contains: Optional[str] = None,
        online_only: bool = True,
        limit: int = 10,
        timeout: float = 5.0,
    ) -> dict:
        """
        Recherche des agents sur le réseau.

            await agent.discover(capabilities=["translate"])
            await agent.discover(roles=["worker"], metadata={"region": "africa"})

        Capacités et permissions sont exigées toutes ensemble ; il suffit
        d'un rôle correspondant. `online_only=False` retrouve aussi les
        agents connus mais actuellement déconnectés.
        """
        query: dict = {"online_only": online_only, "limit": limit}
        if capabilities:  query["capabilities"] = capabilities
        if roles:         query["roles"] = roles
        if permissions:   query["permissions"] = permissions
        if metadata:      query["metadata"] = metadata
        if name_contains: query["name_contains"] = name_contains

        msg = NexusMessage(type=MessageType.DISCOVER, sender=self.qualified_name, content=query, token=self.token)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_requests[msg.id] = future
        await self.ws.send(msg.to_json())
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(msg.id, None)
            raise TimeoutError("Discover timeout.")
