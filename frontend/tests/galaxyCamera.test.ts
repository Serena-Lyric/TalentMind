import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as THREE from 'three'
import { createGalaxyCamera, cameraKey } from '../src/graph/galaxy/camera.ts'
import { spatialPoint } from '../src/graph/galaxy/spatialLayout.ts'

// camera-controls creates an unused DOM rectangle even when no input DOM is connected.
globalThis.DOMRect ??= class {x=0;y=0;width=0;height=0} as typeof DOMRect

const close=(a:number,b:number)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`)
test('roll survives orbit and dolly and restores complete off-center camera state',()=>{
 const rig=createGalaxyCamera()
 rig.resize(1200,800)
 rig.controls.setLookAt(80,120,160,12,3,-9,false);rig.update(0)
 rig.rollBy(1.1);rig.update(0)
 const saved=rig.capture(),orientation=rig.displayCamera.quaternion.clone()
 rig.controls.rotate(.7,.3,false);rig.zoom(1);rig.update(0)
 close(rig.roll,1.1)
 rig.restore(saved,false);rig.update(0)
 assert.deepEqual(rig.capture(),saved)
 close(orientation.angleTo(rig.displayCamera.quaternion),0)
 rig.dispose()
})
test('screen translation follows rolled display right and up and keeps orbit distance',()=>{
 const rig=createGalaxyCamera();rig.resize(1200,800);rig.update(0);rig.rollBy(Math.PI/2)
 const before=rig.capture(),right=new THREE.Vector3(1,0,0).applyQuaternion(rig.displayCamera.quaternion)
 rig.pan(80,0,false);rig.update(0)
 const after=rig.capture(),movement=new THREE.Vector3(...after.target).sub(new THREE.Vector3(...before.target))
 close(Math.abs(movement.normalize().dot(right)),1);close(after.distance,before.distance)
 assert.ok(movement.dot(right)<0,'dragging right moves the target to screen left')
 rig.dispose()
})
test('3D fit includes every point inside asymmetric panel-free area after roll',()=>{
 const rig=createGalaxyCamera();rig.resize(1200,800);rig.rollBy(2.4)
 const points=[new THREE.Vector3(-95,7,-60),new THREE.Vector3(95,-9,60),new THREE.Vector3(0,14,0)]
 const area={left:280,right:800,top:20,bottom:760}
 rig.fit(points,area,false);rig.update(0)
 for(const p of points){const s=rig.project(p);assert.ok(s.visible);assert.ok(s.x>=area.left&&s.x<=area.right);assert.ok(s.y>=area.top&&s.y<=area.bottom)}
 rig.dispose()
})
test('projected node hits stay tied to identity at multiple azimuths and reject behind camera',()=>{
 const rig=createGalaxyCamera();rig.resize(1200,800)
 const p=new THREE.Vector3(8,4,-7)
 for(const angle of [0,Math.PI/2,Math.PI,Math.PI*1.5]){
  rig.controls.rotateTo(angle,.9,false);rig.update(0)
  const screen=rig.project(p);assert.ok(screen.visible)
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(screen.x/600-1,1-screen.y/400),rig.displayCamera)
  close(ray.ray.distanceToPoint(p),0)
 }
 assert.equal(rig.project(rig.displayCamera.position.clone().add(rig.displayCamera.getWorldDirection(new THREE.Vector3()).multiplyScalar(-10))).visible,false)
 rig.dispose()
})
test('camera hotkeys protect inputs, composition and browser modifier shortcuts',()=>{
 const event=(changes:any={})=>({key:'w',target:null,composedPath:()=>[],...changes}) as KeyboardEvent
 assert.equal(cameraKey(event()),'w')
 for(const changes of [{ctrlKey:true},{altKey:true},{metaKey:true},{shiftKey:true},{isComposing:true},{keyCode:229},{defaultPrevented:true},{target:{closest:()=>({})}}])assert.equal(cameraKey(event(changes)),null)
 assert.equal(cameraKey(event(),true),null)
 assert.equal(cameraKey(event({key:'x'})),null)
})
test('display depth is deterministic, spatial and never mutates layout or node facts',()=>{
 const node={id:'skill:python',kind:'skill' as const},layout={x:90,y:60}
 const copy=JSON.stringify({node,layout}),a=spatialPoint(node,layout),b=spatialPoint(node,layout)
 assert.deepEqual(a,b);close(a.x,3);close(a.z,2)
 assert.notEqual(a.y,spatialPoint({id:'skill:java',kind:'skill'},layout).y)
 assert.equal(JSON.stringify({node,layout}),copy)
})
test('reset restores the galaxy center orbit and default roll without oversized sphere framing',()=>{
 const rig=createGalaxyCamera();rig.resize(1200,800);rig.pan(100,40);rig.rollBy(2)
 rig.reset({left:280,right:1200,top:0,bottom:800})
 for(let i=0;i<120;i++)rig.update(1/60)
 const state=rig.capture();state.target.forEach(v=>close(v,0));close(state.roll,0);assert.ok(state.distance<300)
 rig.dispose()
})
test('smooth restore terminates exactly at the saved pose and interrupts previous transition',()=>{
 const rig=createGalaxyCamera();rig.resize(1200,800);rig.rollBy(.8);const saved=rig.capture()
 rig.controls.setLookAt(300,40,20,90,2,3,true)
 for(let i=0;i<12;i++)rig.update(1/60)
 rig.restore(saved,true)
 for(let i=0;i<160;i++)rig.update(1/60)
 assert.deepEqual(rig.capture(),saved)
 const atRest=rig.capture();rig.update(1/60);assert.deepEqual(rig.capture(),atRest)
 rig.dispose()
})
test('manual pan during a focus flight starts at the displayed target without jumping to its endpoint',()=>{
 const rig=createGalaxyCamera();rig.resize(1200,800)
 const area={left:0,right:1200,top:0,bottom:800}
 rig.focus(new THREE.Vector3(220,0,0),area);rig.update(1/60)
 const before=rig.capture();rig.pan(1,0,false);const after=rig.capture()
 assert.ok(new THREE.Vector3(...after.target).distanceTo(new THREE.Vector3(...before.target))<1)
 rig.dispose()
})
test('switching to a currently visible search result cancels the previous offscreen flight',()=>{
 const rig=createGalaxyCamera();rig.resize(1200,800)
 const area={left:0,right:1200,top:0,bottom:800}
 rig.focus(new THREE.Vector3(220,0,0),area);rig.update(1/60)
 rig.focus(new THREE.Vector3(0,0,0),area)
 for(let i=0;i<160;i++)rig.update(1/60)
 const p=rig.project(new THREE.Vector3());assert.ok(p.x>0&&p.x<1200&&p.y>0&&p.y<800)
 rig.dispose()
})
test('the display camera receives the final snap even when controller update returns false',()=>{
 const rig=createGalaxyCamera();rig.resize(1200,800);const saved=rig.capture()
 rig.controls.setLookAt(300,50,200,90,7,-8,false);rig.update(0);rig.restore(saved,true)
 for(let i=0;i<300;i++)rig.update(1/60)
 assert.deepEqual(rig.displayCamera.position.toArray(),rig.capture().position)
 rig.dispose()
})
