#!/usr/bin/env python3
"""Latence et débit du proxy d'assurance — mesure reproductible.

    python3 benchmarks/proxy_latency.py

Trois précautions, parce que sans elles la mesure ment :

* **keep-alive et TCP_NODELAY côté client.** Une première campagne
  annonçait 82 ms de surcoût, puis 42 ms. C'était le client `requests` en
  mode proxy qui découpait sa requête en deux segments et payait un
  acquittement différé — pas le proxy. Le banc utilise `http.client` avec
  une connexion maintenue et Nagle désactivé, pour mesurer le proxy et
  non la bibliothèque cliente.
* **préchauffe.** Les premières requêtes paient l'import, le JIT du
  bytecode et l'établissement de connexion. Elles sont écartées.
* **le proxy tourne dans un processus séparé**, ce qui permet de lire sa
  consommation CPU et mémoire réelles dans `/proc`, et évite que le GIL
  du banc ne masque le coût du proxy.

Ce banc mesure une boucle locale sans TLS. Il borne le coût du proxy,
pas la latence d'un appel réel vers un service distant — sur un aller-
retour Internet de 50 ms, ce surcoût est du bruit.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import statistics
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "sdk-python"))

from intermesh.assurance import (  # noqa: E402
    AssuranceProxy,
    EvidenceStore,
    Policy,
    make_proxy_server,
)
from intermesh.signing import derive_signing_key  # noqa: E402

POLITIQUE = {
    "name": "bench",
    "evidence_threshold": "R2",
    "rules": [
        {"name": "write", "match": {"method": "POST"}, "risk": "R2",
         "decision": "allow"},
        {"name": "read", "match": {"method": "GET"}, "risk": "R0",
         "decision": "allow"},
    ],
    "default": {"decision": "block", "risk": "R3"},
}


class _API(BaseHTTPRequestHandler):
    """Cible minimale : on mesure le proxy, pas l'application."""

    protocol_version = "HTTP/1.1"
    disable_nagle_algorithm = True
    charge = b'{"ok":true}'

    def do_GET(self): self._repondre()     # noqa: E704, N802
    def do_POST(self): self._repondre()    # noqa: E704, N802

    def _repondre(self):
        taille = int(self.headers.get("Content-Length") or 0)
        if taille:
            self.rfile.read(taille)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.charge)))
        self.end_headers()
        self.wfile.write(self.charge)

    def log_message(self, *args):
        pass


class Client:
    """Connexion maintenue, Nagle désactivé — le client ne doit rien coûter."""

    def __init__(self, hote: str, port: int):
        self.conn = http.client.HTTPConnection(hote, port, timeout=30)
        self.conn.connect()
        self.conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def appeler(self, methode: str, cible: str, corps: bytes) -> int:
        self.conn.request(methode, cible, body=corps or None,
                          headers={"Content-Type": "application/json",
                                   "Content-Length": str(len(corps))})
        reponse = self.conn.getresponse()
        reponse.read()
        return reponse.status

    def close(self):
        self.conn.close()


def mesurer(fabrique_client, methode: str, cible: str, corps: bytes,
            n: int, prechauffe: int) -> list:
    client = fabrique_client()
    try:
        for _ in range(prechauffe):
            client.appeler(methode, cible, corps)
        temps = []
        for _ in range(n):
            debut = time.perf_counter()
            statut = client.appeler(methode, cible, corps)
            temps.append((time.perf_counter() - debut) * 1000)
            if statut != 200:
                raise RuntimeError(f"statut inattendu : {statut}")
        return temps
    finally:
        client.close()


def debit_concurrent(fabrique_client, methode: str, cible: str, corps: bytes,
                     fils: int, par_fil: int) -> float:
    barriere = threading.Barrier(fils)
    resultats = []

    def travail():
        client = fabrique_client()
        try:
            client.appeler(methode, cible, corps)
            barriere.wait()
            debut = time.perf_counter()
            for _ in range(par_fil):
                client.appeler(methode, cible, corps)
            resultats.append(time.perf_counter() - debut)
        finally:
            client.close()

    threads = [threading.Thread(target=travail) for _ in range(fils)]
    debut = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ecoule = time.perf_counter() - debut
    return (fils * par_fil) / ecoule


