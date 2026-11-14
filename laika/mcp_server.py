#!/usr/bin/env python3
"""Safe, loopback-only MCP tools for L.A.I.K.A. and Fono.

No shell execution, arbitrary writes, deletes, installs, or admin operations.
"""
from __future__ import annotations
import json, os, platform, shutil, subprocess
from configparser import ConfigParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = int(os.environ.get("LAIKA_MCP_PORT", "8765"))
MAX_BODY = 1_000_000
MAX_READ = 64 * 1024
TEXT_EXTENSIONS = {".txt", ".md", ".py", ".json", ".toml", ".yaml", ".yml", ".csv", ".log", ".ini", ".cfg", ".html", ".css", ".js", ".ts", ".sh", ".xml", ".rst"}
BLOCKED_NAMES = {".ssh", ".gnupg", ".config", ".local", ".pki", ".aws", ".azure", ".env", ".netrc", "id_rsa", "id_ed25519"}
BLOCKED_WORDS = ("secret", "credential", "password", "token", "private-key")
ROOTS = {
    "Desktop": Path.home() / "Desktop",
    "Documents": Path.home() / "Documents",
    "Downloads": Path.home() / "Downloads",
    "LAIKA": Path.home() / "LAIKA",
    "Applications": Path.home() / "Applications",
}

def text_result(value, is_error=False):
    rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": rendered}], "isError": is_error}

def is_blocked(path):
    for part in path.parts:
        low = part.lower()
        if low in BLOCKED_NAMES or any(word in low for word in BLOCKED_WORDS):
            return True
    return False

def safe_path(location, relative="."):
    if location not in ROOTS:
        raise ValueError("Choose Desktop, Documents, Downloads, LAIKA, or Applications.")
    root = ROOTS[location].resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("That path is outside the approved location.")
    if is_blocked(candidate):
        raise ValueError("Access to hidden or sensitive paths is blocked.")
    return candidate

def system_status():
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, rest = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable"}:
                mem[key] = rest.strip()
    except (OSError, ValueError):
        pass
    disk = shutil.disk_usage(Path.home())
    return {
        "computer": platform.node(), "os": platform.platform(),
        "architecture": platform.machine(), "python": platform.python_version(),
        "memory": mem,
        "home_disk_gb": {"total": round(disk.total / 1024**3, 1), "free": round(disk.free / 1024**3, 1)},
        "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
    }

def list_files(location, relative_path="."):
    folder = safe_path(location, relative_path)
    if not folder.exists() or not folder.is_dir():
        raise ValueError("That folder does not exist.")
    entries = []
    for item in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if item.is_symlink() or item.name.startswith(".") or is_blocked(item):
            continue
        try:
            entries.append({"name": item.name, "type": "folder" if item.is_dir() else "file", "size_bytes": item.stat().st_size if item.is_file() else None})
        except OSError:
            continue
        if len(entries) >= 100:
            break
    return {"location": location, "folder": relative_path, "entries": entries}

def search_files(location, query, max_results=25):
    if not query.strip():
        raise ValueError("Search text cannot be empty.")
    root = safe_path(location)
    if not root.exists():
        return {"location": location, "matches": []}
    limit = max(1, min(int(max_results), 25))
    matches, visited = [], 0
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not is_blocked(Path(base) / d)]
        if len(Path(base).relative_to(root).parts) >= 5:
            dirs[:] = []
        for name in files:
            visited += 1
            candidate = Path(base) / name
            if candidate.is_symlink() or name.startswith(".") or is_blocked(candidate):
                continue
            if query.casefold() in name.casefold():
                full = Path(base) / name
                try:
                    matches.append({"path": full.relative_to(root).as_posix(), "size_bytes": full.stat().st_size})
                except OSError:
                    pass
                if len(matches) >= limit:
                    return {"location": location, "matches": matches, "truncated": True}
        if visited >= 5000:
            break
    return {"location": location, "matches": matches, "truncated": visited >= 5000}

