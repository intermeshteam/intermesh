#!/usr/bin/env python3
"""Démonstration reproductible : une action bloquée, une action autorisée.

    python3 examples/assurance/demo.py

L'agent est un script `requests` ordinaire. **Il ne contient aucune ligne
d'InterMesh** — seulement la variable d'environnement `HTTP_PROXY`. C'est
tout l'objet de la démonstration : l'assurance s'ajoute sans toucher au
code de l'agent, donc sans dépendre du langage dans lequel il est écrit.
"""

import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sdk-python"))

from intermesh.assurance import AssuranceProxy, EvidenceStore, Policy  # noqa: E402
from intermesh.assurance.proxy import make_proxy_server  # noqa: E402
from intermesh.signing import derive_signing_key  # noqa: E402

ICI = Path(__file__).resolve().parent
PREUVES = ICI / "evidence.jsonl"


class _API(BaseHTTPRequestHandler):
    """Une API quelconque, qui ne sait rien d'InterMesh."""

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.dumps({"ok": True, "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def titre(texte):
    print(f"\n\033[1m{texte}\033[0m\n" + "─" * 62)


def main():
    PREUVES.unlink(missing_ok=True)

    api = ThreadingHTTPServer(("127.0.0.1", 0), _API)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    api_port = api.server_address[1]

    policy = Policy.load(ICI / "policy.yaml")
    proxy = AssuranceProxy(
        policy, derive_signing_key("cle-de-demonstration-intermesh"),
        EvidenceStore(PREUVES), agent_id="devops-bot", organization_id="acme")
    guard = make_proxy_server(proxy, port=0, quiet=True)
    threading.Thread(target=guard.serve_forever, daemon=True).start()
    proxy_url = f"http://127.0.0.1:{guard.server_address[1]}"

    proxies = {"http": proxy_url}
    base = f"http://127.0.0.1:{api_port}"
    print(f"Politique : {policy.version_label()}   Proxy : {proxy_url}")

    # ------------------------------------------------------------------
    titre("1. ACTION DANGEREUSE — l'agent tente de supprimer une ressource")
    reponse = requests.post(f"{base}/api/v1/delete/database",
                            json={"target": "prod"}, proxies=proxies, timeout=10)
    corps = reponse.json()
    print(f"  HTTP {reponse.status_code}   risque {corps['risk']}   "
          f"règle « {corps['rule']} »")
    print(f"  → {corps['error'].upper()} : {corps['reason']}")
    print(f"  preuve : {corps['evidence_id']}")
    assert reponse.status_code == 403, "l'action dangereuse devait être bloquée"

    # ------------------------------------------------------------------
    titre("2. ACTION À VALIDER — virement, approbation humaine requise")
    reponse = requests.post(f"{base}/api/v1/transfer",
                            json={"amount": 5000}, proxies=proxies, timeout=10)
    corps = reponse.json()
    print(f"  HTTP {reponse.status_code}   risque {corps['risk']}   "
          f"règle « {corps['rule']} »")
    print(f"  → {corps['error'].upper()} : {corps['reason']}")
    assert corps["error"] == "approval_required"

    # ------------------------------------------------------------------
    titre("3. ACTION AUTORISÉE — écriture courante, réellement exécutée")
    reponse = requests.post(f"{base}/api/v1/items", json={"name": "widget"},
                            proxies=proxies, timeout=10)
    print(f"  HTTP {reponse.status_code}   risque "
          f"{reponse.headers.get('X-InterMesh-Risk')}   "
          f"décision {reponse.headers.get('X-InterMesh-Decision')}")
    print(f"  réponse réelle de l'API : {reponse.json()}")
    assert reponse.status_code == 200, "l'action anodine devait passer"
    assert reponse.headers.get("X-InterMesh-Evidence"), "une preuve était attendue"

    # ------------------------------------------------------------------
    titre("4. VÉRIFICATION — par quelqu'un qui ne nous fait pas confiance")
    guard.shutdown()
    api.shutdown()
    lignes = PREUVES.read_text(encoding="utf-8").strip().splitlines()
    print(f"  {len(lignes)} preuves écrites dans {PREUVES.name}\n")

    resultat = subprocess.run(
        [sys.executable, "-m", "intermesh.cli", "verify", str(PREUVES)],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[2] / "sdk-python"))
    print("\n".join(resultat.stdout.splitlines()[7:]))

    # ------------------------------------------------------------------
    titre("5. FALSIFICATION — un champ modifié après coup")
    falsifie = ICI / "evidence-falsifiee.json"
    preuve = json.loads(lignes[0])
    avant = preuve["authorization"]["decision"]
    preuve["authorization"]["decision"] = "allow"   # « ce n'était pas bloqué »
    falsifie.write_text(json.dumps(preuve), encoding="utf-8")
    print(f"  decision : « {avant} » → « allow »")

    resultat = subprocess.run(
        [sys.executable, "-m", "intermesh.cli", "verify", str(falsifie)],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[2] / "sdk-python"))
    print("\n".join(resultat.stdout.splitlines()[7:]))
    falsifie.unlink(missing_ok=True)

    if resultat.returncode == 0:
        print("\033[31m✗ ÉCHEC : la falsification n'a pas été détectée\033[0m")
        return 1

    print("\033[32m✓ Les trois décisions sont prises, prouvées, "
          "et la falsification est détectée.\033[0m\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
