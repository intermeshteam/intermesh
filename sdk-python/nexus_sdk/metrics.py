import time
from typing import Dict, Any


class NexusMetricsCollector:
    """
    Collecteur de metriques standardise compatible Prometheus / OpenMetrics.
    """

    def __init__(self):
        self.start_time = time.time()
        self.counters: Dict[str, int] = {
            "nexus_messages_routed_total": 0,
            "nexus_tasks_submitted_total": 0,
            "nexus_tasks_completed_total": 0,
            "nexus_tasks_failed_total": 0,
            "nexus_auth_failures_total": 0,
        }

    def increment(self, metric_name: str, value: int = 1) -> None:
        if metric_name in self.counters:
            self.counters[metric_name] += value
        else:
            self.counters[metric_name] = value

    def generate_prometheus_output(self, live_gauges: Dict[str, Any]) -> str:
        """
        Genere une sortie textuelle conforme a la specification OpenMetrics.
        """
        lines = []
        lines.append("# HELP nexus_uptime_seconds Duree de fonctionnement du Hub en secondes.")
        lines.append("# TYPE nexus_uptime_seconds gauge")
        lines.append(f"nexus_uptime_seconds {time.time() - self.start_time:.2f}")

        # Ingestion des jauges dynamiques fournies par le Hub
        for gauge_name, gauge_val in live_gauges.items():
            lines.append(f"# HELP {gauge_name} Metrique d'etat instantane du Hub.")
            lines.append(f"# TYPE {gauge_name} gauge")
            lines.append(f"{gauge_name} {gauge_val}")

        # Ingestion des compteurs cumulatifs
        for counter_name, counter_val in self.counters.items():
            lines.append(f"# HELP {counter_name} Compteur cumulatif d'evenements.")
            lines.append(f"# TYPE {counter_name} counter")
            lines.append(f"{counter_name} {counter_val}")

        return "\n".join(lines) + "\n"

metrics = NexusMetricsCollector()
