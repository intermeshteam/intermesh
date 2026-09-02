#!/usr/bin/env python3
"""
Banc de mesure d'une grappe : plusieurs Hubs, et du trafic qui les traverse.

`scripts/benchmark.py` mesure un Hub seul. Il ne dit donc rien du cas qui
intéresse une grande entreprise : plusieurs Hubs, des milliers d'agents
répartis dessus, et des échanges qui franchissent la frontière d'un Hub à
l'autre. Ce script produit ces chiffres-là.

Ce qui est mesuré
-----------------
  * **Connexion**   : cadence d'enregistrement et nombre d'agents tenus,
                      répartis en tourniquet sur la grappe.
  * **Requêtes**    : allers-retours REQUEST/RESPONSE **inter-Hubs** —
                      l'émetteur et la cible sont toujours sur des Hubs
                      différents, sans quoi on remesurerait le cas local.
  * **Tâches**      : TASK_SUBMIT jusqu'à complétion, à travers la grappe.
                      Plus lourdes : elles passent par la persistance
                      partagée et le journal d'audit.
  * **Défaillance** : un Hub est coupé en plein trafic, et l'on mesure ce
                      que font les autres pendant et après.

Ce que les chiffres ne disent pas
---------------------------------
Tout tourne sur une seule machine, en boucle locale, sans TLS. Les cinq
Hubs se partagent les mêmes cœurs et la même mémoire, et se disputent la
même base PostgreSQL. C'est donc une borne **basse** pour le débit agrégé
d'un vrai déploiement où chaque Hub aurait sa machine — et une borne
**haute** pour la latence, puisqu'il n'y a pas de réseau. Les deux effets
ne se compensent pas : ils ne sont simplement pas comparables à une
mesure répartie.

Usage
-----
    python3 scripts/cluster_benchmark.py --dsn postgresql://... --agents 1000
    python3 scripts/cluster_benchmark.py --dsn ... --agents 200 --encrypt
    python3 scripts/cluster_benchmark.py --dsn ... --skip-failure
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import resource
import secrets
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sdk-python"))

from intermesh import InterMeshAgent  # noqa: E402


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def rss_mb() -> float:
    """Mémoire résidente de ce processus. En kio sous Linux, en octets sur macOS."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1024 if sys.platform.startswith("linux") else peak / (1024 * 1024)


class Cluster:
    """Cinq Hubs qui se voient par la table de présence partagée.

    Ils partagent la même base — c'est elle qui porte la présence, donc ce
    qui permet à un Hub de savoir sur lequel de ses frères se trouve un
    agent — et la même clé de signature, sans quoi un jeton émis par l'un
    serait rejeté par l'autre.
    """

    def __init__(self, count: int, base_port: int, dsn: str, org: str):
        self.count = count
        self.base_port = base_port
        self.dsn = dsn
        self.org = org
        self.procs: dict[int, subprocess.Popen] = {}
        self.secret_file = Path(tempfile.mkdtemp()) / "cluster.secret"
        self.secret_file.write_text(secrets.token_hex(32))
        os.chmod(self.secret_file, 0o600)

    def port(self, index: int) -> int:
        return self.base_port + index

    def url(self, index: int) -> str:
        return f"ws://localhost:{self.port(index)}"

    def start_one(self, index: int) -> None:
        port = self.port(index)
        os.system(f"fuser -k {port}/tcp >/dev/null 2>&1")
        proc = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "server" / "hub.py"),
             "--port", str(port), "--org", self.org,
             "--hub-id", f"hub-{index}",
             "--state-dsn", self.dsn,
             "--secret-file", str(self.secret_file),
             "--cluster-url", self.url(index)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.procs[index] = proc

    def start(self) -> None:
        for i in range(self.count):
            self.start_one(i)
        time.sleep(5)
        dead = [i for i, p in self.procs.items() if p.poll() is not None]
        if dead:
            raise RuntimeError(f"Hubs arrêtés au démarrage : {dead} — ports pris, ou base injoignable ?")

    def kill_one(self, index: int) -> None:
        proc = self.procs.pop(index, None)
        if not proc:
            return
        proc.kill()
        proc.wait(timeout=10)

    def stop(self) -> None:
        for proc in self.procs.values():
            proc.terminate()
        for proc in self.procs.values():
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.procs.clear()


