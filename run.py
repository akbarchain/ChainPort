import runpy
import os
import sys
import subprocess

ROOT = os.path.dirname(__file__)
PROJECT_DIR = os.path.join(ROOT, "ChainPort")
TARGET = os.path.join(ROOT, "ChainPort", "run.py")
VENV_PYTHON = os.path.join(PROJECT_DIR, "venv", "Scripts", "python.exe")


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))

if __name__ == "__main__":
    # Always prefer project venv to avoid missing dependencies on global Python.
    if os.path.exists(VENV_PYTHON) and not _same_path(sys.executable, VENV_PYTHON):
        result = subprocess.call([VENV_PYTHON, __file__, *sys.argv[1:]], cwd=ROOT)
        raise SystemExit(result)

    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)
    os.chdir(PROJECT_DIR)
    runpy.run_path(TARGET, run_name="__main__")
