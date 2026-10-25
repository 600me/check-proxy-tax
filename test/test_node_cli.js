'use strict';

const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { execFile } = require('node:child_process');
const path = require('node:path');

const cli = path.join(__dirname, '..', 'bin', 'cli.js');
let server;
let baseUrl;
let alternatingCount = 0;

before(async () => {
  server = http.createServer((req, res) => {
    if (req.url === '/reset') {
      req.socket.destroy();
      return;
    }
    const blocked = req.url === '/blocked' ||
      (req.url === '/alternating' && alternatingCount++ % 2 === 1);
    res.writeHead(blocked ? 403 : 200, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end(blocked ? 'Blocked' : 'IN_STOCK 商品');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
});

function runCli(...args) {
  return new Promise(resolve => {
    execFile(process.execPath, [cli, ...args], { timeout: 15000 }, (error, stdout, stderr) => {
      resolve({ code: error ? error.code : 0, stdout, stderr });
    });
  });
}

async function audit(route, ...args) {
  const result = await runCli('--url', baseUrl + route, '--requests', '4', ...args, '--json');
  assert.equal(result.code, 0, result.stderr);
  assert.equal(result.stderr, '');
  return JSON.parse(result.stdout);
}

test('help and short help exit successfully and list options', async () => {
  for (const flag of ['--help', '-h']) {
    const result = await runCli(flag);
    assert.equal(result.code, 0);
    assert.equal(result.stderr, '');
    for (const option of ['--url', '--requests', '--marker', '--proxy', '--price-per-1k', '--json']) {
      assert.ok(result.stdout.includes(option), option);
    }
  }
});

test('missing URL exits with an actionable error', async () => {
  const result = await runCli();
  assert.equal(result.code, 1);
  assert.equal(result.stdout, '');
  assert.match(result.stderr, /--url is required/);
});

test('successful responses retain nominal cost and report the requested count', async () => {
  const report = await audit('/ok', '--requests', '3', '--marker', 'IN_STOCK');
  assert.equal(report.target_url, baseUrl + '/ok');
  assert.equal(report.requests_sent, 3);
  assert.equal(report.usable_requests, 3);
  assert.equal(report.usable_pct, 100);
  assert.equal(report.tax_multiplier, 1);
  assert.equal(report.nominal_price_per_1k, 0.49);
  assert.equal(report.effective_cost_per_1k, 0.49);
});

test('a marker is optional and supports Unicode', async () => {
  assert.equal((await audit('/ok')).usable_requests, 4);
  assert.equal((await audit('/ok', '--marker', '商品')).usable_requests, 4);
});

test('missing marker makes otherwise successful responses unusable', async () => {
  const report = await audit('/ok', '--marker', 'NOT_PRESENT');
  assert.equal(report.usable_requests, 0);
  assert.equal(report.usable_pct, 0);
  assert.equal(report.tax_multiplier, null);
  assert.equal(report.effective_cost_per_1k, null);
});

test('HTTP failures are unusable even when the body matches the marker', async () => {
  const report = await audit('/blocked', '--marker', 'Blocked');
  assert.equal(report.usable_requests, 0);
  assert.equal(report.usable_pct, 0);
  assert.equal(report.tax_multiplier, null);
  assert.equal(report.effective_cost_per_1k, null);
});

test('a 50 percent usable rate doubles custom effective cost', async () => {
  alternatingCount = 0;
  const report = await audit('/alternating', '--price-per-1k', '1.25');
  assert.equal(report.usable_requests, 2);
  assert.equal(report.usable_pct, 50);
  assert.equal(report.tax_multiplier, 2);
  assert.equal(report.nominal_price_per_1k, 1.25);
  assert.equal(report.effective_cost_per_1k, 2.5);
});

test('fractional usable rates and costs use the documented output precision', async () => {
  alternatingCount = 0;
  const report = await audit('/alternating', '--requests', '3');
  assert.equal(report.usable_requests, 2);
  assert.equal(report.usable_pct, 66.7);
  assert.equal(report.tax_multiplier, 1.5);
  assert.equal(report.effective_cost_per_1k, 0.735);
});

test('connection errors produce a JSON report with no usable requests', async () => {
  const report = await audit('/reset');
  assert.equal(report.requests_sent, 4);
  assert.equal(report.usable_requests, 0);
  assert.equal(report.tax_multiplier, null);
  assert.equal(report.effective_cost_per_1k, null);
});

test('JSON output contains only the public report fields', async () => {
  const report = await audit('/ok');
  assert.deepEqual(Object.keys(report).sort(), [
    'target_url', 'requests_sent', 'usable_requests', 'usable_pct', 'tax_multiplier',
    'nominal_price_per_1k', 'effective_cost_per_1k', 'benchmark_hub'
  ].sort());
  assert.match(report.benchmark_hub, /^https:\/\/.+\?utm_source=npx_cli$/);
});

test('human-readable output includes cost metrics and calculator', async () => {
  const result = await runCli('--url', baseUrl + '/ok', '--requests', '2');
  assert.equal(result.code, 0, result.stderr);
  assert.match(result.stdout, /2 total, 2 usable \(100\.0%\)/);
  assert.match(result.stdout, /Tax Multiplier:\s+1\.00x/);
  assert.match(result.stdout, /Effective Real Cost:\s+\$0\.490/);
  assert.match(result.stdout, /Live Calculator & TCO: https:\/\//);
});
