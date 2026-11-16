// Only this scoped namespace is visible to the opaque package frame.
export function scopedStorage(scope, declaration){
  const prefix='onlinecoc-web:package:'+JSON.stringify(scope)+':';
  const allowed=key=>typeof key==='string'&&key.length<=180&&declaration.some(p=>p.endsWith('*')?key.startsWith(p.slice(0,-1)):key===p);
  const snapshot=()=>{const result={};for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key?.startsWith(prefix)){const name=key.slice(prefix.length);if(allowed(name))result[name]=localStorage.getItem(key);}}return result;};
  return {snapshot,write(key,value){
    if(!allowed(key)||value!==null&&(typeof value!=='string'||value.length>16384))throw Error('STORAGE_KEY_REJECTED');
    const values=snapshot();if(value===null)delete values[key];else values[key]=value;
    if(Object.keys(values).length>64||JSON.stringify(values).length>65536)throw Error('STORAGE_LIMIT');
    if(value===null)localStorage.removeItem(prefix+key);else localStorage.setItem(prefix+key,value);return {saved:true};
  }};
}
