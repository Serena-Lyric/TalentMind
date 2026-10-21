export type VisualVariant='p1a2'|'p21'|'p22'
export function comparisonSettings(search:string) {
 const query=new URLSearchParams(search),variant=query.get('graphVisual')
 const visual:VisualVariant=variant==='p1a2'||variant==='p21'?variant:'p22'
 const presets={overview:{x:498.3153270726714,y:50.94583,scale:.20022320973593533},middle:{x:0,y:0,scale:.75},near:{x:144.2214,y:-12.15694,scale:1.35}}
 const name=query.get('graphCompare') as keyof typeof presets
 const transform=Object.prototype.hasOwnProperty.call(presets,name)?presets[name]:null
 return {visual,transform,preset:transform?name:null,frozen:Boolean(transform)||query.get('freezeVisual')==='1'}
}
