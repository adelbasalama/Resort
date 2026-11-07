"""Start all four local subsystems: .venv/Scripts/python.exe run.py."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent

# Select the installed project environment before importing any dependencies.
# This also makes `python run.py` work from a terminal with a global Python.
PROJECT_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if __name__ == "__main__" and PROJECT_PYTHON.is_file() and Path(sys.executable).absolute() != PROJECT_PYTHON.absolute():
    print("Using the project's .venv Python environment.", flush=True)
    try:
        raise SystemExit(subprocess.call([str(PROJECT_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]]))
    except KeyboardInterrupt:
        raise SystemExit(130)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Project dependencies are missing. Create .venv and install requirements.txt; see README.md.", file=sys.stderr)
    raise SystemExit(1)


def configuration():
    load_dotenv(ROOT / ".env")
    env = os.environ.copy()
    ports = {name: int(env.get(name + "_PORT", default)) for name, default in
             [("RECOGNITION", "5001"), ("GUIDANCE", "5002"), ("DASHBOARD", "5003"), ("WEB", "8501")]}
    if len(set(ports.values())) != 4 or any(not 1 <= p <= 65535 for p in ports.values()):
        raise ValueError("Choose four distinct ports between 1 and 65535 in .env")
    for name, port in ports.items():
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(
                    f"Cannot start {name.lower()}: port {port} on 127.0.0.1 is unavailable. "
                    "If ReSort is already running, open its existing page or stop its launcher with Ctrl+C. "
                    f"Otherwise choose a free {name}_PORT in the root .env."
                ) from exc
    env.update(SERVICE_MODE="http", ALLOW_INSECURE_LOCAL_HTTP="true", HOST="127.0.0.1",
               RECOGNITION_API_URL=f"http://127.0.0.1:{ports['RECOGNITION']}",
               GUIDANCE_API_URL=f"http://127.0.0.1:{ports['GUIDANCE']}",
               DATABASE_PATH=str(ROOT / "data/waste_sorting.sqlite3"),
               RULES_DATABASE_PATH=str(ROOT / "data/rules.sqlite3"),
               RULES_BACKEND=env.get("RULES_BACKEND", "sqlite"),
               RECOGNITION_TIMEOUT_SECONDS=env.get("RECOGNITION_TIMEOUT_SECONDS", "30"),
               GUIDANCE_TIMEOUT_SECONDS=env.get("GUIDANCE_TIMEOUT_SECONDS", "15"),
               PYTHONUNBUFFERED="1")
    return env, ports


def wait_ready(process, url, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Service exited during startup; see logs/. URL: {url}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(.2)
    raise RuntimeError(f"Service did not become ready: {url}; see logs/.")


def main():
    processes, logs = [], []
    try:
        env, ports = configuration()
        (ROOT / "logs").mkdir(exist_ok=True)
        services = [
            ("recognition", "WasteRecognition", ["app.py"], ports["RECOGNITION"], "/health"),
            ("guidance", "ai-coach", ["-m", "app.main"], ports["GUIDANCE"], "/v1/regions"),
            ("dashboard", "subsystem4_dashboard", ["app.py"], ports["DASHBOARD"], "/health"),
            ("web", "web interface", ["-m", "streamlit", "run", "app.py", "--server.address=127.0.0.1",
             f"--server.port={ports['WEB']}", "--server.headless=true", "--browser.gatherUsageStats=false"],
             ports["WEB"], "/_stcore/health"),
        ]
        for name, directory, args, port, health in services:
            log = (ROOT / "logs" / f"{name}.log").open("a", encoding="utf-8")
            logs.append(log)
            process = subprocess.Popen([sys.executable, *args], cwd=ROOT / directory,
                                       env={**env, "PORT": str(port)}, stdout=log, stderr=subprocess.STDOUT)
            processes.append(process)
            wait_ready(process, f"http://127.0.0.1:{port}{health}")
            print(f"{name}: http://127.0.0.1:{port}", flush=True)
        if not env.get("OPENAI_API_KEY"):
            print("OPENAI_API_KEY is unset. Try an illustrated example; real photo recognition requires a key.", flush=True)
        print("All four services are ready. Ctrl+C stops them. Logs: logs/", flush=True)
        while True:
            if any(p.poll() is not None for p in processes):
                raise RuntimeError("A service exited. Check logs/; stopping the other services.")
            time.sleep(.5)
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
