export const mapPositions=new Proxy({1:[90,280],2:[90,180],3:[270,180],4:[120,65],5:[290,65],6:[460,65],7:[460,180],8:[640,180],9:[640,280],10:[460,280]},{get(base,key){if(key in base)return base[key];if(typeof key!=='string')return undefined;const index=Number(key);return Number.isInteger(index)&&index>10?[90+((index-11)%4)*180,420+Math.floor((index-11)/4)*140]:undefined;}});
export function mapRoutes(locations,doors=null){
  const present=new Set(locations.map(l=>l.index)),routes=new Map();
  for(const place of locations)for(const exit of place.exits||[]){
    if(exit===place.index||!present.has(exit)||!mapPositions[exit]||!mapPositions[place.index])continue;
    const [from,to]=[place.index,exit].sort((a,b)=>a-b),key=from+'-'+to;
    const status=doors?.[key]??place.doors?.[exit]??'unknown',observedAt=place.observedAt??'';
    const previous=routes.get(key);
    if(!previous||observedAt>previous.observedAt)routes.set(key,{key,from,to,status:['open','closed','locked'].includes(status)?status:'unknown',observedAt});
  }
  return [...routes.values()].sort((a,b)=>a.from-b.from||a.to-b.to);
}
// Camera coordinates stay in map units; the SVG keeps its original layout size.
const cameras = new Map();
function limits(value, min, max) { return Math.min(max, Math.max(min, value)); }
export function cameraBox(key, original) {
  const camera=cameras.get(key);
  return camera?.original===original ? camera.box.join(' ') : original;
}
function updateCamera(svg, factor, focus, shift=[0,0]) {
  const base=svg.dataset.bounds.split(' ').map(Number), v=svg.viewBox.baseVal;
  const scale=limits(base[2]/v.width*factor,1,6), w=base[2]/scale, h=base[3]/scale;
  const x=limits(focus.x-(focus.x-v.x)*w/v.width+shift[0],base[0],base[0]+base[2]-w);
  const y=limits(focus.y-(focus.y-v.y)*h/v.height+shift[1],base[1],base[1]+base[3]-h);
  const box=[x,y,w,h];
  cameras.set(svg.dataset.camera,{original:svg.dataset.bounds,box});
  svg.setAttribute('viewBox',box.join(' '));
}
function point(svg,x,y) { return new DOMPoint(x,y).matrixTransform(svg.getScreenCTM().inverse()); }
export function enableMapControls() {
  const surface=e=>e.target.closest?.('svg[data-camera]');
  document.addEventListener('wheel',e=>{
    const svg=surface(e);if(!svg)return;
    e.preventDefault();
    updateCamera(svg,e.deltaY<0?1.2:1/1.2,point(svg,e.clientX,e.clientY));
  },{passive:false});
  document.addEventListener('click',e=>{
    const control=e.target.closest('[data-map-scale]');if(!control)return;
    const svg=control.closest('.node-map').querySelector('svg'),v=svg.viewBox.baseVal;
    updateCamera(svg,Number(control.dataset.mapScale),{x:v.x+v.width/2,y:v.y+v.height/2});
  });
  let drag=null, suppress=null;
  document.addEventListener('pointerdown',e=>{
    const svg=surface(e);if(!svg||e.button!==0)return;
    drag={svg,id:e.pointerId,x:e.clientX,y:e.clientY,moved:false};suppress=null;
  });
  document.addEventListener('pointermove',e=>{
    if(!drag||drag.id!==e.pointerId)return;
    const {svg,x,y}=drag;
    if(!svg.isConnected){drag=null;return;}
    if(!drag.moved && Math.hypot(e.clientX-x,e.clientY-y)<5)return;
    drag.moved=true;svg.setPointerCapture(e.pointerId);
    const a=point(svg,x,y),b=point(svg,e.clientX,e.clientY);
    updateCamera(svg,1,a,[a.x-b.x,a.y-b.y]);drag.x=e.clientX;drag.y=e.clientY;
  });
  const end=e=>{if(drag?.id===e.pointerId){suppress=drag.moved?drag.svg:null;drag=null;}};
  document.addEventListener('pointerup',end);document.addEventListener('pointercancel',end);
  document.addEventListener('click',e=>{if(suppress?.contains(e.target)){e.stopImmediatePropagation();suppress=null;}},true);
  document.addEventListener('keydown',e=>{
    const svg=surface(e);if(!svg||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
    e.preventDefault();const v=svg.viewBox.baseVal,delta={ArrowLeft:[-v.width/6,0],ArrowRight:[v.width/6,0],ArrowUp:[0,-v.height/6],ArrowDown:[0,v.height/6]};
    updateCamera(svg,1,{x:v.x,y:v.y},delta[e.key]);
  });
}
export function mapRoutePath({from,to}){
  const [x1,y1]=mapPositions[from],[x2,y2]=mapPositions[to];
  // Skirt room 07's roster, then enter 08 from the left; sharing 08's bottom
  // port with 08–09 would falsely draw a junction between unrelated corridors.
  return from===3&&to===8?`M${x1} ${y1} V248 H550 V196 H${x2}`:`M${x1} ${y1} L${x2} ${y2}`;
}