class ClusterBench:
    def __init__(self, args):
        self.args = args
        self.cluster = Cluster(args.hubs, args.base_port, args.dsn, args.org)
        self.agents: list[InterMeshAgent] = []
        self.agent_hub: list[int] = []          # index du Hub portant chaque agent
        self.results: dict[str, dict] = {}

    # ------------------------------------------------------------------

    async def connect_agents(self) -> None:
        """Répartition en tourniquet sur la grappe."""
        n = self.args.agents
        established, failures = 0, 0
        started = time.perf_counter()

        def make(i: int) -> InterMeshAgent:
            agent = InterMeshAgent(
                name=f"w{i}",
                # Sans org_id explicite, le nom reste « w12 » au lieu de
                # « bench/w12 », et le contrôle d'isolement multi-tenant
                # refuse la cible comme appartenant à une autre organisation.
                org_id=self.args.org,
                hub_url=self.cluster.url(i % self.cluster.count),
                roles=["worker"],
                capabilities=["bench"],
                encrypt=self.args.encrypt,
            )
            agent.on_task(lambda d, t: {"ok": True})
            agent.on_request(lambda m: {"pong": True})
            return agent

        async def bring_up(i: int):
            nonlocal established, failures
            agent = make(i)
            try:
                await agent.connect()
                self.agents.append(agent)
                self.agent_hub.append(i % self.cluster.count)
                established += 1
            except Exception:
                failures += 1

        # Par lots concurrents, et non un par un : une boucle séquentielle
        # mesure le temps d'aller-retour de ce script, pas la cadence que
        # les Hubs soutiennent. Le lot reste borné pour ne pas saturer la
        # file d'écoute avant que les Hubs n'aient acquitté.
        batch = self.args.connect_batch
        for start in range(0, n, batch):
            await asyncio.gather(*(bring_up(i) for i in range(start, min(start + batch, n))))

        # gather ne garantit pas l'ordre d'achèvement : agent_hub a été
        # rempli dans l'ordre d'arrivée, pas d'index. On le reconstruit à
        # partir de l'URL réelle de chaque agent, seule source fiable.
        by_url = {self.cluster.url(i): i for i in range(self.cluster.count)}
        self.agent_hub = [by_url[a.hub_url] for a in self.agents]

        elapsed = time.perf_counter() - started
        self.results["connexions"] = {
            "demandés": n,
            "établis": established,
            "échecs": failures,
            "durée_s": round(elapsed, 2),
            "cadence_par_s": round(established / elapsed, 1) if elapsed else 0,
            "par_hub": established // self.cluster.count,
        }

        self._assert_names_align()

        # Le routage inter-Hubs s'appuie sur la présence publiée en base ;
        # laisser un instant pour qu'elle soit visible de tous.
        await asyncio.sleep(3)

    # ------------------------------------------------------------------

    def _assert_names_align(self) -> None:
        """Le rang dans self.agents doit correspondre au nom qualifié.

        Sans cette vérification, une régression sur l'ordre de collecte
        ferait silencieusement mesurer autre chose que ce qui est annoncé —
        c'est exactement ce qui est arrivé, et cela ne se voyait que sur la
        chronologie de reprise, restée plate à 80 %.
        """
        for index, agent in enumerate(self.agents):
            hub_of_name = self.agent_hub[index]
            if agent.hub_url != self.cluster.url(hub_of_name):
                raise RuntimeError(
                    f"agent {agent.qualified_name} au rang {index} : "
                    f"le Hub enregistré ne correspond pas à son URL")

    def _cross_hub_pairs(self, count: int) -> list[tuple[int, int]]:
        """Paires (émetteur, cible) toujours portées par des Hubs différents."""
        pairs = []
        n = len(self.agents)
        if n < 2:
            return pairs
        for i in range(count):
            sender = i % n
            # Décalage d'un Hub : garantit la traversée quel que soit n.
            target = (sender + 1) % n
            guard = 0
            while self.agent_hub[target] == self.agent_hub[sender] and guard < self.cluster.count:
                target = (target + 1) % n
                guard += 1
            if self.agent_hub[target] != self.agent_hub[sender]:
                pairs.append((sender, target))
        return pairs

    async def measure_requests(self) -> None:
        pairs = self._cross_hub_pairs(self.args.requests)
        if not pairs:
            self.results["requêtes_inter_hubs"] = {"note": "pas assez d'agents pour croiser les Hubs"}
            return

        latencies: list[float] = []
        errors = 0
        semaphore = asyncio.Semaphore(self.args.concurrency)

        async def one(sender_idx: int, target_idx: int):
            nonlocal errors
            async with semaphore:
                sender = self.agents[sender_idx]
                target = self.agents[target_idx].qualified_name
                t0 = time.perf_counter()
                try:
                    await sender.ask(to=target, content={"ping": 1}, timeout=30)
                    latencies.append((time.perf_counter() - t0) * 1000)
                except Exception:
                    errors += 1

        started = time.perf_counter()
        await asyncio.gather(*(one(s, t) for s, t in pairs))
        elapsed = time.perf_counter() - started

        self.results["requêtes_inter_hubs"] = {
            "tentées": len(pairs),
            "abouties": len(latencies),
            "erreurs": errors,
            "durée_s": round(elapsed, 2),
            "débit_par_s": round(len(latencies) / elapsed, 1) if elapsed else 0,
            "p50_ms": round(percentile(latencies, 0.50), 1),
            "p95_ms": round(percentile(latencies, 0.95), 1),
            "p99_ms": round(percentile(latencies, 0.99), 1),
        }

    # ------------------------------------------------------------------

    async def measure_tasks(self) -> None:
        """TASK_SUBMIT inter-Hubs jusqu'à complétion.

        Le garde-fou plafonne les soumissions à 60/minute *par émetteur* :
        les soumissions sont donc réparties sur de nombreux agents, sans
        quoi la mesure ne mesurerait que le garde-fou.
        """
        pairs = self._cross_hub_pairs(self.args.tasks)
        if not pairs:
            self.results["tâches_inter_hubs"] = {"note": "pas assez d'agents pour croiser les Hubs"}
            return

        latencies: list[float] = []
        errors = 0
        semaphore = asyncio.Semaphore(self.args.concurrency)

        async def one(sender_idx: int, target_idx: int):
            nonlocal errors
            async with semaphore:
                sender = self.agents[sender_idx]
                target = self.agents[target_idx].qualified_name
                t0 = time.perf_counter()
                try:
                    await sender.submit_task(
                        title="bench", assignee=target, input_data={"n": 1}, timeout=60,
                    )
                    latencies.append((time.perf_counter() - t0) * 1000)
                except Exception:
                    errors += 1

        started = time.perf_counter()
        await asyncio.gather(*(one(s, t) for s, t in pairs))
        elapsed = time.perf_counter() - started

        self.results["tâches_inter_hubs"] = {
            "tentées": len(pairs),
            "abouties": len(latencies),
            "erreurs": errors,
            "durée_s": round(elapsed, 2),
            "débit_par_s": round(len(latencies) / elapsed, 1) if elapsed else 0,
            "p50_ms": round(percentile(latencies, 0.50), 1),
            "p95_ms": round(percentile(latencies, 0.95), 1),
            "p99_ms": round(percentile(latencies, 0.99), 1),
        }

    # ------------------------------------------------------------------

    async def measure_failure(self) -> None:
        """Coupe un Hub sous charge soutenue et regarde ce que font les autres.

        Une première version envoyait un lot fixe de requêtes puis coupait
        après trois secondes. À plus de mille requêtes par seconde le lot se
        vidait en moins de deux, et le Hub mourait une fois le trafic
        terminé : la mesure ne mesurait rien. La charge est donc pilotée par
        la durée, pas par un compte — des émetteurs bouclent jusqu'à
        l'échéance, et la coupure tombe forcément en plein trafic.

        La question n'est pas « perd-on des messages » : on en perd, ceux qui
        étaient en vol vers le Hub coupé et ceux de ses agents. Elle est de
        savoir si les Hubs restants continuent de se parler, et à quel prix.
        """
        victim = self.cluster.count // 2
        survivors = [i for i in range(self.cluster.count) if i != victim]

        # Uniquement des paires dont les deux extrémités survivent : on
        # mesure la santé du reste de la grappe, pas l'échec attendu du
        # trafic destiné au mort.
        pool = [(s_i, t_i) for s_i, t_i in self._cross_hub_pairs(len(self.agents))
                if self.agent_hub[s_i] in survivors and self.agent_hub[t_i] in survivors]
        if not pool:
            self.results["défaillance"] = {"note": "pas assez d'agents survivants pour mesurer"}
            return

        phase = {"now": "avant"}
        buckets: dict[str, list[float]] = {"avant": [], "pendant": [], "après": []}
        errors: dict[str, int] = {"avant": 0, "pendant": 0, "après": 0}
        # (secondes depuis la coupure, abouti?) pour chaque requête émise
        # après elle. « Ça repart » ne suffit pas : il faut savoir en
        # combien de temps, c'est cela qu'un exploitant met dans son plan
        # de reprise.
        timeline: list[tuple[float, bool]] = []
        kill_time = {"at": None}
        stop = asyncio.Event()

        async def sender_loop(slot: int):
            i = slot
            while not stop.is_set():
                sender_idx, target_idx = pool[i % len(pool)]
                i += len(pool) // max(1, self.args.concurrency) + 1
                sender = self.agents[sender_idx]
                target = self.agents[target_idx].qualified_name
                current = phase["now"]
                t0 = time.perf_counter()
                try:
                    await sender.ask(to=target, content={"ping": 1},
                                     timeout=self.args.failure_timeout)
                    buckets[current].append((time.perf_counter() - t0) * 1000)
                    if kill_time["at"] is not None:
                        timeline.append((t0 - kill_time["at"], True))
                except Exception:
                    errors[current] += 1
                    if kill_time["at"] is not None:
                        timeline.append((t0 - kill_time["at"], False))

        async def killer():
            await asyncio.sleep(self.args.kill_after)
            phase["now"] = "pendant"
            killed = time.perf_counter()
            kill_time["at"] = killed
            # proc.wait() est bloquant : l'appeler directement gèlerait la
            # boucle d'événements, donc la mesure, pendant la coupure même.
            await asyncio.to_thread(self.cluster.kill_one, victim)
            # Fenêtre « pendant » : le temps que les sockets tombent et que
            # la présence du Hub mort cesse d'être fraîche.
            await asyncio.sleep(self.args.failure_window)
            phase["now"] = "après"
            self.results.setdefault("_kill", {})["coupure_à_s"] = round(killed - started, 2)
            await asyncio.sleep(self.args.failure_duration - self.args.kill_after
                                - self.args.failure_window)
            stop.set()

        started = time.perf_counter()
        workers = min(self.args.concurrency, len(pool))
        await asyncio.gather(killer(), *(sender_loop(k) for k in range(workers)))
        elapsed = time.perf_counter() - started

        def rate(name: str, seconds: float) -> float:
            return round(len(buckets[name]) / seconds, 1) if seconds > 0 else 0.0

        after_seconds = max(
            0.001,
            self.args.failure_duration - self.args.kill_after - self.args.failure_window,
        )
        slices: dict[str, str] = {}
        if timeline:
            span = self.args.failure_duration - self.args.kill_after
            width = 10.0
            edge = 0.0
            while edge < span:
                inside = [ok for at, ok in timeline if edge <= at < edge + width]
                if inside:
                    good = sum(1 for ok in inside if ok)
                    slices[f"t+{int(edge)}–{int(edge + width)}s"] = (
                        f"{good}/{len(inside)} abouties "
                        f"({100 * good / len(inside):.0f} %)"
                    )
                edge += width

        self.results["défaillance"] = {
            "hub_coupé": f"hub-{victim}",
            "hubs_restants": len(survivors),
            "agents_perdus_avec_lui": sum(1 for h in self.agent_hub if h == victim),
            "abouties_avant": len(buckets["avant"]),
            "abouties_pendant": len(buckets["pendant"]),
            "abouties_après": len(buckets["après"]),
            "erreurs_avant": errors["avant"],
            "erreurs_pendant": errors["pendant"],
            "erreurs_après": errors["après"],
            "débit_avant_par_s": rate("avant", self.args.kill_after),
            "débit_après_par_s": rate("après", after_seconds),
            "p50_avant_ms": round(percentile(buckets["avant"], 0.50), 1),
            "p50_après_ms": round(percentile(buckets["après"], 0.50), 1),
            "p95_avant_ms": round(percentile(buckets["avant"], 0.95), 1),
            "p95_après_ms": round(percentile(buckets["après"], 0.95), 1),
            "durée_s": round(elapsed, 2),
        }
        if slices:
            self.results["reprise_après_coupure"] = slices

    async def disconnect_all(self) -> None:
        for agent in self.agents:
            try:
                if agent.ws:
                    await agent.ws.close()
            except Exception:
                pass
        self.agents.clear()
        self.agent_hub.clear()


