# PR Proposal 02 — awesome-python-testing

Internal submission package for the Python testing/tooling list. The
ready-to-paste PR body is in the fenced block below.

## Target

| Field | Value |
| --- | --- |
| Repository | [`cleder/awesome-python-testing`](https://github.com/cleder/awesome-python-testing) |
| File to edit | `README.md` |
| Section | `## Tools` (line 258) |
| Exact anchor | Insert immediately before the `CrossHair` entry (line 260) |
| Entry position | First entry in `Tools`, preserving the section's existing alphabetical order (`check-proxy-tax` < `CrossHair`) |
| Branch name | `add-check-proxy-tax` |
| PR title | `Add check-proxy-tax to Tools` |
| Suggested commit | `Add check-proxy-tax to Tools` |

The `Tools` section is alphabetized. `check-proxy-tax` belongs before
`CrossHair`; if a maintainer prefers append-only ordering, move the same line
to the end of the section without changing its text.

## Exact change

```diff
--- a/README.md
+++ b/README.md
@@ -257,6 +257,7 @@
 ## Tools
 
+- [check-proxy-tax](https://github.com/600me/check-proxy-tax) - CLI that samples a URL concurrently and reports usable-response rate, latency, and effective cost per 1,000 usable requests.
 - [CrossHair](https://github.com/pschanely/CrossHair) - An analysis tool for Python that blurs the line between testing and type systems.
 - [csv-quality-gate](https://github.com/hermes-labs-ai/csv-quality-gate) - A Python CLI that checks CSV test datasets and pipeline inputs for missing columns, empty cells, and duplicate rows, with configurable rules and CI exit codes.
 - [ghostwriter](https://hypothesis.readthedocs.io/en/latest/ghostwriter.html) - Writing tests with Hypothesis frees you from the tedium of deciding on and writing out specific inputs to test.
```

The description is one line, starts with the project name, links only to the
source repository, and stays factual. No benchmark, affiliate, or tracking URL
appears in the entry.

## Fit and scope

This entry is a deliberate edge case, so the PR body states the fit rather
than hiding it.

The list collects "Python resources for testing and generating test data".
`check-proxy-tax` is not a test framework and does not generate tests. It is a
Python CLI for the part of integration testing that depends on a live HTTP
endpoint: deciding whether a response is genuinely usable, and failing a
pipeline when it is not.

It belongs in `Tools` for four concrete reasons:

1. **It produces test-signal, not just metrics.** Exit codes `0/1/2` map to
   all-usable, degraded, and none-usable results, so a test job can gate on
   the outcome without parsing prose.
2. **It is deterministic to consume.** `--json` emits one machine-readable
   object and nothing else, suitable for a CI artifact or an assertion in a
   test harness.
3. **It isolates flaky external dependencies.** Tests that call a live URL
   fail for transport reasons that unit tests usually mock away. This tool
   makes status codes, timeout rate, marker misses, and latency visible before
   they are mistaken for application regressions.
4. **It matches the existing `Tools` category.** Neighboring entries are
   command-line analyzers and CI gates (`csv-quality-gate`, `import-effects`,
   `quick-gate-python`), not test frameworks.

If maintainers consider proxy auditing out of scope for this list, closing
without merge is a valid outcome. The entry should not be argued into a
category where it does not fit.

## Ready-to-paste PR body

```markdown
## Summary

- Adds `check-proxy-tax` to the `Tools` section, in alphabetical order before
  `CrossHair`.

## What it does

`check-proxy-tax` is a Python CLI that sends a configurable number of
concurrent requests to one URL and classifies each response as usable or
blocked. Usable means the final status is exactly `200` and, when `--marker`
is supplied, the body contains that marker. `403`, `429`, `5xx`, timeouts,
connection errors, and marker misses are blocked.

It reports usable percentage, effective cost per 1,000 usable requests, tax
multiplier over the nominal price, p50/p95 latency, bytes transferred, and
status/reason counts. `--json` emits a single object. Exit codes are stable:
`0` all usable, `1` degraded, `2` none usable, `3` invalid arguments.

## Why it fits `Tools`

- It turns a flaky live-endpoint dependency into a deterministic CI signal.
- The JSON object is suitable for a test assertion or pipeline artifact.
- It is a standalone Python CLI with no hosted service or account.
- Pure standard library, zero runtime dependencies, MIT licensed.
- It is an analyzer/gate, like the neighboring `Tools` entries, not a test
  framework.

## Verification

- `python3 -m unittest test_cli.py -v` — 14 tests pass offline.
- `python3 -m check_proxy_tax.cli --help` — exits `0`.
- Tested on Python 3.12; declares Python 3.8+.
- `pre-commit run --all-files` run in the fork before opening this PR,
  including `rumdl-fmt`, `typos`, and the dead-link check.

## Disclosure

The project README links to a public benchmark page that may include affiliate
tracking and carries this disclosure verbatim:

> FTC Disclosure: Benchmark links may include affiliate tracking.

No tracking or affiliate link is included in the list entry above.
```

## Pre-submit checklist

1. Fork `cleder/awesome-python-testing` and clone the fork.
2. Create branch `add-check-proxy-tax`.
3. Insert the single line before `CrossHair` in `## Tools`; change nothing
   else. Confirm the file still ends with one newline.
4. Install and run the repository hooks:
   `python3 -m pip install pre-commit && pre-commit run --all-files`.
5. Confirm `git diff --check` is clean and the diff touches only `README.md`.
6. Use the PR title and body above. Keep the description exactly one line.
7. If the maintainer asks for append-only ordering, move the line to the end
   of `Tools`; do not reword it into marketing copy.

## Maintainer objection handling

| Likely objection | Factual response |
| --- | --- |
| "This is a proxy seller's tool." | It does not sell, route, or provision proxies. It measures HTTP responses from one URL and has no account system. The list entry has no tracking URL. |
| "This is not a testing tool." | Correct that it is not a test framework. It is proposed for `Tools` because it turns live-endpoint flakiness into exit codes and JSON assertions for integration tests. If that is out of scope, close the PR. |
| "Why not Load Testing?" | It sends a small diagnostic sample and reports usability, not load, throughput curves, or concurrency limits. |
| "Why not Awesome Python?" | This list is the focused Python testing/tooling audience; the general list's Testing section is framework-oriented. |
| "Is the description too long?" | It is one line and states only observable behavior; it can be shortened to the first clause if preferred. |

## Commands

```bash
gh repo fork cleder/awesome-python-testing --clone
cd awesome-python-testing
git checkout -b add-check-proxy-tax
# edit README.md exactly as shown above
python3 -m pip install pre-commit
pre-commit run --all-files
git add README.md
git commit -m "Add check-proxy-tax to Tools"
git push -u origin add-check-proxy-tax
gh pr create \
  --repo cleder/awesome-python-testing \
  --title "Add check-proxy-tax to Tools" \
  --body-file /path/to/pr-body.md
```
