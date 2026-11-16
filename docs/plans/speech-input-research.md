# AI 语音输入识别调研与接入方案

- 文档类型：计划
- 状态：草案
- 创建日期：2026-11-12
- 最后更新：2026-11-12
- 关联文档：[工程设计](speech-input-design.md)、[施工与验收计划](speech-input-construction-plan.md)、[计划索引](README.md)、[房间 AI 设计](ai-runtime-design.md)、[AI 实施与验收计划](ai-runtime-construction-plan.md)、[文档维护标准](../standards/document-maintenance.md)

## 1. 目标、需求与当前状态

为 OnlineCOC 的独立 AI 模块提供语音输入：用户说出需求，语音模块将音频识别为可编辑文字，再通过 AI 模块的文本入口提交。语音输入与键盘输入共用后续处理流程，AI 模块继续负责上下文、意图理解、工具调用、权限、需求转交和配置提案。

2026-11-12 用户明确了以下两个主要场景：

| 场景 | 使用者与表达示例 | 语音模块交付 | 后续处理归属 |
| --- | --- | --- | --- |
| A：游戏中的行动或需求 | 玩家向 AI 说“帮我查看背包”“我想进行一次侦查”“请向 KP 提交制作某件道具的需求” | 保留原意的文字及所属会话；允许用户修改后发送 | AI 模块识别是咨询、现有动作还是向 KP 提交需求；实际执行仍由主机鉴权和规则处理 |
| B：规则或内容编写 | KP 或开发者向 AI 说“增加一条潜行规则”“为这个地点补充三条线索配置” | 规则、数值、条件和专有名词清晰的文字及所属会话 | AI 模块生成规则或内容提案，并走相应校验、审阅、发布或作者侧保存流程 |

这里的“与 AI 语音交流”首先指用户可以用声音输入，AI 的回复可以继续显示为文字。多轮对话由独立 AI 模块维护，语音模块逐轮提交文字即可。

**需求场景已确认；工程实现尚未开始。** 本文保留官方资料、市场方案及费用依据；服务商推荐、交互和协议已细化至[工程设计](speech-input-design.md)，施工顺序与验收维护在[施工计划](speech-input-construction-plan.md)。它们均为草案，不代表已完成服务开通、音频实测或性能验收。

## 2. 范围与模块边界

首版建议覆盖麦克风授权与录音、停止和取消、音频识别、文字草稿编辑、向当前 AI 输入目标提交、错误提示以及键盘输入回退。工程设计已选择点击开始/结束，按住说话留待后续；不要求用户持续开麦。

以下能力不作为这两个场景的前置条件：多人语音通话、整场会议转录、混合音轨说话人分离、自动会议摘要、语音合成、语音唤醒和全双工打断。它们可以另立后续需求，不扩大本次输入模块的首版范围。

| 模块 | 应承担的职责 | 与本方案的连接 |
| --- | --- | --- |
| 前端输入组件 | 采集、录音状态、识别进度、编辑与发送 | 将识别文字放入现有或待实现的 AI 输入框 |
| 语音服务与识别适配器 | 音频格式转换、供应商调用、结果规范化、取消及用量记录 | 输出文字，不执行游戏动作、不生成规则、不修改配置 |
| 独立 AI 模块 | 会话上下文、意图理解、动作参数提取、需求转交、规则或内容提案 | 接受与键盘输入语义相同的文本请求 |
| 主机或作者侧工具 | 身份、权限、规则执行、校验、审批、发布或保存 | 处理 AI 提交的受控请求，语音模块不能绕过其门禁 |

“我是 KP”“直接发布”等识别文本不改变用户权限。开发者身份也不自动等于某个运行房间的 KP；房间内操作与作者侧编写使用各自的认证和授权流程。

~~~mermaid
flowchart LR
    MIC[玩家或 KP/开发者麦克风] --> CAP[语音采集]
    CAP --> ASR[云端或本地识别服务]
    ASR --> DRAFT[可编辑的文字草稿]
    KEY[键盘输入] --> DRAFT
    DRAFT --> SEND[用户发送到当前 AI 会话]
    SEND --> AI[独立 AI 模块]
    AI --> ACTION[现有动作或向 KP 提交需求]
    AI --> CONTENT[规则或内容配置提案]
