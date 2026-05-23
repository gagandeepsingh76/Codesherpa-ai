from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "frontend"
VENV_ROOT = ROOT / ".venv"
BACKEND_MARKER = VENV_ROOT / ".codesherpa-backend-deps.json"
FRONTEND_MARKER = FRONTEND_ROOT / "node_modules" / ".codesherpa-frontend-deps.json"

DEFAULT_BACKEND_PORTS = [8000, 8001, 8010, 8020, 8080]
DEFAULT_FRONTEND_PORTS = [3000, 3001, 3010, 3020]
HOST = "127.0.0.1"


@dataclass(frozen=True)
class DependencyWorkflow:
    name: str
    manifest: Path
    install_command: list[str]
    backend_command_prefix: list[str]
    marker_paths: list[Path]
    uses_venv: bool = False


@dataclass(frozen=True)
class PortProbe:
    port: int
    available: bool
    reason: str = ""
    details: str = ""


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def is_windows() -> bool:
    return os.name == "nt"


def command_name(name: str) -> str:
    if is_windows():
        return shutil.which(f"{name}.cmd") or shutil.which(name) or name
    return shutil.which(name) or name


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    printable = format_command(command, cwd=cwd)
    print(f"[setup] {printable}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def format_command(command: list[str], *, cwd: Path = ROOT) -> str:
    display: list[str] = []
    for item in command:
        path = Path(item)
        if path.is_absolute():
            try:
                item = str(path.relative_to(cwd))
            except ValueError:
                item = str(path)
        if " " in item and not (item.startswith('"') and item.endswith('"')):
            item = f'"{item}"'
        display.append(item)
    return " ".join(display)


def file_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def marker_matches(marker: Path, payload: dict[str, str]) -> bool:
    if not marker.exists():
        return False
    try:
        existing = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return all(existing.get(key) == value for key, value in payload.items())


def write_marker(marker: Path, payload: dict[str, str]) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def venv_python() -> Path:
    if is_windows():
        return VENV_ROOT / "Scripts" / "python.exe"
    return VENV_ROOT / "bin" / "python"


def create_venv_if_needed() -> None:
    python_path = venv_python()
    if python_path.exists():
        return
    print(f"[setup] Creating Python virtual environment at {rel(VENV_ROOT)}", flush=True)
    run([sys.executable, "-m", "venv", str(VENV_ROOT)])
    run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])


