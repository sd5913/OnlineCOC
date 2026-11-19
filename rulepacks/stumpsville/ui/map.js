export const mapPositions={1:[90,280],2:[90,180],3:[270,180],4:[120,65],5:[290,65],6:[460,65],7:[460,180],8:[640,180],9:[640,280],10:[460,280]};
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
export function mapRoutePath({from,to}){
  const [x1,y1]=mapPositions[from],[x2,y2]=mapPositions[to];
  // Skirt room 07's roster, then enter 08 from the left; sharing 08's bottom
  // port with 08–09 would falsely draw a junction between unrelated corridors.
  return from===3&&to===8?`M${x1} ${y1} V248 H550 V196 H${x2}`:`M${x1} ${y1} L${x2} ${y2}`;
}
