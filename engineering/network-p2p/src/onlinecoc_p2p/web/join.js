const codePattern=/^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{8}$/;
export function displayCode(value){
  return value?.length===8?value.slice(0,4)+"-"+value.slice(4):value||"";
}
export function joinTarget(value,invitation=""){
  const raw=value.trim();
  let target=raw,secret=invitation.trim();
  if(raw.startsWith("OCOC1:")){
    const parts=raw.split(":");
    if(parts.length!==3||!parts[2]||parts[2].length>256)throw new Error("加入信息不完整，请重新复制。");
    target=parts[1];secret=parts[2];
  }
  const code=target.replace(/[\s-]/g,"").toUpperCase();
  if(codePattern.test(code))return {roomCode:code,invitation:secret};
  if(raw.startsWith("OCOC1:")||!target||target.length>128)throw new Error("请输入 8 位房间码或完整房间 ID。");
  return {roomId:target,invitation:secret};
}
export function shareText(room,invitation=""){
  const target=displayCode(room.roomCode)||room.roomId;
  return invitation?"OCOC1:"+target+":"+invitation:target;
}
