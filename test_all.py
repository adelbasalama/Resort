"""Run the four assignment suites in separate Python processes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    failed = False
    environment = os.environ.copy()
    for setting in ("OPENAI_API_KEY", "ADMIN_API_TOKEN", "DASHBOARD_CSV_PATH"):
        environment.pop(setting, None)

    for folder in ("web interface", "WasteRecognition", "ai-coach", "subsystem4_dashboard"):
        print(f"\nTesting {folder}", flush=True)
        with tempfile.TemporaryDirectory() as temp:
            environment["RULES_DATABASE_PATH"] = str(Path(temp) / "rules.sqlite3")
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 "--basetemp", str(Path(temp) / "pytest")],
                cwd=ROOT / folder,
                env=environment,
            )
            failed = failed or result.returncode != 0
    raise SystemExit(int(failed))