~~~

首版建议保留一次普通“发送”操作，不额外增加一套语音审批。动作确认、KP 审核和发布审批仍按 AI/主机流程处理。“语音结束自动发送”如后续开放，应作为明确设置，并继续遵守这些流程。

## 3. 已核查的工程条件

以下依据 2026-11-12 的局部代码核查；不替代全工程验收。

| 当前事实与证据 | 对语音输入的影响 |
| --- | --- |
| [后端项目配置](../../engineering/backend/pyproject.toml)使用 Python 3.14、FastAPI、uvicorn 和 websockets | 可新增 HTTP/流式音频入口；本地推理依赖与 Python 3.14 的兼容性须单独验证 |
| [后端连接](../../engineering/backend/src/onlinecoc/server.py)的 `/api/v1/connect` 用于房间投影快照和文本心跳 | 不能把该连接当成已具备音频上传能力；语音应新增独立接口 |
| [LAN 网关](../../engineering/network-lan/src/onlinecoc_lan/gateway.py)采用路由白名单，现有 WebSocket 转发会关闭二进制消息连接；普通请求体限制为 64 KiB，资产上传另有例外 | 新语音接口必须同步网关路由、帧类型、请求体限制和超时；不能借资产接口绕过限制 |
| LAN 网关地址使用 HTTP，页面策略包含 `connect-src 'self'` | 采用同源服务端中转较容易保持现有访问边界；浏览器直接连接外部供应商需要另评估凭据和连接策略 |
| 浏览器麦克风接口要求安全上下文，localhost 是例外之一 [S01] | 同机演示可使用 localhost；其他玩家访问普通局域网 HTTP 地址时，应先解决受信任 HTTPS 或另选桌面采集入口 |

最新[房间 AI 设计](ai-runtime-design.md)首版聚焦 KP 需求、规则/配置提案及审核发布，并明确外部输入先转成可确认文本、语音模块另行建设。玩家要求执行已有动作、开发者在作者侧编写内容属于本次确认的目标场景，相关 AI 意图编排与入口仍需由 AI 模块覆盖；不能因语音转写完成就宣称这两条业务链全部可用。

