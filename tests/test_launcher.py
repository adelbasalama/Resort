import importlib.util
from pathlib import Path
import socket
import subprocess
import sys

import pytest


def test_occupied_port_names_service_and_explains_recovery(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("resort_launcher", root / "run.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        monkeypatch.setenv("RECOGNITION_PORT", str(port))
        monkeypatch.setenv("GUIDANCE_PORT", "5002")
        monkeypatch.setenv("DASHBOARD_PORT", "5003")
        monkeypatch.setenv("WEB_PORT", "8501")
        with pytest.raises(RuntimeError) as error:
            launcher.configuration()
    message = str(error.value)
    assert "recognition" in message and str(port) in message
    assert "Ctrl+C" in message and "RECOGNITION_PORT" in message


def test_global_python_selects_project_environment_before_startup(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        monkeypatch.setenv("RECOGNITION_PORT", str(listener.getsockname()[1]))
        monkeypatch.setenv("GUIDANCE_PORT", "5002")
        monkeypatch.setenv("DASHBOARD_PORT", "5003")
        monkeypatch.setenv("WEB_PORT", "8501")
        result = subprocess.run([sys._base_executable, str(root / "run.py")],
                                capture_output=True, text=True, timeout=20)
    assert result.returncode == 1
    assert "Using the project's .venv" in result.stdout
    assert "Cannot start recognition" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
