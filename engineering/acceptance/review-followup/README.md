# 审核历史、队列与紧凑引用验收

2026-11-20，ISSUE-017 的 AI 模块专项。工程行为以[裁决队列](../../../docs/current/engineering/ai-rulings.md)、[会话与历史](../../../docs/current/engineering/ai-session-access.md)、[玩家引用](../../../docs/current/engineering/ai-player-knowledge.md)为准。前一阶段的模型实验及通知能力见[审核连续性记录](../review-continuity/README.md)，不并入本轮计数。

本轮独立用例最终 **230/230，100%**。按测试源文件和完整参数化用例名去重，重复回归不累计；完整清单、每轮成功率、失败原因和源文件 SHA-256 见 [results.json](results.json)。包含真实本机宿主、持久仓库、HTTP 与 Edge，以及确定性服务商替身。**新增外部模型调用 0，计费用量 0**；此通过率不代表真实模型业务成功率，也不证明所有配置包组合都已穷尽。

## 已验证结果

- 执行导致来源版本变化后，仍获授权的原 response、裁决 summary/actions/changeSet 与回执保留，过期提示单独展示；真正生成失败且无正文时不补造回答。删除原对象、撤权、策略变化、跨作用域及无法证明的旧搜索继续拒绝。
- 配置数组追加、已有对象改名、truth/description 文本更新可保留历史；删除字段／对象、更换祖先对象 ID、撤权仍隐藏。执行与发布保持原精确基线校验。
- 同一业务来源、同一提交键重复请求复用原任务／候选；同会话同文字没有显式关系时仍独立。改变内容复用提交键返回 SUBMISSION_KEY_CONFLICT。失败后来源更新可创建可追溯后继，未变来源不循环调用模型。
- 新候选就绪后才替代明确关联的旧未执行项；旧项不能通过批次、统一裁决或宿主配置批准入口执行。归档要求理由与 queueDigest，恢复不会消除替代关系，原正文与业务状态持久保留。
- 排队／生成／校验、执行中、未知、部分完成、完成、发布与已有批准记录受保护。取消后的未执行候选进入历史；归档和派发通过同一事务串行，不能形成“已归档却刚入队”的任务。
- 严格玩家正文保留名称、短说明和精确引用入口；完整行动／选项树点开后查看。旧服务端结构回复仅作已授权的只读展示转换。Edge 验证明确回复、重试提交键、取消关联、独立新话题、历史正文和归档恢复交互。

## 各轮结果与失败处理

| 证据 | 通过 / 总数 | 结果说明 |
| --- | ---: | --- |
| [initial.xml](initial.xml) | 23 / 57 | 33 个夹具初始化错误：未建立 basetemp 父目录；1 个旧断言仍要求展开整个引用。修复目录与目标断言后复验 |
| [first.xml](first.xml) | 57 / 57 | 历史、裁决、紧凑引用首组复验 |
| [queue-first.xml](queue-first.xml) | 80 / 80 | 来源幂等、后继、归档及既有裁决修订／玩家申请回归 |
| [ui-first.xml](ui-first.xml) | 4 / 4 | Edge 交互及来源调试回归 |
| [freeze.xml](freeze.xml) | 29 / 29 | 失败后继、归档历史、批准保护、PL 提交键及浏览器 |
| [regression.xml](regression.xml) | 82 / 82 | 历史授权、配置增删改、批次、严格玩家知识与会话 |
| [nodes.xml](nodes.xml) | 0 / 1 | 独立验收导入根目录错误，未执行产品测试 |
| [nodes-final.xml](nodes-final.xml) | 6 / 8 | 夹具通过可变引用误改旧工件，2 项正文更新失败；修正为独立候选副本 |
| [nodes-verified.xml](nodes-verified.xml) | 8 / 8 | 真实旧工件的文本更新、删除与撤权复验 |
| [boundaries-initial.xml](boundaries-initial.xml) | 0 / 6 | 5 项实际缺口：生成态草稿可归档、取消候选仍 active；另 1 项夹具路径属性错误 |
| [boundaries-final.xml](boundaries-final.xml) | 42 / 42 | 修复上述缺口，并增加祖先 ID 更换及仓库重开验证 |
| [dispatch-final.xml](dispatch-final.xml) | 33 / 33 | 并发派发／归档屏障与命令、HTTP、会话回归 |
| [player-retry-initial.xml](player-retry-initial.xml) | 0 / 1 | 实际缺口：直接创作申请按钮未传 submissionKey，丢失响应后重试可能新增申请 |
| [pl-dispatch-initial.xml](pl-dispatch-initial.xml) | 0 / 1 | 实际回归：新增派发事务与公共 PL 提交的外层事务嵌套；包联测发现后在模块公共命令复现 |
| [pl-final.xml](pl-final.xml) | 9 / 9 | 复用现有事务，同时保留并发屏障；PL 自动派发和创作按钮断线重试复验 |
| [public-paths.xml](public-paths.xml) | 61 / 61 | 冻结后的全部公共 PL 派发、知识、申请接收与来源审核路径回归 |

