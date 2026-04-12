#!/usr/bin/env python
"""Build docs and report any warnings or errors.

Runs sphinx-build in -W mode (warnings-as-errors) so CI catches doc regressions.
Exit code mirrors sphinx-build: 0 = clean, non-zero = failure.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"
BUILD_DIR = DOCS_DIR / "_build" / "html"


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "sphinx",
        "-W",
        "--keep-going",
        "-b",
        "html",
        str(DOCS_DIR),
        str(BUILD_DIR),
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print(f"\nDocs built successfully → {BUILD_DIR}/index.html")
    else:
        print(f"\nDocs build FAILED (exit {result.returncode})", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
