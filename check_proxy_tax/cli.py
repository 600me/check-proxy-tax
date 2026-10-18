"""check-proxy-tax: measure what usable proxy traffic actually costs.

The tool sends a burst of concurrent requests to one URL, classifies every
response as usable (HTTP 200 plus an optional marker) or blocked, and converts
the raw per-1,000 price into the price you really pay per 1,000 *usable*
responses.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

__version__ = "0.1.0"

BENCHMARK_URL = (
    "https://scrape.mybskm.top/?utm_source=cli&utm_content=check-proxy-tax"
)
FTC_DISCLOSURE = (
    "FTC Disclosure: Benchmark links may include affiliate tracking."
)
USER_AGENT = (
    "check-proxy-tax/{0} (+https://github.com/600me/check-proxy-tax)".format(
        __version__
    )
)

EXIT_USABLE = 0
EXIT_DEGRADED = 1
EXIT_FAILED = 2
EXIT_USAGE = 3


@dataclass(frozen=True)
class Sample:
    """One completed probe attempt."""

    usable: bool
    status: Optional[int]
    reason: str
    latency_ms: float
    body_bytes: int


@dataclass(frozen=True)
class Metrics:
    """Aggregated economics for one run."""

    total: int
    usable: int
    usable_pct: float
    effective_cost_per_1k: Optional[float]
    tax_multiplier: Optional[float]
    cost_status: str


def _timeout_reason(exc: BaseException) -> str:
    reason = getattr(exc, "reason", exc)
    text = str(reason).lower()
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in text:
        return "timeout"
    if "timeout" in text:
        return "timeout"
    return "connection_error"


def fetch_once(
    url: str,
    marker: Optional[str],
    timeout: float,
    proxy: Optional[str] = None,
) -> Sample:
    """Fetch *url* once and classify the result.

    Usable means: final HTTP status is exactly 200 and, when a marker was
    supplied, the raw response body contains that marker as UTF-8 bytes.
    """

    handlers: List[urllib.request.BaseHandler] = []
    if proxy:
        handlers.append(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )

    started = time.perf_counter()
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            status = int(response.status)
            if status != 200:
                return Sample(False, status, "http_{0}".format(status), elapsed_ms, len(body))
            if marker is not None and marker.encode("utf-8") not in body:
                return Sample(False, status, "marker_missing", elapsed_ms, len(body))
            return Sample(True, status, "ok", elapsed_ms, len(body))
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        try:
            body_bytes = len(exc.read())
        except Exception:
            body_bytes = 0
        return Sample(
            False,
            int(exc.code),
            "http_{0}".format(exc.code),
            elapsed_ms,
            body_bytes,
        )
    except Exception as exc:  # URLError, timeouts, TLS and socket errors
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return Sample(False, None, _timeout_reason(exc), elapsed_ms, 0)


def compute_metrics(usable: int, total: int, nominal_price: float) -> Metrics:
    """Apply the effective-cost formulas to a finished sample set."""

    if total < 1:
        raise ValueError("total must be >= 1")
    if usable < 0 or usable > total:
        raise ValueError("usable must be between 0 and total")
    if nominal_price <= 0:
        raise ValueError("nominal_price must be > 0")

    usable_pct = (usable / total) * 100.0
    if usable == 0:
        return Metrics(total, usable, usable_pct, None, None, "infinite")

    effective_cost = nominal_price / (usable_pct / 100.0)
    tax_multiplier = effective_cost / nominal_price
    return Metrics(
        total,
        usable,
        usable_pct,
        effective_cost,
        tax_multiplier,
        "finite",
    )


def percentile(values: Sequence[float], pct: float) -> Optional[float]:
    """Linear-interpolated percentile (the common numpy/Excel definition)."""

    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _exit_code(metrics: Metrics) -> int:
    if metrics.usable == metrics.total:
        return EXIT_USABLE
    if metrics.usable == 0:
        return EXIT_FAILED
    return EXIT_DEGRADED


def _money(value: Optional[float]) -> str:
    if value is None:
        return "Infinite"
    return "${0:,.4f}".format(value)


def _multiplier(value: Optional[float]) -> str:
    if value is None:
        return "Infinite"
    return "{0:,.2f}x".format(value)


def _human_bytes(count: int) -> str:
    if count < 1024:
        return "{0} B".format(count)
    value = float(count)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024.0:
            return "{0:.2f} {1} ({2:,} bytes)".format(value, unit, count)
    return "{0:.2f} PB ({1:,} bytes)".format(value, count)


def _table(rows: List[Tuple[str, str]], separators: Sequence[int]) -> str:
    label_width = max([len("METRIC")] + [len(label) for label, _ in rows])
    value_width = max([len("VALUE")] + [len(value) for _, value in rows])
    border = "+{0}+{1}+".format(
        "-" * (label_width + 2), "-" * (value_width + 2)
    )

    def row(label: str, value: str) -> str:
        return "| {0:<{1}} | {2:<{3}} |".format(
            label, label_width, value, value_width
        )

    lines = [border, row("METRIC", "VALUE"), border]
    for index, (label, value) in enumerate(rows):
        lines.append(row(label, value))
        if index in separators:
            lines.append(border)
    lines.append(border)
    return "\n".join(lines)


def render_table(report: Dict[str, object]) -> str:
    """Render the human-readable ASCII diagnostic table."""

    latency = report["latency_ms"]  # type: ignore[index]
    status_counts = report["status_counts"]  # type: ignore[index]
    blocked_reasons = report["blocked_reasons"]  # type: ignore[index]

    def pairs(mapping: Dict[str, int]) -> str:
        if not mapping:
            return "none"
        return ", ".join(
            "{0}:{1}".format(key, value)
            for key, value in sorted(mapping.items())
        )

    nominal = float(report["nominal_price_per_1k"])  # type: ignore[arg-type]
    effective = report["effective_cost_per_1k"]
    multiplier = report["tax_multiplier"]

    rows: List[Tuple[str, str]] = [
        ("Target URL", str(report["url"])),
        (
            "Samples",
            "{0} (concurrency {1}, timeout {2:g}s)".format(
                report["requests"], report["concurrency"], report["timeout_seconds"]
            ),
        ),
        ("Marker", str(report["marker"]) if report["marker"] else "(none)"),
        (
            "Usable success",
            "{0} / {1}".format(report["usable_count"], report["requests"]),
        ),
        (
            "Blocked / failed",
            "{0} / {1}".format(report["blocked_count"], report["requests"]),
        ),
        ("Usable rate", "{0:.1f}%".format(float(report["usable_pct"]))),
        ("Nominal price / 1k", _money(nominal)),
        (
            "Effective cost / 1k",
            _money(float(effective) if effective is not None else None),
        ),
        (
            "Tax multiplier",
            _multiplier(float(multiplier) if multiplier is not None else None),
        ),
        ("Latency p50", "{0:.1f} ms".format(float(latency["p50"]))),  # type: ignore[index]
        ("Latency p95", "{0:.1f} ms".format(float(latency["p95"]))),  # type: ignore[index]
        ("Total transferred", _human_bytes(int(report["total_bytes"]))),
        ("Status codes", pairs(status_counts)),  # type: ignore[arg-type]
        ("Blocked reasons", pairs(blocked_reasons)),  # type: ignore[arg-type]
        ("Verdict", _verdict_from_report(report)),
    ]

    title = "check-proxy-tax {0} - proxy economics audit".format(__version__)
    return "{0}\n\n{1}".format(title, _table(rows, separators=(5, 8)))


def _verdict_from_report(report: Dict[str, object]) -> str:
    usable = int(report["usable_count"])  # type: ignore[arg-type]
    total = int(report["requests"])  # type: ignore[arg-type]
    if usable == total:
        return "PASS - every sampled request was usable"
    if usable == 0:
        return "FAIL - no usable responses"
    return "DEGRADED - {0} of {1} requests blocked".format(total - usable, total)


def build_report(
    args: argparse.Namespace,
    samples: Sequence[Sample],
    metrics: Metrics,
) -> Dict[str, object]:
    """Build the JSON-serialisable report shared by both output modes."""

    latencies = [sample.latency_ms for sample in samples]
    status_counts: Counter = Counter(
        "timeout"
        if sample.reason == "timeout"
        else "error"
        if sample.status is None
        else str(sample.status)
        for sample in samples
    )
    blocked_reasons: Counter = Counter(
        sample.reason for sample in samples if not sample.usable
    )

    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    code = _exit_code(metrics)

    return {
        "tool": "check-proxy-tax",
        "version": __version__,
        "url": args.url,
        "marker": args.marker,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "timeout_seconds": args.timeout,
        "proxy_configured": bool(args.proxy),
        "nominal_price_per_1k": args.price_per_1k,
        "usable_count": metrics.usable,
        "blocked_count": metrics.total - metrics.usable,
        "usable_pct": round(metrics.usable_pct, 4),
        "effective_cost_per_1k": (
            round(metrics.effective_cost_per_1k, 6)
            if metrics.effective_cost_per_1k is not None
            else None
        ),
        "tax_multiplier": (
            round(metrics.tax_multiplier, 6)
            if metrics.tax_multiplier is not None
            else None
        ),
        "cost_status": metrics.cost_status,
        "latency_ms": {
            "p50": round(p50, 2) if p50 is not None else None,
            "p95": round(p95, 2) if p95 is not None else None,
            "min": round(min(latencies), 2),
            "max": round(max(latencies), 2),
        },
        "total_bytes": sum(sample.body_bytes for sample in samples),
        "status_counts": dict(sorted(status_counts.items())),
        "blocked_reasons": dict(sorted(blocked_reasons.items())),
        "exit_code": code,
        "benchmark_url": BENCHMARK_URL,
        "ftc_disclosure": FTC_DISCLOSURE,
    }


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer")
    if number < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return number


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number")
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return number


class _ArgumentParser(argparse.ArgumentParser):
    """Keep argument errors distinct from a run where every probe failed."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, "{0}: error: {1}\n".format(self.prog, message))


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="check-proxy-tax",
        description=(
            "Sample a URL concurrently and report the effective cost per "
            "1,000 usable responses after 403s, 429s, 5xx errors, timeouts, "
            "and marker misses."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  check-proxy-tax --url https://example.com/product --requests 20 \\\n"
            "      --marker \"Add to cart\" --price-per-1k 0.49\n"
            "  check-proxy-tax --url https://example.com --json > report.json\n"
            "\n"
            "exit codes:\n"
            "  0  every sampled request was usable\n"
            "  1  some requests were blocked (degraded)\n"
            "  2  no request was usable\n"
            "  3  invalid arguments\n"
            "\n"
            "Benchmark & provider matrix: {0}\n"
            "\n"
            "{1}".format(BENCHMARK_URL, FTC_DISCLOSURE)
        ),
    )
    parser.add_argument("--url", required=True, help="absolute http(s) URL to probe")
    parser.add_argument(
        "--requests",
        type=_positive_int,
        default=20,
        help="number of concurrent samples (default: 20)",
    )
    parser.add_argument(
        "--marker",
        default=None,
        help="string that must appear in the response body for a usable sample",
    )
    parser.add_argument(
        "--price-per-1k",
        type=_positive_float,
        default=0.49,
        help="nominal price per 1,000 requests in USD (default: 0.49)",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="HTTP(S) proxy URL, e.g. http://user:pass@host:port",
    )
    parser.add_argument(
        "--concurrency",
        type=_positive_int,
        default=4,
        help="maximum in-flight requests (default: 4)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=10.0,
        help="per-request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit one JSON object for CI/CD pipelines",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="check-proxy-tax {0}".format(__version__),
    )
    return parser


def run_probe(
    url: str,
    requests: int,
    marker: Optional[str],
    timeout: float,
    proxy: Optional[str],
    concurrency: int,
) -> List[Sample]:
    workers = max(1, min(concurrency, requests))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(fetch_once, url, marker, timeout, proxy)
            for _ in range(requests)
        ]
        return [future.result() for future in futures]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    parsed_url = urllib.parse.urlsplit(args.url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        parser.error("--url must be an absolute http(s) URL")

    try:
        samples = run_probe(
            args.url,
            args.requests,
            args.marker,
            args.timeout,
            args.proxy,
            args.concurrency,
        )
    except KeyboardInterrupt:
        print("check-proxy-tax: interrupted", file=sys.stderr)
        return 130

    metrics = compute_metrics(
        sum(1 for sample in samples if sample.usable),
        len(samples),
        args.price_per_1k,
    )
    report = build_report(args, samples, metrics)

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False))
    else:
        print(render_table(report))
        print()
        print("Benchmark & provider matrix: {0}".format(BENCHMARK_URL))
        print(FTC_DISCLOSURE)

    return _exit_code(metrics)


if __name__ == "__main__":
    sys.exit(main())
