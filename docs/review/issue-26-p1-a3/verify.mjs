import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const out = fileURLToPath(new URL('./', import.meta.url)), repo = fileURLToPath(new URL('../../../', import.meta.url));
const manifest = JSON.parse(await fs.readFile(`${out}/manifest.json`, 'utf8'));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const check = (passed, message) => assert.ok(passed, message);
check(manifest.sourceSha256 === '6565d56dbc5a267eb90144f078c54f3d0c761c9a98ca29a18b4dc9c6cdde38e2', 'original source hash');
check(sha(await fs.readFile(`${repo}/exchange/m3/graph.json`)) === manifest.sourceSha256, 'current source hash');
check(manifest.samples.length === 12 && manifest.videos.length === 2, 'six static pairs and one video pair');
check(manifest.checks.every(c => c.passed) && manifest.console.length === 0, 'all checks and no browser errors');
const pairs = [];
for (const view of ['overview', 'arm-mid', 'arm-near', 'core-near', 'selected', 'neighbors']) {
  const pair = ['baseline', 'adaptive'].map(mode => manifest.samples.find(s => s.mode === mode && s.view === view));
  for (const s of pair) {
    for (const [file, hash] of [[s.file, s.sha256], [s.canvasFile, s.canvasSha256]]) check(sha(await fs.readFile(`${out}/${file}`)) === hash, `media hash ${file}`);
    check(s.state.provenance.sha256 === manifest.sourceSha256 && s.data === 'formal-handover-snapshot', 'explicit real provenance');
    check(s.state.nodes === 7845 && s.state.edges === 11412 && s.state.particles === 214200, 'separate knowledge and decoration counts');
    check(s.state.width === 1600 && s.state.height === 900 && s.state.dpr === 1 && s.state.dustClock === 0, 'fixed resolution and clock');
    check(s.perf.samples === 300 && s.perf.frames.length === 300 && s.perf.foreground === 'visible', 'foreground frame samples');
    check(s.perf.drawCalls.length === 1 && s.perf.drawCalls[0] === 22, 'stable draw calls');
  }
  check(JSON.stringify(pair[0].state.camera) === JSON.stringify(pair[1].state.camera), `${view} exact camera pair`);
  check(JSON.stringify(pair[0].state.target) === JSON.stringify(pair[1].state.target), `${view} exact target pair`);
  check(pair[0].state.selected === pair[1].state.selected && pair[0].state.visibleEdges === pair[1].state.visibleEdges, `${view} same selection/relations`);
  check(pair[0].rawNodesSha256 === pair[1].rawNodesSha256, 'raw fields retained');
  if (view === 'overview') check(pair[0].canvasSha256 === pair[1].canvasSha256, 'adaptive panorama exact baseline pixels');
  else check(pair[0].canvasSha256 !== pair[1].canvasSha256, `${view} adaptive pixels actually differ`);
  check(manifest.checks.some(c => c.name === `baseline/${view} canvas exactly matches e7771d0` && c.passed), `${view} original replay equivalence`);
  pairs.push({ view, baselineMeanMs: pair[0].perf.meanMs, adaptiveMeanMs: pair[1].perf.meanMs, baselineP95Ms: pair[0].perf.p95Ms, adaptiveP95Ms: pair[1].perf.p95Ms });
}
const [b, a] = ['baseline', 'adaptive'].map(mode => manifest.videos.find(v => v.mode === mode));
const videoChecks = [];
for (const v of [b, a]) {
  check(sha(await fs.readFile(`${out}/${v.file}`)) === v.sha256, 'video hash');
  check(v.trace.length === 601 && v.trace.every(f => f.reused), 'all video frames reuse buffers');
  check(Math.abs(v.trace[0].distance - 245) < 1e-8 && Math.abs(v.trace[300].distance - 24) < 1e-8 && Math.abs(v.trace[600].distance - 245) < 1e-8, 'zoom reaches exact endpoints');
  let maxOpacityStep = 0, maxCapStep = 0;
  for (let i = 1; i < v.trace.length; i++) for (let k = 0; k < 5; k++) {
    maxOpacityStep = Math.max(maxOpacityStep, Math.abs(v.trace[i].uniforms[k].opacity - v.trace[i - 1].uniforms[k].opacity));
    maxCapStep = Math.max(maxCapStep, Math.abs(v.trace[i].uniforms[k].cap - v.trace[i - 1].uniforms[k].cap));
  }
  check(maxOpacityStep < .02 && maxCapStep < .1, 'continuous opacity and cap along replay path');
  const frames = v.trace.slice(1).map(f => f.frameMs).sort((x, y) => x - y);
  videoChecks.push({ mode: v.mode, frames: v.trace.length, maxOpacityStep, maxCapStep, meanMs: frames.reduce((x, y) => x + y, 0) / frames.length, p95Ms: frames[Math.ceil(frames.length * .95) - 1], calls: [...new Set(v.trace.map(f => f.calls))] });
}
check(b.trace.every((f, i) => f.camera.every((x, j) => Math.abs(x - a.trace[i].camera[j]) < 1e-8) && f.target.every((x, j) => Math.abs(x - a.trace[i].target[j]) < 1e-8)), 'identical video camera/target at every replay frame');

const git = args => execFileSync('git', args, { cwd: repo, encoding: 'utf8' }).trim();
check(git(['diff', manifest.base, '--', 'backend', 'exchange', 'frontend/src']) === '', 'protected source/data unchanged');
const oldFiles = git(['ls-tree', '-r', '--name-only', manifest.base, 'docs/review/issue-26-p1', 'docs/review/issue-26-p1-a1', 'docs/review/issue-26-p1-a2']).split('\n');
for (const path of oldFiles) check(git(['hash-object', path]) === git(['rev-parse', `${manifest.base}:${path}`]), `old evidence unchanged: ${path}`);
const summary = { sourceSha256: manifest.sourceSha256, checks: manifest.checks.length, originalEvidenceFilesUnchanged: oldFiles.length, panoramaPixelIdentical: true, allSixBaselineViewsMatchOriginal: true, exactVideoPathPaired: true, pairs, videoChecks, recommendation: '实验未优于基线，保留 P1-A.2', limitation: 'Reduced decoration intensity is not proof of a meaningful gain in knowledge readability. Visual judgment still requires product review.' };
await fs.writeFile(`${out}/verification.json`, JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
