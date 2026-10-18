# check-proxy-tax

**Find out what a "cheap" proxy actually costs per 1,000 usable requests.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#install)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Proxy invoices are priced per request, per IP, or per GB. Your scraper is not
paid in those units. It is paid in responses it can actually use. When an edge
returns `403`, a request stalls until timeout, or a `200` arrives without the
product marker, the attempt is still billed. The gap between the advertised
price and the price of usable traffic is **The 403 Tax**.

`check-proxy-tax` measures that gap directly. It fires a small concurrent burst
at one URL, classifies every response as usable or blocked, and reports:

- usable rate and blocked/failed counts;
- effective cost per 1,000 usable requests;
- the tax multiplier over the nominal per-1,000 price;
- p50 / p95 latency and total bytes transferred;
- status-code and failure-reason breakdown.

It is a single core module using only the standard library. No account, no API
key, no external dependencies, no background service.

## Install

Python 3.8 or newer.

```bash
git clone https://github.com/600me/check-proxy-tax.git
cd check-proxy-tax
python3 -m pip install .
check-proxy-tax --help
```

You can also run it straight from a checkout without installing:

```bash
python3 -m check_proxy_tax.cli --url https://example.com --requests 5
```

The package is PyPI-ready (`python3 -m build` produces a wheel and sdist), but
installing from source is the supported path until the first PyPI release.

## Quick start

```bash
check-proxy-tax \
  --url "https://example.com/product/123" \
  --requests 20 \
  --marker "Add to cart" \
  --price-per-1k 0.49
```

```text
check-proxy-tax 0.1.0 - proxy economics audit

+---------------------+------------------------------------------+
| METRIC              | VALUE                                    |
+---------------------+------------------------------------------+
| Target URL          | https://example.com/product/123          |
| Samples             | 20 (concurrency 4, timeout 10s)          |
| Marker              | Add to cart                              |
| Usable success      | 14 / 20                                  |
| Blocked / failed    | 6 / 20                                   |
| Usable rate         | 70.0%                                    |
+---------------------+------------------------------------------+
| Nominal price / 1k  | $0.4900                                  |
| Effective cost / 1k | $0.7000                                  |
| Tax multiplier      | 1.43x                                    |
+---------------------+------------------------------------------+
| Latency p50         | 212.4 ms                                 |
| Latency p95         | 1840.9 ms                                |
| Total transferred   | 1.18 MB (1,234,567 bytes)                |
| Status codes        | 200:14, 403:5, timeout:1                 |
| Blocked reasons     | http_403:5, timeout:1                    |
| Verdict             | DEGRADED - 6 of 20 requests blocked      |
+---------------------+------------------------------------------+

Benchmark & provider matrix: https://scrape.mybskm.top/?utm_source=cli&utm_content=check-proxy-tax
FTC Disclosure: Benchmark links may include affiliate tracking.
```

## What counts as usable

A sample is **usable** only when both conditions hold:

1. the final HTTP status is exactly `200`;
2. when `--marker` is supplied, the response body contains that string
   (case-sensitive, matched against the raw UTF-8 bytes).

Everything else is **blocked**: `403`, `429`, other `4xx`, `5xx`, timeout,
connection/TLS failure, or a `200` without the marker. Redirects are followed
and the final status is classified.

That definition is deliberately strict. A `200` challenge page, a consent
screen, or an empty shell is not inventory your scraper can use.

## The math

```text
usable_pct            = usable_count / total_requests * 100
effective_cost_per_1k = nominal_price_per_1k / (usable_pct / 100)
tax_multiplier        = effective_cost_per_1k / nominal_price_per_1k
```

If `usable_count` is `0`, the effective cost is **Infinite**: no amount of
nominal budget buys a usable response at that sample rate. The JSON output
sets `effective_cost_per_1k` and `tax_multiplier` to `null` and
`cost_status` to `"infinite"`, which keeps the document valid JSON.

### Worked example

You pay **$0.49 per 1,000 requests**. You sample 20 requests and 14 come back
usable with the expected marker.

```text
usable_pct            = 14 / 20 * 100 = 70.0%
effective_cost_per_1k = 0.49 / 0.70   = $0.70
tax_multiplier        = 0.70 / 0.49   = 1.43x
```