AI-0 的 [Request 机器契约](../../engineering/contracts/ai.json)已建立，其字段及接收端缺口已核对到[工程设计第 6 节](speech-input-design.md#6-与独立-ai-模块的对接契约)。这不表示 AI 公共入口已经实现；输入层可先独立验证，端到端验收依赖对应 AI 场景已具备文本处理能力。

## 4. 现有方案及接入方式

### 4.1 云端识别

| 方案 | 已查证的接入能力 | 对本次需求的判断 |
| --- | --- | --- |
| 阿里云百炼 ASR | 文件转写使用 HTTP；实时转写使用 WebSocket。Qwen-Audio 3.1 系列区分 Message 短段输入、Streaming 持续转写、Filetrans 文件转写，部分模型支持热词及上下文 [S02] | 首轮候选。短段需求优先比较 Message 或文件转写路径；需要边说边显示时比较 Streaming/Fun-ASR-Realtime。逐个模型核对能力，不能混用其参数 |
| 豆包流式语音识别 2.0 | WebSocket；一句话接口在句末返回稳定结果，实时接口持续返回可能修订的结果 [S04] | 首轮候选。首版可只消费稳定句子；实时出字作为体验增强，不要求整场持续监听 |
| 腾讯云 ASR | WebSocket、签名鉴权及 SDK，返回句首、中间与句末结果；支持多种语言和方言 [S06] | 有现成腾讯云账户时可纳入对照；需处理音频发送节奏、断线及新会话标识 |
| 讯飞流式语音听写 | WebSocket/平台 SDK，中文动态修正；本次查阅的接口面向 1 分钟内的听写 [S07] | 适合短段输入和方言试验；较长规则描述需要提示、分段或另选产品 |
| OpenAI Transcription | `gpt-transcribe` 用于文件或已提交音频轮次；`gpt-live-transcribe` 用于低延迟实时识别，提供关键词与语言提示 [S08—S11] | 可作多语言或适用地区部署的候选；先核对账户服务地区与网络。当前实时模型不提供说话人标签、词级时间戳或置信度，但本次单用户输入通常不依赖这些字段 |
| Azure Speech | Speech SDK，支持实时、快速文件及批量转写，也提供领域定制 [S12] | 可在已有 Azure 基础设施或多语言部署需求时评估 |

OpenAI 官方文件转写文档在本次查阅时已将旧 `whisper-1`、`gpt-4o-transcribe` 等托管模型标记为弃用，并列出 2027-02-26 停用时间；新接入按当前文档选型 [S08]。这一托管 API 变更不表示本地 Whisper 开源权重失效。

### 4.2 本地识别与浏览器内置能力

| 方案 | 接入方式 | 适用条件及限制 |
| --- | --- | --- |
| FunASR | Python 推理、组合 VAD/标点等组件，或运行时 WebSocket 服务；Paraformer-zh-streaming 是其流式候选之一 [S13] | 可作为中文本地试点。离线与流式模型分别选择；工具代码与模型权重许可分别核对 |
| Qwen3-ASR | 0.6B/1.7B 模型，支持离线和流式；官方工具的流式推理目前通过 vLLM 后端 [S14] | 可作为多语言本地候选，按真实硬件验证启动、显存、吞吐和延迟，不直接把厂商批量吞吐当作单句延迟 |
| faster-whisper / whisper.cpp | Python/CTranslate2 或 C/C++ 本地推理；持续实时输入需要分段与流式封装 [S15—S16] | 适合录完再识别及多语言对照。Windows 分发、模型体积、CPU/GPU 性能需实测 |
| sherpa-onnx | ONNX Runtime，本地离线推理并支持 Windows 等平台 [S17] | 可评估桌面 CPU 部署，实际语言、热词与流式能力取决于所选模型 |
| Web Speech API | 浏览器 `SpeechRecognition` [S18] | 原型接入较少，但兼容性有限；部分浏览器将音频发往服务端，不能视为统一离线能力。不建议作为唯一后端 |

“本地识别”需要标明运行位置：可以在玩家设备，也可以在 KP 主机或局域网服务。后两者仍会从玩家设备传输音频。识别在本地完成也不代表后续 AI 请求不外发；两段处理的目标和保留策略应分别说明。

## 5. 接入设计的后续细化

2026-11-12 在本调研基础上形成[独立语音输入模块工程设计](speech-input-design.md)：建议首版采用阿里云百炼北京地域 `fun-asr-realtime`，豆包保留为对照备选；浏览器经同源服务端流式上传 PCM，停止后编辑完整文字，通过应用的统一文本端口提交独立 AI 模块。

推荐选择基于协议及现有技术栈匹配，准确率与费用仍需真实样本核验。录音状态机、音频帧、供应商配置、AI 字段桥接、错误/限额和 LAN 条件以工程设计为唯一维护来源，不在本文重复参数。

## 6. 费用口径与估算

以下是 2026-11-12 查阅的指定产品公开单价，用于预算示例，不是整个服务商统一价格，也不代表质量相同。

| 服务 | 公开单价 | 每音频小时折算 |
| --- | --- | --- |
| 豆包流式语音识别 2.0，按量后付费 [S05] | 1 元/小时 | 1 元 |
| 阿里云 `fun-asr-realtime`，北京地域 [S03] | 0.00033 元/秒 | 1.188 元 |
| OpenAI `gpt-transcribe` [S10] | 0.0045 美元/分钟 | 0.27 美元 |
| OpenAI `gpt-live-transcribe` [S11] | 0.017 美元/分钟 | 1.02 美元 |

阿里云 Qwen-Audio 3.1 系列采用输入/输出 Token 计费，不能直接套用 Fun-ASR 的小时价格 [S03]。免费额度、资源包、并发购买、地区、取整和静音计费规则需在选定产品时再核对。

针对本次短段输入，可按“用户数 × 每人每天输入次数 × 平均录音秒数 ÷ 3600”估算每日上传音频小时数。示例假设为 6 人、每人每天 20 次、每次 15 秒，共 0.5 音频小时；按表中小时价线性估算，豆包约 0.50 元、Fun-ASR 约 0.594 元。该示例不含最小计费单位、重试、AI 推理、服务器、存储与网络费用。

整场转录只作为后续范围参照：6 人各上传一路且持续 4 小时，共 24 音频小时，线性估算分别为 24 元和 28.512 元。当前两个需求场景不需要默认采用这种持续计费方式。

本地模型没有同样的云端按分钟调用费，但有硬件、安装包、维护和算力占用成本；未实测前不承诺普通电脑可满足任意模型或多人并发。

## 7. 施工与验收入口

详细任务已细化为[SI-0—SI-6 施工与验收计划](speech-input-construction-plan.md)，覆盖契约/语料、独立服务、录音控件、阿里云联调、宿主/LAN、AI 对接和最终试点。该计划替代本调研早期 S0—S3 粗分期，当前所有语音工作包仍未实施。

验收须区分“语音输入模块可用”“AI 已接收文字”和“动作/配置业务完成”。真实 AI 入口缺失时可先验证替身，但不能声称两个场景的端到端验收已通过。

## 8. 已确认范围与待确认事项

用户确认的两个 AI 输入场景继续有效，整场字幕、会议记录与完整语音对话保留为后续参考，不作为首版要求。尚待确认的账号、试测预算、设备、语料、LAN 证书及 AI 接口责任方统一维护在[工程设计第 9 节](speech-input-design.md#9-首版验收门槛与待确认项)。

## 9. 官方资料与查阅日期

以下来源均于 **2026-11-12** 查阅。来源支持产品能力和公开价格；对 OnlineCOC 的选型、架构和实施顺序为本文建议。上线前重新核对模型、区域、参数、配额、价格与弃用公告。

| 编号 | 来源 |
| --- | --- |
| S01 | [MDN：getUserMedia 与安全上下文](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) |
| S02 | [阿里云百炼：语音识别概述与选型](https://help.aliyun.com/zh/model-studio/asr-model/) |
| S03 | [阿里云百炼：模型调用价格](https://help.aliyun.com/zh/model-studio/model-pricing) |
| S04 | [火山引擎：流式语音识别接入必读](https://docs.volcengine.com/docs/doubao-voice/access-must-read-1-1?lang=zh) |
| S05 | [火山引擎：豆包语音计费说明](https://docs.volcengine.com/docs/doubao-voice/billing-instructions?lang=zh) |
| S06 | [腾讯云：实时语音识别 WebSocket](https://cloud.tencent.com.cn/document/product/1093/48982) |
| S07 | [讯飞：语音听写流式 WebAPI](https://static.xfyun.cn/doc/asr/voicedictation/API.html) |
| S08 | [OpenAI：文件语音转写](https://developers.openai.com/api/docs/guides/speech-to-text) |
| S09 | [OpenAI：实时语音转写](https://developers.openai.com/api/docs/guides/realtime-transcription) |
| S10 | [OpenAI：GPT-Transcribe 模型及价格](https://developers.openai.com/api/docs/models/gpt-transcribe) |
| S11 | [OpenAI：GPT-Live-Transcribe 模型及价格](https://developers.openai.com/api/docs/models/gpt-live-transcribe) |
| S12 | [Microsoft：Azure Speech to Text](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-to-text) |
| S13 | [FunASR 官方仓库](https://github.com/modelscope/FunASR) |
| S14 | [Qwen3-ASR 官方仓库](https://github.com/QwenLM/Qwen3-ASR) |
| S15 | [SYSTRAN faster-whisper 仓库](https://github.com/SYSTRAN/faster-whisper) |
| S16 | [whisper.cpp 仓库](https://github.com/ggml-org/whisper.cpp) |
| S17 | [sherpa-onnx 官方文档](https://k2-fsa.github.io/sherpa/onnx/index.html) |
| S18 | [MDN：SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition) |
