import { ShaderMaterial, Color } from 'three'

// Analytic photosphere: sphere normals, limb darkening, granulation and a separate corona.
// Static surface coordinates avoid temporal noise/shimmer while orbiting or zooming.
export function createStellarMaterial(kind:number,color:string) {
 return new ShaderMaterial({transparent:true,depthWrite:false,depthTest:false,
  uniforms:{dpr:{value:1},halo:{value:2.6},kind:{value:kind},typeColor:{value:new Color(color)}},
  vertexShader:`attribute float radius,outline,stellarType,seed,emphasis;
   uniform float dpr,halo;varying float shown,ring,coreRadius,footprint,starType,phase,boost;
   void main(){shown=step(.001,radius);ring=outline;coreRadius=radius;starType=stellarType;phase=seed;boost=emphasis;
    footprint=2.*(radius*halo+4.);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_PointSize=max(1.,footprint*dpr);}`,
  fragmentShader:`uniform float kind;uniform vec3 typeColor;
   varying float shown,ring,coreRadius,footprint,starType,phase,boost;
   float hash(vec3 p){return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453);}
   float noise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
    mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
   void main(){if(shown<.5)discard;
    vec2 pixel=(gl_PointCoord-.5)*footprint;float compact=starType>2.5?.57:starType>1.5?.68:starType>.5?1.08:.9;
    float core=max(.45,coreRadius*compact),r=length(pixel)/core,aa=max(.018,.8/core);
    vec3 warm=vec3(1.,.065,.004),cool=vec3(.12,.40,1.);
    vec3 temp=starType<.5?cool:starType<1.5?warm:starType<2.5?vec3(.83,.91,1.):vec3(.38,.82,1.);
    float angle=atan(pixel.y,pixel.x),rays=1.+.14*sin(angle*7.+phase*17.)+.08*sin(angle*13.-phase*11.);
    float corona=exp(-max(0.,r-1.)*(starType>.5&&starType<1.5?1.65:3.1))*.19*rays;
    corona*=smoothstep(.8,1.2,r)*(1.-smoothstep(2.,3.,r));
    float disk=1.-smoothstep(1.-aa,1.+aa,r),z=sqrt(max(0.,1.-min(1.,r*r)));
    float detail=smoothstep(3.,14.,coreRadius),surface=.65;
    if(detail>.001&&r<1.1){vec3 n=vec3(pixel/core,z);float grain=noise(n*22.+phase*37.);
     float cells=noise(n*9.+phase*19.);surface=.50+.29*grain+.18*cells;
     surface-=.15*smoothstep(.63,.8,noise(n*4.+phase*11.));}
    float limb=.30+.70*pow(z,.55);
    vec3 photosphere=mix(temp,vec3(1.,.97,.90),.15+.23*z)*surface*limb;
    if(starType>1.5)photosphere=mix(temp,vec3(1.),.45+.4*z)*(.65+.3*z);
    float beam=0.;if(starType>2.5){vec2 q=mat2(cos(phase*6.28),-sin(phase*6.28),sin(phase*6.28),cos(phase*6.28))*pixel/core;
     beam=exp(-q.x*q.x*120.)*exp(-abs(q.y)*.65)*smoothstep(.75,1.1,abs(q.y))*.68;}
    float alpha=max(disk,corona)+beam;vec3 rgb=(photosphere*disk+temp*(corona+beam))/max(alpha,.001);
    // A stable colored bracket outside the photosphere carries knowledge type, independently of temperature.
    float markerRadius=coreRadius*1.45+2.;float marker=(1.-smoothstep(.4,1.2,abs(length(pixel)-markerRadius)));
    float sector=kind<.5?step(.79,abs(sin(angle*2.))):kind<1.5?step(.91,abs(cos(angle))):step(.88,abs(sin(angle)));
    marker*=sector*(.40+.35*ring)*smoothstep(1.2,4.,coreRadius);float outlineRing=(1.-smoothstep(.3,1.1,abs(length(pixel)-markerRadius-2.)))*ring*.5;
    rgb=mix(rgb,typeColor,marker);alpha=max(alpha,marker);rgb=mix(rgb,vec3(.83,.93,1.),outlineRing);alpha=max(alpha,outlineRing);
    if(alpha<.008)discard;gl_FragColor=vec4(rgb*(1.+boost*.22),min(1.,alpha));}`})
}

