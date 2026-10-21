import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { GraphNode } from '../src/api/graph.ts'
import { searchNodes, nextSearchIndex } from '../src/graph/nebulaViewport.ts'

const node = (id: string, label: string, kind: GraphNode['kind'] = 'skill'): GraphNode => ({id,label,kind,size:10,color:''})
test('python 87个结果精确名称先行，下一项遍历其余86项且可反向循环', () => {
  const graph = [...Array.from({length:86},(_,i)=>node('v'+i, 'Python '+i)), node('exact','Python')]
  const matches = searchNodes(graph,'python',new Set(['skill']))
  assert.equal(matches.length,87)
  assert.equal(matches[0].id,'exact')
  let cursor = -1
  const visited = new Set<string>()
  for (let i=0;i<87;i++) { cursor=nextSearchIndex(cursor,matches.length,1); visited.add(matches[cursor].id) }
  assert.equal(visited.size,87)
  assert.equal(cursor,86)
  assert.equal(nextSearchIndex(cursor,87,1),0)
  assert.equal(nextSearchIndex(0,87,-1),86)
  assert.equal(nextSearchIndex(1,87,-1),0)
  assert.deepEqual(matches,searchNodes([...graph].reverse(),'python',new Set(['skill'])))
})
test('空结果/空词不索引，刷新后越界游标从稳定端点重新开始', () => {
  assert.equal(nextSearchIndex(-1,0,1),-1)
  assert.equal(nextSearchIndex(90,2,1),0)
  assert.equal(nextSearchIndex(90,2,-1),1)
  assert.equal(nextSearchIndex(-1,2,-1),1)
  assert.deepEqual(searchNodes([node('a','Python')],' ',new Set(['skill'])),[])
  assert.deepEqual(searchNodes([node('a','Python')],'python',new Set(['job'])),[])
})
