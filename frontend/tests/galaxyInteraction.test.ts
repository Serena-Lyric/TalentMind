import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createGalaxyCamera } from '../src/graph/galaxy/camera.ts'
import { graphComponent } from './helpers/graphComponent.ts'

globalThis.DOMRect ??= class {x=0;y=0;width=0;height=0} as typeof DOMRect
const event=(changes:any={})=>({key:'w',preventDefault(){},composedPath:()=>[],...changes})
test('the actual Vue right drag pans in rolled screen space and wheel never rotates',t=>{
 const app=graphComponent();t.after(app.stop)
 const rig=createGalaxyCamera();t.after(rig.dispose);app.state.cameraRig.value=rig;rig.resize(1200,800);rig.rollBy(1.2)
 app.state.canvasRef.value.setPointerCapture=()=>{}
 const before=rig.capture()
 app.state.onPointerDown({button:2,clientX:500,clientY:400,pointerId:1})
 app.state.onPointerMove({clientX:560,clientY:420})
 const panned=rig.capture();assert.notDeepEqual(panned.target,before.target);assert.deepEqual(panned.quaternion,before.quaternion)
 app.state.onPointerUp()
 app.state.onWheel({clientX:600,clientY:400,deltaY:-120})
 assert.equal(rig.roll,1.2);assert.ok(rig.capture().distance<panned.distance)
 const zoomed=rig.capture();app.state.onWheel({clientX:600,clientY:400,deltaY:-120,ctrlKey:true});assert.deepEqual(rig.capture(),zoomed)
})
test('actual Vue keyboard lifecycle clears held motion on composition, modifier and blur',t=>{
 const app=graphComponent();t.after(app.stop)
 const rig=createGalaxyCamera();t.after(rig.dispose);app.state.cameraRig.value=rig
 const s=app.state
 s.cameraKeydown(event());assert.deepEqual([...s.cameraKeys],['w'])
 s.cameraKeyup(event());assert.equal(s.cameraKeys.size,0)
 s.cameraKeydown(event());s.compositionStart();assert.equal(s.cameraKeys.size,0)
 s.cameraKeydown(event());assert.equal(s.cameraKeys.size,0)
 s.compositionEnd();s.cameraKeydown(event());s.cameraKeydown(event({key:'Control',ctrlKey:true}));assert.equal(s.cameraKeys.size,0)
 s.cameraKeydown(event());s.clearCameraKeys();assert.equal(s.cameraKeys.size,0)
})
test('a click with pointer jitter below the Vue drag threshold preserves the complete camera',t=>{
 const app=graphComponent();t.after(app.stop)
 const rig=createGalaxyCamera();t.after(rig.dispose);app.state.cameraRig.value=rig
 app.state.canvasRef.value.setPointerCapture=()=>{}
 const saved=rig.capture()
 app.state.onPointerDown({button:0,clientX:500,clientY:400,pointerId:1})
 app.state.onPointerMove({clientX:501,clientY:401});app.state.onPointerUp()
 assert.equal(app.state.drag.moved,false);assert.deepEqual(rig.capture(),saved)
})
