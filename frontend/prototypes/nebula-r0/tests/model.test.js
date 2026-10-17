import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dust, fit, labelBoxes, makeIndex, project, radius, search, visibleNodes } from '../model.js';
const data = JSON.parse(readFileSync(new URL('../public/data.json', import.meta.url)));
const original = JSON.parse(readFileSync(new URL('../../../../exchange/m3/graph.json', import.meta.url)));
const index = makeIndex(data);
const all = { job: true, skill: true, industry: true };

test('fixed source and every original entity/edge survive the spatial protocol', () => {
  assert.equal(data.nodes.length, 7845); assert.equal(data.edges.length, 11412);
  assert.equal(data.metadata.sourceSha256, '6565d56dbc5a267eb90144f078c54f3d0c761c9a98ca29a18b4dc9c6cdde38e2');
  for (const n of data.nodes) { assert.equal(n.nodeId, n.properties.id); assert(n.xyz.every(Number.isFinite)); }
  for (const e of data.edges) { assert.equal(e.source, e.properties.source); assert.equal(e.target, e.properties.target); assert.equal(e.type, e.properties.type); }
  assert.deepEqual(data.nodes.map(n => n.properties), [...original.nodes].sort((a,b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const edgeKey = e => JSON.stringify([e.source, e.target, e.type]);
  assert.deepEqual(new Map(data.edges.map(e => [edgeKey(e),e.properties])), new Map(original.edges.map(e => [edgeKey(e),e])));
});
test('Python degree and full selected neighborhood survive overview LOD and type filters', () => {
  assert.equal(index.adjacent.get('skill:python').length, 222);
  const visible = visibleNodes(data, { selected: 'skill:python', zoom: 1, types: all, matches: [] }, index);
  const ids = new Set(visible.map(n => n.nodeId));
  for (const e of index.adjacent.get('skill:python')) { assert(ids.has(e.source)); assert(ids.has(e.target)); }
  const filtered = visibleNodes(data, { selected: 'skill:python', zoom: 1, types: { ...all, job: false }, matches: [] }, index);
  assert(!filtered.some(n => n.type === 'job'));
  assert.equal(index.adjacent.get('skill:python').length, 222);
});
test('zoom reveals real leaves and pixel radius always remains bounded for all types', () => {
  const distant = visibleNodes(data, { selected: null, zoom: 1, types: all, matches: [] }, index);
  const near = visibleNodes(data, { selected: null, zoom: 4, types: all, matches: [] }, index);
  assert.equal(distant.length, 717); assert.equal(near.length, 7845);
  for (const n of data.nodes) for (const z of [.1, 1, 6, 40]) assert(radius(n, z, 6, true) <= 6);
});
test('same input produces same decoration; particles have no real IDs', () => {
  const a = dust(data.communities), b = dust(data.communities);
  assert.deepEqual(a, b); assert(a.length > 17000);
  assert(a.every(n => !('nodeId' in n) && !('edgeId' in n)));
});
test('search exact result first; all results retain real identity', () => {
  const results = search(data.nodes, 'Python', all);
  assert(results.length > 1); assert.equal(results[0].nodeId, 'skill:python');
  assert.equal(new Set(results.map(n => n.nodeId)).size, results.length);
});
test('explicit neighborhood fit includes every endpoint at the same camera rotation', () => {
  const ids = new Set(['skill:python']);
  for (const e of index.adjacent.get('skill:python')) { ids.add(e.source); ids.add(e.target); }
  const nodes = [...ids].map(id => index.byId.get(id));
  const original = { k: .5, x: 25, y: 30, yaw: .3, pitch: .1 };
  const saved = { ...original }; const next = fit(nodes, 900, 750, original);
  for (const n of nodes) { const [x,y] = project(n.xyz, next); assert(x >= 49 && x <= 851); assert(y >= 54 && y <= 696); }
  assert.deepEqual(original, saved);
});
test('labels are bounded and non-overlapping, selected priority wins', () => {
  const ids = labelBoxes([{ id: 'ordinary', x: 10, y: 50, width: 90, priority: 1 }, { id: 'selected', x: 10, y: 50, width: 90, priority: 1000 }, { id: 'offscreen', x: 290, y: 50, width: 90, priority: 9999 }], 300, 200);
  assert.deepEqual([...ids], ['selected']);
});
