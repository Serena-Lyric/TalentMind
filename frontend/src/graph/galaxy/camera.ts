import * as THREE from 'three'
import CameraControls from 'camera-controls'
import type { Bounds } from '../nebulaEdges'

CameraControls.install({THREE})
export interface CameraState {
 position:[number,number,number];target:[number,number,number];up:[number,number,number]
 quaternion:[number,number,number,number];distance:number;roll:number;fov:number;zoom:number
}
export function cameraKey(event:KeyboardEvent,composing=false) {
 if(composing||event.isComposing||event.keyCode===229||event.defaultPrevented||event.ctrlKey||event.altKey||event.metaKey||event.shiftKey)return null
 const path=[event.target,...(event.composedPath?.()||[])] as (Element|null)[]
 if(path.some(t=>t?.closest?.('input, textarea, select, button, a, summary, [role="textbox"], [contenteditable]:not([contenteditable="false"])')))return null
 const key=event.key.toLowerCase()
 return ['w','a','s','d','q','e','r'].includes(key)?key:null
}
export function createGalaxyCamera() {
 const camera=new THREE.PerspectiveCamera(43,1,.1,2400)
 camera.position.set(42,180,188)
 // Intentionally no DOM connection: one input adapter owns all mouse/keyboard actions.
 const controls=new CameraControls(camera),displayCamera=camera.clone()
 controls.minDistance=8;controls.maxDistance=1600;controls.smoothTime=.22;controls.draggingSmoothTime=.08
 controls.setLookAt(42,180,188,0,0,0,false)
 let roll=0,rollEnd=0,width=1,height=1,revision=0
 const lastPosition=new THREE.Vector3(),lastQuaternion=new THREE.Quaternion()
 const sync=()=>{
  displayCamera.copy(camera);displayCamera.rotateZ(roll);displayCamera.updateMatrixWorld();lastPosition.copy(camera.position);lastQuaternion.copy(camera.quaternion);revision++
 }
 const update=(delta:number)=>{
  const changed=controls.update(delta),oldRoll=roll
  if(Math.abs(rollEnd-roll)<1e-7)roll=rollEnd
  else if(delta>0)roll+=(rollEnd-roll)*(1-Math.exp(-delta*18))
  const moved=!camera.position.equals(lastPosition)||!camera.quaternion.equals(lastQuaternion)
  if(changed||oldRoll!==roll||moved)sync()
  return changed||oldRoll!==roll||moved
 }
 update(0);sync()
 const stopAtCurrent=()=>{
  const position=controls.getPosition(new THREE.Vector3(),false),target=controls.getTarget(new THREE.Vector3(),false)
  // camera-controls.stop() snaps to the old endpoint; rebase both internal states first.
  controls.stop();controls.setLookAt(position.x,position.y,position.z,target.x,target.y,target.z,false);rollEnd=roll
 }
 const capture=():CameraState=>({position:controls.getPosition(new THREE.Vector3(),false).toArray(),target:controls.getTarget(new THREE.Vector3(),false).toArray(),up:camera.up.toArray(),quaternion:displayCamera.quaternion.toArray(),distance:controls.distance,roll,fov:camera.fov,zoom:camera.zoom})
 const restore=(state:CameraState,smooth=true)=>{
  stopAtCurrent();camera.up.fromArray(state.up);controls.updateCameraUp();camera.fov=state.fov;camera.zoom=state.zoom;camera.updateProjectionMatrix()
  rollEnd=state.roll;if(!smooth)roll=rollEnd
  controls.setLookAt(...state.position,...state.target,smooth);update(0);sync()
 }
 const viewScratch=new THREE.Vector3(),projectScratch=new THREE.Vector3()
 const project=(point:THREE.Vector3)=>{
  const view=viewScratch.copy(point).applyMatrix4(displayCamera.matrixWorldInverse),p=projectScratch.copy(point).project(displayCamera)
  return {x:(p.x+1)*width/2,y:(1-p.y)*height/2,depth:-view.z,visible:-view.z>=camera.near&&-view.z<=camera.far&&Number.isFinite(p.x)&&Number.isFinite(p.y)}
 }
 const pan=(dx:number,dy:number,smooth=false)=>{
  stopAtCurrent()
  const unit=2*controls.distance*Math.tan(THREE.MathUtils.degToRad(camera.fov/2))/height/camera.zoom
  const movement=new THREE.Vector3(-dx*unit,dy*unit,0).applyQuaternion(displayCamera.quaternion)
  const target=controls.getTarget(new THREE.Vector3(),false).add(movement)
  controls.moveTo(target.x,target.y,target.z,smooth);update(0);sync()
 }
 const fit=(points:THREE.Vector3[],area:Bounds,smooth=true)=>{
  if(!points.length)return
  stopAtCurrent()
  const sphere=new THREE.Box3().setFromPoints(points).getBoundingSphere(new THREE.Sphere())
  const fraction=Math.min(Math.max(1,area.right-area.left)/width,Math.max(1,area.bottom-area.top)/height)
  const halfFov=Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*Math.min(1,width/height))
  const distance=Math.min(controls.maxDistance,Math.max(controls.minDistance,sphere.radius/Math.sin(halfFov)/fraction*1.12))
  const unit=2*distance*Math.tan(THREE.MathUtils.degToRad(camera.fov/2))/height
  const offset=new THREE.Vector3((width-area.left-area.right)/2*unit,(area.top+area.bottom-height)/2*unit,0).applyQuaternion(displayCamera.quaternion)
  const target=sphere.center.clone().add(offset)
  const direction=camera.position.clone().sub(controls.getTarget(new THREE.Vector3(),false)).normalize()
  const position=target.clone().addScaledVector(direction,distance)
  controls.setLookAt(position.x,position.y,position.z,target.x,target.y,target.z,smooth);update(0);sync()
 }
 const initial=capture()
 return {camera,displayCamera,controls,project,pan,fit,capture,restore,update,
  get roll(){return roll},get revision(){return revision},
  get scale(){return height/(2*controls.distance*Math.tan(THREE.MathUtils.degToRad(camera.fov/2)))*camera.zoom/30},
  resize(w:number,h:number){width=w;height=h;camera.aspect=w/h;camera.updateProjectionMatrix();sync()},
  rollBy(delta:number){roll+=delta;rollEnd=roll;sync()},
  orbit(dx:number,dy:number){stopAtCurrent();const c=Math.cos(roll),s=Math.sin(roll);controls.rotate(-(dx*c-dy*s)*.006,-(dx*s+dy*c)*.006,false);update(0);sync()},
  zoom(direction:number){stopAtCurrent();controls.dollyTo(THREE.MathUtils.clamp(controls.distance*Math.exp(direction*.14),controls.minDistance,controls.maxDistance),false);update(0);sync()},
  focus(point:THREE.Vector3,area:Bounds){
   stopAtCurrent()
   const screen=project(point)
   if(screen.visible&&screen.x>area.left+24&&screen.x<area.right-24&&screen.y>area.top+24&&screen.y<area.bottom-24)return
   const target=point.clone(),unit=2*controls.distance*Math.tan(THREE.MathUtils.degToRad(camera.fov/2))/height
   target.add(new THREE.Vector3((width-area.left-area.right)/2*unit,(area.top+area.bottom-height)/2*unit,0).applyQuaternion(displayCamera.quaternion))
   controls.moveTo(target.x,target.y,target.z,true)
  },
  reset(area:Bounds){restore(initial,false);controls.dollyTo(initial.distance*Math.max(1,640/Math.max(160,area.right-area.left)),false);update(0);sync()},
  dispose(){controls.dispose()},
 }
}
export type GalaxyCamera=ReturnType<typeof createGalaxyCamera>
