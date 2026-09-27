"""
Panther Agent - Python Agent Runtime Server
IPC / API Server providing the local interface between the desktop shell and the agent engine.
Runs as a local lightweight service (default port: 5050).
"""

import sys
import os

pkg_dir = os.path.dirname(os.path.abspath(__file__))
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

import json
import logging
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

# Import modules
from database import DatabaseManager
from config_manager import ConfigManager
from resource_governor import ResourceGovernor
from device_manager import DeviceManager
from screen_observer import ScreenObserver
from ocr_processor import OcrProcessor
from action_executor import ActionExecutor
from verification_engine import VerificationEngine, GoalVerifier
from model_manager import ModelManager
from state_engine import StateEngine
from setup_manager import SetupManager
from agent_controller import AgentController
from model_catalog import get_model_catalog

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("panther.server")

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    request_queue_size = 128

class PantherRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 10.0

    def log_message(self, format, *args):
        # Prevent standard HTTP access noise from flooding console
        pass

    def _send_json(self, status_code: int, data: dict):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.close_connection = True

    def do_OPTIONS(self):
        try:
            self.send_response(204)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.close_connection = True

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            runtime = self.server.runtime

            if path == "/api/status":
                self._send_json(200, runtime["controller"].get_current_status())

            elif path == "/api/screen/current":
                obs = runtime["screen"].get_current_observation()
                if obs:
                    self._send_json(200, obs.to_dict(include_nodes=True))
                else:
                    self._send_json(200, {"observation_id": None, "nodes": []})

            elif path == "/api/screen/diff":
                diff = runtime["screen"].get_last_diff()
                self._send_json(200, diff or {})

            elif path == "/api/device":
                self._send_json(200, runtime["device"].get_profile())

            elif path == "/api/tasks/history":
                limit = int(qs.get("limit", ["50"])[0])
                self._send_json(200, {"tasks": runtime["db"].get_task_history(limit)})

            elif path.startswith("/api/tasks/") and len(path.split("/")) == 4:
                task_id = path.split("/")[3]
                task_data = runtime["db"].get_task_details(task_id)
                if task_data:
                    self._send_json(200, task_data)
                else:
                    self._send_json(404, {"error": f"Task '{task_id}' not found."})

            elif path == "/api/models":
                self._send_json(200, {
                    "models": runtime["model"].get_available_models(),
                    "active_model": runtime["config"].get_value("model", "selected_model")
                })

            elif path == "/api/models/health":
                self._send_json(200, runtime["model"].check_ollama_health())

            elif path == "/api/config":
                self._send_json(200, runtime["config"].get_full_config())

            elif path == "/api/diagnostics":
                limit = int(qs.get("limit", ["100"])[0])
                min_level = qs.get("level", [None])[0]
                self._send_json(200, {
                    "logs": runtime["db"].get_diagnostics(limit, min_level)
                })

            elif path in ("/api/setup", "/api/setup/status"):
                self._send_json(200, runtime["setup"].get_setup_status())

            elif path == "/api/setup/catalog":
                self._send_json(200, {
                    "catalog": get_model_catalog(),
                    "tier": runtime["device"].get_profile().get("tier", 1)
                })

            elif path == "/api/setup/model/progress":
                status = runtime["setup"].get_setup_status()
                self._send_json(200, status.get("download_progress", {}))

            elif path == "/api/health":
                self._send_json(200, {"status": "ok", "app": "Panther Agent Runtime", "version": "0.1.0-alpha"})

            else:
                self._send_json(404, {"error": f"Endpoint '{path}' not found."})
        except Exception as e:
            logger.exception("Error handling GET %s: %s", self.path, str(e))
            self._send_json(500, {"error": "Internal Server Error", "detail": str(e)})

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            runtime = self.server.runtime
            content_length = int(self.headers.get("Content-Length", 0))
            body = {}
            if content_length > 0:
                raw_body = self.rfile.read(content_length).decode("utf-8")
                try:
                    body = json.loads(raw_body)
                except Exception:
                    pass

            if path == "/api/tasks/start":
                goal = body.get("goal", "").strip()
                title = body.get("title")
                if not goal:
                    self._send_json(400, {"error": "Missing mandatory 'goal' field."})
                    return
                result = runtime["controller"].start_task(goal, title)
                code = 200 if result.get("success") else 400
                self._send_json(code, result)

            elif path == "/api/tasks/pause":
                self._send_json(200, runtime["controller"].pause_task())

            elif path == "/api/tasks/resume":
                self._send_json(200, runtime["controller"].resume_task())

            elif path == "/api/tasks/cancel":
                self._send_json(200, runtime["controller"].cancel_task())

            elif path == "/api/config":
                section = body.get("section")
                updates = body.get("updates", {})
                if not section:
                    self._send_json(400, {"error": "Missing 'section' parameter."})
                    return
                updated = runtime["config"].update_section(section, updates)
                self._send_json(200, {"section": section, "config": updated})

            elif path == "/api/config/reset":
                all_cfg = runtime["config"].reset_to_defaults()
                self._send_json(200, {"message": "Configuration reset to defaults.", "config": all_cfg})

            elif path == "/api/models/select":
                model_id = body.get("model_id")
                if not model_id:
                    self._send_json(400, {"error": "Missing 'model_id'."})
                    return
                runtime["config"].update_section("model", {"selected_model": model_id})
                self._send_json(200, {"success": True, "selected_model": model_id})

            elif path == "/api/setup/run":
                res = runtime["setup"].run_preflight_checks()
                self._send_json(200, res)

            elif path == "/api/setup/scan":
                self._send_json(200, runtime["setup"].scan_device_and_capabilities())

            elif path == "/api/setup/model/select":
                model_id = body.get("model_id")
                if not model_id:
                    self._send_json(400, {"error": "Missing 'model_id'."})
                    return
                try:
                    res = runtime["setup"].select_model(model_id)
                    self._send_json(200, res)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})

            elif path == "/api/setup/model/download":
                model_id = body.get("model_id")
                res = runtime["setup"].start_model_download(model_id)
                self._send_json(200, res)

            elif path == "/api/setup/model/download/cancel":
                res = runtime["setup"].cancel_model_download()
                self._send_json(200, res)

            elif path == "/api/setup/verify":
                res = runtime["setup"].verify_and_test_model()
                self._send_json(200, res)

            elif path == "/api/setup/complete":
                res = runtime["setup"].complete_setup()
                self._send_json(200, res)

            elif path == "/api/setup/reset":
                res = runtime["setup"].reset_setup()
                self._send_json(200, res)

            else:
                self._send_json(404, {"error": f"Endpoint '{path}' not found."})
        except Exception as e:
            logger.exception("Error handling POST %s: %s", self.path, str(e))
            self._send_json(500, {"error": "Internal Server Error", "detail": str(e)})

