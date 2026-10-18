import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.NEBULA_PLAYWRIGHT ? pathToFileURL(process.env.NEBULA_PLAYWRIGHT).href : 'playwright');
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:18128/?diagnostics=1');
  await page.waitForFunction(() => document.querySelector('#universe').dataset.ready === 'true');
  const graph = JSON.parse(await page.locator('#universe').getAttribute('data-graph'));
  assert.equal(graph.nodes, 7845); assert.equal(graph.edges, 11412);
  assert.equal(await page.locator('#diagnostics').count(), 0);
  await page.locator('#graph-query').fill('skill:python');
  await page.locator('#graph-results').selectOption('skill:python');
  assert.match(await page.locator('#graph-detail').innerText(), /nodes\[1\]/);
  await page.goto('http://127.0.0.1:18128/?data=demo&diagnostics=1');
  await page.waitForFunction(() => document.querySelector('#universe').dataset.ready === 'true');
  assert.equal(await page.locator('#graph-tools').isVisible(), false);
  assert.equal(await page.locator('#diagnostics').count(), 0);
  assert.match(await page.locator('.demo-mark').innerText(), /合成/);
  assert.equal(errors.length, 0);
  await fs.writeFile(new URL('./production-checks.json', import.meta.url), JSON.stringify({ graph, selection: 'skill:python → nodes[1]', explicitDemoRollback: true, productionDiagnosticsAbsent: true, errors }, null, 2));
  console.log('Production snapshot, raw selection, explicit demo rollback and absent DEV diagnostics verified.');
} finally { await browser.close(); }
