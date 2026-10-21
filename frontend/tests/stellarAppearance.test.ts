import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Vector3 } from 'three'
import { stellarProfile, stellarSize, transitionDust, STELLAR_VERSION } from '../src/graph/galaxy/stellarAppearance.ts'

test('恒星外观只依赖稳定ID与显式预设，四类均可复现',()=>{
 const types=new Set(Array.from({length:100},(_,i)=>stellarProfile('real:'+i).type))
 assert.equal(types.size,4)
 assert.deepEqual(stellarProfile('skill:python'),stellarProfile('skill:python'))
 assert.equal(stellarProfile('skill:python','red-giant').type,'red-giant')
 assert.match(STELLAR_VERSION,/v1/)
})
test('近景尺寸连续有上限，选中细节逐渐增强，无距离阈值跳变',()=>{
 for(const scale of [.01,.2,.8,1,10,100]){
  assert.ok(stellarSize(scale,false).radius<=7)
  assert.ok(stellarSize(scale,true).radius<=28)
  assert.ok(Math.abs(stellarSize(scale,true).radius-stellarSize(scale+.0001,true).radius)<.02)
 }
 assert.ok(stellarSize(5,true).radius>stellarSize(.01,true).radius)
 assert.ok((stellarSize(100,true,64,1.5).radius*2.6+4)*2*1.5<=64)
})
test('装饰过渡层可复现、独立计数且不改写真实坐标',()=>{
 const positions=new Map([['skill:python',new Vector3(12,3,6)],['job:a',new Vector3(80,-2,25)]])
 const before=[...positions].map(([id,p])=>[id,p.toArray()])
 const a=transitionDust(positions),b=transitionDust(positions)
 assert.deepEqual(a,b);assert.equal(a.count,24)
 assert.deepEqual([...positions].map(([id,p])=>[id,p.toArray()]),before)
 assert.equal(a.position.length,a.count*3)
})