At 1,000,000 requests per month the invoice is `$490`. Because only 70% of
attempts are usable, you need about 1,428,571 attempts to obtain 1,000,000
usable responses, which costs about `$700`. **The 403 Tax is $210 per month**
on that volume.

The model assumes blocked attempts are billed, which is how per-request and
per-IP plans normally work. If your provider bills only successful requests,
set `--price-per-1k` to the effective rate you want to test and read the
multiplier as a quality signal rather than a surcharge.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--url URL` | required | Absolute `http(s)` URL to probe. |
| `--requests N` | `20` | Number of samples. |
| `--marker STRING` | none | String that must appear in the body for a sample to count as usable. |
| `--price-per-1k FLOAT` | `0.49` | Nominal price per 1,000 requests, in USD. |
| `--proxy URL` | none | HTTP(S) proxy, e.g. `http://user:pass@host:port`. |
| `--concurrency N` | `4` | Maximum in-flight requests. |
| `--timeout SECONDS` | `10` | Per-request timeout. |
| `--json` | off | Emit one JSON object and nothing else. |
| `--version` | | Print the version and exit. |
| `--help` | | Show help, including the FTC disclosure. |

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every sampled request was usable. |
| `1` | Degraded: at least one request was blocked, at least one succeeded. |
| `2` | Failed: no request was usable. |
| `3` | Invalid arguments or URL. |

This makes the CLI useful as a gate without parsing text: `0` is the only
fully healthy result. A CI job that must not fail on a degraded sample can
capture the code and inspect the JSON instead.

## JSON output

`--json` writes a single JSON object to stdout, suitable for `jq`, dashboards,
or a CI artifact. Diagnostics never share that stream.

```json
{
  "tool": "check-proxy-tax",
  "version": "0.1.0",
  "url": "https://example.com/product/123",
  "marker": "Add to cart",
  "requests": 20,
  "concurrency": 4,
  "timeout_seconds": 10.0,
  "proxy_configured": false,
  "nominal_price_per_1k": 0.49,
  "usable_count": 14,
  "blocked_count": 6,
  "usable_pct": 70.0,
  "effective_cost_per_1k": 0.7,
  "tax_multiplier": 1.428571,
  "cost_status": "finite",
  "latency_ms": {
    "p50": 212.4,
    "p95": 1840.9,
    "min": 141.2,
    "max": 2190.7
  },
  "total_bytes": 1234567,
  "status_counts": {
    "200": 14,
    "403": 5,
    "timeout": 1
  },
  "blocked_reasons": {
    "http_403": 5,
    "timeout": 1
  },
  "exit_code": 1,
  "benchmark_url": "https://scrape.mybskm.top/?utm_source=cli&utm_content=check-proxy-tax",
  "ftc_disclosure": "FTC Disclosure: Benchmark links may include affiliate tracking."
}
```

`status_counts` uses the numeric HTTP status as a string, or `timeout` /
`error` when no status was received. `blocked_reasons` uses `http_<status>`,
`marker_missing`, `timeout`, or `connection_error`.

## CI example

```yaml
name: proxy-cost-gate
on:
  workflow_dispatch:
  schedule:
    - cron: "17 6 * * *"

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python3 -m pip install .
      - name: Audit effective proxy cost
        env:
          TARGET_URL: https://example.com/product/123
        run: |
          set +e
          check-proxy-tax \
            --url "$TARGET_URL" \
            --requests 30 \
            --marker "Add to cart" \
            --price-per-1k 0.49 \
            --json > proxy-report.json
          code=$?
          set -e
          cat proxy-report.json
          # Gate on usable rate, not on the raw exit code.
          jq -e '.usable_pct >= 95 and .cost_status == "finite"' proxy-report.json
```

Run the suite locally with:

```bash
python3 -m unittest test_cli.py -v
```

The tests use a local `http.server`; they do not touch the network.

## Benchmark and provider matrix

Public benchmark and provider comparison:

<https://scrape.mybskm.top/?utm_source=cli&utm_content=check-proxy-tax>

FTC Disclosure: Benchmark links may include affiliate tracking.

## License

MIT. See [LICENSE](LICENSE).

Copyright (c) 2026 Kais / 600me.