def describe_machine(args) -> dict:
    return {
        "python": platform.python_version(),
        "système": f"{platform.system()} {platform.release()}",
        "cœurs": os.cpu_count(),
        "hubs": args.hubs,
        "chiffrement_e2e": bool(args.encrypt),
        "transport": "ws:// en boucle locale, sans TLS",
        "état": "PostgreSQL partagé",
    }


def report(bench: ClusterBench) -> None:
    print()
    print("=" * 72)
    print("  BANC D'ESSAI EN GRAPPE — InterMesh")
    print("=" * 72)

    for key, value in describe_machine(bench.args).items():
        print(f"  {key:<18} {value}")
    print(f"  {'mémoire client':<18} {rss_mb():.0f} Mo (pic du processus de charge)")
    print()

    for section, values in bench.results.items():
        print(f"  {section.replace('_', ' ').upper()}")
        for key, value in values.items():
            print(f"    {key:<28} {value}")
        print()

    print("=" * 72)
    print("  Une seule machine, boucle locale : borne BASSE pour le débit")
    print("  agrégé (cinq Hubs partagent huit cœurs et une base), borne")
    print("  HAUTE pour la latence (aucun réseau). Non comparable à une")
    print("  mesure répartie.")
    print("=" * 72)


async def run(args) -> int:
    bench = ClusterBench(args)
    print(f"→ démarrage de {args.hubs} Hubs…", flush=True)
    bench.cluster.start()

    try:
        print(f"→ connexion de {args.agents} agents en tourniquet…", flush=True)
        await bench.connect_agents()
        print(f"   {bench.results['connexions']['établis']} connectés", flush=True)

        print("→ requêtes inter-Hubs…", flush=True)
        await bench.measure_requests()

        print("→ tâches inter-Hubs…", flush=True)
        await bench.measure_tasks()

        if not args.skip_failure:
            print("→ coupure d'un Hub en plein trafic…", flush=True)
            await bench.measure_failure()

        await bench.disconnect_all()
    finally:
        bench.cluster.stop()

    report(bench)

    if args.json:
        Path(args.json).write_text(
            json.dumps({"machine": describe_machine(args), "résultats": bench.results},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nrésultats écrits dans {args.json}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Banc de mesure d'une grappe InterMesh")
    p.add_argument("--dsn", required=True, help="PostgreSQL partagé par la grappe")
    p.add_argument("--hubs", type=int, default=5)
    p.add_argument("--base-port", type=int, default=9200)
    p.add_argument("--org", default="bench")
    p.add_argument("--agents", type=int, default=1000)
    p.add_argument("--requests", type=int, default=2000)
    p.add_argument("--tasks", type=int, default=1000)
    p.add_argument("--concurrency", type=int, default=100)
    p.add_argument("--connect-batch", type=int, default=50,
                   help="agents ouverts simultanément pendant la montée en charge")
    p.add_argument("--encrypt", action="store_true", help="chiffrement de bout en bout")
    p.add_argument("--skip-failure", action="store_true")
    p.add_argument("--kill-after", type=float, default=8.0,
                   help="secondes de trafic soutenu avant de couper un Hub")
    p.add_argument("--failure-duration", type=float, default=24.0,
                   help="durée totale de la phase de défaillance")
    p.add_argument("--failure-window", type=float, default=4.0,
                   help="fenêtre « pendant » juste après la coupure")
    p.add_argument("--failure-timeout", type=float, default=5.0,
                   help="délai par requête pendant la phase de défaillance. Court "
                        "devant la fenêtre « après », sans quoi une requête bloquée "
                        "n'est jamais comptée et la phase paraît vide.")
    p.add_argument("--json", help="écrit les résultats bruts dans ce fichier")
    args = p.parse_args()

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
