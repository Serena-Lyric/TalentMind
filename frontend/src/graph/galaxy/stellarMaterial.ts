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
