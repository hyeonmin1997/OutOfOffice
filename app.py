"""Local demo HTTP server. Start with: python3 app.py."""

import json
import os
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from planner import LLMResponseError
from service import ATTACK, NORMAL, Service

STATIC_DIR = Path(__file__).resolve().parent / "static"
CASES_FILE = STATIC_DIR.parent / "eval" / "cases.json"
# Attacks that succeeded with Defense OFF against qwen2.5:3b (see eval/DATA_CARD.md).
BASELINE_EXAMPLES = ("a_dev_exfil_appended", "a_test_task_overwrite_fake_system")
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
PORT = 8000
# Requests must name this server; another Host means DNS rebinding or a proxy.
ALLOWED_HOSTS = (f"127.0.0.1:{PORT}", f"localhost:{PORT}")
ALLOWED_ORIGINS = (None, *(f"http://{host}" for host in ALLOWED_HOSTS))


def baseline_examples():
    """Measured attack cases for the Defense OFF comparison, read from the case file."""
    try:
        cases = {c["id"]: c for c in json.loads(CASES_FILE.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return []
    return [
        {"id": cid, "goal": cases[cid]["goal"], "split": cases[cid]["split"],
         "mail": cases[cid]["mail"]}
        for cid in BASELINE_EXAMPLES if cid in cases
    ]


def make_handler(service):
    """Bind one local demo service to the HTTP routes."""

    class Handler(BaseHTTPRequestHandler):
        def reply(self, value, status=200):
            payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def host_denied(self):
            if self.headers.get("Host") in ALLOWED_HOSTS:
                return False
            self.reply({"error": "Host denied"}, 403)
            return True

        def do_GET(self):
            if self.host_denied():
                return
            if self.path in ASSETS:
                filename, content_type = ASSETS[self.path]
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write((STATIC_DIR / filename).read_bytes())
            elif self.path == "/state":
                self.reply(service.state())
            elif self.path == "/examples":
                self.reply({"normal": NORMAL, "attack": ATTACK,
                            "baseline": baseline_examples()})
            else:
                self.reply({"error": "Not found"}, 404)

        def do_POST(self):
            # Read the (bounded) body first: replying with it unread can reset the
            # connection before the client sees the response.
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            body = self.rfile.read(length) if 0 < length <= 16000 else b""
            # Only a trusted local demonstrator may operate this server.
            if self.host_denied():
                return
            if self.headers.get("Origin") not in ALLOWED_ORIGINS:
                return self.reply({"error": "Origin denied"}, 403)
            try:
                if not 0 < length <= 16000:
                    raise ValueError("Invalid request size")
                value = json.loads(body)
                if self.path == "/plan":
                    result = service.plan(
                        value["mail"], value["mode"], value["mail_id"],
                        value.get("defense", True),
                    )
                elif self.path == "/approve":
                    if type(value.get("accept")) is not bool:
                        raise ValueError("Boolean approval required")
                    if type(value.get("id")) is not str:
                        raise ValueError("Approval id must be a string")
                    result = service.approve(value["id"], value["accept"])
                elif self.path == "/import":
                    result = service.import_seed()
                elif self.path == "/reset":
                    service.reset()
                    result = {"status": "reset"}
                else:
                    return self.reply({"error": "Not found"}, 404)
                self.reply(result)
            except (ValueError, KeyError, TypeError) as error:
                self.reply({"error": str(error)}, 400)
            except (urllib.error.URLError, TimeoutError):
                self.reply(
                    {
                        "error": "LLM 서버에 연결하지 못했습니다. Ollama가 실행 중인지, "
                        "모델을 받았는지(ollama pull) 확인하세요. 이미 실행된 행동은 DB에서 확인하세요."
                    },
                    503,
                )
            except LLMResponseError:
                self.reply(
                    {
                        "error": "LLM 서버의 응답 형식이 올바르지 않습니다. 모델 이름과 "
                        "엔드포인트(chat completions, tool calling 지원)를 확인하세요."
                    },
                    502,
                )
            except Exception:
                # Do not expose provider responses or credentials through HTTP errors.
                self.reply(
                    {
                        "error": "실행 중 오류가 발생했습니다. DB 결과를 확인하고 API 설정을 점검하세요."
                    },
                    500,
                )

    return Handler


def main():
    service = Service(os.getenv("DB_PATH", str(STATIC_DIR.parent / "data/demo.sqlite")))
    server = HTTPServer(("127.0.0.1", PORT), make_handler(service))
    print(f"Open http://127.0.0.1:{PORT} — trusted local demo only")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.db.close()


if __name__ == "__main__":
    main()
