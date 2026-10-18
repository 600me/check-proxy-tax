#!/usr/bin/env python3
"""Objective acceptance checks for the check-proxy-tax Step 2 work order.

Run from the repository root:

    python3 verify_step2_cli.py

Exit code 0 means every assertion below passed. The script is intentionally
read-only apart from creating temporary files under the system temp directory;
it never edits the repository or pushes to GitHub.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, List

ROOT = Path(__file__).resolve().parent
REPO_SLUG = "600me/check-proxy-tax"
REPO_URL = "https://github.com/{0}".format(REPO_SLUG)
FTC = "FTC Disclosure: Benchmark links may include affiliate tracking."
BENCHMARK = "https://scrape.mybskm.top/?utm_source=cli&utm_content=check-proxy-tax"

PASSED: List[str] = []
FAILED: List[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(command: List[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def check(name: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - acceptance runner reports all
        FAILED.append(name)
        print("[FAIL] {0}".format(name))
        print("       {0}: {1}".format(type(exc).__name__, exc))
    else:
        PASSED.append(name)
        print("[PASS] {0}".format(name))


def tail(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    return text[-limit:] if len(text) > limit else text


# ---------------------------------------------------------------------------
# Local HTTP fixture for an end-to-end CLI smoke test
# ---------------------------------------------------------------------------

OK_BODY = b"<html><body>STEP2_USABLE_MARKER</body></html>"
BLOCK_BODY = b"<html><body>blocked</body></html>"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    lock = threading.Lock()
    counter = 0

    def _send(self, status: int, body: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/ok":
            self._send(200, OK_BODY)
        elif path == "/blocked":
            self._send(403, BLOCK_BODY)
        elif path == "/mixed":
            with Handler.lock:
                index = Handler.counter
                Handler.counter += 1
            self._send(200 if index % 2 == 0 else 403, OK_BODY if index % 2 == 0 else BLOCK_BODY)
        else:
            self._send(404, b"not found")

    def log_message(self, format, *args):  # noqa: A002
        return


@contextmanager
def fixture_server():
    Handler.counter = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{0}".format(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

REQUIRED_FILES = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "test_cli.py",
    "verify_step2_cli.py",
    "check_proxy_tax/__init__.py",
    "check_proxy_tax/cli.py",
    "awesome-pr-proposals/01-awesome-web-scraping.md",
    "awesome-pr-proposals/02-awesome-python-testing.md",
)


def check_required_files() -> None:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    require(not missing, "missing files: {0}".format(", ".join(missing)))
    for name in REQUIRED_FILES:
        require((ROOT / name).stat().st_size > 0, "empty file: {0}".format(name))


def check_pyproject() -> None:
    raw = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    data = tomllib.loads(raw)
    project = data["project"]
    require(project["name"] == "check-proxy-tax", "unexpected project name")
    require(project["version"] == "0.1.0", "unexpected version")
    require(project["requires-python"].startswith(">=3.8"), "requires-python must be >=3.8")
    require(project["dependencies"] == [], "runtime dependencies must be empty")
    require(
        project["scripts"]["check-proxy-tax"] == "check_proxy_tax.cli:main",
        "console entry point mismatch",
    )
    require("MIT" in raw, "MIT license metadata missing")


def check_license() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    require("MIT License" in text, "LICENSE is not MIT")
    require("Kais / 600me" in text, "LICENSE author missing")
    require("WITHOUT WARRANTY" in text, "MIT warranty clause missing")


def check_readme() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = (
        "The 403 Tax",
        FTC,
        BENCHMARK,
        "pip install .",
        "--requests",
        "--marker",
        "--price-per-1k",
        "--proxy",
        "--concurrency",
        "--timeout",
        "--json",
        "effective_cost_per_1k",
        "Exit codes",
    )
    for needle in required:
        require(needle in text, "README missing: {0}".format(needle))
    require(
        re.search(r"usable_pct\s*=\s*usable_count / total_requests", text) is not None,
        "README formula missing",
    )


def check_help() -> None:
    result = run([sys.executable, "-m", "check_proxy_tax.cli", "--help"])
    require(result.returncode == 0, "help exited {0}: {1}".format(result.returncode, tail(result.stderr)))
    for needle in (
        "--url",
        "--requests",
        "--marker",
        "--price-per-1k",
        "--proxy",
        "--concurrency",
        "--timeout",
        "--json",
        FTC,
        BENCHMARK,
    ):
        require(needle in result.stdout, "help missing: {0}".format(needle))


def check_unit_tests() -> None:
    result = run([sys.executable, "-m", "unittest", "test_cli.py"], timeout=240)
    require(
        result.returncode == 0,
        "unittest exited {0}\nstdout:\n{1}\nstderr:\n{2}".format(
            result.returncode, tail(result.stdout), tail(result.stderr)
        ),
    )
    require(
        re.search(r"Ran \d+ tests?", result.stderr) is not None,
        "unittest did not report a test count",
    )
    require("\nOK" in result.stderr or result.stderr.strip().endswith("OK"), "unittest did not end with OK")


def check_cli_json_and_table() -> None:
    with fixture_server() as base:
        ok = run(
            [
                sys.executable,
                "-m",
                "check_proxy_tax.cli",
                "--url",
                base + "/ok",
                "--requests",
                "5",
                "--concurrency",
                "2",
                "--marker",
                "STEP2_USABLE_MARKER",
                "--price-per-1k",
                "0.49",
                "--json",
            ]
        )
        require(ok.returncode == 0, "all-usable run exited {0}: {1}".format(ok.returncode, tail(ok.stderr)))
        report = json.loads(ok.stdout)
        require(report["usable_count"] == 5, "usable_count != 5")
        require(report["usable_pct"] == 100.0, "usable_pct != 100")
        require(report["cost_status"] == "finite", "cost_status != finite")
        require(abs(report["effective_cost_per_1k"] - 0.49) < 1e-9, "effective cost != nominal")
        require(abs(report["tax_multiplier"] - 1.0) < 1e-9, "tax multiplier != 1")
        require(report["total_bytes"] == len(OK_BODY) * 5, "total_bytes mismatch")
        require(report["benchmark_url"] == BENCHMARK, "benchmark URL mismatch")
        require(report["ftc_disclosure"] == FTC, "FTC disclosure mismatch")

        blocked = run(
            [
                sys.executable,
                "-m",
                "check_proxy_tax.cli",
                "--url",
                base + "/blocked",
                "--requests",
                "3",
                "--json",
            ]
        )
        require(blocked.returncode == 2, "all-blocked run exited {0}, expected 2".format(blocked.returncode))
        blocked_report = json.loads(blocked.stdout)
        require(blocked_report["usable_count"] == 0, "all-blocked usable_count != 0")
        require(blocked_report["cost_status"] == "infinite", "all-blocked cost_status != infinite")
        require(blocked_report["effective_cost_per_1k"] is None, "all-blocked cost must be null")

        mixed = run(
            [
                sys.executable,
                "-m",
                "check_proxy_tax.cli",
                "--url",
                base + "/mixed",
                "--requests",
                "10",
                "--concurrency",
                "3",
                "--marker",
                "STEP2_USABLE_MARKER",
                "--json",
            ]
        )
        require(mixed.returncode == 1, "mixed run exited {0}, expected 1".format(mixed.returncode))
        mixed_report = json.loads(mixed.stdout)
        require(mixed_report["usable_count"] == 5, "mixed usable_count != 5")
        require(abs(mixed_report["usable_pct"] - 50.0) < 1e-9, "mixed usable_pct != 50")
        require(abs(mixed_report["effective_cost_per_1k"] - 0.98) < 1e-9, "mixed effective cost != 0.98")
        require(abs(mixed_report["tax_multiplier"] - 2.0) < 1e-9, "mixed multiplier != 2")

        table = run(
            [
                sys.executable,
                "-m",
                "check_proxy_tax.cli",
                "--url",
                base + "/ok",
                "--requests",
                "2",
                "--marker",
                "STEP2_USABLE_MARKER",
            ]
        )
        require(table.returncode == 0, "table run exited {0}".format(table.returncode))
        for needle in ("METRIC", "VALUE", "Usable rate", "Tax multiplier", BENCHMARK, FTC):
            require(needle in table.stdout, "table output missing: {0}".format(needle))
        require("Benchmark & provider matrix: " + BENCHMARK in table.stdout, "benchmark footer mismatch")
        require(table.stdout.isascii(), "table output contains non-ASCII characters")


def check_github_http_200() -> None:
    result = subprocess.run(
        'curl -s -I "https://github.com/{0}" | grep -q "200"'.format(REPO_SLUG),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    require(
        result.returncode == 0,
        "curl|grep 200 failed (exit {0}): {1}".format(result.returncode, tail(result.stderr)),
    )

    headers = run(["curl", "-s", "-I", "-L", REPO_URL], timeout=60)
    require(headers.returncode == 0, "curl HEAD failed")
    status_lines = re.findall(r"^HTTP/\S+\s+(\d{3})", headers.stdout, re.MULTILINE)
    require("200" in status_lines, "no HTTP 200 status line: {0}".format(status_lines))


def check_github_api_public() -> None:
    request = urllib.request.Request(
        "https://api.github.com/repos/{0}".format(REPO_SLUG),
        headers={"User-Agent": "check-proxy-tax-verify/0.1.0", "Accept": "application/vnd.github+json"},
    )
    data = None
    last_error = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(4)
    if data is None:
        raise AssertionError("GitHub API unavailable: {0}".format(last_error))
    require(data["private"] is False, "repository is not public")
    require(data["name"] == "check-proxy-tax", "repository name mismatch")
    require(data["full_name"] == REPO_SLUG, "repository owner/name mismatch")
    license_info = data.get("license") or {}
    require(license_info.get("spdx_id") == "MIT", "GitHub license is not MIT")
    expected_description = (
        "CLI tool to audit real proxy costs, 403 blowout multipliers, and "
        "effective price per 1,000 usable requests."
    )
    require(data.get("description") == expected_description, "repository description mismatch")


def check_git_state() -> None:
    status = run(["git", "status", "--porcelain"])
    require(status.returncode == 0, "git status failed: {0}".format(tail(status.stderr)))
    require(status.stdout.strip() == "", "working tree is not clean:\n{0}".format(status.stdout))

    branch = run(["git", "symbolic-ref", "--short", "HEAD"])
    require(branch.returncode == 0, "not on a branch")
    require(branch.stdout.strip() == "main", "branch is not main: {0}".format(branch.stdout.strip()))

    remote = run(["git", "remote", "get-url", "origin"])
    require(remote.returncode == 0, "origin remote missing")
    require(
        remote.stdout.strip() == "https://github.com/{0}.git".format(REPO_SLUG),
        "origin URL mismatch: {0}".format(remote.stdout.strip()),
    )

    fetch = run(["git", "fetch", "origin", "--quiet"], timeout=120)
    require(fetch.returncode == 0, "git fetch failed: {0}".format(tail(fetch.stderr)))

    head = run(["git", "rev-parse", "HEAD"])
    origin = run(["git", "rev-parse", "origin/main"])
    require(head.returncode == 0 and origin.returncode == 0, "cannot resolve HEAD/origin/main")
    require(
        head.stdout.strip() == origin.stdout.strip(),
        "HEAD {0} != origin/main {1}".format(head.stdout.strip(), origin.stdout.strip()),
    )


def check_awesome_proposals() -> None:
    first = (ROOT / "awesome-pr-proposals/01-awesome-web-scraping.md").read_text(
        encoding="utf-8"
    )
    second = (ROOT / "awesome-pr-proposals/02-awesome-python-testing.md").read_text(
        encoding="utf-8"
    )
    for needle in (
        "lorien/awesome-web-scraping",
        "cli.md",
        "## Network",
        "Add check-proxy-tax to Network CLI tools",
        "https://github.com/600me/check-proxy-tax",
        FTC,
    ):
        require(needle in first, "proposal 01 missing: {0}".format(needle))
    for needle in (
        "cleder/awesome-python-testing",
        "## Tools",
        "Add check-proxy-tax to Tools",
        "https://github.com/600me/check-proxy-tax",
        FTC,
    ):
        require(needle in second, "proposal 02 missing: {0}".format(needle))
    require("ready-to-paste pr body" in first.lower(), "proposal 01 has no PR body")
    require("ready-to-paste pr body" in second.lower(), "proposal 02 has no PR body")


def check_no_external_imports() -> None:
    source = (ROOT / "check_proxy_tax/cli.py").read_text(encoding="utf-8")
    imports = re.findall(r"^\s*(?:import|from)\s+([a-zA-Z0-9_.]+)", source, re.MULTILINE)
    stdlib = {
        "__future__",
        "argparse",
        "collections",
        "concurrent",
        "dataclasses",
        "json",
        "math",
        "socket",
        "statistics",
        "sys",
        "time",
        "typing",
        "urllib",
    }
    external = sorted({name.split(".")[0] for name in imports} - stdlib)
    require(not external, "non-stdlib imports found: {0}".format(external))


def main() -> int:
    print("check-proxy-tax Step 2 acceptance")
    print("repository: {0}".format(ROOT))
    print()

    check("required deliverables exist", check_required_files)
    check("pyproject packaging metadata", check_pyproject)
    check("MIT license and author", check_license)
    check("README content and FTC disclosure", check_readme)
    check("CLI --help exits 0 with full option set", check_help)
    check("CLI imports only the Python standard library", check_no_external_imports)
    check("offline unittest suite exits 0", check_unit_tests)
    check("end-to-end CLI JSON, cost math, and ASCII table", check_cli_json_and_table)
    check("GitHub repository returns HTTP 200", check_github_http_200)
    check("GitHub repository is public with MIT license", check_github_api_public)
    check("git is clean and synced with origin/main", check_git_state)
    check("awesome PR proposal package", check_awesome_proposals)

    print()
    print(
        "{0} passed, {1} failed, {2} total".format(
            len(PASSED), len(FAILED), len(PASSED) + len(FAILED)
        )
    )
    if FAILED:
        print("FAILED: {0}".format(", ".join(FAILED)))
        return 1
    print("STEP 2 ACCEPTANCE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
