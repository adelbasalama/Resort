"""Run each subsystem in isolation, then the real cross-subsystem integration tests."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    failed = False
    test_root = ROOT / "data/test-runs"
    test_root.mkdir(parents=True, exist_ok=True)
    for folder in ["web interface", "ai-coach", "subsystem4_dashboard", "."]:
        print(f"\nTesting {folder}", flush=True)
        with tempfile.TemporaryDirectory(dir=test_root) as temp:
            result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                     "--basetemp", str(Path(temp) / "pytest")], cwd=ROOT / folder)
            failed = failed or result.returncode != 0
    raise SystemExit(int(failed))
