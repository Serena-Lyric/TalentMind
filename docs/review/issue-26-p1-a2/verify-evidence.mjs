import fs from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
const repo = fileURLToPath(new URL('../../../', import.meta.url)), out = fileURLToPath(new URL('./', import.meta.url));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const graphBytes = await fs.readFile(`${repo}/exchange/m3/graph.json`), graph = JSON.parse(graphBytes);
const manifest = JSON.parse(await fs.readFile(`${out}/capture-manifest.json`));
const checks = [];
for (const view of ['overview', 'arm', 'core', 'selected', 'zoom']) {
  const samples = manifest.samples.filter(sample => sample.view === view);
  assert.equal(samples.length, 3);
  for (const sample of samples) {
    assert.equal(sha(await fs.readFile(`${out}/${sample.file}`)), sample.sha256);
    assert.equal(sample.stats.dustClock, 0);
    for (const key of ['camera', 'target']) assert.ok(sample.stats[key].every((value, i) => Math.abs(value - samples[0].stats[key][i]) < .00001));
    assert.equal(sample.stats.dpr, 1); assert.equal(sample.stats.width, 1600); assert.equal(sample.stats.height, 900);
    assert.equal(JSON.parse(sample.capture).seed, 261018);
  }
  checks.push(`${view}: same camera/target/seed/clock/viewport/DPR, three original PNG hashes verified`);
}
const historical = execFileSync('git', ['ls-tree', '-r', '--name-only', '994edb6', 'docs/review/issue-26-p1-a', 'docs/review/issue-26-p1-a1'], { cwd: repo, encoding: 'utf8' }).trim().split('\n').filter(path => /\.(png|jpg|webm)$/.test(path));
for (const path of historical) assert.equal(sha(await fs.readFile(`${repo}/${path}`)), sha(execFileSync('git', ['show', `994edb6:${path}`], { cwd: repo, maxBuffer: 64 * 1024 * 1024 })));
assert.equal(sha(await fs.readFile(`${repo}/frontend/visual-lab/dist/m3-graph.json`)), sha(graphBytes));
const sources = { sha256: sha(graphBytes), bytes: graphBytes.length, nodes: graph.nodes.length, edges: graph.edges.length,
  examples: [0, 1].map(index => ({ path: `nodes[${index}]`, raw: graph.nodes[index] })),
  edgeExamples: [0, 24].map(index => ({ path: `edges[${index}]`, raw: graph.edges[index] })),
  python: { stored_job_count: graph.nodes.find(n => n.id === 'skill:python').job_count, actual_incident_edges: graph.edges.filter(e => e.source === 'skill:python' || e.target === 'skill:python').length },
};
const density = {};
for (const [label, path] of [['p1a', '.p1a-baseline/'], ['p1a1', '.p1a1-baseline/'], ['p1a2', '']]) {
  const { generateParticles } = await import(`../../../frontend/visual-lab/${path}src/generate.js`);
  const { spiralPoint } = await import(`../../../frontend/visual-lab/${path}src/config.js`);
  const data = generateParticles('stars'); let sampled = 0, interArm = 0;
  for (let i = 0; i < data.count; i++) {
    const x = data.position[i * 3], z = data.position[i * 3 + 2], r = Math.hypot(x, z);
    if (r < 25 || r > 90) continue;
    let nearest = Math.PI;
    for (let arm = 0; arm < 4; arm++) { const [a, , b] = spiralPoint(r, arm); const angle = Math.atan2(z, x) - Math.atan2(b, a); nearest = Math.min(nearest, Math.abs(Math.atan2(Math.sin(angle), Math.cos(angle)))); }
    sampled++; if (nearest > .45) interArm++;
  }
  density[label] = { sampled, interArm, ratio: interArm / sampled, metric: 'Geometric star positions only: radius 25..90, nearest arm angular distance >0.45 radians; not a visual quality score.' };
}
const images = [];
for (const filename of (await fs.readdir(out)).filter(name => name.endsWith('.png'))) images.push({ file: filename, sha256: sha(await fs.readFile(`${out}/${filename}`)) });
const result = { checks, images, historicalBinaryFilesUnchanged: historical.length, historicalPaths: historical, source: sources, density };
await fs.writeFile(`${out}/evidence-verification.json`, JSON.stringify(result, null, 2));
console.log(JSON.stringify({ checks, historicalUnchanged: historical.length, sha256: sources.sha256, density }));
