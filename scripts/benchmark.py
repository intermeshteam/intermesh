#!/usr/bin/env python3
"""
Banc de mesure du Hub : combien d'agents, combien de messages par seconde.

Personne ne peut répondre à un appel d'offres sans ces chiffres, et il n'en
existait aucun. Ce script en produit, et dit précisément dans quelles
conditions — un débit sans son contexte ne veut rien dire.

Ce qui est mesuré
-----------------
  * **Connexion**    : à quelle cadence des agents s'enregistrent, et
                       combien tiennent simultanément.
  * **Requêtes**     : allers-retours REQUEST/RESPONSE entre deux agents,
                       débit et latences p50/p95/p99.
  * **Tâches**       : soumissions TASK_SUBMIT jusqu'à complétion, qui
                       passent par la persistance et le journal d'audit —
                       plus lourdes qu'une requête, et plus représentatives
                       d'un usage réel.

Ce que les chiffres ne disent pas
---------------------------------
Tout tourne sur une seule machine, en boucle locale, sans TLS. C'est donc
une **borne haute** : un déploiement réel ajoute la latence réseau, le
chiffrement du transport, et le fait que les agents ne sont pas tous sur le
même processeur. Le chiffrement de bout en bout est mesuré séparément
(`--encrypt`) parce qu'il déplace le coût côté agent, pas côté Hub.

Usage
-----
    python3 scripts/benchmark.py                    # profil par défaut
    python3 scripts/benchmark.py --agents 200 --requests 2000
    python3 scripts/benchmark.py --encrypt          # avec chiffrement E2E
    python3 scripts/benchmark.py --state-dsn postgresql://...
"""

from __future__ import annotations

import argparse
import asyncio
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sdk-python"))

from intermesh import InterMeshAgent  # noqa: E402


