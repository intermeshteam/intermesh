"""Le proxy d'assurance : ce qui sort réellement du système.

Un SDK enregistre ce que l'agent *déclare* avoir fait. Le proxy enregistre
ce qui *est parti sur le réseau*. Pour une preuve destinée à un tiers, la
différence est décisive : une attestation produite par le système audité,
sur la foi de ses propres déclarations, ne vaut rien devant un auditeur.

Il se place sur le chemin, pas dans le code :

    export HTTP_PROXY=http://localhost:8443

Aucune ligne à écrire, dans aucun langage. C'est la réponse à la
contrainte multi-langages : non pas une ligne partout, mais zéro ligne.

## Ce que le proxy voit, et ce qu'il ne voit pas

En clair (`http://`), la requête arrive en URI absolue : méthode, hôte,
chemin, en-têtes et corps sont visibles. La classification porte sur tout.

En TLS (`https://`), le client envoie `CONNECT hôte:443` puis chiffre.
**Le proxy ne voit que l'hôte et le port** — ni chemin, ni corps. Une
règle sur `path_contains` ne peut donc pas s'appliquer, et le proxy le
dit dans la preuve plutôt que de laisser croire qu'il a jugé sur pièces.
Voir la limite en tête de `docs/ASSURANCE.md` : lever cette restriction
suppose d'interrompre le TLS avec une autorité de certification installée
sur le client, ce que ce MVP ne fait pas.
"""

from __future__ import annotations

import http.client
import json
import select
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..canonical import sha256_hex
from .evidence import GENESIS, ActionEvidence, payload_digest
from .policy import ALLOW, APPROVAL, BLOCK, Policy
from .risk import RiskLevel

DEFAULT_PORT = 8443
# Ces en-têtes portent des secrets. On enregistre leur présence, jamais
# leur valeur : une preuve qui contiendrait un jeton serait elle-même la
# fuite qu'elle prétend documenter.
SENSITIVE = {"authorization", "proxy-authorization", "cookie", "set-cookie",
             "x-api-key", "api-key", "x-auth-token"}
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "te",
              "proxy-authorization", "trailers", "transfer-encoding", "upgrade"}


