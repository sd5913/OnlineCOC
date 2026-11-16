"use strict";
const boot=event=>{
  if(event.source!==parent||event.data?.type!=="onlinecoc:render"||typeof event.data.html!=="string")return;
  window.removeEventListener("message",boot);
  document.open();document.write(event.data.html);document.close();
};
window.addEventListener("message",boot);
parent.postMessage({type:"onlinecoc:sandbox-ready"},"*");