def load_pyproject(path: Path) -> dict:
    if not path.exists() or tomllib is None:
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def detect_python_workflow() -> DependencyWorkflow:
    pyproject = ROOT / "pyproject.toml"
    poetry_lock = ROOT / "poetry.lock"
    uv_lock = ROOT / "uv.lock"
    requirements = ROOT / "requirements.txt"
    backend_requirements = ROOT / "backend" / "requirements.txt"
    requirements_in = ROOT / "requirements.in"
    pipfile = ROOT / "Pipfile"

    pyproject_data = load_pyproject(pyproject)
    has_poetry = bool(pyproject_data.get("tool", {}).get("poetry")) or poetry_lock.exists()
    has_uv = uv_lock.exists() or bool(pyproject_data.get("tool", {}).get("uv"))

    if has_uv and shutil.which("uv"):
        return DependencyWorkflow(
            name="uv",
            manifest=uv_lock if uv_lock.exists() else pyproject,
            install_command=[command_name("uv"), "sync"],
            backend_command_prefix=[command_name("uv"), "run", "python"],
            marker_paths=[uv_lock if uv_lock.exists() else pyproject],
        )

    if has_poetry and shutil.which("poetry"):
        return DependencyWorkflow(
            name="poetry",
            manifest=poetry_lock if poetry_lock.exists() else pyproject,
            install_command=[command_name("poetry"), "install"],
            backend_command_prefix=[command_name("poetry"), "run", "python"],
            marker_paths=[poetry_lock if poetry_lock.exists() else pyproject],
        )

    if requirements.exists():
        python_path = venv_python()
        return DependencyWorkflow(
            name="pip + requirements.txt",
            manifest=requirements,
            install_command=[str(python_path), "-m", "pip", "install", "-r", str(requirements)],
            backend_command_prefix=[str(python_path)],
            marker_paths=[requirements],
            uses_venv=True,
        )

    if backend_requirements.exists():
        python_path = venv_python()
        return DependencyWorkflow(
            name="pip + backend/requirements.txt",
            manifest=backend_requirements,
            install_command=[str(python_path), "-m", "pip", "install", "-r", str(backend_requirements)],
            backend_command_prefix=[str(python_path)],
            marker_paths=[backend_requirements],
            uses_venv=True,
        )

    if requirements_in.exists():
        python_path = venv_python()
        return DependencyWorkflow(
            name="pip-tools",
            manifest=requirements_in,
            install_command=[
                str(python_path),
                "-m",
                "pip",
                "install",
                "pip-tools",
                "-r",
                str(requirements_in),
            ],
            backend_command_prefix=[str(python_path)],
            marker_paths=[requirements_in],
            uses_venv=True,
        )

    if pyproject.exists():
        python_path = venv_python()
        return DependencyWorkflow(
            name="pip + pyproject.toml",
            manifest=pyproject,
            install_command=[str(python_path), "-m", "pip", "install", "-e", str(ROOT)],
            backend_command_prefix=[str(python_path)],
            marker_paths=[pyproject],
            uses_venv=True,
        )

    if pipfile.exists() and shutil.which("pipenv"):
        return DependencyWorkflow(
            name="pipenv",
            manifest=pipfile,
            install_command=[command_name("pipenv"), "install", "--dev"],
            backend_command_prefix=[command_name("pipenv"), "run", "python"],
            marker_paths=[pipfile],
        )

    raise SystemExit(
        "Could not detect Python dependencies. Add requirements.txt, pyproject.toml, "
        "poetry.lock, uv.lock, requirements.in, or Pipfile at the repository root."
    )


def ensure_backend_dependencies(workflow: DependencyWorkflow, *, no_install: bool) -> None:
    print(f"[deps] Python workflow: {workflow.name} ({rel(workflow.manifest)})", flush=True)
    if no_install:
        print("[deps] Backend dependency install skipped by --no-install", flush=True)
        return

    if workflow.uses_venv:
        create_venv_if_needed()

    payload = {
        "workflow": workflow.name,
        "manifest_hash": file_hash(workflow.marker_paths),
        "python": platform.python_version(),
    }
    if marker_matches(BACKEND_MARKER, payload):
        print("[deps] Backend dependencies already match the detected manifest", flush=True)
        return

    run(workflow.install_command)
    write_marker(BACKEND_MARKER, payload)


def detect_frontend_install_command() -> list[str]:
    if not (FRONTEND_ROOT / "package.json").exists():
        raise SystemExit("Missing frontend/package.json; cannot start the frontend.")
    return [command_name("npm"), "--prefix", str(FRONTEND_ROOT), "install"]


