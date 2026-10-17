import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateDemo, generateParticles } from '../src/generate.js';
import { FAMILIES } from '../src/config.js';

test('synthetic graph is deterministic, explicitly demo, and every curve has real sample endpoints', () => {
  const graph = generateDemo(); assert.deepEqual(graph, generateDemo());
  const ids = new Set(graph.nodes.map(node => node.id)); assert.equal(ids.size, graph.nodes.length);
  assert.equal(FAMILIES.length, 8); assert.equal(new Set(graph.nodes.map(node => node.type)).size, 5);
  assert.ok(graph.nodes.some(node => node.families.length > 1));
  assert.ok(graph.nodes.every(node => node.demo && node.position.every(Number.isFinite)));
  assert.ok(graph.edges.every(edge => edge.demo && ids.has(edge.source) && ids.has(edge.target)));
});

test('decorative positions repeat exactly and contain three dimensional depth', () => {
  const a = generateParticles('stars'), b = generateParticles('stars');
  assert.deepEqual(a.position, b.position);
  const heights = a.position.filter((_, index) => index % 3 === 1);
  assert.ok(Math.max(...heights) - Math.min(...heights) > 10);
});
