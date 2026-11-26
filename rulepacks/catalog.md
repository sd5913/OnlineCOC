# 配置包实例统计与管理

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-12
- 最后更新：2026-11-26
- 关联文档：[配置包开发指南](README.md)、[文档索引](../docs/README.md)、[维护标准](../docs/standards/document-maintenance.md)

记录 `rulepacks/` 下的具体包及调研项目。实例表于 2026-11-12 从原“独立配置包”入口迁入；工程接入与支持工具继续在[开发指南](README.md)维护。

## 登记概况

当前登记 **3 项**：已有实现 **2 项**，调研/计划 **1 项**。版本和状态依据各包入口核对；“已有实现”不表示全部需求或验收已完成。

| 配置包或项目 | 目录 | 当前版本 | 状态与主要限制 | 详情 |
| --- | --- | --- | --- | --- |
| 树桩镇 Stumpsville | `stumpsville/` | 0.9.0 | 后端0.2.0/Room v3与包格式2；新版AI资料查询和0.3.0开房串；完整网页PL、版本化服务/存储桥、按需资源和双击分享已通过本地及公网强制TURN双浏览器18预设；云端已更新，真人独立家庭/移动网验收待完成；KP地图仅玩家角色，PL当前地点发现名单；独立房间/裁决/地图页及原生AI对话/语义引用（本地模拟模型验收），网页入口默认加载AI；保留旧P2P基础入口、LAN、一屏三栏与本机KP独立管理；自动执行需KP页面在线，部分原文待终校 | [包入口](stumpsville/README.md)、[网页](stumpsville/docs/current/web.md)、[验收](stumpsville/tests/README.md) |
| 铃蔓回转录（工作簿名称） | `mini-detective-pack/` | 0.2.0 | 已实现自动行动与分区界面；规则基于复原草案，特殊方法和语义分歧仍需主持裁定 | [包入口](mini-detective-pack/README.md)、[验收](mini-detective-pack/tests/README.md) |
| 调查型线上跑团对照包 | `investigation-vtt-reference/` | 未登记 | 资料调研与试配准备，不计入已有实现 | [项目入口](investigation-vtt-reference/README.md)、[计划](investigation-vtt-reference/docs/plans/README.md) |

## 登记维护

1. 新增项目时登记稳定目录、名称、版本、状态及入口，并同步上方数量；工程内置 demo 不纳入本表。
2. 发布或状态变化时先更新包内实现与验收文档，再更新本表。原作版本与配置包版本分别标明，计划和已实现能力分开记录。
3. 迁移、停用或归档时说明替代关系，修复引用并同步[实际目录清单](../docs/current/engineering/hierarchy.md)。详细能力、操作和测试结果只维护在包内正文。