def read_text_file(location, path):
    file_path = safe_path(location, path)
    if not file_path.is_file():
        raise ValueError("That file does not exist.")
    if file_path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError("Only common text and source-code files can be read.")
    if file_path.stat().st_size > MAX_READ:
        raise ValueError("That file is larger than the 64 KiB reading limit.")
    return file_path.read_text(encoding="utf-8", errors="replace")

def desktop_entries():
    roots = [Path.home() / ".local/share/applications", Path("/usr/local/share/applications"), Path("/usr/share/applications")]
    found = {}
    for root in roots:
        if not root.is_dir():
            continue
        for file in root.rglob("*.desktop"):
            if file.is_symlink() or is_blocked(file):
                continue
            parser = ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(file, encoding="utf-8")
                section = parser["Desktop Entry"]
                if section.getboolean("Hidden", fallback=False) or section.getboolean("NoDisplay", fallback=False):
                    continue
                name = section.get("Name", "").strip()
                if name:
                    desktop_id = file.relative_to(root).as_posix()[:-8]
                    found[desktop_id] = name
            except (OSError, KeyError, ValueError):
                continue
    return found

def find_applications(query=""):
    q = query.casefold().strip()
    rows = [{"desktop_id": app_id, "name": name} for app_id, name in desktop_entries().items()
            if not q or q in app_id.casefold() or q in name.casefold()]
    rows.sort(key=lambda row: row["name"].casefold())
    return rows[:50]

