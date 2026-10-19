import * as THREE from 'three'
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js'
// @ts-expect-error P1-A.2 original JS art module, selectively reused from e7771d0.
import { createDust } from './particles.js'
// @ts-expect-error P1-A.2 art parameters (not a business taxonomy).
import { CONFIG } from './config.js'
import type { Transform } from '../nebulaViewport'
import type { GraphNode } from '../../api/graph'
import type { Point } from '../nebulaViewport'
import type { VisualVariant } from '../comparisonView'
// @ts-expect-error Original P1-A.2 knowledge shader; replay only, no synthetic data fallback.
import { createKnowledge } from './p1a2Knowledge.js'

export function createGalaxyBackground(canvas:HTMLCanvasElement, view:()=>Transform, onFailure:()=>void, options:{visual:VisualVariant;frozen:boolean}={visual:'p22',frozen:false}) {
  const renderer = new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'})
  renderer.setClearColor('#000001'); renderer.toneMapping=THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure=CONFIG.render.exposure
  const scene=new THREE.Scene(), camera=new THREE.OrthographicCamera(-100,100,100,-100,.1,1600)
  camera.position.z=700
  const dustGroup=new THREE.Group();scene.add(dustGroup)
  const dust=createDust(dustGroup,options.visual==='p22')
  // Fixed tilted disk: same transform as #28 knowledge Canvas, no orbit or auto-flight.
  dustGroup.rotation.x=Math.asin(.65)
  const referenceGroup=new THREE.Group();scene.add(referenceGroup)
  let knowledge:any=null,referenceNodes:unknown=null
  const disposeObjects=(group:THREE.Object3D)=>group.traverse(object=>{
    const points=object as THREE.Points
    points.geometry?.dispose();const materials=Array.isArray(points.material)?points.material:[points.material];materials.forEach(m=>m?.dispose())
  })
  const composer=new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene,camera))
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(1,1),CONFIG.render.bloomStrength,CONFIG.render.bloomRadius,CONFIG.render.bloomThreshold))
  composer.addPass(new OutputPass())
  let width=0,height=0,previous=0,clock=0,frame=0,stopped=false
  const samples:number[]=[]
  const renderSamples:number[]=[]
  function resize(w:number,h:number) {
    width=w;height=h
    const dpr=Math.min(devicePixelRatio||1,CONFIG.render.dpr)
    renderer.setPixelRatio(dpr);renderer.setSize(w,h,false)
    composer.setPixelRatio(dpr);composer.setSize(w,h);dust.resize(h,dpr)
  }
  function animate(time:number) {
    if(stopped) return
    frame=requestAnimationFrame(animate)
    if(document.hidden || !width || !height) {previous=0;return}
    const start=performance.now()
    if(previous) {samples.push(time-previous);if(samples.length>600)samples.shift()}
    clock+=previous?Math.min(.05,(time-previous)/1000)*CONFIG.motion.initial:0;previous=time
    const t=view(), unit=30*t.scale
    camera.left=-width/(2*unit);camera.right=width/(2*unit);camera.top=height/(2*unit);camera.bottom=-height/(2*unit)
    camera.position.set(-t.x/30,t.y/30,700);camera.updateProjectionMatrix();camera.updateMatrixWorld()
    // Point shader uses perspective sizing; scale pixels to the equivalent fixed projection.
    dust.resize(700*unit,Math.min(devicePixelRatio||1,CONFIG.render.dpr))
    dust.update(options.frozen?0:clock)
    knowledge?.resize(700*unit,Math.min(devicePixelRatio||1,CONFIG.render.dpr))
    try {composer.render()} catch {stopped=true;cancelAnimationFrame(frame);onFailure()}
    renderSamples.push(performance.now()-start);if(renderSamples.length>600)renderSamples.shift()
  }
  const lost=(event:Event)=>{event.preventDefault();stopped=true;cancelAnimationFrame(frame);onFailure()}
  canvas.addEventListener('webglcontextlost',lost)
  frame=requestAnimationFrame(animate)
  const percentiles=(values:number[])=>{
    const sorted=[...values].sort((a,b)=>a-b)
    return {samples:sorted.length,p50:sorted[Math.floor(sorted.length*.5)]??null,p95:sorted[Math.floor(sorted.length*.95)]??null}
  }
  return {resize,
    reference(nodes:(GraphNode&{point:Point})[],ids:Set<string>,selected:string|null) {
      if(options.visual!=='p1a2')return
      if(referenceNodes!==nodes){disposeObjects(referenceGroup);referenceGroup.clear();knowledge=createKnowledge(referenceGroup,{nodes:nodes.map(n=>({id:n.id,type:n.kind==='job'?0:n.kind==='skill'?2:3,position:[n.point.x/30,-n.point.y/30,0]})),edges:[]});referenceNodes=nodes}
      knowledge.filter({nodeIds:ids,edgeIndices:[]});knowledge.select(selected)
    },
    stats:()=>({frames:percentiles(samples),renderSubmissionMs:percentiles(renderSamples),particles:dust.count,visual:options.visual,frozen:options.frozen,clock:options.frozen?0:clock,dpr:renderer.getPixelRatio(),fixedProjection:'orthographic',referenceKnowledge:knowledge?.counts(),renderer:renderer.capabilities.isWebGL2?'WebGL2':'WebGL'}),
    dispose(){stopped=true;cancelAnimationFrame(frame);canvas.removeEventListener('webglcontextlost',lost);disposeObjects(scene);composer.passes.forEach(pass=>pass.dispose());composer.dispose();renderer.dispose()}
  }
}
