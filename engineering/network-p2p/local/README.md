# 本地接入资料

本目录存放本机配置、证书、运行状态和测试输出；除本说明外均被 Git 忽略，不随常规提交共享。忽略规则不提供加密或操作系统访问控制，不要强制入库。

| 文件或目录 | 用途 |
| --- | --- |
| server-info.md、server.json | 实例资料及 SSH 包装配置；密钥只记录路径 |
| ssh-known-hosts、ssh-check.json | SSH 主机指纹与接入核对结果 |
| client-config.json | 房主目录地址、发布凭据、宿主地址及状态路径 |
| test-ca.pem | 测试 CA 公钥，可随玩家包分发 |
| test-ca.key、deployment-secrets.json | CA 私钥、发布令牌和 TURN 主密钥，仅限运维本机 |
| deploy/、deploy.tar.gz | 包含服务端私密配置和证书私钥的部署材料，不可给玩家 |
| host-session/ | 稳定房间身份、主机密钥、会话锁和账号封禁 |
| acceptance/ | 详细验收 XML、截图和机器结果；共享精选结果在上级 acceptance/ |
| browsers/、pip-cache/ | 可重建的测试浏览器与安装缓存 |
| player-bundle-smoke/ | 玩家包独立启动验收副本 |

用户提供的原始私钥仍保留在上级 tmp/，未复制进玩家分发包。操作与生成文件见[模块入口](../README.md)及[工程说明](../../../docs/current/engineering/network-p2p.md)。

新检出时可用[空白模板](../server-info.example.md)准备本机资料，不将密码、私钥正文或云 API Secret 写入共享文档。
