# check-proxy-tax

**Audit the real cost of scraping proxies, 403 blowout multipliers, and effective price per 1,000 usable requests.**

[![PyPI version](https://img.shields.io/pypi/v/check-proxy-tax.svg)](https://pypi.org/project/check-proxy-tax/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#install)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Proxy invoices are priced per gigabyte, per IP, or per nominal request. Your production pipelines are not paid in raw network attempts; they are paid in responses they can actually parse and use.

When an edge gateway returns `403 Forbidden`, stalls on Cloudflare challenges until connection timeout, or returns HTTP `200` containing an empty consent screen, **your provider still bills you for the bandwidth or request slot**. The financial gap between advertised unit prices and the true cost of usable data is **The 403 Tax**.

`check-proxy-tax` is a zero-dependency CLI diagnostic tool that measures this tax empirically under real concurrent network conditions.

---

## The Economics: Advertised Rates vs. True Usable Cost

### Real-World Loss Scenario

Consider an e-commerce price monitoring or search scraping pipeline targeting 10,000,000 monthly requests:

- **Advertised Nominal Price**: $0.49 per 1,000 requests ($490 / month).
- **Observed Usable Rate**: 70% (25% HTTP 403 blocks + 5% timeout/captcha drops).
- **Required Total Attempts**: `10,000,000 / 0.70 = 14,285,714` requests.
- **Actual Billed Invoice**: `14,285,714 * $0.00049 = $700.00`.
- **The Monthly 403 Tax**: **$210.00 cash wasted** directly on blocked attempts (a 1.43x price blowout), plus downstream worker compute idling and retry queue latency.

At enterprise scale (100M+ monthly requests or residential GB pipelines), a 35% block rate burns tens of thousands of dollars annually in silent retry tax.

```text
usable_pct            = usable_count / total_requests * 100
effective_cost_per_1k = nominal_price_per_1k / (usable_pct / 100)
tax_multiplier        = effective_cost_per_1k / nominal_price_per_1k
```

---

## 2026 Residential & Scraper Provider Benchmark (5-Tier Comparison)

Below is the verified price and 403-Tax sensitivity matrix across the top 6 residential proxy and scraping API providers. Use the verified gateway jump links to access current volume discounts and free trial pools.

| Provider | Core Strength | Tier 1 (Starter) | Tier 2 (Growth) | Tier 3 (Pro) | Tier 4 (Business) | Tier 5 (Enterprise) | Verified Gateway |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Decodo (Smartproxy)** | 65M+ Residential IPs, 99.9% uptime, City targeting | $4.50 / GB | $3.50 / GB (25 GB) | $2.80 / GB (100 GB) | $2.20 / GB (500 GB) | $1.80 / GB (1 TB+) | [Explore Decodo Tier Plans](https://go.272738.xyz/decodo?src=pypi_check_proxy_tax) |
| **Webshare** | Budget-first private & rotating datacenter / residential | $2.99 / mo (100 IPs) | $1.50 / GB (Residential) | $1.00 / GB (50 GB) | $0.85 / GB (250 GB) | Custom Dedicated Subnets | [Explore Webshare Tier Plans](https://go.272738.xyz/webshare?src=pypi_check_proxy_tax) |
| **ScraperAPI** | Zero-block unblocker API, handles JS rendering & CAPTCHAs | $49 / mo (100k API reqs) | $149 / mo (1M API reqs) | $299 / mo (3M API reqs) | $999 / mo (14M API reqs) | Dedicated Edge Endpoints | [Explore ScraperAPI Tier Plans](https://go.272738.xyz/scraperapi?src=pypi_check_proxy_tax) |
| **9Proxy** | Clean residential pool, pay-per-IP without monthly expiration | $0.20 / IP (Starter 100 IPs) | $0.15 / IP (500 IPs) | $0.11 / IP (1,000 IPs) | $0.08 / IP (5,000 IPs) | $0.05 / IP (10,000+ IPs) | [Explore 9Proxy Tier Plans](https://go.272738.xyz/9proxy?src=pypi_check_proxy_tax) |
| **Pawns.app** | 100% peer-to-peer real residential ethical consumer devices | $3.00 / GB | $2.50 / GB (10 GB) | $2.00 / GB (50 GB) | $1.50 / GB (200 GB) | Custom Bulk Matrix | [Explore Pawns.app Tier Plans](https://go.272738.xyz/pawns?src=pypi_check_proxy_tax) |
| **PacketStream** | Distributed peer-to-peer residential traffic sharing network | $1.00 / GB flat | $1.00 / GB (20 GB) | $1.00 / GB (100 GB) | $1.00 / GB (500 GB) | Reseller Bulk Bandwidth | [Explore PacketStream Tier Plans](https://go.272738.xyz/packetstream?src=pypi_check_proxy_tax) |

### Effective Cost Multiplier Table (Per 1 Million Usable Requests)

Assuming a baseline nominal target rate of $0.50 per 1,000 requests ($500.00 / 1M nominal requests):

| Observed Block Rate | Usable Success Rate | Tax Multiplier | Billed Attempts Needed | True Effective Cost / 1M Usable | 403 Waste Tax |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0% (Clean Edge)** | 100% | **1.00x** | 1,000,000 | **$500.00** | $0.00 |
| **10%** | 90% | **1.11x** | 1,111,111 | **$555.56** | +$55.56 |
| **20%** | 80% | **1.25x** | 1,250,000 | **$625.00** | +$125.00 |
| **30%** | 70% | **1.43x** | 1,428,571 | **$714.29** | +$214.29 |
| **40%** | 60% | **1.67x** | 1,666,667 | **$833.33** | +$333.33 |
| **50% (Degraded Edge)** | 50% | **2.00x** | 2,000,000 | **$1,000.00** | **+$500.00 (100% Surcharge!)** |

---

## Installation

`check-proxy-tax` is packaged as a pure Python wheel with **zero external dependencies**. Requires Python 3.8+.

```bash
pip install check-proxy-tax --upgrade
```

Verify the installation:

```bash
check-proxy-tax --version
# check-proxy-tax 1.1.0
```

---

## CLI Usage & Quick Start

### 1. Basic Single-Endpoint Audit

```bash
check-proxy-tax \
  --url "https://target-domain.com/product/123" \
  --requests 30 \
  --concurrency 4 \
  --marker "In Stock" \
  --price-per-1k 0.49
```

Output:

```text
check-proxy-tax 1.1.0 - proxy economics audit

+---------------------+------------------------------------------+
| METRIC              | VALUE                                    |
+---------------------+------------------------------------------+
| Target URL          | https://target-domain.com/product/123    |
| Samples             | 30 (concurrency 4, timeout 10s)          |
| Marker              | In Stock                                 |
| Usable success      | 21 / 30                                  |
| Blocked / failed    | 9 / 30                                   |
| Usable rate         | 70.0%                                    |
+---------------------+------------------------------------------+
| Nominal price / 1k  | $0.4900                                  |
| Effective cost / 1k | $0.7000                                  |
| Tax multiplier      | 1.43x                                    |
+---------------------+------------------------------------------+
| Latency p50         | 218.4 ms                                 |
| Latency p95         | 1780.2 ms                                |
| Total transferred   | 1.84 MB (1,932,104 bytes)                |
| Status codes        | 200:21, 403:7, timeout:2                 |
| Blocked reasons     | http_403:7, timeout:2                    |
| Verdict             | DEGRADED - 9 of 30 requests blocked      |
+---------------------+------------------------------------------+

Benchmark & provider matrix: https://scrape.mybskm.top/?utm_source=cli&utm_content=check-proxy-tax
```

### 2. Compare 2026 Provider Pricing (`--compare-providers`)

Inspect the built-in 2026 benchmark cost comparison table across the top 6 residential and scraping networks:

```bash
check-proxy-tax --compare-providers
```

### 3. Machine-Readable JSON Output for CI/CD

Integrate directly into your scraping infrastructure or deployment gates:

```bash
check-proxy-tax \
  --url "https://target-domain.com/api/v1/catalog" \
  --requests 50 \
  --price-per-1k 0.50 \
  --json
```

JSON Output Schema:

```json
{
  "tool": "check-proxy-tax",
  "version": "1.1.0",
  "url": "https://target-domain.com/api/v1/catalog",
  "marker": null,
  "requests": 50,
  "concurrency": 4,
  "timeout_seconds": 10.0,
  "proxy_configured": false,
  "nominal_price_per_1k": 0.5,
  "usable_count": 35,
  "blocked_count": 15,
  "usable_pct": 70.0,
  "effective_cost_per_1k": 0.7142857142857143,
  "tax_multiplier": 1.4285714285714286,
  "cost_status": "finite",
  "latency_ms": {
    "p50": 218.4,
    "p95": 1780.2,
    "min": 145.1,
    "max": 2410.8
  },
  "total_bytes": 3210450,
  "status_counts": {
    "200": 35,
    "403": 12,
    "timeout": 3
  },
  "blocked_reasons": {
    "http_403": 12,
    "timeout": 3
  },
  "exit_code": 1
}
```

---

## Exit Codes for Automated Gateways

| Exit Code | Classification | Meaning |
| :---: | :--- | :--- |
| `0` | **PASS** | 100% of sampled requests were usable HTTP 200 with matching marker. |
| `1` | **DEGRADED** | Partial delivery: 1+ requests failed or were blocked by edge firewalls. |
| `2` | **FAILED** | Zero usable responses (complete block or infinite tax). |
| `3` | **USAGE** | Invalid command-line arguments or malformed target URL. |

Use exit code `0` in your deployment gate to ensure proxies are warming up properly before routing production traffic.

---

## Options Reference

```text
usage: check-proxy-tax [-h] --url URL [--requests N] [--marker STRING]
                       [--price-per-1k FLOAT] [--proxy URL] [--concurrency N]
                       [--timeout SECONDS] [--compare-providers] [--json]
                       [--version]

options:
  -h, --help            show this help message and exit
  --url URL             absolute http(s) URL to probe
  --requests N          sample size (default: 20)
  --marker STRING       string that must appear in the body to count as usable
  --price-per-1k FLOAT  nominal USD price per 1,000 requests (default: 0.49)
  --proxy URL           HTTP(S) proxy URI (http://user:pass@host:port)
  --concurrency N       maximum in-flight requests (default: 4)
  --timeout SECONDS     per-request socket timeout in seconds (default: 10.0)
  --compare-providers   display 2026 proxy benchmark pricing and tax comparison table
  --json                emit single JSON object for pipelines and dashboards
  --version             show program's version number and exit
```

---

## License

MIT License. Copyright (c) 2026 Kais / 600me.


---

## 🌐 Official Documentation, Docker Image & Web Calculators

* **Official Technical Manual (Read the Docs, DA 92)**: [residential-proxy-and-scraping-tax-benchmark](https://cloud-infra-tco-benchmarks.readthedocs.io/en/latest/residential-proxy-and-scraping-tax-benchmark/)
* **Production Docker Container (Docker Hub, DA 93)**: [600megd/proxy-tax-calculator](https://hub.docker.com/r/600megd/proxy-tax-calculator)
* **Interactive Live Calculator**: [Web Benchmark & TCO Estimator](https://proxy.mybskm.top/)
* **Interactive Documentation Portal**: [Proxy & Infrastructure Docs](https://proxy.mybskm.top/docs/)
