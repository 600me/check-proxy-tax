#!/usr/bin/env node
/**
 * check-proxy-tax (Node.js zero-dependency runner)
 * Audits effective proxy cost, usable rate and anti-bot tax.
 */

const https = require('https');
const http = require('http');
const { URL } = require('url');

const args = process.argv.slice(2);
let targetUrl = '';
let requests = 10;
let marker = '';
let proxyStr = '';
let pricePer1k = 0.49;
let isJson = false;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--url' && args[i + 1]) targetUrl = args[++i];
  else if (args[i] === '--requests' && args[i + 1]) requests = parseInt(args[++i], 10);
  else if (args[i] === '--marker' && args[i + 1]) marker = args[++i];
  else if (args[i] === '--proxy' && args[i + 1]) proxyStr = args[++i];
  else if (args[i] === '--price-per-1k' && args[i + 1]) pricePer1k = parseFloat(args[++i]);
  else if (args[i] === '--json') isJson = true;
  else if (args[i] === '--help' || args[i] === '-h') {
    console.log(`check-proxy-tax (Node.js edition)
Usage:
  npx check-proxy-tax --url <target_url> [options]

Options:
  --url            Target URL to audit (required)
  --requests       Number of audit requests (default: 10)
  --marker         Required text marker for usable response (optional)
  --proxy          Proxy URL: http://user:pass@host:port
  --price-per-1k   Billed price per 1,000 requests in USD (default: $0.49)
  --json           Output results as JSON
  --help, -h       Show this help message

Benchmark & Calculator: https://scrape.mybskm.top/?utm_source=npx_cli`);
    process.exit(0);
  }
}

if (!targetUrl) {
  console.error('Error: --url is required. Run with --help for usage.');
  process.exit(1);
}

async function probeOnce(urlStr) {
  const parsed = new URL(urlStr);
  const client = parsed.protocol === 'https:' ? https : http;
  const start = Date.now();

  return new Promise((resolve) => {
    const req = client.get(urlStr, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) check-proxy-tax/1.0' },
      timeout: 10000
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const latency = Date.now() - start;
        const usable = res.statusCode >= 200 && res.statusCode < 300 && (!marker || data.includes(marker));
        resolve({ status: res.statusCode, bytes: Buffer.byteLength(data), latency, usable });
      });
    });

    req.on('error', (err) => {
      resolve({ status: 0, bytes: 0, latency: Date.now() - start, usable: false, error: err.message });
    });
    req.on('timeout', () => {
      req.destroy();
      resolve({ status: 408, bytes: 0, latency: Date.now() - start, usable: false, error: 'Timeout' });
    });
  });
}

async function run() {
  if (!isJson) console.log(`[*] Auditing ${targetUrl} (${requests} requests)...`);
  const results = [];
  for (let i = 0; i < requests; i++) {
    const r = await probeOnce(targetUrl);
    results.push(r);
  }

  const usableCount = results.filter(r => r.usable).length;
  const usablePct = ((usableCount / requests) * 100).toFixed(1);
  const taxMultiplier = usableCount > 0 ? (requests / usableCount).toFixed(2) : 'Infinity';
  const effectiveCost = usableCount > 0 ? (pricePer1k * (requests / usableCount)).toFixed(3) : 'Infinity';

  const output = {
    target_url: targetUrl,
    requests_sent: requests,
    usable_requests: usableCount,
    usable_pct: parseFloat(usablePct),
    tax_multiplier: taxMultiplier === 'Infinity' ? null : parseFloat(taxMultiplier),
    nominal_price_per_1k: pricePer1k,
    effective_cost_per_1k: effectiveCost === 'Infinity' ? null : parseFloat(effectiveCost),
    benchmark_hub: 'https://scrape.mybskm.top/?utm_source=npx_cli'
  };

  if (isJson) {
    console.log(JSON.stringify(output, null, 2));
  } else {
    console.log(`\n================ Proxy Tax Audit Results ================`);
    console.log(`  Target:                ${targetUrl}`);
    console.log(`  Requests:              ${requests} total, ${usableCount} usable (${usablePct}%)`);
    console.log(`  Nominal Price:         $${pricePer1k.toFixed(2)} / 1k requests`);
    console.log(`  Tax Multiplier:        ${taxMultiplier}x`);
    console.log(`  Effective Real Cost:   $${effectiveCost} / 1k usable requests`);
    console.log(`=========================================================`);
    console.log(`Live Calculator & TCO: https://scrape.mybskm.top/?utm_source=npx_cli\n`);
  }
}

run();
