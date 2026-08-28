import json
from typing import Optional, Tuple, List, Callable, Any
from intermesh.metrics import metrics


class HealthCheckHandler:
    """
    Gestionnaire universel de requetes HTTP de supervision (/healthz, /readyz, /metrics).
    """

    def __init__(self, readiness_evaluator: Optional[Callable[[], bool]] = None,
                 state_metrics_provider: Optional[Callable[[], dict]] = None):
        self.readiness_evaluator = readiness_evaluator
        self.state_metrics_provider = state_metrics_provider

    def handle_request(self, path: str) -> Optional[Tuple[int, List[Tuple[str, str]], bytes]]:
        """
        Traite une requete HTTP entrante.
        Retourne (status_code, headers, body) si le chemin correspond a un endpoint gere,
        ou None s'il s'agit d'une requete de mise a niveau WebSocket.
        """
        clean_path = path.split("?")[0].rstrip("/")

        if clean_path == "/healthz":
            payload = json.dumps({"status": "ok", "service": "nexus-hub"}).encode("utf-8")
            headers = [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(payload))),
                ("Access-Control-Allow-Origin", "*")
            ]
            return 200, headers, payload

        elif clean_path == "/readyz":
            is_ready = self.readiness_evaluator() if self.readiness_evaluator else True
            status_code = 200 if is_ready else 503
            status_str = "ready" if is_ready else "unavailable"
            payload = json.dumps({"status": status_str, "ready": is_ready}).encode("utf-8")
            headers = [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(payload))),
                ("Access-Control-Allow-Origin", "*")
            ]
            return status_code, headers, payload

        elif clean_path == "/metrics":
            live_gauges = self.state_metrics_provider() if self.state_metrics_provider else {}
            output = metrics.generate_prometheus_output(live_gauges)
            payload = output.encode("utf-8")
            headers = [
                ("Content-Type", "text/plain; version=0.0.4; charset=utf-8"),
                ("Content-Length", str(len(payload))),
                ("Access-Control-Allow-Origin", "*")
            ]
            return 200, headers, payload

        return None