def ensure_frontend_dependencies(*, no_install: bool) -> None:
    manifest_paths = [FRONTEND_ROOT / "package.json"]
    lockfile = FRONTEND_ROOT / "package-lock.json"
    if lockfile.exists():
        manifest_paths.append(lockfile)

    print("[deps] Frontend workflow: npm (frontend/package.json)", flush=True)
    if no_install:
        print("[deps] Frontend dependency install skipped by --no-install", flush=True)
        return

    payload = {
        "workflow": "npm",
        "manifest_hash": file_hash(manifest_paths),
        "node_modules": str((FRONTEND_ROOT / "node_modules").exists()),
    }
    if (FRONTEND_ROOT / "node_modules").exists() and marker_matches(FRONTEND_MARKER, payload):
        print("[deps] Frontend dependencies already match package manifests", flush=True)
        return

    run(detect_frontend_install_command())
    payload["node_modules"] = "True"
    write_marker(FRONTEND_MARKER, payload)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def upsert_env_file(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            output.append(raw_line)
            continue
        key = raw_line.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(raw_line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def validate_env_files(api_url: str, frontend_url: str) -> dict[str, str]:
    root_env = ROOT / ".env"
    example = ROOT / ".env.example"
    if not root_env.exists() and example.exists():
        print("[env] .env was missing; creating it from .env.example", flush=True)
        root_env.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    upsert_env_file(root_env, {"NEXT_PUBLIC_API_URL": api_url})
    upsert_env_file(FRONTEND_ROOT / ".env.local", {"NEXT_PUBLIC_API_URL": api_url})

    env_values = parse_env_file(root_env)
    if not env_values.get("OPENAI_API_KEY"):
        print("[env] OPENAI_API_KEY is empty; AI chat will use deterministic local fallbacks", flush=True)
    if not env_values.get("CODESHERPA_MODEL"):
        upsert_env_file(root_env, {"CODESHERPA_MODEL": "gpt-4.1-mini"})
        env_values["CODESHERPA_MODEL"] = "gpt-4.1-mini"

    env_values["NEXT_PUBLIC_API_URL"] = api_url
    env_values["CODESHERPA_FRONTEND_URL"] = frontend_url
    env_values["CODESHERPA_ALLOWED_ORIGINS"] = ",".join(
        [
            frontend_url,
            frontend_url.replace("127.0.0.1", "localhost"),
            frontend_url.replace("localhost", "127.0.0.1"),
        ]
    )
    print(f"[env] Frontend API URL set to {api_url}", flush=True)
    return env_values


def probe_port(port: int, host: str = HOST) -> PortProbe:
    connect_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connect_sock.settimeout(0.5)
    try:
        if connect_sock.connect_ex((host, port)) == 0:
            details = describe_port(port)
            return PortProbe(
                port=port,
                available=False,
                reason="port is already accepting TCP connections",
                details=details,
            )
    finally:
        connect_sock.close()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
        return PortProbe(port=port, available=True)
    except OSError as exc:
        try:
            sock.close()
        except OSError:
            pass
        reason = str(exc)
        if is_windows() and getattr(exc, "winerror", None) == 10013:
            reason = "Windows denied binding this port, often because the port is reserved or protected"
        details = describe_port(port)
        return PortProbe(port=port, available=False, reason=reason, details=details)


def describe_port(port: int) -> str:
    if is_windows():
        return describe_port_windows(port)
    return describe_port_unix(port)


def describe_port_windows(port: int) -> str:
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""

    pids: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        state = parts[3].upper()
        pid = parts[4]
        if state == "LISTENING" and local_address.rsplit(":", 1)[-1] == str(port):
            pids.add(pid)

    if not pids:
        return ""

    process_names: list[str] = []
    for pid in sorted(pids):
        try:
            task = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            rows = list(csv.reader(task.stdout.splitlines()))
            name = rows[0][0] if rows and rows[0] else "unknown"
            process_names.append(f"PID {pid} ({name})")
        except OSError:
            process_names.append(f"PID {pid}")
    return "occupied by " + ", ".join(process_names)


def describe_port_unix(port: int) -> str:
    lsof = shutil.which("lsof")
    if lsof:
        result = subprocess.run(
            [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if len(lines) > 1:
            return "occupied: " + " | ".join(lines[1:3])
    ss = shutil.which("ss")
    if ss:
        result = subprocess.run([ss, "-ltnp"], capture_output=True, text=True, check=False)
        matches = [line.strip() for line in result.stdout.splitlines() if f":{port} " in line]
        if matches:
            return "occupied: " + " | ".join(matches[:2])
    return ""


def choose_port(label: str, requested: int | None, candidates: list[int]) -> tuple[int, list[PortProbe]]:
    ordered: list[int] = []
    if requested:
        ordered.append(requested)
    ordered.extend(candidates)
    ordered.extend(range(max(candidates) + 1, max(candidates) + 100))

    seen: set[int] = set()
    probes: list[PortProbe] = []
    for port in ordered:
        if port in seen:
            continue
        seen.add(port)
        probe = probe_port(port)
        probes.append(probe)
        if probe.available:
            if probes[0].port != port:
                print(f"[ports] {label} falling back to available port {port}", flush=True)
            return port, probes
        detail = f" ({probe.details})" if probe.details else ""
        print(f"[ports] {label} port {port} unavailable: {probe.reason}{detail}", flush=True)

    raise SystemExit(f"No available {label} port found near {ordered[0]}.")


def print_windows_reserved_hint(probes: list[PortProbe]) -> None:
    if not is_windows():
        return
    if not any("denied" in probe.reason.lower() for probe in probes):
        return
    print("[ports] Windows reported a protected port. Check reserved ranges with:", flush=True)
    print("[ports]   netsh interface ipv4 show excludedportrange protocol=tcp", flush=True)


def health_url(port: int) -> str:
    return f"http://{HOST}:{port}/health"


def wait_for_backend(port: int, process: subprocess.Popen[str], timeout: int = 45) -> None:
    url = health_url(port)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Backend process exited early with code {process.returncode}")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    print(f"[backend] Health check passed: {url}", flush=True)
                    return
        except URLError:
            pass
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Backend did not become healthy at {url} within {timeout}s")


def wait_for_frontend(port: int, process: subprocess.Popen[str], timeout: int = 90) -> None:
    url = f"http://{HOST}:{port}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Frontend process exited early with code {process.returncode}")
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    print(f"[frontend] HTTP check passed: {url} ({response.status})", flush=True)
                    return
        except URLError:
            pass
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Frontend did not respond at {url} within {timeout}s")


def stream_process(name: str, process: subprocess.Popen[str]) -> threading.Thread:
    def _stream() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            print(f"[{name}] {line}", end="", flush=True)

    thread = threading.Thread(target=_stream, daemon=True)
    thread.start()
    return thread


def start_process(name: str, command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    print(f"[start] {name}: {format_command(command, cwd=cwd)}", flush=True)
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if is_windows() else 0
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=creationflags,
    )
    stream_process(name, process)
    return process


def stop_process(process: subprocess.Popen[str], *, graceful_console_break: bool = True) -> None:
    if process.poll() is not None:
        return
    if is_windows() and not graceful_console_break:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        return

    try:
        if is_windows() and graceful_console_break:
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
    except Exception:
        process.terminate()

    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        if is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            process.kill()


def build_backend_command(workflow: DependencyWorkflow, port: int) -> list[str]:
    return workflow.backend_command_prefix + [
        "-m",
        "uvicorn",
        "backend.main:app",
        "--reload",
        "--host",
        HOST,
        "--port",
        str(port),
    ]


def build_frontend_command(port: int) -> list[str]:
    return [
        command_name("npm"),
        "--prefix",
        str(FRONTEND_ROOT),
        "run",
        "dev",
        "--",
        "--hostname",
        HOST,
        "--port",
        str(port),
    ]


def print_summary(
    workflow: DependencyWorkflow,
    backend_command: list[str],
    frontend_command: list[str],
    backend_port: int,
    frontend_port: int,
) -> None:
    print("", flush=True)
    print("CodeSherpa dev startup plan", flush=True)
    print(f"  Python deps: {workflow.name} via {rel(workflow.manifest)}", flush=True)
    print(f"  Backend:     http://{HOST}:{backend_port}", flush=True)
    print(f"  Health:      {health_url(backend_port)}", flush=True)
    print(f"  Frontend:    http://{HOST}:{frontend_port}", flush=True)
    print("  Commands:", flush=True)
    print(f"    {format_command(workflow.install_command)}", flush=True)
    print(f"    {format_command(detect_frontend_install_command())}", flush=True)
    print(f"    {format_command(backend_command)}", flush=True)
    print(f"    NEXT_PUBLIC_API_URL=http://{HOST}:{backend_port} {format_command(frontend_command)}", flush=True)
    print("", flush=True)


def build_env(base_values: dict[str, str], backend_port: int, frontend_port: int) -> tuple[dict[str, str], dict[str, str]]:
    backend_env = os.environ.copy()
    frontend_env = os.environ.copy()
    backend_env.update(base_values)
    frontend_env.update(base_values)

    backend_env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "BACKEND_PORT": str(backend_port),
            "PORT": str(backend_port),
        }
    )
    frontend_env.update(
        {
            "NEXT_PUBLIC_API_URL": f"http://{HOST}:{backend_port}",
            "PORT": str(frontend_port),
        }
    )
    return backend_env, frontend_env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the CodeSherpa backend and frontend locally.")
    parser.add_argument("--backend-port", type=int, default=None, help="Preferred backend port before fallback.")
    parser.add_argument("--frontend-port", type=int, default=None, help="Preferred frontend port before fallback.")
    parser.add_argument("--no-install", action="store_true", help="Skip dependency installation checks.")
    parser.add_argument("--check", action="store_true", help="Print diagnostics and commands without starting servers.")
    parser.add_argument("--smoke-test", action="store_true", help="Start both services, verify HTTP responses, then stop.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workflow = detect_python_workflow()

    backend_port, backend_probes = choose_port(
        "backend",
        args.backend_port or int(os.environ.get("BACKEND_PORT", "0") or 0) or None,
        DEFAULT_BACKEND_PORTS,
    )
    frontend_port, frontend_probes = choose_port(
        "frontend",
        args.frontend_port or int(os.environ.get("FRONTEND_PORT", "0") or 0) or None,
        DEFAULT_FRONTEND_PORTS,
    )
    print_windows_reserved_hint(backend_probes + frontend_probes)

    api_url = f"http://{HOST}:{backend_port}"
    frontend_url = f"http://{HOST}:{frontend_port}"
    env_values = validate_env_files(api_url, frontend_url)

    backend_command = build_backend_command(workflow, backend_port)
    frontend_command = build_frontend_command(frontend_port)
    print_summary(workflow, backend_command, frontend_command, backend_port, frontend_port)

    if args.check:
        print("[check] Diagnostics completed. Servers were not started.", flush=True)
        return 0

    ensure_backend_dependencies(workflow, no_install=args.no_install)
    ensure_frontend_dependencies(no_install=args.no_install)

    backend_env, frontend_env = build_env(env_values, backend_port, frontend_port)
    backend = start_process("backend", backend_command, cwd=ROOT, env=backend_env)
    frontend: subprocess.Popen[str] | None = None
    try:
        wait_for_backend(backend_port, backend)
        frontend = start_process("frontend", frontend_command, cwd=ROOT, env=frontend_env)
        if args.smoke_test:
            wait_for_frontend(frontend_port, frontend)
            print("[smoke] CodeSherpa backend and frontend started successfully", flush=True)
            return 0

        print("", flush=True)
        print("CodeSherpa is running locally", flush=True)
        print(f"  Frontend: http://{HOST}:{frontend_port}", flush=True)
        print(f"  Backend:  http://{HOST}:{backend_port}", flush=True)
        print(f"  Health:   {health_url(backend_port)}", flush=True)
        print("Press Ctrl+C to stop both services.", flush=True)

        while True:
            if backend.poll() is not None:
                raise RuntimeError(f"Backend exited with code {backend.returncode}")
            if frontend.poll() is not None:
                raise RuntimeError(f"Frontend exited with code {frontend.returncode}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[stop] Shutting down CodeSherpa dev services", flush=True)
    finally:
        if frontend is not None:
            stop_process(frontend, graceful_console_break=False)
        stop_process(backend)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"[error] Command failed with exit code {exc.returncode}: {format_command(exc.cmd)}", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
