"""Build a source client bundle; explicit allowlist excludes every operator secret."""
import json
import zipfile
from pathlib import Path

from onlinecoc_p2p.common import atomic_json,digest

root=Path(__file__).resolve().parents[1]
config=json.loads((root/"local/client-config.json").read_text(encoding="utf-8"))
output=root/"dist/onlinecoc-player.zip"
output.parent.mkdir(exist_ok=True)
readme="""OnlineCOC 联网测试客户端

要求：Windows x64、Python 3.14、Chrome 或 Edge。首次安装需要联网下载依赖。
1. 将压缩包完整解压到一个独立文件夹。
2. 双击 play.cmd；首次自动安装依赖，以后直接打开联机页面。
3. 输入房主提供的 8 位房间码；私有房间直接粘贴完整加入信息（已包含邀请）。
4. 有房间密码时填写，提交后等待房主审批（如启用）。
5. 房间准入通过后，使用房主分配的游戏账号登录，确认并下载玩家内容。

这个包只能加入房间，不包含房主发布凭据、SSH 密钥、TURN 主密钥或证书私钥。
local/test-ca.pem 仅由本客户端校验测试服务器，不安装到系统证书库。
房主停机后当前房间不可继续；断线时重新加入。测试服务器有到期时间，由房主维护。
"""
with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
    for relative in ("pyproject.toml","requirements.lock","requirements.txt","setup.ps1","start.ps1","play.cmd"):
        archive.write(root/relative,relative)
    for path in (root/"src/onlinecoc_p2p").rglob("*"):
        if path.is_file() and path.suffix in {".py",".js",".html",".css"} and "__pycache__" not in path.parts:
            archive.write(path,str(path.relative_to(root)).replace("\\","/"))
    archive.writestr("local/client-config.json",json.dumps({"directory":config["directory"],
        "caFile":"test-ca.pem","statePath":"player-session"},ensure_ascii=False,indent=2))
    archive.write(config["caFile"],"local/test-ca.pem")
    archive.writestr("README.txt",readme)
with zipfile.ZipFile(output) as archive:
    names=archive.namelist()
    assert not any(n.endswith((".key",".ppk")) or "tmp/" in n or "pem" in n and n!="local/test-ca.pem" for n in names)
    player=json.loads(archive.read("local/client-config.json"))
    assert set(player)=={"directory","caFile","statePath"}
    private=json.loads((root/"local/deployment-secrets.json").read_text(encoding="utf-8"))
    for name in names:
        raw=archive.read(name)
        for value in private.values():
            assert value.encode() not in raw
        assert b"BEGIN PRIVATE KEY" not in raw
atomic_json(root/"local/acceptance/player-bundle.json",{"file":output.name,"bytes":output.stat().st_size,
    "sha256":digest(output.read_bytes()),"operatorSecretsAbsent":True,"pythonRequired":"3.14 x64"})
print(json.dumps({"file":str(output),"bytes":output.stat().st_size,"operatorSecretsAbsent":True}))
