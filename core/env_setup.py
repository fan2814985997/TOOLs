import sys
import subprocess
from typing import List, Tuple

# ===== Only what the extractor really needs =====
REQUIRED_PIP = [
    "PySide6",
    "pymupdf",
    "pandas",
    "openpyxl",
    "python-docx",
]


def run_cmd(args: List[str]) -> Tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True)
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        return p.returncode, out.strip()
    except Exception as e:
        return 1, str(e)


def ensure_pip_packages(pkgs: List[str] = None) -> List[str]:
    """
    Check and auto-install required Python packages.
    Returns list of still-missing packages (empty if OK).
    """
    pkgs = pkgs or REQUIRED_PIP
    missing = []

    for pkg in pkgs:
        code, _ = run_cmd([sys.executable, "-m", "pip", "show", pkg])
        if code != 0:
            missing.append(pkg)

    if not missing:
        return []

    # auto install missing
    code, out = run_cmd([sys.executable, "-m", "pip", "install", *missing])
    if code != 0:
        return missing

    return []