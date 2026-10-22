import {test} from 'node:test'
import assert from 'node:assert/strict'
import {graphComponent} from './helpers/graphComponent.ts'
import {createGalaxySpatialFieldCache} from '../src/graph/galaxy/GalaxySpatialField.ts'
import {createDust} from '../src/graph/galaxy/particles.js'
import {Group, Points} from 'three'
import {fileURLToPath} from 'node:url'
import {createGalaxyCamera} from '../src/graph/galaxy/camera.ts'

test('空间回退保留真实数据集与相机参数',t=>{
 const app=graphComponent(undefined,'?graphDataset=real&graphSpace=node-field-v1&graphCamera=fixed');t.after(app.stop)
 assert.equal(app.state.legacySpaceHref,'?graphDataset=real&graphSpace=legacy&graphCamera=fixed#/graph')
})

test('空间默认使用节点场，显式旧版、固定相机和受控对照保持回退',t=>{
 for(const [search,enabled] of [
  ['',true],
  ['?graphSpace=node-field-v1',true],
  ['?graphDataset=real',true],
  ['?graphSpace=legacy',false],
  ['?graphCamera=fixed',false],
  ['?graphCompare=overview',false],
  ['?graphVisual=p21',false],
 ] as const){
  const app=graphComponent(undefined,search);t.after(app.stop)
  assert.equal(app.state.nodeFieldMode,enabled,search||'普通菜单入口')
 }
})

test('default Vue layout path refreshes field coordinates and failed reload releases stale knowledge',async t=>{
 const app=graphComponent(undefined,'?nebulaDebug=1');t.after(app.stop)
 const s=app.state,scene=new Group(),dust=createDust(scene),cache=createGalaxySpatialFieldCache()
 globalThis.DOMRect??=class {x=0;y=0;width=0;height=0} as typeof DOMRect
 globalThis.window={devicePixelRatio:1} as any;t.after(()=>{delete (globalThis as any).window})
 const rig=createGalaxyCamera();t.after(rig.dispose);rig.resize(1200,800);s.cameraRig.value=rig
 const knowledge=app.load(fileURLToPath(new URL('../src/graph/galaxy/knowledge.ts',import.meta.url))).createSpatialKnowledge(rig)
 t.after(knowledge.dispose);s.spatialKnowledge=knowledge
 const layer=scene.children[0] as Points,positions=knowledge.positions
 s.galaxy={stats:()=>cache.stats(),setSpatialField(input:any){dust.setField(input?cache.get(input):null);if(!input)cache.clear()}}
 const data={nodes:[{id:'a',kind:'skill',label:'a'}],edges:[],stats:{totalNodes:1,totalEdges:0}}
 s.artifact.value={schema_version:'test',snapshot_sha256_lf:'first',nodes:[{id:'a',x:1800,y:300,degree:1}]}
 await s.buildLayout(data,0)
 const first=layer.geometry.getAttribute('position')
 assert.ok(first.array.some((v:number,i:number)=>i%3===0&&v>100))
 s.artifact.value={...s.artifact.value,snapshot_sha256_lf:'second',nodes:[{id:'a',x:-1800,y:300,degree:1}]}
 await s.buildLayout(data,0)
 assert.notDeepEqual(layer.geometry.getAttribute('position').array,first.array)
 const nodes=[...data.nodes,{id:'b',kind:'skill',label:'b'}],edges=[{source:'a',target:'b',kind:'REQUIRES',sourceIndex:0}]
 knowledge.setData(nodes,edges,[...s.artifact.value.nodes,{id:'b',x:120,y:10,degree:1}])
 knowledge.update(s.canvasRef.value,{activeKinds:new Set(['skill']),selectedId:'a',focusIds:new Set(['a','b']),priority:new Set(['a','b']),matches:new Set(),hoveredId:null,panels:[],showDerived:false,derived:[]})
 const lines=knowledge.group.children.find((c:any)=>c.isLineSegments)
 assert.equal(lines.geometry.drawRange.count,24)
 await s.loadGraph()
 assert.equal(s.graphData.value.nodes.length,0);assert.equal(positions.size,0);assert.equal(cache.stats().entries,0)
 assert.equal(lines.geometry.drawRange.count,0,'failed reload must not leave old selected relations on screen')
 for(const item of scene.children as Points[]){item.geometry.dispose();(item.material as any).dispose()}
})
