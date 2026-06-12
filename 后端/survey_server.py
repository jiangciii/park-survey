import argparse
import json
import mimetypes
import os
import secrets
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from survey_backend import SurveyRepository, export_ce_choices_csv, export_respondents_csv


SESSION_COOKIE = "survey_admin_session"


def split_csv_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_db_target(value: str) -> str | Path:
    if value.startswith("mysql://"):
        return value
    return Path(value)


def create_server(host: str, port: int, db_path: str | Path, project_root: str | Path):
    repository = SurveyRepository(db_path)
    project_root = Path(project_root)
    admin_user = os.environ.get("SURVEY_ADMIN_USER", "admin")
    admin_password = os.environ.get("SURVEY_ADMIN_PASSWORD", "admin123456")
    public_base_url = os.environ.get("SURVEY_PUBLIC_BASE_URL", "").rstrip("/")
    api_base_url = os.environ.get("SURVEY_API_BASE_URL", "").rstrip("/")
    allow_origins = split_csv_env(os.environ.get("SURVEY_ALLOW_ORIGIN"))
    sessions: dict[str, dict] = {}

    class SurveyHTTPRequestHandler(BaseHTTPRequestHandler):
        server_version = "SurveyResearchServer/0.2"

        def log_message(self, format, *args):
            return

        @property
        def repo(self) -> SurveyRepository:
            return repository

        def _cors_headers(self) -> dict[str, str]:
            if not allow_origins:
                return {}

            request_origin = self.headers.get("Origin", "")
            if "*" in allow_origins:
                return {
                    "Access-Control-Allow-Origin": request_origin or "*",
                    "Vary": "Origin",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                }

            if request_origin and request_origin in allow_origins:
                return {
                    "Access-Control-Allow-Origin": request_origin,
                    "Vary": "Origin",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                }

            return {}

        def _send_bytes(self, status: int, body: bytes, content_type: str, extra_headers: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in self._cors_headers().items():
                self.send_header(key, value)
            if extra_headers:
                for key, value in extra_headers.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_text(
            self,
            status: int,
            text: str,
            content_type: str = "text/html; charset=utf-8",
            extra_headers: dict | None = None,
        ):
            self._send_bytes(status, text.encode("utf-8"), content_type, extra_headers)

        def _send_json(self, status: int, payload: dict, extra_headers: dict | None = None):
            self._send_text(status, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8", extra_headers)

        def _read_json(self) -> dict:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                return {}
            raw = self.rfile.read(content_length)
            return json.loads(raw.decode("utf-8"))

        def _redirect(self, location: str):
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", location)
            self.send_header("Cache-Control", "no-store")
            for key, value in self._cors_headers().items():
                self.send_header(key, value)
            self.end_headers()

        def _runtime_config_js(self) -> str:
            payload = {
                "apiBaseUrl": api_base_url,
                "publicBaseUrl": public_base_url,
                "surveyPath": "/survey",
                "adminLoginPath": "/admin/login",
            }
            return (
                "window.__SURVEY_RUNTIME__ = Object.assign({}, "
                "window.__SURVEY_RUNTIME__ || {}, "
                f"{json.dumps(payload, ensure_ascii=False)});"
            )

        def _serve_file(self, file_path: Path):
            if not file_path.exists() or not file_path.is_file():
                self._send_text(HTTPStatus.NOT_FOUND, "Not found", "text/plain; charset=utf-8")
                return
            content_type, _ = mimetypes.guess_type(file_path.name)
            self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), content_type or "application/octet-stream")

        def _get_cookie_value(self, key: str) -> str | None:
            raw_cookie = self.headers.get("Cookie")
            if not raw_cookie:
                return None
            cookie = SimpleCookie()
            cookie.load(raw_cookie)
            morsel = cookie.get(key)
            return morsel.value if morsel else None

        def _admin_session(self) -> dict | None:
            token = self._get_cookie_value(SESSION_COOKIE)
            return sessions.get(token)

        def _require_admin_api(self) -> bool:
            if self._admin_session():
                return True
            self._send_json(HTTPStatus.UNAUTHORIZED, {"status": "error", "message": "管理员未登录"})
            return False

        def _require_admin_page(self) -> bool:
            if self._admin_session():
                return True
            self._redirect("/admin/login")
            return False

        def _static_file_for_path(self, request_path: str) -> Path | None:
            static_map = {
                "/survey": project_root / "survey_web.html",
                "/static/survey_app.js": project_root / "survey_app.js",
                "/static/admin_app.css": project_root / "admin_app.css",
                "/static/admin_login.js": project_root / "admin_login.js",
                "/static/admin_dashboard.js": project_root / "admin_dashboard.js",
                "/static/admin_response.js": project_root / "admin_response.js",
                "/admin/login": project_root / "admin_login.html",
                "/admin/dashboard": project_root / "admin_dashboard.html",
            }
            if request_path in static_map:
                return static_map[request_path]
            if request_path.startswith("/assets/"):
                return project_root / request_path.lstrip("/")
            return None

        def do_OPTIONS(self):
            self.send_response(HTTPStatus.NO_CONTENT)
            for key, value in self._cors_headers().items():
                self.send_header(key, value)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/":
                self._send_text(
                    HTTPStatus.OK,
                    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>城市公园使用体验调研</title>
  <style>
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #f4f7fb;
      color: #24364b;
      display: flex;
      min-height: 100vh;
      align-items: center;
      justify-content: center;
    }
    .shell {
      width: min(520px, calc(100vw - 40px));
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid rgba(191, 205, 223, 0.6);
      border-radius: 28px;
      box-shadow: 0 24px 60px rgba(74, 103, 140, 0.12);
      padding: 32px 28px;
    }
    h1 {
      margin: 0 0 12px;
      font-size: 28px;
      line-height: 1.2;
    }
    p {
      margin: 0 0 20px;
      color: #5d728b;
      line-height: 1.7;
    }
    .links {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 132px;
      padding: 12px 18px;
      border-radius: 999px;
      text-decoration: none;
      font-weight: 600;
      transition: transform 0.18s ease, box-shadow 0.18s ease;
    }
    a.primary {
      background: linear-gradient(135deg, #5d9fc0, #5b83d4);
      color: #fff;
      box-shadow: 0 14px 30px rgba(91, 131, 212, 0.2);
    }
    a.secondary {
      background: #eef4fb;
      color: #365272;
      border: 1px solid rgba(170, 190, 214, 0.8);
    }
  </style>
</head>
<body>
  <main class="shell">
    <h1>城市公园使用体验调研</h1>
    <p>服务已启动。前台问卷和管理员后台都已就绪，可从下方入口继续访问。</p>
    <div class="links">
      <a class="primary" href="/survey">进入问卷</a>
      <a class="secondary" href="/admin/login">管理员后台</a>
    </div>
  </main>
</body>
</html>""",
                )
                return

            if path == "/healthz":
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return

            if path == "/static/runtime-config.js":
                self._send_text(HTTPStatus.OK, self._runtime_config_js(), "application/javascript; charset=utf-8")
                return

            if path == "/admin/login" and self._admin_session():
                self._redirect("/admin/dashboard")
                return

            if path == "/api/admin/dashboard":
                if not self._require_admin_api():
                    return
                params = parse_qs(parsed.query)
                status = params.get("status", [None])[0]
                search = params.get("search", [None])[0]
                self._send_json(HTTPStatus.OK, self.repo.dashboard_summary(status=status, search=search))
                return

            if path.startswith("/api/admin/responses/"):
                if not self._require_admin_api():
                    return
                respondent_id = path.rsplit("/", 1)[-1]
                detail = self.repo.get_response_detail(respondent_id)
                if detail is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "答卷不存在"})
                    return
                self._send_json(HTTPStatus.OK, detail)
                return

            if path == "/api/admin/export/respondents.csv":
                if not self._require_admin_api():
                    return
                self._send_bytes(
                    HTTPStatus.OK,
                    export_respondents_csv(self.repo),
                    "text/csv; charset=utf-8",
                    {"Content-Disposition": 'attachment; filename="respondents.csv"'},
                )
                return

            if path == "/api/admin/export/ce_choices.csv":
                if not self._require_admin_api():
                    return
                self._send_bytes(
                    HTTPStatus.OK,
                    export_ce_choices_csv(self.repo),
                    "text/csv; charset=utf-8",
                    {"Content-Disposition": 'attachment; filename="ce_choices.csv"'},
                )
                return

            if path.startswith("/admin/responses/"):
                if not self._require_admin_page():
                    return
                self._serve_file(project_root / "admin_response.html")
                return

            if path == "/admin/dashboard":
                if not self._require_admin_page():
                    return
                self._serve_file(project_root / "admin_dashboard.html")
                return

            file_path = self._static_file_for_path(path)
            if file_path is not None:
                self._serve_file(file_path)
                return

            self._send_text(HTTPStatus.NOT_FOUND, "Not found", "text/plain; charset=utf-8")

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            body = self._read_json()

            if path == "/api/respondents/start":
                respondent_id = self.repo.start_response(body.get("started_at"))
                self._send_json(HTTPStatus.OK, {"status": "ok", "respondent_id": respondent_id})
                return

            if path == "/api/respondents/draft":
                respondent_id = body.get("respondent_id")
                if not respondent_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "缺少 respondent_id"})
                    return
                self.repo.save_draft(respondent_id, body.get("payload"), body.get("client_meta"))
                self._send_json(HTTPStatus.OK, {"status": "ok", "respondent_id": respondent_id})
                return

            if path == "/api/respondents/submit":
                respondent_id = body.get("respondent_id")
                payload = body.get("payload")
                if not respondent_id or not payload:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "缺少提交数据"})
                    return
                completion_code = self.repo.submit_response(respondent_id, payload, body.get("client_meta"))
                self._send_json(
                    HTTPStatus.OK,
                    {"status": "ok", "respondent_id": respondent_id, "completion_code": completion_code},
                )
                return

            if path == "/api/admin/login":
                username = body.get("username", "")
                password = body.get("password", "")
                if username != admin_user or password != admin_password:
                    self._send_json(HTTPStatus.UNAUTHORIZED, {"status": "error", "message": "账号或密码错误"})
                    return
                token = secrets.token_urlsafe(24)
                sessions[token] = {"username": username}
                self._send_json(
                    HTTPStatus.OK,
                    {"status": "ok", "username": username},
                    {"Set-Cookie": f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax"},
                )
                return

            if path == "/api/admin/logout":
                token = self._get_cookie_value(SESSION_COOKIE)
                if token and token in sessions:
                    sessions.pop(token, None)
                self._send_json(
                    HTTPStatus.OK,
                    {"status": "ok"},
                    {"Set-Cookie": f"{SESSION_COOKIE}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0"},
                )
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "未找到接口"})

    return ThreadingHTTPServer((host, port), SurveyHTTPRequestHandler)


def main():
    parser = argparse.ArgumentParser(description="Run the survey research web system")
    parser.add_argument("--host", default=os.environ.get("SURVEY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", os.environ.get("SURVEY_PORT", "8000"))))
    parser.add_argument("--db", default=os.environ.get("SURVEY_DB_PATH", "survey_data.db"))
    parser.add_argument("--root", default=os.environ.get("SURVEY_PROJECT_ROOT", "."))
    args = parser.parse_args()

    db_target = normalize_db_target(args.db)
    server = create_server(args.host, args.port, db_target, Path(args.root).resolve())
    public_base_url = os.environ.get("SURVEY_PUBLIC_BASE_URL", "").rstrip("/")
    survey_url = f"{public_base_url}/survey" if public_base_url else f"http://{args.host}:{args.port}/survey"
    print(f"Survey server running at {survey_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