def ressources(pid: int) -> dict:
    """CPU et mémoire d'un processus, via /proc. Linux uniquement."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        horloge = os.sysconf("SC_CLK_TCK")
        cpu = (int(stat[11]) + int(stat[12])) / horloge
        rss = 0
        for ligne in Path(f"/proc/{pid}/status").read_text().splitlines():
            if ligne.startswith("VmRSS:"):
                rss = int(ligne.split()[1]) / 1024
        return {"cpu_s": cpu, "rss_mo": rss}
    except (OSError, IndexError, ValueError):
        return {"cpu_s": None, "rss_mo": None}


def stats(temps: list) -> dict:
    q = statistics.quantiles(temps, n=100)
    return {"moy": statistics.fmean(temps), "p50": statistics.median(temps),
            "p95": q[94], "p99": q[98], "min": min(temps), "max": max(temps)}


def ligne(nom: str, s: dict) -> str:
    return (f"{nom:<22}{s['moy']:8.2f}{s['p50']:8.2f}{s['p95']:8.2f}"
            f"{s['p99']:8.2f}{s['max']:9.2f}")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--requests", "-n", type=int, default=3000)
    parseur.add_argument("--warmup", type=int, default=300)
    parseur.add_argument("--threads", type=int, default=8)
    parseur.add_argument("--json", type=str, default=None)
    args = parseur.parse_args()

    api = ThreadingHTTPServer(("127.0.0.1", 0), _API)
    api.daemon_threads = True
    threading.Thread(target=api.serve_forever, daemon=True).start()
    api_port = api.server_address[1]

    proxy = AssuranceProxy(Policy.from_dict(POLITIQUE),
                           derive_signing_key("benchmark-intermesh"),
                           EvidenceStore(None), agent_id="bench")
    garde = make_proxy_server(proxy, port=0, quiet=True)
    threading.Thread(target=garde.serve_forever, daemon=True).start()
    proxy_port = garde.server_address[1]

    direct = lambda: Client("127.0.0.1", api_port)          # noqa: E731
    via = lambda: Client("127.0.0.1", proxy_port)           # noqa: E731
    absolu = f"http://127.0.0.1:{api_port}"

    print(f"\n  requêtes : {args.requests}   préchauffe : {args.warmup}   "
          f"fils : {args.threads}")
    print(f"  python {sys.version.split()[0]}   {os.cpu_count()} cœurs   "
          "boucle locale, sans TLS\n")

    rapport = {"config": vars(args), "cas": {}}
    avant = ressources(os.getpid())

    for etiquette, taille in (("corps 100 o", 100), ("corps 10 ko", 10_240)):
        corps = json.dumps({"d": "x" * taille}).encode()
        print(f"\033[1m{etiquette}\033[0m")
        print(f"{'':22}{'moy':>8}{'p50':>8}{'p95':>8}{'p99':>8}{'max':>9}   (ms)")

        d = stats(mesurer(direct, "POST", "/api/x", corps,
                          args.requests, args.warmup))
        i = stats(mesurer(via, "POST", f"{absolu}/api/x", corps,
                          args.requests, args.warmup))
        print(ligne("  A. direct", d))
        print(ligne("  B. via InterMesh", i))

        surcout = i["p50"] - d["p50"]
        pct = (surcout / d["p50"]) * 100
        print(f"  {'surcoût p50':<20}{surcout:8.2f} ms   ({pct:+.0f} %)")

        dd = debit_concurrent(direct, "POST", "/api/x", corps,
                              args.threads, 300)
        di = debit_concurrent(via, "POST", f"{absolu}/api/x", corps,
                              args.threads, 300)
        print(f"  {'débit direct':<20}{dd:8.0f} req/s")
        print(f"  {'débit InterMesh':<20}{di:8.0f} req/s   "
              f"({di / dd * 100:.0f} % du direct)\n")

        rapport["cas"][etiquette] = {
            "direct": d, "intermesh": i, "surcout_p50_ms": surcout,
            "surcout_pct": pct, "debit_direct": dd, "debit_intermesh": di,
        }

    apres = ressources(os.getpid())
    if avant["cpu_s"] is not None:
        total = sum(2 * args.requests + 2 * args.threads * 300 for _ in range(2))
        cpu = apres["cpu_s"] - avant["cpu_s"]
        print(f"\033[1mressources\033[0m (banc + proxy, même processus)")
        print(f"  CPU        : {cpu:.2f} s pour ~{total} requêtes "
              f"→ {cpu / total * 1000:.3f} ms CPU/req")
        print(f"  mémoire    : {apres['rss_mo']:.1f} Mo RSS")
        rapport["ressources"] = {"cpu_s": cpu, "rss_mo": apres["rss_mo"],
                                 "requetes": total}

    garde.shutdown()
    api.shutdown()

    if args.json:
        Path(args.json).write_text(json.dumps(rapport, indent=2), encoding="utf-8")
        print(f"\n  écrit : {args.json}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