def open_application(desktop_id):
    apps = desktop_entries()
    if desktop_id not in apps:
        raise ValueError("That application is not in the installed desktop-app catalogue.")
    launcher = shutil.which("gtk-launch")
    if not launcher:
        raise RuntimeError("gtk-launch is not installed; no fallback command will be executed.")
    subprocess.Popen([launcher, desktop_id], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return "Opened " + apps[desktop_id] + "."

def open_file(location, path):
    file_path = safe_path(location, path)
    if not file_path.is_file():
        raise ValueError("That file does not exist.")
    safe_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
                       ".mp4", ".mkv", ".mp3", ".wav", ".ogg", ".flac",
                       ".txt", ".md", ".csv", ".docx", ".xlsx", ".pptx",
                       ".odt", ".ods", ".odp"}
    if file_path.suffix.lower() not in safe_extensions:
        raise ValueError("For safety, this file type cannot be launched or opened by the assistant.")
    opener = shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("xdg-open is unavailable.")
    subprocess.Popen([opener, str(file_path)], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return "Opened " + file_path.name + "."

def open_website(url):
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only complete HTTP or HTTPS website addresses are allowed.")
    opener = shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("xdg-open is unavailable.")
    subprocess.Popen([opener, url.strip()], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return "Opened the website in your default browser."

TOOLS = [
 {"name":"get_system_status","description":"Read basic non-sensitive laptop status: OS, architecture, memory and free disk space.","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
 {"name":"list_files","description":"List visible files and folders in Desktop, Documents, Downloads, LAIKA, or Applications. Does not read contents.","inputSchema":{"type":"object","properties":{"location":{"type":"string","enum":list(ROOTS)},"relative_path":{"type":"string","description":"Folder relative to selected location; . means its root."}},"required":["location"],"additionalProperties":False}},
 {"name":"search_files","description":"Search file names, not file contents, in one approved folder. Hidden and sensitive folders are excluded.","inputSchema":{"type":"object","properties":{"location":{"type":"string","enum":list(ROOTS)},"query":{"type":"string"},"max_results":{"type":"integer","minimum":1,"maximum":25}},"required":["location","query"],"additionalProperties":False}},
 {"name":"read_text_file","description":"Read a small text or source-code file in an approved folder. Maximum 64 KiB. Hidden and sensitive paths are blocked.","inputSchema":{"type":"object","properties":{"location":{"type":"string","enum":list(ROOTS)},"path":{"type":"string","description":"File path relative to selected location."}},"required":["location","path"],"additionalProperties":False}},
 {"name":"find_applications","description":"Find installed desktop applications by visible name. Does not launch anything.","inputSchema":{"type":"object","properties":{"query":{"type":"string"}},"additionalProperties":False}},
 {"name":"open_application","description":"Launch an installed desktop application by desktop_id returned by find_applications. Does not run arbitrary shell commands.","inputSchema":{"type":"object","properties":{"desktop_id":{"type":"string"}},"required":["desktop_id"],"additionalProperties":False}},
 {"name":"open_file","description":"Open a safe document, image, or media file in an approved folder using its normal desktop application. Executables and scripts are blocked.","inputSchema":{"type":"object","properties":{"location":{"type":"string","enum":list(ROOTS)},"path":{"type":"string"}},"required":["location","path"],"additionalProperties":False}},
 {"name":"open_website","description":"Open a user-requested HTTP or HTTPS URL in the default browser.","inputSchema":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"],"additionalProperties":False}},
]

def call_tool(name, args):
    try:
        if name == "get_system_status": value = system_status()
        elif name == "list_files": value = list_files(args["location"], args.get("relative_path", "."))
        elif name == "search_files": value = search_files(args["location"], args["query"], args.get("max_results", 25))
        elif name == "read_text_file": value = read_text_file(args["location"], args["path"])
        elif name == "find_applications": value = find_applications(args.get("query", ""))
        elif name == "open_application": value = open_application(args["desktop_id"])
        elif name == "open_file": value = open_file(args["location"], args["path"])
        elif name == "open_website": value = open_website(args["url"])
        else: return text_result("Unknown tool: " + name, True)
        return text_result(value)
    except (KeyError, TypeError, ValueError, OSError, RuntimeError) as exc:
        return text_result("Action refused: " + str(exc), True)

class Handler(BaseHTTPRequestHandler):
    server_version = "LAIKA-MCP/0.1"
    def log_message(self, fmt, *args):
        print("[LAIKA MCP] " + (fmt % args), flush=True)
    def send_json(self, status, payload=None):
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body: self.wfile.write(body)
    def do_GET(self):
        if self.path == "/health": self.send_json(200, {"status":"ok","service":"laika-mcp","version":"0.1"})
        else: self.send_json(404, {"error":"not found"})
    def do_POST(self):
        if self.path not in {"/mcp", "/"}:
            self.send_json(404, {"error":"not found"}); return
        # Reject DNS-rebinding / cross-origin browser requests. Fono's native
        # client sends no Origin header; local web clients may use loopback.
        host = self.headers.get("Host", "").split(":", 1)[0].strip("[]").lower()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            self.send_json(403, {"error":"host not allowed"}); return
        origin = self.headers.get("Origin")
        if origin:
            parsed_origin = urlparse(origin)
            if parsed_origin.scheme not in {"http", "https"} or parsed_origin.hostname not in {"127.0.0.1", "localhost", "::1"}:
                self.send_json(403, {"error":"origin not allowed"}); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                self.send_json(413, {"error":"request size rejected"}); return
            request = json.loads(self.rfile.read(length))
            method, request_id = request.get("method"), request.get("id")
            if method == "notifications/initialized":
                self.send_json(202); return
            if method == "initialize":
                result = {"protocolVersion":"2025-03-26","capabilities":{"tools":{}},
                          "serverInfo":{"name":"laika-local-tools","version":"0.1.0"}}
            elif method == "tools/list": result = {"tools":TOOLS}
            elif method == "tools/call":
                params = request.get("params") or {}
                result = call_tool(params.get("name", ""), params.get("arguments") or {})
            else:
                self.send_json(200, {"jsonrpc":"2.0","id":request_id,"error":{"code":-32601,"message":"Method not found"}}); return
            self.send_json(200, {"jsonrpc":"2.0","id":request_id,"result":result})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error":"invalid request","detail":str(exc)})

def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"L.A.I.K.A. local tools listening at http://{HOST}:{PORT}/mcp", flush=True)
    print("Loopback only. No shell execution, writes, deletes, or remote file access.", flush=True)
    try: server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == "__main__":
    main()