def init_runtime(db_path: str = None) -> dict:
    """Instantiates and wires all modular runtime subsystems."""
    db = DatabaseManager(db_path)
    config = ConfigManager(db)
    governor = ResourceGovernor(db, config)
    device = DeviceManager(db)
    ocr = OcrProcessor(db, config)
    screen = ScreenObserver(db, config, ocr)
    executor = ActionExecutor(db, config, screen)
    verification = VerificationEngine(db)
    goal_ver = GoalVerifier(db)
    model = ModelManager(db, config)
    state = StateEngine(db)
    setup = SetupManager(db, config, device, model)

    controller = AgentController(
        db=db,
        config=config,
        resource_governor=governor,
        screen_observer=screen,
        action_executor=executor,
        verification_engine=verification,
        goal_verifier=goal_ver,
        model_manager=model,
        state_engine=state
    )

    # Initial device and setup evaluation
    device.inspect_device()
    setup.run_preflight_checks()

    return {
        "db": db,
        "config": config,
        "governor": governor,
        "device": device,
        "screen": screen,
        "ocr": ocr,
        "executor": executor,
        "verification": verification,
        "goal_ver": goal_ver,
        "model": model,
        "state": state,
        "setup": setup,
        "controller": controller
    }

def run_server(port: int = 5050):
    runtime = init_runtime()
    server = ThreadingHTTPServer(("127.0.0.1", port), PantherRequestHandler)
    server.runtime = runtime

    logger.info("Panther Agent Python Runtime initialized on http://127.0.0.1:%d", port)

    def shutdown_handler(signum, frame):
        logger.info("Initiating clean shutdown of Panther Agent runtime...")
        server.shutdown()
        server.server_close()
        logger.info("Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown_handler(None, None)

if __name__ == "__main__":
    port = int(os.environ.get("PANTHER_PORT", 5050))
    run_server(port)
