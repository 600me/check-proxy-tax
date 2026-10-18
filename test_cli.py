"""Offline test suite for check-proxy-tax.

Every network call goes to a throwaway local HTTP server, so the suite works
without internet access and never depends on a third-party proxy provider.
"""

import json
import subprocess
import sys
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from check_proxy_tax.cli import (
    BENCHMARK_URL,
    FTC_DISCLOSURE,
    __version__,
    compute_metrics,
    percentile,
)

ROOT = Path(__file__).resolve().parent
OK_BODY = b"<html><body><h1>IN_STOCK</h1><p>sku 42</p></body></html>"
MISSING_BODY = b"<html><body><h1>OUT_OF_STOCK</h1></body></html>"
FORBIDDEN_BODY = b"<html><body>request blocked by edge policy</body></html>"


class ProbeHandler(BaseHTTPRequestHandler):
    """Small deterministic server with success, block, and slow routes."""

    protocol_version = "HTTP/1.1"
    flaky_lock = threading.Lock()
    flaky_counter = 0

    def _send(self, status, body):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Test-Server", "check-proxy-tax")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The client already hit its timeout; the late reply is discarded.
            pass

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]
        if path == "/ok":
            self._send(200, OK_BODY)
        elif path == "/missing":
            self._send(200, MISSING_BODY)
        elif path == "/forbidden":
            self._send(403, FORBIDDEN_BODY)
        elif path == "/slow":
            time.sleep(2.0)
            self._send(200, OK_BODY)
        elif path == "/flaky":
            with self.flaky_lock:
                index = ProbeHandler.flaky_counter
                ProbeHandler.flaky_counter += 1
            if index % 2 == 0:
                self._send(200, OK_BODY)
            else:
                self._send(403, FORBIDDEN_BODY)
        else:
            self._send(404, b"not found")

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        return


