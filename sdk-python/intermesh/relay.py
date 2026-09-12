"""Le relais de registre : l'annuaire des clés et le livre de comptes.

Un serveur qui encaisse a besoin de deux choses qu'il ne peut pas inventer
seul : la clé publique de celui qui prétend payer, et un endroit où la
dette s'accumule pour être facturée. Le relais tient les deux.

Il s'appuie sur `http.server` de la bibliothèque standard, volontairement :
le registre est le composant dont on veut pouvoir dire qu'il n'embarque
aucune dépendance. Il tient en un fichier JSON et ne demande ni base de
données ni processus tiers.

**Il n'est pas authentifié, et il écoute sur `localhost` par défaut.**
Ce n'est pas un oubli : poser une authentification bancale serait pire que
d'annoncer clairement qu'il n'y en a pas. Exposer ce port suppose de
mettre une authentification devant — un proxy, un réseau privé.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .payments.keyring import Keyring
from .payments.ledger import DEFAULT_CREDIT_LIMIT, Ledger, LedgerError
from .payments.price import PriceError
from .signing import key_fingerprint

DEFAULT_PORT = 8402  # 402, comme le code HTTP


class Registry:
    """Registre et trousseau, persistés ensemble dans un seul fichier."""

    def __init__(self, ledger: Optional[Ledger] = None,
                 keyring: Optional[Keyring] = None,
                 path: Optional[Path] = None):
        self.ledger = ledger or Ledger()
        self.keyring = keyring or Keyring()
        self.path = Path(path) if path else None
        # Réentrant : `_save` est appelé aussi bien depuis l'extérieur que
        # depuis une opération qui détient déjà le verrou.
        self._lock = threading.RLock()
        # Un serveur tiers débite ce registre sans passer par le relais.
        # Sans ce branchement, son écriture n'atteignait jamais le disque.
        self.ledger.on_change = lambda _ledger: self._save()

    # ------------------------------------------------------------------

    def register(self, agent_id: str, public_pem: str,
                 credit_limit: str = DEFAULT_CREDIT_LIMIT) -> dict:
        with self._lock:
            fingerprint = self.keyring.add(agent_id, public_pem)
            account = self.ledger.open_account(agent_id, credit_limit)
            self._save()
        return {"agent_id": agent_id, "fingerprint": fingerprint,
                "credit_limit": str(account.credit_limit),
                "currency": account.currency}

    def account(self, agent_id: str) -> dict:
        account = self.ledger.account(agent_id)
        return {**account.to_dict(), "available": str(account.available)}

    def statement(self, agent_id: str, since: Optional[float] = None,
                  until: Optional[float] = None) -> dict:
        charges = self.ledger.statement(agent_id, since, until)
        return {
            "agent_id": agent_id,
            "charges": [c.to_dict() for c in charges],
            "count": len(charges),
            "total_owed": str(self.ledger.total_owed(agent_id, since, until).amount),
            "currency": self.ledger.currency,
        }

    def settle(self, agent_id: str, amount: str) -> dict:
        with self._lock:
            account = self.ledger.settle(agent_id, amount)
            self._save()
        return account.to_dict()

    def public_key(self, agent_id: str) -> dict:
        pem = self.keyring.public_pem(agent_id)
        if not pem:
            raise KeyError(agent_id)
        return {"agent_id": agent_id, "public_key": pem,
                "fingerprint": key_fingerprint(pem)}

    def integrity(self) -> dict:
        intact = self.ledger.verify_integrity()
        return {"intact": intact, "entries": len(self.ledger.audit.chain)}

    # ------------------------------------------------------------------

    def _save(self) -> None:
        if not self.path:
            return
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"ledger": self.ledger.export_state(),
                       "keyring": self.keyring.to_dict()}
            # Écriture puis remplacement : un relais tué en plein écrit ne
            # doit pas laisser un registre tronqué derrière lui.
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp.replace(self.path)
            self.path.chmod(0o600)

    @classmethod
    def load(cls, path: str | Path) -> "Registry":
        file = Path(path)
        if not file.is_file():
            return cls(path=file)
        data = json.loads(file.read_text(encoding="utf-8"))
        return cls(ledger=Ledger.import_state(data.get("ledger", {})),
                   keyring=Keyring(data.get("keyring", {})),
                   path=file)


class _Handler(BaseHTTPRequestHandler):
    server_version = "InterMeshLedger"
    registry: Registry  # posé par `serve`
    quiet: bool = False

    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - imposé par http.server
        path, query = self._split()
        try:
            if path == "/health":
                return self._json(200, {"status": "ok"})
            if path == "/verify":
                return self._json(200, self.registry.integrity())
            if path.startswith("/keys/"):
                return self._json(200, self.registry.public_key(path[6:]))
            if path.startswith("/accounts/") and path.endswith("/statement"):
                agent = path[len("/accounts/"):-len("/statement")]
                return self._json(200, self.registry.statement(
                    agent, _float(query, "since"), _float(query, "until")))
            if path.startswith("/accounts/"):
                return self._json(200, self.registry.account(path[len("/accounts/"):]))
        except KeyError as exc:
            return self._json(404, {"error": "unknown_agent", "agent_id": str(exc)})
        except LedgerError as exc:
            return self._json(404, {"error": "unknown_account", "reason": str(exc)})
        self._json(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path, _ = self._split()
        try:
            body = self._body()
        except ValueError as exc:
            return self._json(400, {"error": "bad_json", "reason": str(exc)})

        try:
            if path == "/register":
                return self._json(201, self.registry.register(
                    body["agent_id"], body["public_key"],
                    body.get("credit_limit", DEFAULT_CREDIT_LIMIT)))
            if path == "/settle":
                return self._json(200, self.registry.settle(
                    body["agent_id"], str(body["amount"])))
        except KeyError as exc:
            return self._json(400, {"error": "missing_field", "field": str(exc)})
        except (LedgerError, PriceError, ValueError) as exc:
            return self._json(400, {"error": "rejected", "reason": str(exc)})
        self._json(404, {"error": "not_found", "path": path})

    # ------------------------------------------------------------------

    def _split(self) -> Tuple[str, dict]:
        parsed = urlparse(self.path)
        return parsed.path.rstrip("/") or "/", parse_qs(parsed.query)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            data = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError(str(exc)) from exc
        if not isinstance(data, dict):
            raise ValueError("un objet JSON est attendu")
        return data

    def _json(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args) -> None:
        if not self.quiet:
            super().log_message(fmt, *args)


def _float(query: dict, key: str) -> Optional[float]:
    values = query.get(key)
    try:
        return float(values[0]) if values else None
    except (TypeError, ValueError):
        return None


def make_server(registry: Registry, host: str = "127.0.0.1",
                port: int = DEFAULT_PORT, quiet: bool = False) -> ThreadingHTTPServer:
    handler = type("_BoundHandler", (_Handler,),
                   {"registry": registry, "quiet": quiet})
    return ThreadingHTTPServer((host, port), handler)


def serve(state: Optional[str] = None, host: str = "127.0.0.1",
          port: int = DEFAULT_PORT) -> int:
    """Démarre le relais jusqu'à Ctrl+C."""
    registry = Registry.load(state) if state else Registry()
    httpd = make_server(registry, host, port)

    where = state or "mémoire seule (rien ne survivra à l'arrêt)"
    print(f"\033[32m✓ Registre InterMesh sur http://{host}:{port}\033[0m")
    print(f"  état     : {where}")
    print(f"  comptes  : {len(registry.keyring)}")
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("\033[33m  ⚠ ce relais n'a aucune authentification : ne l'exposez "
              "que derrière un proxy ou un réseau privé.\033[0m")
    print("  Ctrl+C pour arrêter.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du registre.")
    finally:
        httpd.server_close()
    return 0
