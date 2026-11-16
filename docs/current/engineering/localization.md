# 独立本地化工具工程入口

- 文档类型：当前
- 文档子类：工程
- 状态：有效
- 创建日期：2026-11-12
- 最后更新：2026-11-12
- 关联文档：[工程索引](README.md)、[工具入口](../../../tools/localization/README.md)、[施工计划](../../plans/localization-construction-plan.md)

独立工具已在 tools/localization 建立自有 workspace、依赖锁、消息解析、Electron 技术预览、CLI 帮助及最小打包。生产构建输入不依赖 OnlineCOC 核心或具体配置包，本次未修改 engineering/、rulepacks/ 或游戏运行数据。

**当前阶段 L10N-0 进行中，3/4 条件通过。** 原生目录选择已能打开并导航中文空格路径，最终选择回传因桌面自动化接口受阻及用户暂时无法接管而未验收；不能标为阶段完成。L10N-1～6 未开始，尚无正式可视化 CRUD、事务保存、资源发布或 TextRef fallback 能力。

具体版本、模块、命令与边界只在[工具现行架构](../../../tools/localization/docs/architecture.md)维护；阶段结果见[验收记录](../../../tools/localization/docs/acceptance.md)和[机器报告](../../../tools/localization/docs/evidence/l10n-0.json)。

实际首测是 Windows 10 19045 x64；设计目标 Windows 11 x64 新环境尚未验证。开发预览已能在仓库外复制目录中运行，不能代替 L10N-6 完整发行验收。
