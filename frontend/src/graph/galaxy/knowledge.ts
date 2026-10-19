import * as THREE from 'three'
import type { GraphNode, GraphEdge } from '../../api/graph'
import type { Bounds } from '../nebulaEdges'
import { createStarSprites, starAppearance, placeStarLabels, type StarLabel } from '../starPresentation'
import { visibleKnowledgeIds, type LayoutNode } from '../historicalSnapshot'
import { spatialPoint, DEPTH_VERSION } from './spatialLayout'
import { relationCurve, spatialRelations, pickProjected, derivedSpatialEdges } from './spatialKnowledge'
import type { GalaxyCamera } from './camera'
import { stellarProfile, stellarSize, transitionDust, STELLAR_VERSION, STELLAR_TYPES, type StellarType } from './stellarAppearance'
import { createStellarMaterial, createKnowledgeStellarMaterial } from './stellarMaterial'
import { knowledgeProfile, knowledgeColors, screenDensity, densityAppearance, KNOWLEDGE_STELLAR_VERSION } from './visualSemantics'

const colors={job:'#4da6ff',skill:'#2ee66b',industry:'#c77dff'}
type Projection={id:string;x:number;y:number;depth:number;visible:boolean;radius:number}
export function createSpatialKnowledge(rig:GalaxyCamera,stellar=true,version:'p24'|'p25'='p25') {
 const semantic=stellar&&version==='p25'
 const group=new THREE.Group(),positions=new Map<string,THREE.Vector3>(),byId=new Map<string,GraphNode>(),bounds=new Map<GraphEdge,THREE.Box3>()
 const sprites=createStarSprites(colors),textures:THREE.Texture[]=[],pointLayers:{nodes:GraphNode[];object:THREE.Points;radius:Float32Array;outline:Float32Array}[]=[]
 let nodes:GraphNode[]=[],edges:GraphEdge[]=[],meta=new Map<string,LayoutNode>(),dataRevision=0,planKey='',edgeKey='',projection=new Map<string,Projection>(),lastPlan:ReturnType<typeof spatialRelations>|null=null
 let updateCount=0,geometryBuilds=0,labelCacheHits=0
 const metrics=new Map<string,number>()
 let dust:THREE.Points|null=null,dustCount=0,maxPointSize=64
 function disposeDust(){if(dust){group.remove(dust);dust.geometry.dispose();(dust.material as THREE.Material).dispose();dust=null}dustCount=0}
 const lineGeometry=new THREE.BufferGeometry()
 const lineMaterial=new THREE.ShaderMaterial({transparent:true,depthWrite:false,depthTest:false,
  uniforms:{focus:{value:-1},selected:{value:0}},
  vertexShader:`attribute vec3 tint;attribute float sourceIndex;varying vec3 color;varying float edgeId;
   void main(){color=tint;edgeId=sourceIndex;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
  fragmentShader:`uniform float focus,selected;varying vec3 color;varying float edgeId;
   void main(){float emphasis=1.-step(.25,abs(edgeId-focus));float alpha=focus>=0.?mix(.045,.95,emphasis):mix(.16,.27,selected);gl_FragColor=vec4(color,alpha);}`})
 const lines=new THREE.LineSegments(lineGeometry,lineMaterial);lines.frustumCulled=false;lines.renderOrder=1;group.add(lines)
 function disposePoints(){for(const layer of pointLayers){group.remove(layer.object);layer.object.geometry.dispose();(layer.object.material as THREE.Material).dispose()}pointLayers.length=0;textures.forEach(t=>t.dispose());textures.length=0}
 function setData(nextNodes:GraphNode[],nextEdges:GraphEdge[],layout:LayoutNode[]) {
  disposePoints();nodes=nextNodes;edges=nextEdges;meta=new Map(layout.map(n=>[n.id,n]));positions.clear();byId.clear();bounds.clear();projection.clear();metrics.clear();planKey='';edgeKey='';dataRevision++
  for(const node of nodes){byId.set(node.id,node);positions.set(node.id,spatialPoint(node,meta.get(node.id)!))}
  disposeDust()
  if(stellar){
   const data=transitionDust(positions);dustCount=data.count
   const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(data.position,3));geometry.setAttribute('phase',new THREE.BufferAttribute(data.phase,1))
   const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    uniforms:{height:{value:800},dpr:{value:1}},
    vertexShader:`attribute float phase;uniform float height,dpr;varying float tint;void main(){tint=phase;vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=clamp(height*.22/max(1.,-p.z),.6,2.8)*dpr;}`,
    fragmentShader:`varying float tint;void main(){float r=length(gl_PointCoord-.5)*2.;float a=exp(-r*r*3.)*${semantic?'.095':'.15'};if(r>1.)discard;gl_FragColor=vec4(mix(vec3(.34,.43,.73),vec3(.63,.46,.8),tint),a);}`})
   dust=new THREE.Points(geometry,material);dust.frustumCulled=false;group.add(dust)
  }
  for(const edge of edges){const curve=relationCurve(edge,positions);bounds.set(edge,new THREE.Box3().setFromPoints([curve.v0,curve.v1,curve.v2]))}
  for(const kind of ['job','skill','industry'] as const){
   const members=nodes.filter(n=>n.kind===kind),array=new Float32Array(members.length*3),radius=new Float32Array(members.length),outline=new Float32Array(members.length)
   members.forEach((n,i)=>positions.get(n.id)!.toArray(array,i*3))
   const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(array,3));geometry.setAttribute('radius',new THREE.BufferAttribute(radius,1).setUsage(THREE.DynamicDrawUsage));geometry.setAttribute('outline',new THREE.BufferAttribute(outline,1).setUsage(THREE.DynamicDrawUsage))
   geometry.setAttribute('stellarType',new THREE.Float32BufferAttribute(members.map(n=>stellarProfile(n.id).index),1).setUsage(THREE.DynamicDrawUsage));geometry.setAttribute('seed',new THREE.Float32BufferAttribute(members.map(n=>stellarProfile(n.id).seed),1));geometry.setAttribute('emphasis',new THREE.BufferAttribute(new Float32Array(members.length),1).setUsage(THREE.DynamicDrawUsage))
   geometry.setAttribute('haloStrength',new THREE.BufferAttribute(new Float32Array(members.length).fill(1),1).setUsage(THREE.DynamicDrawUsage));geometry.setAttribute('opacity',new THREE.BufferAttribute(new Float32Array(members.length).fill(1),1).setUsage(THREE.DynamicDrawUsage))
   const maxRadius={job:5,skill:3.6,industry:2.8}[kind],sprite=stellar?undefined:sprites.get(kind,maxRadius),texture=sprite?new THREE.CanvasTexture(sprite.canvas):null;if(texture)textures.push(texture)
   const halo={job:2.7,skill:2.4,industry:2.2}[kind]
   const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,depthTest:false,
    uniforms:{sprite:{value:texture},dpr:{value:1},halo:{value:halo}},
    vertexShader:`attribute float radius,outline;uniform float dpr,halo;varying float shown,ring,coreRadius,footprint;
     void main(){shown=step(.001,radius);ring=outline;coreRadius=radius;footprint=2.*(radius*halo+1.);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_PointSize=max(1.,footprint*dpr);}`,
    fragmentShader:`uniform sampler2D sprite;varying float shown,ring,coreRadius,footprint;
     void main(){if(shown<.5)discard;vec4 c=texture2D(sprite,gl_PointCoord);float r=length(gl_PointCoord-.5)*footprint;float ringAlpha=(1.-smoothstep(.3,.9,abs(r-coreRadius-2.)))*ring*.8;c=mix(c,vec4(.9,.96,1.,max(c.a,ringAlpha)),ringAlpha);if(c.a<.005)discard;gl_FragColor=c;}`})
   const actualMaterial=semantic?createKnowledgeStellarMaterial(['job','skill','industry'].indexOf(kind),knowledgeColors[kind]):stellar?createStellarMaterial(['job','skill','industry'].indexOf(kind),colors[kind]):material
   if(stellar)material.dispose()
   const object=new THREE.Points(geometry,actualMaterial);object.frustumCulled=false;object.renderOrder=2;group.add(object);pointLayers.push({nodes:members,object,radius,outline})
  }
 }
 function buildLines(selected:GraphEdge[]) {
  const key=selected.map(e=>e.sourceIndex??`${e.source}|${e.target}`).join(',')
  if(key===edgeKey)return
  edgeKey=key;geometryBuilds++;lineGeometry.dispose()
  const points:number[]=[],tints:number[]=[],indices:number[]=[],progress:number[]=[]
  for(const edge of selected){
   const curve=relationCurve(edge,positions),palette=semantic?knowledgeColors:colors
   const source=new THREE.Color(palette[byId.get(edge.source)!.kind]),target=new THREE.Color(palette[byId.get(edge.target)!.kind]),color=new THREE.Color()
   for(let i=0;i<12;i++)for(const t of [i/12,(i+1)/12]){curve.getPoint(t).toArray(points,points.length);color.copy(source).lerp(target,t);tints.push(color.r,color.g,color.b);indices.push(edge.sourceIndex??-2);progress.push(t)}
  }
  lineGeometry.setAttribute('position',new THREE.Float32BufferAttribute(points,3));lineGeometry.setAttribute('tint',new THREE.Float32BufferAttribute(tints,3));lineGeometry.setAttribute('sourceIndex',new THREE.Float32BufferAttribute(indices,1));lineGeometry.setAttribute('progress',new THREE.Float32BufferAttribute(progress,1));lineGeometry.setDrawRange(0,points.length/3)
 }
 function update(canvas:HTMLCanvasElement,state:{activeKinds:Set<string>;selectedId?:string;focusIds:Set<string>;priority:Set<string>;matches:Set<string>;hoveredId:string|null;focusedEdge?:GraphEdge;panels:Bounds[];showDerived:boolean;derived:GraphEdge[];stellarPreset?:StellarType}) {
  const start=performance.now(),ctx=canvas.getContext('2d')!,width=canvas.clientWidth,height=canvas.clientHeight,dpr=window.devicePixelRatio||1,scale=rig.scale
  const visibleIds=visibleKnowledgeIds(nodes,meta,scale,state.priority)
  if(dust){const material=dust.material as THREE.ShaderMaterial;material.uniforms.height.value=height;material.uniforms.dpr.value=Math.min(dpr,1.5)}
  const key=`${dataRevision}:${[...state.activeKinds]}:${state.selectedId}:${scale<.35?0:scale<.9?1:2}:${[...state.priority]}:${!state.selectedId?rig.revision:0}`
  if(planKey!==key){
   planKey=key
   const frustum=new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(rig.displayCamera.projectionMatrix,rig.displayCamera.matrixWorldInverse))
   lastPlan=spatialRelations(edges,byId,positions,{visibleIds,activeKinds:state.activeKinds,selectedId:state.selectedId,scale,frustum,bounds})
  }
  const plan=lastPlan!,highlight=new Set(state.focusedEdge?[state.focusedEdge.source,state.focusedEdge.target]:[])
  const derived=state.showDerived?derivedSpatialEdges(state.derived,byId,visibleIds,state.activeKinds):[]
  buildLines([...plan.edges,...derived]);lineMaterial.uniforms.focus.value=state.focusedEdge?.sourceIndex??-1;lineMaterial.uniforms.selected.value=state.selectedId?1:0
  projection.clear()
  // Project once, then evaluate the continuous occupancy field. No density-based culling.
  const projected=new Map<string,ReturnType<GalaxyCamera['project']>>()
  for(const node of nodes)if(state.activeKinds.has(node.kind)&&visibleIds.has(node.id))projected.set(node.id,rig.project(positions.get(node.id)!))
  const density=semantic?screenDensity([...projected].filter(([,p])=>p.visible&&p.x>=-64&&p.x<=width+64&&p.y>=-64&&p.y<=height+64).map(([id,p])=>({id,x:p.x,y:p.y}))):new Map<string,number>()
  let compressed=0,maxDensity=0
  const labels:(StarLabel&{text:string;font:string})[]=[],obstacles:{id:string;bounds:Bounds}[]=[]
  for(const layer of pointLayers){
   (layer.object.material as THREE.ShaderMaterial).uniforms.dpr.value=Math.min(dpr,1.5)
   layer.nodes.forEach((node,i)=>{
    if(!state.activeKinds.has(node.kind)||!visibleIds.has(node.id)){layer.radius[i]=0;layer.outline[i]=0;return}
    const p=projected.get(node.id)!,selected=node.id===state.selectedId,hovered=node.id===state.hoveredId||highlight.has(node.id),matched=state.matches.has(node.id)
    const localScale=height/(2*Math.max(.1,p.depth)*Math.tan(THREE.MathUtils.degToRad(rig.camera.fov/2)))/30
    const related=Boolean(state.selectedId&&state.focusIds.has(node.id))
    const appearance=starAppearance(node.kind,localScale,selected,matched,hovered||related)
    if(stellar){appearance.radius=stellarSize(localScale,selected,maxPointSize,Math.min(dpr,1.5)).radius;appearance.outline=selected||hovered||matched||related;appearance.label=appearance.label||selected}
    const pickRadius=appearance.radius,occupancy=density.get(node.id)||0,clarity=densityAppearance(occupancy,selected||hovered||matched||related)
    if(semantic){appearance.radius*=({job:.9,skill:.68,industry:.82}[node.kind])*clarity.radius;if(clarity.radius<.97)compressed++;maxDensity=Math.max(maxDensity,occupancy)}
    const visible=p.visible
    layer.radius[i]=visible?appearance.radius:0;layer.outline[i]=appearance.outline?1:0
    layer.object.geometry.getAttribute('stellarType').setX(i,state.stellarPreset?STELLAR_TYPES.indexOf(state.stellarPreset):stellarProfile(node.id).index)
    layer.object.geometry.getAttribute('emphasis').setX(i,selected ? 1 : (related || hovered) ? .5 : 0)
    layer.object.geometry.getAttribute('haloStrength').setX(i,clarity.halo);layer.object.geometry.getAttribute('opacity').setX(i,clarity.opacity)
    if(!visible)return
    const point={id:node.id,...p,radius:semantic?pickRadius:appearance.radius};projection.set(node.id,point)
    if(p.x<0||p.y<0||p.x>width||p.y>height)return
    const radius=appearance.radius;obstacles.push({id:node.id,bounds:{left:p.x-radius-2,right:p.x+radius+2,top:p.y-radius-2,bottom:p.y+radius+2}})
    if(!appearance.label)return
    const priority=selected?4:hovered?3:matched?2:node.kind==='job'?1:0
    // The final placement budget is 140; pre-budget ordinary candidates before measuring text.
    if(labels.length>320&&priority<2)return
    const text=node.label.length>28?node.label.slice(0,27)+'…':node.label,font=`${selected||hovered?11:10}px "Microsoft YaHei", sans-serif`,metricKey=font+text
    let measured=metrics.get(metricKey)
    if(measured===undefined){ctx.font=font;measured=ctx.measureText(text).width;metrics.set(metricKey,measured)}else labelCacheHits++
    const half=measured/2+3,y=p.y+radius+13
    labels.push({id:node.id,text,font,priority,bounds:{left:p.x-half,right:p.x+half,top:y-11,bottom:y+3},alternatives:[{left:p.x+radius+7,right:p.x+radius+7+2*half,top:p.y-7,bottom:p.y+7},{left:p.x-half,right:p.x+half,top:p.y-radius-21,bottom:p.y-radius-7}]})
   })
   layer.object.geometry.getAttribute('radius').needsUpdate=true;layer.object.geometry.getAttribute('outline').needsUpdate=true
   layer.object.geometry.getAttribute('stellarType').needsUpdate=true;layer.object.geometry.getAttribute('emphasis').needsUpdate=true
   layer.object.geometry.getAttribute('haloStrength').needsUpdate=true;layer.object.geometry.getAttribute('opacity').needsUpdate=true
  }
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height)
  const placements=placeStarLabels(labels,{left:0,right:width,top:0,bottom:height},state.panels,obstacles,scale<.35?12:scale<.9?70:140)
  for(const label of labels){const box=placements.get(label.id);if(!box)continue;ctx.font=label.font;ctx.textAlign='center';ctx.strokeStyle='rgba(0,0,5,.95)';ctx.lineWidth=3;const x=(box.left+box.right)/2,y=box.bottom-3;ctx.strokeText(label.text,x,y);ctx.fillStyle='rgba(232,239,255,.84)';ctx.fillText(label.text,x,y)}
  updateCount++
  const frustum=new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(rig.displayCamera.projectionMatrix,rig.displayCamera.matrixWorldInverse))
  const sourceIndices=plan.edges.map(e=>e.sourceIndex!),intersecting=plan.edges.filter(e=>{const box=bounds.get(e);return box&&frustum.intersectsBox(box)}).length
  const selected=state.selectedId?projection.get(state.selectedId):undefined
  return {audit:plan.audit,drawnSourceIndices:sourceIndices,submitted:plan.edges.length,intersecting,visibleNodes:projection.size,labels:{candidates:labels.length,drawn:placements.size},drawMs:performance.now()-start,derivedSubmitted:derived.length,depthVersion:DEPTH_VERSION,updateCount,geometryBuilds,labelCacheHits,scale,
   stellarVersion:semantic?KNOWLEDGE_STELLAR_VERSION:stellar?STELLAR_VERSION:'p23',transitionParticles:dustCount,maxPointSize,density:{compressed,max:maxDensity},selectedStar:stellar&&state.selectedId?{...(semantic?knowledgeProfile(byId.get(state.selectedId)!.kind,state.selectedId):stellarProfile(state.selectedId,state.stellarPreset)),radius:selected?.radius}:null,
   pickCandidates:[...projection.values()].filter(p=>p.x>280&&p.x<width-400&&p.y>30&&p.y<height-40).slice(0,30)}
 }
 return {group,setData,update,positions,setPointLimit:(value:number)=>{maxPointSize=value},
  pick:(x:number,y:number)=>pickProjected(projection.values(),x,y),
  projected:(id:string)=>projection.get(id),
  dispose(){disposePoints();disposeDust();lineGeometry.dispose();lineMaterial.dispose();sprites.clear();positions.clear();bounds.clear();projection.clear();metrics.clear()},
 }
}
export type SpatialKnowledge=ReturnType<typeof createSpatialKnowledge>
