# PR Proposal 01 — awesome-web-scraping

Submission package for a one-line addition to the list. Do not paste this whole
file into GitHub; the ready-to-use PR body is in the fenced block below.

## Target

| Field | Value |
| --- | --- |
| Repository | [`lorien/awesome-web-scraping`](https://github.com/lorien/awesome-web-scraping) |
| File to edit | `cli.md` |
| Section | `## Network` (line 11) |
| Exact anchor | Replace the `EMPTY CONTENT` placeholder on line 13 |
| Entry position | First and only entry in `Network`; the section is currently a placeholder |
| Branch name | `add-check-proxy-tax` |
| PR title | `Add check-proxy-tax to Network CLI tools` |
| Suggested commit | `Add check-proxy-tax to Network CLI tools` |

`cli.md` currently reads:

```text
## Network

EMPTY CONTENT

## Web Scraping
```

The contribution rules require appending to the end of a list and adding a
new section only when necessary. No new section is needed: `Network` already
exists, is empty, and is described by the repository as the home for
"network and data processing tools with command line interface".

## Exact change

```diff
--- a/cli.md
+++ b/cli.md
@@ -10,7 +10,7 @@
 
 ## Network
 
-EMPTY CONTENT
+* [check-proxy-tax](https://github.com/600me/check-proxy-tax) - CLI that samples a URL concurrently and reports the usable-response rate and effective cost per 1,000 usable requests.
 
 ## Web Scraping
```

The entry is one line, starts with the project name, links only to the source
repository, and describes behavior rather than making a quality claim. No
affiliate, tracking, or benchmark URL appears in the list entry.

## Why this belongs in `Network`

- **It is standalone software.** A Python package with a console entry point;
  no hosted service, account, API key, or remote control plane is required.
- **Its primary job is network measurement.** It fetches one HTTP(S) URL
  concurrently, classifies every response, and reports transport-level
  outcomes (status codes, timeouts, latency, bytes, usable rate).
- **It is a CLI, not a library.** The `check-proxy-tax` command is the product;
  `python3 -m check_proxy_tax.cli` is equivalent when running from a checkout.
- **It has no runtime dependencies.** Pure Python 3.8+ standard library.
- **It is inspectable.** One package, one core module, MIT licensed.

It is not a scraper framework, parser, proxy marketplace, or hosted API, so it
does not belong in `Web Scraping`, `HTML/XML Parsing`, or the proxy
marketplace section of `README.md`.

## Ready-to-paste PR body

```markdown
## Summary

- Adds `check-proxy-tax` to the `Network` section of `cli.md`, replacing the
  `EMPTY CONTENT` placeholder.

## What it does

`check-proxy-tax` sends a configurable number of concurrent requests to one
URL, then classifies each response as usable or blocked. A response is usable
only when the final status is exactly `200` and, if `--marker` is supplied,
the body contains that marker. `403`, `429`, `5xx`, timeouts, connection
errors, and marker misses are reported as blocked.

The CLI reports:

- usable count and usable percentage;
- effective cost per 1,000 usable requests;
- tax multiplier over the nominal per-1,000 price;
- p50 and p95 latency;
- total bytes transferred;
- status-code and blocked-reason counts;
- stable exit codes (`0` all usable, `1` degraded, `2` none usable, `3` bad
  arguments) and an optional single-object `--json` report for CI.

## Why it fits this list

- Standalone command-line tool; no hosted service or account.
- Pure Python standard library, zero runtime dependencies.
- Primary purpose is HTTP network measurement, not scraping orchestration.
- MIT licensed and covered by an offline `unittest` suite.
- The `Network` section is currently an `EMPTY CONTENT` placeholder, so this
  is an append to an existing category rather than a new category.

## Verification

- `python3 -m unittest test_cli.py -v` — 14 tests pass.
- `python3 -m check_proxy_tax.cli --help` — exits `0`.
- Tested on Python 3.12; package declares Python 3.8+.
- `npm install && npm run check` run in the fork before opening this PR.

## Disclosure

The project README links to a public benchmark page that may include affiliate
tracking and carries this disclosure verbatim:

> FTC Disclosure: Benchmark links may include affiliate tracking.

No tracking or affiliate link is included in the list entry above.
```

## Eligibility gate — do not submit yet

`CONTRIBUTING.md` in `lorien/awesome-web-scraping` restricts "projects whose
GitHub repo is younger than a month". The `600me/check-proxy-tax` repository
was created on **2026-10-19**, so the earliest compliant submission date is
**2026-11-19**. Opening the PR earlier gives a maintainer a factual reason to
close it. Prepare the fork and branch now, hold the `gh pr create` call until
the repository is at least 30 days old, and re-run the checks below on that
date.

## Pre-submit checklist

1. Confirm the repository is at least 30 days old.
2. Fork `lorien/awesome-web-scraping` and clone the fork.
3. Run `git config core.hooksPath .githooks`.
4. Apply the one-line change to `cli.md`; do not touch other lists.
5. Run `npm install && npm run check`.
6. Confirm `git diff --check` is clean and the diff contains only `cli.md`.
7. Open the PR with the title and body above.
8. If a maintainer prefers the entry at the end of a different category,
   accept the placement change; the description and link stay unchanged.

## Maintainer FAQ

| Question | Factual response |
| --- | --- |
| "This is a promotional tool." | The list entry contains no tracking URL. The CLI is MIT licensed, has no account or upsell, and the README discloses its benchmark link under FTC language. |
| "Repo is too new." | Wait until 2026-11-19 before submitting. |
| "It duplicates proxy lists." | It does not sell or route proxy traffic; it measures whether responses are usable and computes effective cost. |
| "Why not Web Scraping?" | It does not crawl or extract. Its only output is transport and cost statistics for one URL. |
| "Is it maintained?" | The package ships an offline test suite, typed public functions, and a stable JSON schema; issues are enabled on the repository. |

## Commands

```bash
gh repo fork lorien/awesome-web-scraping --clone
cd awesome-web-scraping
git config core.hooksPath .githooks
git checkout -b add-check-proxy-tax
# edit cli.md exactly as shown above
npm install
npm run check
git add cli.md
git commit -m "Add check-proxy-tax to Network CLI tools"
git push -u origin add-check-proxy-tax
gh pr create \
  --repo lorien/awesome-web-scraping \
  --title "Add check-proxy-tax to Network CLI tools" \
  --body-file /path/to/pr-body.md
```