class EvidenceStore:
    """Journal de preuves en JSON Lines, chaîné par empreinte.

    Une ligne par preuve : le format se lit avec `tail`, se coupe sans
    outil et ne se corrompt pas entièrement si le processus meurt en plein
    écriture — seule la dernière ligne est perdue, et le chaînage la
    signale.
    """

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._last_hash = GENESIS
        self.count = 0
        if self.path and self.path.is_file():
            self._resume()

    def _resume(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._last_hash = (record.get("evidence") or {}).get("hash", self._last_hash)
            self.count += 1

    @property
    def last_hash(self) -> str:
        return self._last_hash

    def append(self, record: dict) -> dict:
        with self._lock:
            self._last_hash = (record.get("evidence") or {}).get("hash", GENESIS)
            self.count += 1
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                self.path.chmod(0o600)
        return record


class AssuranceProxy:
    """Assemble politique, preuve et journal. Sans dépendance HTTP."""

    def __init__(self, policy: Policy, private_key: Ed25519PrivateKey,
                 store: EvidenceStore, agent_id: str = "unknown-agent",
                 organization_id: str = "default"):
        self.policy = policy
        self.key = private_key
        self.store = store
        self.agent_id = agent_id
        self.organization_id = organization_id

    def assess(self, method: str, url: str):
        return self.policy.evaluate(method, url)

    def record(self, *, method: str, url: str, verdict, status: str,
               payload_hash: Optional[str] = None,
               response_status: Optional[int] = None,
               response_hash: Optional[str] = None,
               **extra) -> dict:
        evidence = ActionEvidence.build(
            agent_id=self.agent_id,
            organization_id=self.organization_id,
            method=method, target=url, risk=verdict.risk,
            decision=verdict.decision, policy=self.policy.version_label(),
            rule=verdict.rule,
            payload_hash=payload_hash, status=status,
            response_status=response_status, response_hash=response_hash,
            prev_hash=self.store.last_hash,
            extra={"reason": verdict.reason or None, **extra},
        )
        return self.store.append(evidence.sign(self.key))


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "InterMeshAssurance"
    # Sans ceci, l'algorithme de Nagle retient l'en-tête en attendant le
    # corps pendant que le pair attend l'en-tête pour acquitter : 40 ms de
    # blocage mutuel à chaque requête, mesurés à 82 ms de surcoût médian.
    # Le coût réel de la signature est de l'ordre de la centaine de
    # microsecondes — tout le reste était ce blocage.
    disable_nagle_algorithm = True
    proxy: AssuranceProxy
    quiet: bool = False

    def setup(self):
        super().setup()
        # Le client écrit ses en-têtes puis son corps en deux segments. Son
        # Nagle attend l'acquittement du premier ; notre acquittement
        # différé attend 40 ms. TCP_QUICKACK casse cette attente mutuelle.
        # Linux seulement — ailleurs, l'option n'existe pas et son absence
        # ne doit pas empêcher le proxy de démarrer.
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        except (AttributeError, OSError):
            pass

    # ------------------------------------------------------------------

    def do_GET(self): self._handle("GET")            # noqa: E704, N802
    def do_POST(self): self._handle("POST")          # noqa: E704, N802
    def do_PUT(self): self._handle("PUT")            # noqa: E704, N802
    def do_PATCH(self): self._handle("PATCH")        # noqa: E704, N802
    def do_DELETE(self): self._handle("DELETE")      # noqa: E704, N802
    def do_HEAD(self): self._handle("HEAD")          # noqa: E704, N802

    # ------------------------------------------------------------------

    def _handle(self, method: str) -> None:
        url = self.path
        if not url.startswith("http"):
            # Requête directe plutôt que via proxy : on le dit au lieu de
            # deviner un hôte.
            return self._json(400, {"error": "not_a_proxy_request",
                                    "hint": "configurez HTTP_PROXY"})

        body = self._read_body()
        verdict = self.proxy.assess(method, url)

        if verdict.decision == BLOCK:
            record = self.proxy.record(method=method, url=url, verdict=verdict,
                                       status="blocked",
                                       payload_hash=payload_digest(body))
            return self._refusal(403, "blocked", verdict, record)

        if verdict.decision == APPROVAL:
            record = self.proxy.record(method=method, url=url, verdict=verdict,
                                       status="pending_approval",
                                       payload_hash=payload_digest(body))
            return self._refusal(403, "approval_required", verdict, record)

        self._forward(method, url, body, verdict)

    def _forward(self, method: str, url: str, body: bytes, verdict) -> None:
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP}
        try:
            status, payload, out_headers = _send_upstream(method, url, body, headers)
        except Exception as exc:
            self.proxy.record(method=method, url=url, verdict=verdict,
                              status="failed", payload_hash=payload_digest(body),
                              error=type(exc).__name__)
            return self._json(502, {"error": "upstream_unreachable",
                                    "reason": str(exc)})

        record = None
        if self.proxy.policy.requires_evidence(verdict.risk):
            record = self.proxy.record(
                method=method, url=url, verdict=verdict, status="executed",
                payload_hash=payload_digest(body), response_status=status,
                response_hash=sha256_hex(payload) if payload else None)

        extra = [(k, v) for k, v in out_headers if k.lower() != "content-length"]
        extra.append(("X-InterMesh-Risk", str(verdict.risk)))
        extra.append(("X-InterMesh-Decision", verdict.decision))
        if record:
            extra.append(("X-InterMesh-Evidence", record["action_id"]))
        self._respond(status, extra, b"" if method == "HEAD" else payload,
                      content_length=len(payload))

    # ------------------------------------------------------------------

    def do_CONNECT(self) -> None:  # noqa: N802
        """Tunnel TLS — l'hôte est visible, le chemin ne l'est pas."""
        host, _, port = self.path.partition(":")
        url = f"https://{host}"
        verdict = self.proxy.assess("CONNECT", url)

        if verdict.decision in (BLOCK, APPROVAL):
            status = "blocked" if verdict.decision == BLOCK else "pending_approval"
            record = self.proxy.record(method="CONNECT", url=url, verdict=verdict,
                                       status=status, tls_opaque=True)
            return self._refusal(403, status, verdict, record)

        try:
            upstream = socket.create_connection((host, int(port or 443)), timeout=15)
        except OSError as exc:
            return self._json(502, {"error": "connect_failed", "reason": str(exc)})

        if self.proxy.policy.requires_evidence(verdict.risk):
            # `tls_opaque` est la mention d'honnêteté : la preuve atteste
            # d'une connexion vers un hôte, pas d'une action sur un chemin.
            self.proxy.record(method="CONNECT", url=url, verdict=verdict,
                              status="tunnelled", tls_opaque=True)

        self.send_response(200, "Connection Established")
        self.end_headers()
        self._pipe(self.connection, upstream)

    @staticmethod
    def _pipe(client: socket.socket, upstream: socket.socket) -> None:
        sockets = [client, upstream]
        try:
            while True:
                readable, _, errored = select.select(sockets, [], sockets, 30)
                if errored or not readable:
                    break
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is client else client).sendall(data)
        except OSError:
            pass
        finally:
            for sock in sockets:
                try:
                    sock.close()
                except OSError:
                    pass

    # ------------------------------------------------------------------

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _refusal(self, status: int, kind: str, verdict, record: dict) -> None:
        self._json(status, {
            "error": kind,
            "risk": str(verdict.risk),
            "rule": verdict.rule,
            "reason": verdict.reason or None,
            "policy": self.proxy.policy.version_label(),
            "evidence_id": record["action_id"],
            "evidence_hash": record["evidence"]["hash"],
        })

    def _json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._respond(status, [("Content-Type", "application/json; charset=utf-8")], raw)

    def _respond(self, status: int, headers: list, body: bytes,
                 content_length: Optional[int] = None) -> None:
        """Statut, en-têtes et corps en **une seule écriture**.

        `send_response` + `end_headers` + `write(body)` produit deux
        segments TCP. Le pair attend la suite avant d'acquitter, l'émetteur
        attend l'acquittement avant d'envoyer : 40 ms de blocage par
        requête, mesurés. Les composants internes du proxy totalisent
        1,2 ms — tout le reste venait de ce découpage.
        """
        lines = [f"HTTP/1.1 {status} {self.responses.get(status, ('',))[0]}".encode()]
        for key, value in headers:
            lines.append(f"{key}: {value}".encode())
        lines.append(f"Content-Length: {content_length if content_length is not None else len(body)}".encode())
        lines.append(b"")
        lines.append(body)
        self.wfile.write(b"\r\n".join(lines))
        self.log_request(status)

    def log_message(self, fmt: str, *args) -> None:
        if not self.quiet:
            super().log_message(fmt, *args)