各轮包含重复用例，不把表内总数相加作为覆盖数。XML 文件名保留实际执行时命名，带 final 的中间记录也可能包含失败，以表内状态和 results.json 为准。失败材料保留，没有以复验输出覆盖失败输出。

## 故障反馈与处理

| 情况 | 反馈与处理 |
| --- | --- |
| 旧回答仍授权但依据变化 | 保留原正文和只读提示，继续时重新查当前资料、另行准备与审核 |
| 来源删除／撤权／旧证明不足 | 隐藏旧正文，保留明确来源错误；重新选择当前授权来源，不伪造历史 |
| 同提交键不同内容／同请求不同候选 | 明确冲突；修改需求使用新提交键，配置候选使用原提案修订 |
| 队列版本冲突 | 刷新当前记录，按最新 queueDigest 操作，不覆盖并发变更 |
| 受保护／被替代／归档项 | 显示不可操作原因；未知执行核对原回执，旧项不能重新批准 |
| 生成失败 | 保留原失败状态、错误和诊断；来源改变后显式创建后继，或在原会话补充后继续 |

## 复现与产物

使用工程虚拟环境和隔离临时目录；先创建 `work/`。按各 XML 所列用例运行 `python -B -m pytest`，增加 `-p no:cacheprovider --basetemp=本目录/work/唯一目录 --junitxml=本目录/新证据.xml`。额外边界脚本为 [test_history_nodes.py](test_history_nodes.py)、[test_queue_boundaries.py](test_queue_boundaries.py)、[test_player_retry.py](test_player_retry.py)，主用例位于 `engineering/ai/tests/test_review_followup*.py`。临时宿主与身份库仅位于已忽略的 work/，不使用正式房间。

运行 `engineering/.venv/Scripts/python.exe -B engineering/acceptance/review-followup/record_results.py` 重建统计。脚本将混合运行中缺失的 XML 类名归一到实际测试文件，避免重复计算。截图 [history-ui.png](history-ui.png) 展示旧回复和过期提示同时存在。

引擎仅扩充严格命令 Schema，独立 [55 项契约验收](../queue-schema/README.md) 不并入上述 230 项。

配置包最终[真实宿主整链](../../../rulepacks/stumpsville/tests/review-followup-results.json) **6/6**，包含 PL 紧凑引用点击语义详情、实际批准后保留旧正文、同目录重启保持；使用 10 次本地替身调用，外部 API 为 0。[裁决工作台](../../../rulepacks/stumpsville/tests/ruling-workspace-results.json) **14/14**，[独立队列 UI](../../../rulepacks/stumpsville/tests/review-queue-ui-results.json) **4/4**；包侧另报恢复通路 15/15、来源关联纯验证 6 组。各项分开记录，不与模块用例混算。

包联测保留了漏派发／文案断言等夹具失败、网页导入别名构建错误及 PL 嵌套事务产品失败。网页构建器已支持导入别名，资源重新构建并通过语法检查。实际运行房间需要重启宿主，已导出的网页需重新构建后使用新版组件；本轮没有重启或迁移正式房间。
