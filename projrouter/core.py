from __future__ import annotations
import os
import re
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import tomllib  # Python 3.11+

VALID_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(frozen=True)
class GlobalCfg:
    root: Path
    domain: str
    https_port: int
    nginx_routes_file: Path


class RouterError(RuntimeError):
    pass


def _run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise RouterError(
            f"Command failed: {' '.join(cmd)}\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}"
        )
    return p


def _atomic_write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(tmp, mode)
    tmp.replace(path)


def _is_port_listening(host: str, port: int, timeout: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def _systemd_is_active(service: str) -> bool:
    p = subprocess.run(["systemctl", "is-active", service], text=True, capture_output=True)
    return p.returncode == 0 and p.stdout.strip() == "active"


def _curl_ok(url: str, timeout_s: int = 2, insecure: bool = False) -> bool:
    cmd = ["curl", "-fsS", "--max-time", str(timeout_s)]
    if insecure:
        cmd.append("-k")
    cmd.append(url)
    p = subprocess.run(cmd, text=True, capture_output=True)
    return p.returncode == 0


class RouterManager:
    """
    Manager för:
      - registry.toml (source of truth)
      - generering av nginx routes include-fil
      - generering av minimal backend web.py per projekt
      - systemd service per projekt (start/stop)
      - check() som verifierar hela kedjan
    """

    def __init__(self, registry_path: str | Path):
        self.registry_path = Path(registry_path)

    # ---------- registry ----------
    def _load_registry(self) -> Tuple[GlobalCfg, Dict[str, int]]:
        if not self.registry_path.exists():
            raise RouterError(f"Registry saknas: {self.registry_path}")

        data = tomllib.loads(self.registry_path.read_text(encoding="utf-8"))
        g = data.get("global", {})
        projects = data.get("projects", {})

        try:
            cfg = GlobalCfg(
                root=Path(g["root"]),
                domain=str(g["domain"]),
                https_port=int(g["https_port"]),
                nginx_routes_file=Path(g["nginx_routes_file"]),
            )
        except KeyError as e:
            raise RouterError(f"Registry saknar global-fält: {e}")

        proj_map: Dict[str, int] = {}
        for name, port in projects.items():
            proj_map[str(name)] = int(port)

        return cfg, proj_map

    def _save_registry(self, cfg: GlobalCfg, proj_map: Dict[str, int]) -> None:
        # Minimal TOML-serialisering (kontrollerad format)
        lines = []
        lines.append("[global]")
        lines.append(f'root = "{cfg.root}"')
        lines.append(f'domain = "{cfg.domain}"')
        lines.append(f"https_port = {cfg.https_port}")
        lines.append(f'nginx_routes_file = "{cfg.nginx_routes_file}"')
        lines.append("")
        lines.append("[projects]")
        for name in sorted(proj_map.keys()):
            lines.append(f'{name} = {proj_map[name]}')
        lines.append("")

        _atomic_write(self.registry_path, "\n".join(lines), mode=0o644)

    # ---------- generation ----------
    def _project_dir(self, cfg: GlobalCfg, project_name: str) -> Path:
        return cfg.root / project_name

    def _service_name(self, project_name: str) -> str:
        # systemd service: proj-<name>.service (minskar risk att krocka)
        return f"proj-{project_name}.service"

    def _make_web_py(self, project_dir: Path, project_name: str) -> Path:
        """
        Minimal HTTP backend som lyssnar 127.0.0.1:<PORT> och svarar:
          /        -> Hello world: <project>
          /health  -> ok
        """
        code = f"""#!/usr/bin/env python3
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler

PROJECT = {project_name!r}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            body = b"ok\\n"
            self.send_response(200)
        else:
            body = ("Hello world: " + PROJECT + "\\n").encode("utf-8")
            self.send_response(200)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Enkel logg
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    args = ap.parse_args()
    httpd = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Backend {{PROJECT}} listening on http://127.0.0.1:{{args.port}}")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
"""
        web_py = project_dir / "web.py"
        project_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write(web_py, code, mode=0o755)
        return web_py

    def _make_systemd_unit(self, project_name: str, project_dir: Path, port: int) -> Path:
        unit_path = Path("/etc/systemd/system") / self._service_name(project_name)
        unit = f"""[Unit]
Description=Project backend {project_name}
After=network.target

[Service]
Type=simple
WorkingDirectory={project_dir}
ExecStart=/usr/bin/python3 {project_dir}/web.py --port {port}
Restart=always
# Kör som root om du vill slippa permissions-strul under utveckling:
User={os.getenv("USER", "root")}
Group={os.getenv("USER", "root")}

[Install]
WantedBy=multi-user.target
"""
        _atomic_write(unit_path, unit, mode=0o644)
        return unit_path

    def _gen_nginx_routes(self, cfg: GlobalCfg, proj_map: Dict[str, int]) -> str:
        # Nginx routes-fil ägs helt av verktyget
        header = [
            "# AUTOGENERATED FILE - DO NOT EDIT",
            "# Generated from registry.toml",
            "",
        ]
        blocks = []
        for name in sorted(proj_map.keys()):
            port = proj_map[name]
            path = f"/{name}/"
            blocks.append(
f"""location {path} {{
    proxy_pass http://127.0.0.1:{port}/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}}
"""
            )
        return "\n".join(header) + "\n".join(blocks)

    def _write_and_reload_nginx(self, cfg: GlobalCfg, proj_map: Dict[str, int]) -> None:
        routes = self._gen_nginx_routes(cfg, proj_map)
        _atomic_write(cfg.nginx_routes_file, routes, mode=0o644)

        # Validate + reload
        _run(["nginx", "-t"], check=True)
        _run(["systemctl", "reload", "nginx"], check=True)

    # ---------- public API ----------
    def activate(self, project_name: str, http_port: int) -> None:
        if not VALID_NAME.match(project_name):
            raise RouterError(f"Ogiltigt projektnamn: {project_name} (tillåt: a-zA-Z0-9_-)")
        if not (1 <= http_port <= 65535):
            raise RouterError(f"Ogiltig port: {http_port}")

        cfg, proj_map = self._load_registry()

        # Krockar?
        if project_name in proj_map and proj_map[project_name] != http_port:
            # tillåt portbyte, men se till att den nya inte krockar
            pass
        if http_port in proj_map.values() and proj_map.get(project_name) != http_port:
            raise RouterError(f"Port {http_port} används redan av annat projekt i registry")

        # Om port redan lyssnar, flagga (kan vara gammal process)
        if _is_port_listening("127.0.0.1", http_port):
            raise RouterError(f"Port {http_port} är redan i bruk på 127.0.0.1")

        # Skapa projekt
        project_dir = self._project_dir(cfg, project_name)
        web_py = self._make_web_py(project_dir, project_name)

        # Skriv unit + starta tjänst (kräver sudo)
        self._make_systemd_unit(project_name, project_dir, http_port)
        _run(["systemctl", "daemon-reload"])
        _run(["systemctl", "enable", "--now", self._service_name(project_name)])

        # Uppdatera registry
        proj_map[project_name] = http_port
        self._save_registry(cfg, proj_map)

        # Uppdatera nginx routes + reload
        self._write_and_reload_nginx(cfg, proj_map)

        # Snabb sanity: backend + extern route
        if not _curl_ok(f"http://127.0.0.1:{http_port}/health", timeout_s=2):
            raise RouterError(f"Backend health fail: http://127.0.0.1:{http_port}/health")
        if not _curl_ok(f"https://{cfg.domain}:{cfg.https_port}/{project_name}/health", timeout_s=4, insecure=True):
            raise RouterError(f"Extern health fail: https://{cfg.domain}:{cfg.https_port}/{project_name}/health")

    def deactivate(self, project_name: str) -> None:
        cfg, proj_map = self._load_registry()
        if project_name not in proj_map:
            raise RouterError(f"Projekt saknas i registry: {project_name}")

        # Stoppa tjänst (men rör inte filer i root)
        svc = self._service_name(project_name)
        _run(["systemctl", "disable", "--now", svc], check=False)

        # Ta bort från registry
        del proj_map[project_name]
        self._save_registry(cfg, proj_map)

        # Uppdatera nginx routes + reload
        self._write_and_reload_nginx(cfg, proj_map)

    def check(self) -> None:
        cfg, proj_map = self._load_registry()
        errors: List[str] = []

        # nginx config test
        p = subprocess.run(["nginx", "-t"], text=True, capture_output=True)
        if p.returncode != 0:
            errors.append(f"nginx -t failed:\n{p.stdout}\n{p.stderr}")

        # nginx service
        if not _systemd_is_active("nginx"):
            errors.append("nginx service is not active")

        # routes file exists
        if not cfg.nginx_routes_file.exists():
            errors.append(f"nginx routes file missing: {cfg.nginx_routes_file}")
        else:
            expected = self._gen_nginx_routes(cfg, proj_map)
            actual = cfg.nginx_routes_file.read_text(encoding="utf-8")
            if actual != expected:
                errors.append("nginx routes file differs from registry (run activate/deactivate or resync)")

        # per project checks
        for name in sorted(proj_map.keys()):
            port = proj_map[name]
            svc = self._service_name(name)

            if not _systemd_is_active(svc):
                errors.append(f"{name}: systemd not active ({svc})")

            if not _is_port_listening("127.0.0.1", port):
                errors.append(f"{name}: port not listening on 127.0.0.1:{port}")
                continue

            if not _curl_ok(f"http://127.0.0.1:{port}/health", timeout_s=2):
                errors.append(f"{name}: backend health failed http://127.0.0.1:{port}/health")

            # extern check via nginx (insecure ok pga certkedja/dev)
            if not _curl_ok(f"https://{cfg.domain}:{cfg.https_port}/{name}/health", timeout_s=4, insecure=True):
                errors.append(f"{name}: external health failed https://{cfg.domain}:{cfg.https_port}/{name}/health")

        if errors:
            raise RouterError("CHECK FAILED:\n- " + "\n- ".join(errors))