def _send_upstream(method: str, url: str, body: bytes,
                   headers: dict) -> Tuple[int, bytes, list]:
    """Relaie vers la cible, sans Nagle.

    `urllib` ne désactive pas l'algorithme de Nagle : l'en-tête partait
    seul, le pair attendait la suite pour acquitter, et chaque requête
    payait 40 ms de blocage mutuel. Passer par `http.client` permet de
    poser TCP_NODELAY sur la socket avant d'écrire quoi que ce soit.
    """
    parts = urlsplit(url)
    secure = parts.scheme == "https"
    port = parts.port or (443 if secure else 80)
    cls = http.client.HTTPSConnection if secure else http.client.HTTPConnection

    connection = cls(parts.hostname, port, timeout=30)
    try:
        connection.connect()
        connection.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        connection.request(method, path, body=body or None, headers=headers)

        response = connection.getresponse()
        payload = response.read()
        out = [(k, v) for k, v in response.getheaders()
               if k.lower() not in HOP_BY_HOP]
        return response.status, payload, out
    finally:
        connection.close()


def make_proxy_server(proxy: AssuranceProxy, host: str = "127.0.0.1",
                      port: int = DEFAULT_PORT,
                      quiet: bool = False) -> ThreadingHTTPServer:
    handler = type("_BoundProxyHandler", (_ProxyHandler,),
                   {"proxy": proxy, "quiet": quiet})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def redact(headers) -> dict:
    """Présence des en-têtes sensibles, jamais leur valeur."""
    return {k: ("<redacted>" if k.lower() in SENSITIVE else v)
            for k, v in headers.items()}