// Kind governs the body itself: sphere, compact diamond star, or an oblate ringed body.
// The P2.4 material above is intentionally retained byte-for-byte for visual fallback.
export function createKnowledgeStellarMaterial(kind:number,color:string) {
 return new ShaderMaterial({transparent:true,depthWrite:false,depthTest:false,
  uniforms:{dpr:{value:1},halo:{value:2.6},kind:{value:kind},typeColor:{value:new Color(color)}},
  vertexShader:`attribute float radius,outline,seed,emphasis,haloStrength,opacity;
   uniform float dpr,halo;varying float shown,ring,coreRadius,footprint,phase,boost,haze,alphaScale;
   void main(){shown=step(.001,radius);ring=outline;coreRadius=radius;phase=seed;boost=emphasis;haze=haloStrength;alphaScale=opacity;
    footprint=2.*(radius*halo+4.);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_PointSize=max(1.,footprint*dpr);}`,
  fragmentShader:`uniform float kind;uniform vec3 typeColor;
   varying float shown,ring,coreRadius,footprint,phase,boost,haze,alphaScale;
   float grain(vec3 p){return fract(sin(dot(floor(p),vec3(127.1,311.7,74.7)))*43758.5453);}
   void main(){if(shown<.5)discard;
    vec2 pixel=(gl_PointCoord-.5)*footprint,q=pixel/max(.45,coreRadius);
    float angle=atan(q.y,q.x),isSkill=step(.5,kind)*(1.-step(1.5,kind)),isScene=step(1.5,kind);
    vec2 body=q;body.y/=mix(1.,.72,isScene);
    float r=length(body),diamond=(abs(q.x)+abs(q.y))*.83;
    r=mix(r,diamond,isSkill*.65);float aa=max(.025,.7/max(1.,coreRadius));
    float disk=1.-smoothstep(.86-aa,.86+aa,r),z=sqrt(max(0.,1.-min(1.,r*r)));
    float detail=smoothstep(2.,12.,coreRadius),texture=.72;
    texture+=detail*(grain(vec3(body*19.,phase*91.))-.5)*.22;
    texture+=detail*sin(body.y*19.+phase*13.+sin(body.x*9.)*.5)*.06;
    float light=.36+.64*pow(z,.65);
    vec3 surface=mix(typeColor,vec3(.85,.91,1.),.08+.22*z)*light*texture;
    float corona=exp(-max(0.,length(q)-.7)*4.2)*smoothstep(.62,1.05,length(q))*.16*haze;
    corona*=1.-smoothstep(1.65,2.5,length(q));
    // Small opposing rays distinguish skills even without color; no random pulsar identity.
    float rays=isSkill*exp(-min(abs(q.x),abs(q.y))*24.)*exp(-length(q)*2.6)*smoothstep(.7,1.,length(q))*.32*haze;
    vec2 orbit=mat2(.94,-.342,.342,.94)*q;
    float ellipse=length(vec2(orbit.x,orbit.y/.36));
    float band=isScene*(1.-smoothstep(.045,.13,abs(ellipse-1.48)))*.40;
    band*=mix(1.,1.-disk,step(0.,orbit.y));
    float alpha=max(disk,max(corona+rays,band));
    vec3 rgb=(surface*disk+typeColor*(corona+rays+band))/max(alpha,.001);
    float selection=(1.-smoothstep(.035,.12,abs(length(q)-1.95)))*ring*.42;
    rgb=mix(rgb,vec3(.82,.91,1.),selection);alpha=max(alpha,selection);
    if(alpha<.008)discard;gl_FragColor=vec4(rgb*(1.+boost*.12),min(1.,alpha*alphaScale));}`})
}