@contextmanager
def live_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProbeHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{0}".format(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class CliTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ProbeHandler.flaky_counter = 0
        cls._server_context = live_server()
        cls.base_url = cls._server_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._server_context.__exit__(None, None, None)

    def run_cli(self, *args, timeout=40):
        return subprocess.run(
            [sys.executable, "-m", "check_proxy_tax.cli"] + list(args),
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )

    def run_json(self, *args):
        result = self.run_cli(*args, "--json")
        self.assertTrue(
            result.stdout.startswith("{"),
            msg="expected pure JSON, got: {0!r}".format(result.stdout[:200]),
        )
        return result, json.loads(result.stdout)

    def test_all_usable_with_marker(self):
        result, report = self.run_json(
            "--url",
            self.base_url + "/ok",
            "--requests",
            "6",
            "--concurrency",
            "3",
            "--marker",
            "IN_STOCK",
            "--price-per-1k",
            "0.49",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["usable_count"], 6)
        self.assertEqual(report["blocked_count"], 0)
        self.assertEqual(report["usable_pct"], 100.0)
        self.assertEqual(report["cost_status"], "finite")
        self.assertAlmostEqual(report["effective_cost_per_1k"], 0.49)
        self.assertAlmostEqual(report["tax_multiplier"], 1.0)
        self.assertEqual(report["total_bytes"], len(OK_BODY) * 6)
        self.assertEqual(report["status_counts"], {"200": 6})
        self.assertEqual(report["blocked_reasons"], {})
        self.assertEqual(report["exit_code"], 0)
        self.assertGreaterEqual(report["latency_ms"]["p50"], 0.0)
        self.assertGreaterEqual(report["latency_ms"]["p95"], 0.0)

    def test_403_marks_every_request_blocked(self):
        result, report = self.run_json(
            "--url", self.base_url + "/forbidden", "--requests", "4"
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["usable_count"], 0)
        self.assertEqual(report["blocked_count"], 4)
        self.assertEqual(report["usable_pct"], 0.0)
        self.assertIsNone(report["effective_cost_per_1k"])
        self.assertIsNone(report["tax_multiplier"])
        self.assertEqual(report["cost_status"], "infinite")
        self.assertEqual(report["status_counts"], {"403": 4})
        self.assertEqual(report["blocked_reasons"], {"http_403": 4})
        self.assertEqual(report["exit_code"], 2)

    def test_marker_missing_is_blocked_even_on_200(self):
        result, report = self.run_json(
            "--url",
            self.base_url + "/missing",
            "--requests",
            "4",
            "--marker",
            "IN_STOCK",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["usable_count"], 0)
        self.assertEqual(report["status_counts"], {"200": 4})
        self.assertEqual(report["blocked_reasons"], {"marker_missing": 4})

    def test_timeout_is_blocked(self):
        result, report = self.run_json(
            "--url",
            self.base_url + "/slow",
            "--requests",
            "2",
            "--concurrency",
            "2",
            "--timeout",
            "0.2",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["usable_count"], 0)
        self.assertEqual(report["blocked_reasons"], {"timeout": 2})
        self.assertEqual(report["total_bytes"], 0)

    def test_partial_block_doubles_effective_cost(self):
        result, report = self.run_json(
            "--url",
            self.base_url + "/flaky",
            "--requests",
            "10",
            "--concurrency",
            "4",
            "--marker",
            "IN_STOCK",
            "--price-per-1k",
            "0.49",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["usable_count"], 5)
        self.assertEqual(report["blocked_count"], 5)
        self.assertEqual(report["usable_pct"], 50.0)
        self.assertAlmostEqual(report["effective_cost_per_1k"], 0.98)
        self.assertAlmostEqual(report["tax_multiplier"], 2.0)
        self.assertEqual(report["cost_status"], "finite")

    def test_json_shape_and_types(self):
        result, report = self.run_json(
            "--url", self.base_url + "/ok", "--requests", "3"
        )
        self.assertEqual(result.returncode, 0)
        required = {
            "tool",
            "version",
            "url",
            "marker",
            "requests",
            "concurrency",
            "timeout_seconds",
            "proxy_configured",
            "nominal_price_per_1k",
            "usable_count",
            "blocked_count",
            "usable_pct",
            "effective_cost_per_1k",
            "tax_multiplier",
            "cost_status",
            "latency_ms",
            "total_bytes",
            "status_counts",
            "blocked_reasons",
            "exit_code",
            "benchmark_url",
            "ftc_disclosure",
        }
        self.assertTrue(required.issubset(report))
        self.assertEqual(report["tool"], "check-proxy-tax")
        self.assertEqual(report["version"], __version__)
        self.assertIsInstance(report["latency_ms"], dict)
        self.assertEqual(set(report["latency_ms"]), {"p50", "p95", "min", "max"})
        self.assertEqual(report["benchmark_url"], BENCHMARK_URL)
        self.assertEqual(report["ftc_disclosure"], FTC_DISCLOSURE)
        self.assertIsInstance(report["proxy_configured"], bool)

    def test_ascii_table_output_and_footer(self):
        result = self.run_cli(
            "--url", self.base_url + "/ok", "--requests", "3"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout
        self.assertIn("check-proxy-tax {0}".format(__version__), output)
        self.assertIn("+", output)
        self.assertIn("| METRIC", output)
        self.assertIn("Usable rate", output)
        self.assertIn("100.0%", output)
        self.assertIn("Benchmark & provider matrix: " + BENCHMARK_URL, output)
        self.assertIn(FTC_DISCLOSURE, output)
        self.assertTrue(output.isascii(), "table must stay ASCII")

    def test_help_exits_zero_and_discloses_affiliate_links(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: check-proxy-tax", result.stdout)
        for option in (
            "--url",
            "--requests",
            "--marker",
            "--price-per-1k",
            "--proxy",
            "--concurrency",
            "--timeout",
            "--json",
        ):
            self.assertIn(option, result.stdout)
        self.assertIn(FTC_DISCLOSURE, result.stdout)
        self.assertIn(BENCHMARK_URL, result.stdout)
        self.assertIn("0  every sampled request was usable", result.stdout)

    def test_version_exits_zero(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("check-proxy-tax {0}".format(__version__), result.stdout)

    def test_invalid_arguments_exit_three(self):
        cases = (
            ("--url", self.base_url + "/ok", "--requests", "0"),
            ("--url", self.base_url + "/ok", "--concurrency", "0"),
            ("--url", self.base_url + "/ok", "--timeout", "0"),
            ("--url", "ftp://example.com/file"),
            (),
        )
        for case in cases:
            with self.subTest(args=case):
                result = self.run_cli(*case)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("error:", result.stderr)


class FormulaTestCase(unittest.TestCase):
    def test_effective_cost_formula(self):
        metrics = compute_metrics(14, 20, 0.49)
        self.assertEqual(metrics.total, 20)
        self.assertEqual(metrics.usable, 14)
        self.assertAlmostEqual(metrics.usable_pct, 70.0)
        self.assertAlmostEqual(metrics.effective_cost_per_1k, 0.70)
        self.assertAlmostEqual(metrics.tax_multiplier, 1.4285714285714286)
        self.assertEqual(metrics.cost_status, "finite")

    def test_zero_usable_is_infinite(self):
        metrics = compute_metrics(0, 20, 0.49)
        self.assertIsNone(metrics.effective_cost_per_1k)
        self.assertIsNone(metrics.tax_multiplier)
        self.assertEqual(metrics.cost_status, "infinite")

    def test_invalid_inputs_rejected(self):
        for usable, total, price in ((0, 0, 0.49), (3, 2, 0.49), (0, 2, 0)):
            with self.subTest(usable=usable, total=total, price=price):
                with self.assertRaises(ValueError):
                    compute_metrics(usable, total, price)

    def test_percentile_interpolation(self):
        self.assertEqual(percentile([], 50), None)
        self.assertEqual(percentile([10.0], 95), 10.0)
        self.assertAlmostEqual(percentile([10.0, 20.0], 50), 15.0)
        self.assertAlmostEqual(percentile([10.0, 20.0], 95), 19.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
