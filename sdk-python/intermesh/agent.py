import asyncio
import inspect
import json
import sys
from ssl import SSLContext
from typing import Callable, Optional, List, Any, Union

import websockets

from intermesh.message import MessageType, InterMeshMessage
from intermesh.identity import AgentIdentity
from intermesh.task import InterMeshTask, TaskStatus
from intermesh.crypto import (generate_keypair, get_public_key_pem, encrypt_for,
                             decrypt_with, looks_encrypted)
from intermesh.egress import EgressPolicy, apply_egress


class EncryptionMismatch(ValueError):
    """Les deux côtés ne s'accordent pas sur le chiffrement.

    Levée plutôt que de rendre du texte chiffré à un gestionnaire, qui le
    traiterait comme des données et rendrait un résultat faux.
    """
from intermesh.schema import SchemaRegistry, default_registry


class InterMeshAgent:
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
        ssl: Optional[SSLContext] = None,
        egress_policy: Optional[EgressPolicy] = None,
    ):
        self.org_id = org_id
        self.name = name
        self.api_key = api_key
        self._hub_candidates: List[str] = [hub_url] if isinstance(hub_url, str) else list(hub_url)
        self.hub_url = self._hub_candidates[0]
        self.ws = None
        self.token: Optional[str] = None
        self.encrypt = encrypt
        # Contexte TLS pour joindre un Hub en wss://. Utile lorsque le Hub
        # présente un certificat d'une autorité privée, absente du magasin
        # système : voir intermesh.peering.build_peer_ssl_context.
        self._ssl = ssl
        # Politique de sortie appliquée avant chiffrement : c'est le seul
        # point du chemin nominal où le contenu est encore en clair.
        self.egress_policy = egress_policy
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
        """1-LINE INTEGRATION: Transforme n'importe quelle fonction Python en Agent InterMesh."""
        from intermesh.adapters import from_callable as _from_callable
        return _from_callable(fn=fn, name=name, capabilities=capabilities, **kwargs)

    @classmethod
    def from_langchain(cls, chain_or_runnable: Any, name: str, capabilities: Optional[List[str]] = None, **kwargs):
        """1-LINE INTEGRATION: Transforme un Runnable LangChain / CrewAI en Agent InterMesh."""
        from intermesh.adapters import from_langchain as _from_langchain
        return _from_langchain(chain_or_runnable=chain_or_runnable, name=name, capabilities=capabilities, **kwargs)

    @classmethod
    def from_command(cls, command, name: str, capabilities: Optional[List[str]] = None, **kwargs):
        """1-LINE INTEGRATION: n'importe quel exécutable, dans n'importe quel langage."""
        from intermesh.bridge import from_command as _from_command
        return _from_command(command=command, name=name, capabilities=capabilities, **kwargs)

    @classmethod
    def from_http(cls, url: str, name: str, capabilities: Optional[List[str]] = None, **kwargs):
        """1-LINE INTEGRATION: n'importe quel service HTTP déjà en ligne."""
        from intermesh.bridge import from_http as _from_http
        return _from_http(url=url, name=name, capabilities=capabilities, **kwargs)

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
        ws = await websockets.connect(url, ssl=self._ssl)
        reg_payload = self.identity.to_dict()
        if self.api_key:
            reg_payload["api_key"] = self.api_key

        reg_msg = InterMeshMessage(type=MessageType.REGISTER, sender=self.name, content=reg_payload)
        await ws.send(reg_msg.to_json())
        res = InterMeshMessage.from_json(await ws.recv())

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
            self._learn_siblings(res.content.get("cluster_hubs"))
            print(f"✅ [{self.qualified_name}] Connecté sur {url} | E2E: {'🔒 ON' if self.encrypt else '🔓 OFF'}")
        elif res.type == MessageType.ERROR:
            print(f"❌ [{self.name}] Refusé : {res.content}")
            await ws.close()
            raise PermissionError(res.content)

    def _learn_siblings(self, urls) -> None:
        """Ajoute les Hubs frères annoncés par le Hub à la liste de repli.

        Un agent ne connaît que l'adresse qu'on lui a donnée. Si ce Hub
        meurt, la boucle de reconnexion rejoue indéfiniment la même adresse
        morte, alors qu'un frère de la même grappe l'accepterait — c'est
        mesurable, et c'était le comportement avant ceci.

        Les énumérer à la main dans chaque agent serait possible, mais ne
        survivrait pas à l'ajout d'un Hub : la liste vieillirait en silence,
        ce qui revient à ne pas l'avoir. Le Hub, lui, sait qui est vivant.

        Les adresses reçues sont *ajoutées*, jamais substituées : celle que
        l'exploitant a écrite reste la première essayée.
        """
        if not isinstance(urls, list):
            return
        for candidate in urls:
            if isinstance(candidate, str) and candidate and candidate not in self._hub_candidates:
                self._hub_candidates.append(candidate)

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

    async def serve_forever(self):
        """Se connecte et reste en service jusqu'à interruption.

        Sans ça, une intégration « en une ligne » n'en est pas une : il
        fallait encore écrire la boucle asyncio qui maintient l'agent en vie.
        """
        await self.connect()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.close()

    def run(self):
        """Version bloquante de `serve_forever`, pour un script sans asyncio.

            InterMeshAgent.from_callable(ma_fonction, name="bot").run()
        """
        try:
            asyncio.run(self.serve_forever())
        except KeyboardInterrupt:
            print(f"\n[{self.qualified_name}] arrêt demandé.")

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

    def _apply_egress(self, target: str, payload):
        """Filtre un contenu sortant s'il quitte l'organisation.

        Les échanges internes ne sont pas filtrés : la politique décrit ce
        qui ne doit pas franchir la frontière, pas ce que les départements
        d'une même entreprise ont le droit de se dire.
        """
        if self.egress_policy is None or self.egress_policy.is_empty:
            return payload
        target_org = target.split("/")[0] if target and "/" in target else "default"
        if target_org == self.org_id:
            return payload

        filtered, triggered = apply_egress(payload, target_org, self.egress_policy)
        if triggered:
            print(f"🛡️  [{self.qualified_name}] Egress vers '{target_org}' : "
                  f"{', '.join(triggered)}")
        return filtered

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
        except Exception as exc:
            # Une charge reconnaissable comme chiffrée mais qu'on n'arrive pas
            # à ouvrir n'est pas une chaîne ordinaire : la rendre telle quelle
            # la ferait traiter comme des données.
            if looks_encrypted(encrypted_content):
                raise EncryptionMismatch(
                    "Charge chiffrée illisible : elle a été chiffrée pour une autre "
                    "clé publique que celle de cet agent. Un agent qui se reconnecte "
                    "sous le même nom change de clé ; l'émetteur doit alors la "
                    "redemander (WHO_IS) avant de chiffrer."
                ) from exc
            try: return json.loads(encrypted_content)
            except json.JSONDecodeError: return encrypted_content

    def _unwrap_incoming(self, value, what: str):
        """Rend la charge exploitable, ou refuse franchement.

        Le piège que ceci ferme : avec `encrypt=False`, aucun déchiffrement
        n'était tenté et le texte chiffré arrivait tel quel au gestionnaire,
        qui le traitait comme des données. La tâche « réussissait » et
        rendait un résultat faux — le pire mode de défaillance pour un
        produit dont l'argument est le chiffrement de bout en bout.
        """
        if self.encrypt:
            return self._decrypt_content(value) if isinstance(value, str) else value

        if looks_encrypted(value):
            raise EncryptionMismatch(
                f"{what} chiffré reçu alors que le chiffrement est désactivé sur cet "
                f"agent (encrypt=False). Activez-le ici, ou désactivez-le chez "
                f"l'émetteur : les deux côtés doivent s'accorder. Sans ce refus, le "
                f"texte chiffré serait traité comme des données."
            )
        return value

    async def _respond_to_request(self, msg) -> None:
        """Exécute le gestionnaire de requêtes et renvoie la réponse.

        Séparée de la boucle d'écoute pour que celle-ci reste disponible :
        le chiffrement de la réponse a besoin d'un aller-retour WHO_IS, que
        la boucle doit pouvoir traiter pendant que cette tâche l'attend.
        """
        try:
            handler = self._request_handler
            reply = await handler(msg) if inspect.iscoroutinefunction(handler) else handler(msg)
            reply = self._apply_egress(msg.sender, reply)
            if self.encrypt:
                pk = await self._fetch_public_key(msg.sender)
                if pk:
                    reply = self._encrypt_content(pk, reply)
                else:
                    # Sans clé, la réponse partirait en clair alors que
                    # l'appelant a demandé le chiffrement. Le dire est le
                    # minimum : une dégradation silencieuse vers le clair
                    # est pire qu'une erreur.
                    print(f"⚠️  [{self.qualified_name}] Clé publique de "
                          f"{msg.sender} introuvable : réponse NON chiffrée.")
            await self.ws.send(InterMeshMessage(
                type=MessageType.RESPONSE, sender=self.qualified_name, to=msg.sender,
                reply_to=msg.id, content=reply, token=self.token,
            ).to_json())
        except Exception as exc:
            print(f"⚠️  [{self.qualified_name}] Réponse impossible : {exc}")

    async def _listen_loop(self):
        try:
            async for raw in self.ws:
                msg = InterMeshMessage.from_json(raw)

                if msg.type in (MessageType.RESPONSE, MessageType.IDENTITY, MessageType.DISCOVER_RESULT, MessageType.ADMIN_RESULT) and msg.reply_to in self._pending_requests:
                    future = self._pending_requests.pop(msg.reply_to)
                    if not future.done():
                        content = msg.content
                        if self.encrypt and msg.type == MessageType.RESPONSE and isinstance(content, str):
                            content = self._decrypt_content(content)
                        future.set_result(content)

                elif msg.type == MessageType.TASK_ASSIGN:
                    task = InterMeshTask.from_dict(msg.content)
                    asyncio.create_task(self._execute_assigned_task(task))

                elif msg.type == MessageType.TASK_UPDATE:
                    task = InterMeshTask.from_dict(msg.content)
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
                        # Hors de la boucle, comme TASK_ASSIGN. Répondre ici
                        # même conduisait à un interblocage : chiffrer la
                        # réponse exige la clé publique du demandeur, obtenue
                        # par un WHO_IS dont la réponse ne peut être traitée
                        # que par cette boucle — alors bloquée à l'attendre.
                        # Le WHO_IS expirait donc systématiquement (3 s par
                        # requête) et, faute de clé, la réponse repartait en
                        # clair alors que le chiffrement était demandé.
                        asyncio.create_task(self._respond_to_request(msg))

                elif msg.type == MessageType.MESSAGE:
                    content = self._unwrap_incoming(msg.content, "Message")
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

    async def _execute_assigned_task(self, task: InterMeshTask):
        print(f"⚙️  [{self.qualified_name}] Tâche: '{task.title}' de {task.orchestrator}")
        task.update_status(TaskStatus.RUNNING)
        await self.ws.send(InterMeshMessage(type=MessageType.TASK_UPDATE, sender=self.qualified_name, content=task.to_dict(), token=self.token).to_json())

        try:
            # Dans le bloc : un refus de déchiffrement doit rapporter la tâche
            # en échec avec sa raison, pas remonter jusqu'à la boucle d'écoute.
            decrypted_input = self._unwrap_incoming(task.input_data, "Contenu de tâche")
            if self._task_handler:
                output = await self._task_handler(decrypted_input, task) if inspect.iscoroutinefunction(self._task_handler) else self._task_handler(decrypted_input, task)
            else:
                raise NotImplementedError("Aucun handler.")
            encrypted_output = await self._translate_for(task.orchestrator, output)
            encrypted_output = self._apply_egress(task.orchestrator, encrypted_output)
            if self.encrypt:
                pk = await self._fetch_public_key(task.orchestrator)
                if pk: encrypted_output = self._encrypt_content(pk, encrypted_output)
            # task.summary peut avoir été renseigné par le handler (en clair,
            # contrairement à output_data qui peut être chiffré) : sinon on
            # retombe sur un résumé générique pour la page de résumés.
            summary = task.summary or f"Tâche « {task.title} » terminée par {self.qualified_name}."
            task.update_status(TaskStatus.COMPLETED, output_data=encrypted_output, summary=summary)
        except Exception as e:
            task.update_status(TaskStatus.FAILED, error_message=str(e), summary=task.summary or f"Échec de « {task.title} » : {e}")

        await self.ws.send(InterMeshMessage(type=MessageType.TASK_UPDATE, sender=self.qualified_name, content=task.to_dict(), token=self.token).to_json())
        print(f"✅ [{self.qualified_name}] Tâche terminée: {task.status.value.upper()}")

    async def send(self, to: str, content):
        ec = await self._translate_for(to, content)
        ec = self._apply_egress(to, ec)
        if self.encrypt:
            pk = await self._fetch_public_key(to)
            if pk: ec = self._encrypt_content(pk, ec)
        await self.ws.send(InterMeshMessage(type=MessageType.MESSAGE, sender=self.qualified_name, to=to, content=ec, token=self.token).to_json())

    async def ask(self, to: str, content, timeout: float = 10.0):
        ec = await self._translate_for(to, content)
        ec = self._apply_egress(to, ec)
        if self.encrypt:
            pk = await self._fetch_public_key(to)
            if pk: ec = self._encrypt_content(pk, ec)
        msg = InterMeshMessage(type=MessageType.REQUEST, sender=self.qualified_name, to=to, content=ec, token=self.token)
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
        ei = self._apply_egress(assignee, ei)
        if self.encrypt:
            pk = await self._fetch_public_key(assignee)
            if pk: ei = self._encrypt_content(pk, ei)
        task = InterMeshTask(title=title, orchestrator=self.qualified_name, assignee=assignee, input_data=ei)
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
        await self.ws.send(InterMeshMessage(type=MessageType.TASK_SUBMIT, sender=self.qualified_name, to=assignee, content=content, token=self.token).to_json())
        print(f"📝 [{self.qualified_name}] Tâche ➜ {assignee}")
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_tasks.pop(task.task_id, None)
            raise TimeoutError(f"Tâche '{title}' expirée ({timeout}s).")

    async def who_is(self, agent_name: str, timeout: float = 5.0) -> dict:
        msg = InterMeshMessage(type=MessageType.WHO_IS, sender=self.qualified_name, content=agent_name, token=self.token)
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
        msg = InterMeshMessage(type=MessageType.DISCOVER, sender=self.qualified_name, content=query, token=self.token)
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
        msg = InterMeshMessage(
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
