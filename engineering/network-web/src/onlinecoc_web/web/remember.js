// Opt-in autofill on this browser/origin only. Never stores recovery codes or sessions.
export function rememberLogin(scope, name, password, checkbox, clearButton, onError=()=>{}) {
  const key="onlinecoc-web:remember:"+scope;
  const erase=()=>{
    try {localStorage.removeItem(key);clearButton.hidden=true;return true;}
    catch {onError("当前浏览器未能清除账密，请在浏览器设置中清除本站数据。");return false;}
  };
  try {
    const stored=JSON.parse(localStorage.getItem(key)||"null");
    if(stored&&typeof stored.name==="string"&&typeof stored.password==="string"){
      name.value=stored.name;password.value=stored.password;checkbox.checked=true;clearButton.hidden=false;
    }
  } catch { /* Storage may be disabled; ordinary login must still work. */ }
  checkbox.addEventListener("change",()=>{if(!checkbox.checked)erase();});
  clearButton.addEventListener("click",()=>{
    if(erase()){checkbox.checked=false;name.value="";password.value="";}
  });
  // Reflect an explicit clear from another tab without keeping an obsolete autofill.
  window.addEventListener("storage",event=>{
    if((event.key===key||event.key===null)&&event.newValue===null){checkbox.checked=false;clearButton.hidden=true;password.value="";}
  });
  return {
    save(loginName, loginPassword){
      if(!checkbox.checked){erase();return;}
      try {localStorage.setItem(key,JSON.stringify({name:loginName,password:loginPassword}));clearButton.hidden=false;}
      catch {onError("登录成功，但当前浏览器不允许保存账密。");}
    }
  };
}