def percentile(values: list[float], pct: float) -> float:
    """Percentile par interpolation linéaire.

    `statistics.quantiles` découpe en n groupes et ne donne pas directement
    un p99 sur un petit échantillon ; ici la définition est explicite.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


class Bench:
    def __init__(self, args):
        self.args = args
        self.url = f"ws://localhost:{args.port}"
        self.hub = None
        self.results: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Cycle de vie du Hub
    # ------------------------------------------------------------------

    def start_hub(self) -> None:
        cmd = [
            sys.executable, "-u", str(ROOT / "server" / "hub.py"),
            "--port", str(self.args.port), "--org", "bench",
            "--ephemeral-secret",
        ]
        # L'état éphémère mesure le Hub seul ; un DSN mesure le Hub *avec*
        # sa persistance, ce qui est la configuration réelle d'un
        # déploiement. Les deux chiffres sont utiles, ils ne se comparent
        # pas.
        if self.args.state_dsn:
            cmd += ["--state-dsn", self.args.state_dsn]
        else:
            cmd.append("--ephemeral-state")

        self.hub = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        if self.hub.poll() is not None:
            raise RuntimeError("le Hub s'est arrêté au démarrage — port déjà pris ?")

    def stop_hub(self) -> None:
        if not self.hub:
            return
        self.hub.terminate()
        try:
            self.hub.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.hub.kill()

    # ------------------------------------------------------------------
    # Mesures
    # ------------------------------------------------------------------

    async def measure_connections(self) -> list[InterMeshAgent]:
        """Cadence d'enregistrement et nombre d'agents tenus simultanément."""
        n = self.args.agents
        agents: list[InterMeshAgent] = []
        failures = 0

        started = time.perf_counter()
        for i in range(n):
            a = InterMeshAgent(
                name=f"w{i}", hub_url=self.url, roles=["worker"],
                capabilities=["bench"], encrypt=self.args.encrypt,
            )
            a.on_task(lambda d, t: {"ok": True})
            a.on_request(lambda m: {"pong": True})
            try:
                await a.connect()
                agents.append(a)
            except Exception:
                failures += 1
        elapsed = time.perf_counter() - started

        self.results["connexions"] = {
            "demandées": n,
            "établies": len(agents),
            "échecs": failures,
            "durée_s": round(elapsed, 2),
            "cadence_par_s": round(len(agents) / elapsed, 1) if elapsed else 0,
        }
        return agents

    async def measure_requests(self, target: str) -> None:
        """Allers-retours REQUEST/RESPONSE, à concurrence fixée."""
        lead = InterMeshAgent(name="bench_lead", hub_url=self.url,
                              roles=["admin"], encrypt=self.args.encrypt)
        await lead.connect()

        total = self.args.requests
        latencies: list[float] = []
        errors = 0
        semaphore = asyncio.Semaphore(self.args.concurrency)

        async def one():
            nonlocal errors
            async with semaphore:
                t0 = time.perf_counter()
                try:
                    await lead.ask(to=target, content={"ping": 1}, timeout=30)
                    latencies.append((time.perf_counter() - t0) * 1000)
                except Exception:
                    errors += 1

        started = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(total)))
        elapsed = time.perf_counter() - started

        self.results["requêtes"] = {
            "envoyées": total,
            "abouties": len(latencies),
            "erreurs": errors,
            "durée_s": round(elapsed, 2),
            "débit_par_s": round(len(latencies) / elapsed, 1) if elapsed else 0,
            "latence_ms": {
                "p50": round(percentile(latencies, 0.50), 2),
                "p95": round(percentile(latencies, 0.95), 2),
                "p99": round(percentile(latencies, 0.99), 2),
                "moy": round(statistics.fmean(latencies), 2) if latencies else 0,
            },
        }
        await lead.ws.close()

    async def measure_tasks(self, target: str) -> None:
        """Soumissions de tâches : passent par la persistance et l'audit.

        Les soumissions sont réparties sur plusieurs orchestrateurs. Les
        garde-fous limitent chaque agent à `max_tasks_per_minute` (60 par
        défaut) : tout envoyer depuis un seul agent mesurerait ce plafond
        par agent, pas la capacité du Hub. Le nombre d'orchestrateurs est
        calculé pour rester sous ce seuil.
        """
        per_agent_cap = self.args.per_agent_cap
        needed = max(1, -(-self.args.tasks // per_agent_cap))  # division plafond
        leads: list[InterMeshAgent] = []
        for i in range(needed):
            lead_i = InterMeshAgent(name=f"bench_lead_{i}", hub_url=self.url,
                                    roles=["admin"], encrypt=self.args.encrypt)
            await lead_i.connect()
            leads.append(lead_i)

        total = self.args.tasks
        latencies: list[float] = []
        errors = 0
        reasons: dict[str, int] = {}
        semaphore = asyncio.Semaphore(self.args.concurrency)

        async def one(i: int):
            nonlocal errors
            async with semaphore:
                t0 = time.perf_counter()
                try:
                    submitter = leads[i % len(leads)]
                    await submitter.submit_task(f"bench-{i}", target, {"i": i}, timeout=30)
                    latencies.append((time.perf_counter() - t0) * 1000)
                except Exception as exc:
                    errors += 1
                    # La cause compte plus que le compte : un refus par
                    # garde-fou et une saturation ne se corrigent pas
                    # de la même manière.
                    # Regrouper : le nom de la tâche varie à chaque échec et
                    # produirait une ligne par erreur au lieu d'un décompte.
                    raw = str(exc)
                    label = re.sub(r"'[^']*'", "'…'", raw).split(":")[0][:70] \
                        or type(exc).__name__
                    reasons[label] = reasons.get(label, 0) + 1

        started = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(total)))
        elapsed = time.perf_counter() - started

        self.results["tâches"] = {
            "soumises": total,
            "abouties": len(latencies),
            "erreurs": errors,
            "durée_s": round(elapsed, 2),
            "débit_par_s": round(len(latencies) / elapsed, 1) if elapsed else 0,
            "latence_ms": {
                "p50": round(percentile(latencies, 0.50), 2),
                "p95": round(percentile(latencies, 0.95), 2),
                "p99": round(percentile(latencies, 0.99), 2),
            },
            "causes": reasons,
            "orchestrateurs": len(leads),
        }
        for lead_i in leads:
            await lead_i.ws.close()

    # ------------------------------------------------------------------

    async def run(self) -> None:
        agents = await self.measure_connections()
        if not agents:
            raise RuntimeError("aucun agent n'a pu se connecter")

        target = agents[0].qualified_name
        await self.measure_requests(target)
        await self.measure_tasks(target)

        for a in agents:
            try:
                await a.ws.close()
            except Exception:
                pass


def describe_machine() -> dict:
    return {
        "python": platform.python_version(),
        "système": f"{platform.system()} {platform.release()}",
        "processeurs": os.cpu_count(),
    }


def report(bench: Bench) -> None:
    args = bench.args
    print()
    print("=" * 66)
    print("  BANC DE MESURE — HUB INTERMESH")
    print("=" * 66)

    m = describe_machine()
    print(f"  machine     : {m['système']}, {m['processeurs']} cœurs, Python {m['python']}")
    print(f"  transport   : ws:// en boucle locale, sans TLS")
    print(f"  chiffrement : {'E2E activé' if args.encrypt else 'désactivé'}")
    print(f"  état        : {'PostgreSQL' if args.state_dsn else 'éphémère (mémoire)'}")
    print(f"  concurrence : {args.concurrency}")
    print("-" * 66)

    c = bench.results["connexions"]
    print(f"  Connexions   {c['établies']}/{c['demandées']} en {c['durée_s']}s "
          f"→ {c['cadence_par_s']}/s" + (f"  ({c['échecs']} échec(s))" if c["échecs"] else ""))

    for key in ("requêtes", "tâches"):
        r = bench.results[key]
        done = r.get("abouties")
        lat = r["latence_ms"]
        print(f"  {key.capitalize():<12} {done} en {r['durée_s']}s "
              f"→ {r['débit_par_s']}/s"
              + (f"  ({r['erreurs']} erreur(s))" if r["erreurs"] else ""))
        print(f"               latence p50 {lat['p50']} ms · p95 {lat['p95']} ms · p99 {lat['p99']} ms")
        if r.get("orchestrateurs", 1) > 1:
            print(f"               réparties sur {r['orchestrateurs']} orchestrateurs "
                  f"(plafond garde-fou : 60 tâches/min/agent)")
        for cause, n in (r.get("causes") or {}).items():
            print(f"               ↳ {n}× {cause}")

    print("-" * 66)
    print("  Borne haute : une seule machine, boucle locale, sans TLS.")
    print("  Un déploiement réel ajoute réseau, TLS et agents distants.")
    print("=" * 66)
    print()


def main() -> int:
    p = argparse.ArgumentParser(description="Banc de mesure du Hub InterMesh")
    p.add_argument("--agents", type=int, default=100, help="Agents connectés simultanément")
    p.add_argument("--requests", type=int, default=1000, help="Allers-retours REQUEST/RESPONSE")
    p.add_argument("--tasks", type=int, default=300, help="Tâches soumises")
    p.add_argument("--concurrency", type=int, default=50, help="Envois en vol simultanés")
    p.add_argument("--per-agent-cap", type=int, default=55,
                   help="Tâches par orchestrateur avant d'en ajouter un autre. "
                        "Doit rester sous max_tasks_per_minute des garde-fous (60).")
    p.add_argument("--port", type=int, default=8899)
    p.add_argument("--encrypt", action="store_true", help="Active le chiffrement E2E")
    p.add_argument("--state-dsn", type=str, default=None,
                   help="Mesure avec persistance PostgreSQL au lieu de l'état mémoire")
    args = p.parse_args()

    bench = Bench(args)
    try:
        bench.start_hub()
        asyncio.run(bench.run())
        report(bench)
    finally:
        bench.stop_hub()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
