import asyncio
import inspect
import json
import sys
from typing import Callable, Optional, List, Any, Union

import websockets

from nexus_sdk.message import MessageType, NexusMessage
from nexus_sdk.identity import AgentIdentity
from nexus_sdk.task import NexusTask, TaskStatus
from nexus_sdk.crypto import generate_keypair, get_public_key_pem, encrypt_for, decrypt_with
from nexus_sdk.schema import SchemaRegistry, default_registry


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
        hub_url: Union[str, List[str]] = "ws://localhost:8765",
        encrypt: bool = True,
        auto_reconnect: bool = False,
        reconnect_backoff: float = 0.5,
        reconnect_max_backoff: float = 15.0,
        schema: Optional[str] = None,
        schema_registry: Optional[SchemaRegistry] = None,
    ):
        self.org_id = org_id
        self.name = name
        self.api_key = api_key
        self._hub_candidates: List[str] = [hub_url] if isinstance(hub_url, str) else list(hub_url)
        self.hub_url = self._hub_candidates[0]
        self.ws = None
        self.token: Optional[str] = None
        self.encrypt = encrypt
        self.auto_reconnect = auto_reconnect
        self._reconnect_backoff = reconnect_backoff
        self._reconnect_max_backoff = reconnect_max_backoff
        self._closing = False
        self._on_failover_handler: Optional[Callable] = None
        self._message_handler: Optional[Callable] = None
        self._request_handler: Optional[Callable] = None
        self._task_handler: Optional[Callable] = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._pending_tasks: dict[str, asyncio.Future] = {}
        self._public_key_cache: dict[str, str] = {}
        self.schema_registry = schema_registry or default_registry()
        self._target_schema_cache: dict[str, Optional[str]] = {}

        self._private_key = generate_keypair()
        self._public_key_pem = get_public_key_pem(self._private_key)

        self.identity = AgentIdentity(
            name=name,
            org_id=org_id,
            capabilities=capabilities or [],
            roles=roles or ["standard"],
            permissions=permissions or [],
            metadata=metadata or {},
            public_key=self._public_key_pem,
            schema=schema
        )
        self.qualified_name = self.identity.qualified_name

    @classmethod
    def from_callable(cls, fn: Callable[[Any], Any], name: str, capabilities: Optional[List[str]] = None, **kwargs):
        """1-LINE INTEGRATION: Transforme n'importe quelle fonction Python en Agent Nexus."""
        from nexus_sdk.adapters import from_callable as _from_callable
        return _from_callable(fn=fn, name=name, capabilities=capabilities, **kwargs)

    @classmethod
    def from_langchain(cls, chain_or_runnable: Any, name: str, capabilities: Optional[List[str]] = None, **kwargs):
        """1-LINE INTEGRATION: Transforme un Runnable LangChain / CrewAI en Agent Nexus."""
        from nexus_sdk.adapters import from_langchain as _from_langchain
        return _from_langchain(chain_or_runnable=chain_or_runnable, name=name, capabilities=capabilities, **kwargs)

    def on_message(self, handler: Callable): self._message_handler = handler
    def on_request(self, handler: Callable): self._request_handler = handler
    def on_task(self, handler: Callable): self._task_handler = handler

    def on_failover(self, handler: Callable):
        """
        Appelé après une reconnexion automatique réussie sur un Hub différent
        du précédent : `handler(old_url, new_url)`. N'a d'effet qu'avec
        `auto_reconnect=True`.
        """
        self._on_failover_handler = handler

    async def _register_on(self, url: str) -> None:
        """Connexion + REGISTER sur une URL donnée. Lève sur refus ou échec réseau."""
        ws = await websockets.connect(url)
        reg_payload = self.identity.to_dict()
        if self.api_key:
            reg_payload["api_key"] = self.api_key

        reg_msg = NexusMessage(type=MessageType.REGISTER, sender=self.name, content=reg_payload)
        await ws.send(reg_msg.to_json())
        res = NexusMessage.from_json(await ws.recv())

        if res.type == MessageType.REGISTERED:
            self.ws = ws
            self.hub_url = url
            self.token = res.content.get("token")
            self.qualified_name = res.content.get("qualified_name", self.name)
            if "roles" in res.content: self.identity.roles = res.content["roles"]
            if "permissions" in res.content: self.identity.permissions = res.content["permissions"]
            if "org_id" in res.content:
                self.identity.org_id = res.content["org_id"]
                self.org_id = res.content["org_id"]
            print(f"✅ [{self.qualified_name}] Connecté sur {url} | E2E: {'🔒 ON' if self.encrypt else '🔓 OFF'}")
        elif res.type == MessageType.ERROR:
            print(f"❌ [{self.name}] Refusé : {res.content}")
            await ws.close()
            raise PermissionError(res.content)

    async def connect(self):
        """
        Connexion initiale. Avec plusieurs URLs de Hub, essaie chacune dans
        l'ordre — un Hub injoignable (réseau) passe au suivant, un refus
        explicite (`PermissionError`) est propagé tel quel : ce n'est pas un
        problème de disponibilité, réessayer ailleurs ne changerait rien.
        """
        last_exc: Optional[Exception] = None
        for url in self._hub_candidates:
            try:
                await self._register_on(url)
                break
            except PermissionError:
                raise
            except Exception as exc:
                last_exc = exc
                continue
        else:
            raise ConnectionError(
                f"Impossible de joindre un Hub parmi {self._hub_candidates} : {last_exc}"
            )

        asyncio.create_task(self._listen_loop())

    async def close(self):
        """Déconnexion volontaire : n'entraîne jamais de reconnexion automatique."""
        self._closing = True
        if self.ws is not None:
            await self.ws.close()

    def _fail_pending(self, reason: str) -> None:
        error = ConnectionError(reason)
        for future in list(self._pending_requests.values()):
            if not future.done():
                future.set_exception(error)
        self._pending_requests.clear()
        for future in list(self._pending_tasks.values()):
            if not future.done():
                future.set_exception(error)
        self._pending_tasks.clear()

    async def _reconnect_loop(self):
        """
        Tente de rejoindre un Hub (le même, ou un autre candidat de la liste)
        avec un recul exponentiel, jusqu'à réussite ou fermeture volontaire.

        Ceci suppose que les Hubs candidats sont des répliques opérationnelles
        de la même organisation (même backend d'état partagé côté Hub) — ce
        module ne fait pas d'élection de leader ni de promotion automatique
        d'un Hub de secours : c'est un mécanisme de reconnexion côté client,
        pas un orchestrateur de cluster.
        """
        old_url = self.hub_url
        attempt = 0
        while not self._closing:
            for url in self._hub_candidates:
                try:
                    await self._register_on(url)
                    if self._on_failover_handler and url != old_url:
                        result = self._on_failover_handler(old_url, url)
                        if inspect.isawaitable(result):
                            await result
                    asyncio.create_task(self._listen_loop())
                    return
                except PermissionError:
                    raise
                except Exception:
                    continue
            attempt += 1
            backoff = min(self._reconnect_max_backoff, self._reconnect_backoff * (2 ** min(attempt, 5)))
            await asyncio.sleep(backoff)

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

    async def _fetch_target_schema(self, agent_name: str) -> Optional[str]:
        if agent_name in self._target_schema_cache:
            return self._target_schema_cache[agent_name]
        try:
            data = await self.who_is(agent_name, timeout=3.0)
            target_schema = data.get("schema") if isinstance(data, dict) else None
        except Exception:
            target_schema = None
        self._target_schema_cache[agent_name] = target_schema
        return target_schema

    async def _translate_for(self, target: str, payload):
        """
        Traduit `payload` vers le schéma déclaré par `target`, si on connaît
        le nôtre et le sien et qu'ils diffèrent. Sans schéma déclaré des deux
        côtés, ou si le payload n'est pas un dict, rien n'est modifié — la
        traduction n'invente jamais de structure.
        """
        if not self.identity.schema or not isinstance(payload, dict):
            return payload
        target_schema = await self._fetch_target_schema(target)
        if not target_schema or target_schema == self.identity.schema:
            return payload
        try:
            return self.schema_registry.translate(payload, target_schema, self.identity.schema)
        except Exception:
            return payload

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
                        if not future.done():
                            if isinstance(msg.content, str) and msg.content.startswith("ADMIN_DENIED"):
                                future.set_exception(PermissionError(msg.content))
                            else:
                                future.set_exception(RuntimeError(msg.content))
                    for tid, fut in list(self._pending_tasks.items()):
                        if not fut.done():
                            fut.set_exception(RuntimeError(msg.content))
                            self._pending_tasks.pop(tid)

        except websockets.ConnectionClosed:
            pass
        finally:
            # La boucle `async for` sort SANS exception sur une fermeture
            # normale (code 1000/1001) — le nettoyage doit donc tourner ici,
            # pas seulement dans le except, sinon une déconnexion propre
            # laisse les appels en attente bloqués jusqu'à leur propre timeout.
            print(f"⚠️  [{self.qualified_name}] Déconnecté.")
            self._fail_pending("Connexion au Hub perdue.")
            if self.auto_reconnect and not self._closing:
                asyncio.create_task(self._reconnect_loop())

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
            encrypted_output = await self._translate_for(task.orchestrator, output)
            if self.encrypt:
                pk = await self._fetch_public_key(task.orchestrator)
                if pk: encrypted_output = self._encrypt_content(pk, encrypted_output)
            task.update_status(TaskStatus.COMPLETED, output_data=encrypted_output)
        except Exception as e:
            task.update_status(TaskStatus.FAILED, error_message=str(e))

        await self.ws.send(NexusMessage(type=MessageType.TASK_UPDATE, sender=self.qualified_name, content=task.to_dict(), token=self.token).to_json())
        print(f"✅ [{self.qualified_name}] Tâche terminée: {task.status.value.upper()}")

    async def send(self, to: str, content):
        ec = await self._translate_for(to, content)
        if self.encrypt:
            pk = await self._fetch_public_key(to)
            if pk: ec = self._encrypt_content(pk, ec)
        await self.ws.send(NexusMessage(type=MessageType.MESSAGE, sender=self.qualified_name, to=to, content=ec, token=self.token).to_json())

    async def ask(self, to: str, content, timeout: float = 10.0):
        ec = await self._translate_for(to, content)
        if self.encrypt:
            pk = await self._fetch_public_key(to)
            if pk: ec = self._encrypt_content(pk, ec)
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

    async def submit_task(self, title: str, assignee: str, input_data, timeout: float = 15.0,
                          estimated_cost: float = 0.0, parent_task_id: Optional[str] = None,
                          escrow: Optional[dict] = None):
        ei = await self._translate_for(assignee, input_data)
        if self.encrypt:
            pk = await self._fetch_public_key(assignee)
            if pk: ei = self._encrypt_content(pk, ei)
        task = NexusTask(title=title, orchestrator=self.qualified_name, assignee=assignee, input_data=ei)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_tasks[task.task_id] = future
        content = task.to_dict()
        if estimated_cost:
            content["estimated_cost"] = estimated_cost
        if parent_task_id:
            content["parent_task_id"] = parent_task_id
        if escrow:
            content["escrow"] = escrow
        await self.ws.send(NexusMessage(type=MessageType.TASK_SUBMIT, sender=self.qualified_name, to=assignee, content=content, token=self.token).to_json())
        print(f"📝 [{self.qualified_name}] Tâche ➜ {assignee}")
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_tasks.pop(task.task_id, None)
            raise TimeoutError(f"Tâche '{title}' expirée ({timeout}s).")

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

    async def discover(self, timeout: float = 5.0, **query) -> dict:
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

    async def admin(self, command: str, **params) -> dict:
        """
        Envoie une commande à la console d'administration du Hub.

        Raises:
            PermissionError: la commande a été refusée par `authorize()`
                (identité non authentifiée par clé d'API, ou rôle
                insuffisant) — message préfixé par `ADMIN_DENIED:`.
            RuntimeError: la commande a été exécutée mais refusée par le
                gestionnaire lui-même (ex: hors du périmètre de l'org).
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
            return await asyncio.wait_for(future, timeout=15.0)
        except asyncio.TimeoutError:
            self._pending_requests.pop(msg.id, None)
            raise TimeoutError(f"Commande admin '{command}' expirée.")
