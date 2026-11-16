import {IntlMessageFormat} from './messageformat.js';
const PROJECT='stumpsville', SOURCE='zh-CN';
let resourceLoader;
let resources={}, contracts={}, requested=sessionStorage.getItem('sv.locale')||SOURCE;
export const locale=()=>requested;
export async function initLocale(base){
  const fetchJSON=async path=>{if(globalThis.stumpsvilleWeb)return globalThis.stumpsvilleWeb.json(path);const r=await fetch(new URL(path,base));if(!r.ok)throw Error('Localization resource unavailable');return r.json();};
  resourceLoader=fetchJSON;
  const loaded=await Promise.allSettled([...new Set([SOURCE,requested])].map(async lang=>[lang,await fetchJSON('locales/'+lang+'/ui.json')]));
  resources=Object.fromEntries(loaded.filter(x=>x.status==='fulfilled').map(x=>x.value));
  try{contracts=(await fetchJSON('locales/meta/catalog/ui.json')).entries;}catch{contracts={};}
  document.documentElement.lang=requested;
}
export function resolve(ref,language=requested){
  const fail=code=>({text:ref.errorText||'[Text unavailable]',status:'error',requestedLocale:language,resolvedLocale:null,diagnosticCode:code});
  if(ref.projectId!==PROJECT||ref.namespace!=='ui')return fail('SCOPE_MISMATCH');
  const langs=[language,...(language.startsWith('en-')?['en']:language==='zh-Hans'?['zh-CN']:[]),SOURCE];
  for(const lang of [...new Set(langs)]){
    const template=resources[lang]?.[ref.key];if(typeof template!=='string'||!template||/<\/?[a-z][^>]*>/i.test(template))continue;
    try{
      const params=ref.params||{}, contract=contracts[ref.key]?.params||{};
      for(const [key,c] of Object.entries(contract)){
        if(typeof params[key] !== (c.type==='enum'?'string':c.type))throw Error('PARAMETER_TYPE');
        if(c.type==='number'&&!Number.isFinite(params[key]))throw Error('PARAMETER_TYPE');
        if(c.type==='enum'&&!c.values?.includes(params[key]))throw Error('PARAMETER_TYPE');
      }
      const text=new IntlMessageFormat(template,lang,{},{ignoreTag:true}).format(params);
      if(typeof text!=='string')throw Error('INVALID_TEXT');
      return {text,status:lang===language?'translated':'fallback',requestedLocale:language,resolvedLocale:lang,diagnosticCode:null};
    }catch{}
  }
  return ref.onMissing!=='error'&&ref.fallback?{text:ref.fallback,status:'fallback',requestedLocale:language,resolvedLocale:null,diagnosticCode:'MISSING_TEXT'}:fail('MISSING_TEXT');
}
export const t=(key,params={},fallback)=>resolve({kind:'textRef',projectId:PROJECT,namespace:'ui',key,params,fallback,onMissing:'fallback'}).text;
export async function setLocale(value){if(['en','zh-CN'].includes(value)&&!resources[value])resources[value]=await resourceLoader('locales/'+value+'/ui.json');requested=['en','zh-CN'].includes(value)?value:SOURCE;sessionStorage.setItem('sv.locale',requested);document.documentElement.lang=requested;}
