import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        pass  # don't spam service logs with health-check hits


def start_health_server(port: int) -> HTTPServer:
    """A deliberately minimal `/health` endpoint on its own thread, purely
    so `docker compose`/Kubernetes can tell this process is alive — the
    reference implementation had no Dockerfile healthcheck for any of its
    four Python services. Not a metrics endpoint (that's Phase 12)."""
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server listening on :%d/health", port)
    return server
