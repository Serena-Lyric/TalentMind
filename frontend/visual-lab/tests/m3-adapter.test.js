import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as adapter from '../src/m3-adapter.js';
import * as THREE from 'three';
import { createKnowledge } from '../src/knowledge.js';

const snapshot = JSON.parse(readFileSync(new URL('../../../exchange/m3/graph.json', import.meta.url)));
const small = () => ({ nodes: [
  { id: 'job:a', type: 'job', name_zh: '工程师', source: ['boss'] },
  { id: 'skill:c', type: 'skill', name: 'c++' },
  { id: 'skill:c%23', type: 'skill', name: 'c#' },
], edges: [
  { source: 'job:a', target: 'skill:c', type: 'REQUIRES', is_required: null, weight: null },
  { source: 'job:a', target: 'skill:c', type: 'REQUIRES', is_required: false },
] });

test('adapter preserves every official identity, edge occurrence and raw source index', () => {
  assert.equal(typeof adapter.adaptM3, 'function');
  const graph = adapter.adaptM3(snapshot);
  assert.equal(graph.nodes.length, 7845); assert.equal(graph.edges.length, 11412);
  graph.nodes.forEach((node, index) => {
    assert.equal(node.id, snapshot.nodes[index].id); assert.equal(node.raw, snapshot.nodes[index]);
    assert.equal(node.sourceIndex, index); assert.ok(node.position.every(Number.isFinite));
    assert.equal(node.demo, false);
  });
  graph.edges.forEach((edge, index) => { assert.equal(edge.raw, snapshot.edges[index]); assert.equal(edge.sourceIndex, index); });
  assert.deepEqual(graph.provenance.nodeKinds, { job: 717, skill: 4671, industry: 2457 });
  assert.deepEqual(graph.provenance.edgeKinds, { REQUIRES: 8866, APPLIES_TO: 2539, RELATED_TO: 7 });
  assert.deepEqual(adapter.adaptM3(snapshot).nodes.map(n => n.position), graph.nodes.map(n => n.position));
});

test('legacy collisions, parallel edges and null requirements are retained without canonical repair', () => {
  const graph = adapter.adaptM3(small());
  assert.deepEqual(graph.nodes.map(n => n.id), ['job:a', 'skill:c', 'skill:c%23']);
  assert.equal(graph.edges.length, 2); assert.equal(graph.edges[0].raw.is_required, null);
  assert.equal(graph.edges[0].raw.weight, null); assert.equal(graph.edges[1].raw.is_required, false);
});

test('invalid contracts fail rather than silently dropping data or inventing demo nodes', () => {
  for (const mutate of [
    g => g.nodes.push(g.nodes[0]), g => g.nodes[0].id = '',
    g => g.nodes[0].type = 'invented', g => g.edges[0].target = 'missing',
    g => g.edges[0].type = 'invented', g => g.edges[0].source = 4,
    g => g.nodes[0].type = ['job'], g => g.nodes[0].type = {},
    g => g.nodes[0].type = null, g => g.nodes[0].type = 0,
  ]) { const graph = small(); mutate(graph); assert.throws(() => adapter.adaptM3(graph)); }
  assert.throws(() => adapter.adaptM3({ nodes: [] }));
});

test('filters expose only induced edges and exact one-hop focus, including empty results', () => {
  const graph = adapter.adaptM3(small());
  let view = adapter.filterGraph(graph, { kind: 'skill' });
  assert.deepEqual([...view.nodeIds], ['skill:c', 'skill:c%23']); assert.deepEqual(view.edgeIndices, []);
  view = adapter.filterGraph(graph, { query: '工程师' }); assert.deepEqual([...view.nodeIds], ['job:a']);
  view = adapter.filterGraph(graph, { query: 'not-found' }); assert.equal(view.nodeIds.size, 0);
  view = adapter.filterGraph(graph, { focus: 'job:a' });
  assert.deepEqual([...view.nodeIds], ['job:a', 'skill:c']); assert.deepEqual(view.edgeIndices, [0, 1]);
  view = adapter.filterGraph(graph, { relation: 'RELATED_TO' }); assert.deepEqual(view.edgeIndices, []);
});

test('full graph renders in three batches, and high-degree selection keeps all links with bounded brightness', () => {
  const graph = adapter.adaptM3(snapshot), scene = new THREE.Scene();
  const knowledge = createKnowledge(scene, graph);
  assert.equal(scene.children.length, 3);
  knowledge.select('skill:python');
  assert.equal(knowledge.counts().highlightedEdges, 222);
  assert.ok(scene.children[2].material.opacity < .08, 'hundreds of links must not pile up as an opaque central light');
  knowledge.filter(adapter.filterGraph(graph, { kind: 'job' }));
  assert.equal(knowledge.counts().highlightedEdges, 0);
  assert.equal(knowledge.counts().visibleNodes, 717); assert.equal(knowledge.counts().visibleEdges, 7);
  knowledge.filter(adapter.filterGraph(graph, { query: 'not-present-261018' }));
  assert.equal(knowledge.pick(800, 450, new THREE.PerspectiveCamera(), 1600, 900), null);
  scene.children.forEach(object => { object.geometry.dispose(); object.material.dispose(); });
});
