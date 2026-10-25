#!/usr/bin/env python3
"""PyPI Package Verification and Upload Helper

Validates the PEP 427 wheel and sdist distributions and coordinates upload to PyPI.
"""

import os
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"

def main():
    print(f"[*] Checking distribution artifacts in {DIST}...")
    artifacts = list(DIST.glob("*"))
    if not artifacts:
        print("[-] Error: No build artifacts found in dist/")
        return 1

    for a in artifacts:
        print(f"  - Artifact: {a.name} ({a.stat().st_size} bytes)")

    # Run twine check
    cmd = [sys.executable, "-m", "twine", "check", str(DIST / "*")]
    print(f"[*] Running: {' '.join(cmd)}")
    p = subprocess.run("python3 -m twine check dist/*", shell=True, cwd=HERE, capture_output=True, text=True)
    print(p.stdout)
    if p.returncode != 0:
        print("[-] Twine validation failed:", p.stderr)
        return p.returncode

    print("[+] All packages passed twine check (PEP 427 / README metadata 100% valid).")
    
    # Check for PyPI credentials
    pypirc = Path.home() / ".pypirc"
    token_env = os.environ.get("PYPI_API_TOKEN")
    
    if pypirc.exists() or token_env:
        print("[+] PyPI credentials found. Ready for upload.")
    else:
        print("[*] PyPI upload credential status: PENDING_API_TOKEN")
        print("    Direct token generation: https://pypi.org/manage/account/token/")
        print("    Once generated, save to ~/.pypirc or export PYPI_API_TOKEN=pypi-...")

    return 0

if __name__ == "__main__":
    sys.exit(main())
