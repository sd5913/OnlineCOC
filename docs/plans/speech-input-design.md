# 独立语音输入模块工程设计

- 文档类型：计划
- 状态：草案
- 创建日期：2026-11-12
- 最后更新：2026-11-12
- 关联文档：[方案调研](speech-input-research.md)、[施工与验收计划](speech-input-construction-plan.md)、[房间 AI 设计](ai-runtime-design.md)、[计划索引](README.md)

## 1. 设计基线与交付边界

用户已确认两个场景：玩家用语音要求执行动作或向 KP 提交需求；KP/开发者用语音要求增加规则或内容配置。共同输入链为“录音 → 转写 → 编辑文字 → 提交独立 AI 模块”。AI 继续负责多轮上下文、意图、工具和业务审批，语音模块不实现这些业务。

本次仅形成设计和施工计划。除明确标注为已核查的现有代码、AI-0 契约及厂商协议外，以下目录、协议、字段及初始参数均为**待实施设计基线**；服务商选择仍须通过真实录音验收后才能用于正式发布。

| 决定 | 首版基线与理由 |
| --- | --- |
| 识别服务 | 首选阿里云百炼北京地域 `fun-asr-realtime`；已有明确开始/结束/失败事件，PCM 音频与 JSON 控制消息便于在当前 Python/WebSocket 栈中适配 |
| 备选 | 豆包流式语音识别 2.0 作为效果及费用对照；首版只交付一个真实适配器，不自动切换供应商 |
| 采集与传输 | 浏览器 `getUserMedia`＋`AudioWorklet`，统一为 16 kHz、单声道、PCM signed 16-bit little-endian；录制期间经同源 WebSocket 中转 |
| 交互 | 点击开始/停止；最终文字由用户编辑并点击普通“发送”。流式文字显示在独立预览区，不改动正在编辑的输入框 |
| 停止策略 | 用户显式停止，或达到 120 秒上限时正常结束采集并等待尾部结果；供应商句末不自动结束整轮录音 |
| 模块形态 | 独立 Python 包＋无框架浏览器 ES module；通过宿主注入身份、目标授权和配置，不导入 AI 业务包 |
| AI 对接 | 应用侧桥接同一个文本提交端口；语音服务不从后端自动发起 AI 请求 |
| 首批环境 | Windows 桌面 Chrome/Edge，普通话及中英术语；本机 localhost 起步，LAN 必须另通过 HTTPS 验收 |
| 后续扩展 | 本地识别适配器、手机/Safari、文件导入、按住说话、自动发送、TTS 与多人通话分别验收，不作为首版依赖 |

## 2. 服务商配置与选择门槛

### 2.1 阿里云首版适配

官方 WebSocket 流程为 `run-task` → `task-started` → 音频 → `finish-task` → `task-finished`，识别结果在过程中到达。北京业务空间端点为 `wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference`，由服务端使用 Bearer API Key 鉴权。[接入文档](https://help.aliyun.com/zh/model-studio/fun-asr-realtime-websocket-api)

参数基线选 `model=fun-asr-realtime`、`format=pcm`、`sample_rate=16000`、`heartbeat=true`；录制中的静音仍发送采集帧，在本地 120 秒上限内允许用户停顿。语言提示默认不传，避免把中英混用误设为不支持的多语言提示数组。首轮不传对话上下文或词表；后续可由管理员配置经过可见性审查的公开术语词表，逐次携带隐藏剧本不在首版范围。精确参数及模型差异以[客户端事件](https://help.aliyun.com/zh/model-studio/fun-asr-client-events)为依据。

`fun-asr-realtime` 为可变化的模型别名。联调记录保存配置修订、实际请求模型 ID、查阅及测试时间；只有账号可用且通过相同验收的固定版本才可替换为快照。不能将某一快照的能力、上下文支持或测试结论直接转移给别名。

`SpeechProviderProfile` 采用独立配置命名空间：

| 字段 | 约束 |
| --- | --- |
| `profileId`、`revision` | 管理员定义的稳定 ID 与递增修订；录音会话固定创建时修订 |
| `adapter` | 首版仅 `aliyun-funasr-realtime`；测试环境可注入 `fake`，发行环境禁止选用 |
| `region`、`workspaceId`、`model` | 首版北京白名单与指定模型；服务器据此构造端点，不接受玩家 URL |
| `credentialRef` | 主机环境或秘密存储引用；无实际密钥的示例可入库，凭据不返回浏览器 |
| `limits` | 单轮时长、并发、日音频预算与超时；不得超过供应商账号配额 |
| `vocabularyRef` | 可选、管理员配置；词表创建上传作为独立配置操作，默认关闭 |

配置在本机管理入口修改并探测；探测只做配置/连接检查，音频试测使用指定样本，不附带房间内容。未配置时返回 `SPEECH_UNAVAILABLE`，键盘及 AI 文本输入继续可用。

### 2.2 备选与退出条件

选择阿里云主要依据协议和当前技术栈的匹配，不宣称其准确率领先。豆包保留为 SI-3 同样本对照，其一句话与实时接口的区别见[官方接入说明](https://docs.volcengine.com/docs/doubao-voice/access-must-read-1-1?lang=zh)；费用比较使用[调研第 6 节](speech-input-research.md#6-费用口径与估算)，不在本文复制价格表。

出现账号不可用、目标网络不稳定或质量/延迟不达标时，停止将阿里云标为可发布，保留录音与适配层，评审是否改为豆包。更换供应商需要新 profile、相同语料回归和外发说明；不在失败后悄悄把同一音频传给第二家，也不自动重放收费请求。本地模型通过同一适配器协议扩展，运行环境独立于宿主 Python 依赖。

## 3. 模块、依赖与拟定目录

### 3.1 组合方式

首版在宿主进程中组合异步 `SpeechService`，由宿主控制启停，不单独暴露新公网端口。独立指代码、协议、测试及配置边界独立；无需重复建设账号或房间系统。识别等待不占用 Host 房间写锁；宿主适配器只在短暂鉴权时读取必要状态。

~~~mermaid
flowchart LR
  MIC[麦克风与 AudioWorklet] --> WEB[SpeechInput 控件]
  WEB --> HTTP[同源 speech API]
  HTTP --> SERVICE[独立 SpeechService]
  SERVICE --> ASR[供应商适配器]
  ASR --> SERVICE
  SERVICE --> WEB
  WEB --> DRAFT[应用文本编辑器]
  DRAFT --> PORT[AiTextPort]
  PORT --> AI[独立 AI 模块]
  AUTH[宿主身份与目标授权] --> HTTP
~~~

| 拟定路径 | 职责 |
| --- | --- |
| `engineering/speech-input/pyproject.toml`、`src/onlinecoc_speech/` | 独立 Python 包；模型、状态、会话、限额和适配器协议 |
| `src/onlinecoc_speech/providers/aliyun.py` | 上游握手、事件解析、PCM 转发、错误规范化 |
| `web/speech-input.js`、`web/pcm-worklet.js` | 无框架输入控件、采样转换与采集生命周期；相对上述模块根目录 |
| `contracts/speech.json`、`tests/` | 模块自有版本化契约、假服务、音频及协议夹具 |
| `engineering/backend/src/onlinecoc/speech_api.py` | 新增宿主 HTTP/WS 适配；注入认证和目标授权，不放入核心包 |
| `engineering/client-sdk/client.js` | 增加单独 SpeechTransport 接口；不修改现有房间快照协议语义 |
| `engineering/network-lan/` | 精确开放新增路由与音频帧，TLS/Origin 配置和网关验收 |
| `engineering/acceptance/speech-input/` | 隔离端到端与人工音频验收；生成物放自身输出目录 |

这些是拟新增或拟改路径，不写入 hierarchy 的实际目录清单，实际创建时再登记。语音包不引用 `onlinecoc_ai`、游戏规则或包存档；未来作者工具通过不同宿主适配器复用同一控件与服务。

核心端口采用以下逻辑签名，具体 Python 类型在 SI-0 冻结：

- `SpeechService.create(principal, authorizedTarget, profile, request) -> SessionView`
- `open_stream(sessionId, principal) -> StreamHandle`；同一会话最多一个流。
- `StreamHandle.write(seq, pcm)`、`finish(lastSeq)`、`cancel()`、`events()`。
- `ProviderAdapter.open(profile, audioSpec) -> ProviderStream`；流提供 `write_pcm`、`finish`、`cancel` 和规范化事件。
- `AccessPort.authorize(principal, targetRef) -> AuthorizedTarget`，并在连接、读取及运行期间复核。

`AuthorizedTarget` 由宿主生成，含 `scopeKey`、`targetRef`、`targetRevision`、`consumerKind`、`maxTextChars`；它可以代表房间需求输入框或作者工作区，不要求 AI 已有“会话”实体。创建者身份和认证会话引用来自服务端，不由浏览器提交。

## 4. 录音到文字的生命周期

### 4.1 用户流程与编辑保护

1. 点击开始时固定输入目标及其修订，保存编辑器 revision；请求麦克风权限。权限弹窗未回应时可以取消，迟到的授权结果必须立即停止其 tracks。
2. 授权成功后创建转写会话并建立同源 WS。供应商确认开始后显示“可以说话”，此时才连接采集图并发送音频。准备期间不缓存用户语音，避免不知情上传或开头无界排队。
3. 录制时显示时长、音量与独立预览。预览允许句内替换，已有手写草稿保持不变。
4. 点击停止时先停止取新样本，再排空 Worklet 尾帧，随后发 `stop`；服务端等尾部识别和完成事件。达到 120 秒使用相同正常停止流程。
5. 完整结果进入候选区。编辑器 revision 未变化时，按“原有文本＋必要换行＋本轮完整文字”追加一次；已变化时由用户点击“插入到当前草稿”，不得覆盖。每轮保留插入标记，禁止重复追加。
6. 用户修改并发送后，由应用调用同一个 AI 文本端口。转写成功不等于 AI 接收成功，AI 接收成功也不等于动作或配置已生效。

切换目标、退出账号或关闭页面时取消尚未完成的录音，停止 tracks、释放 AudioContext、关闭流并丢弃迟到事件；已完成候选文字按原目标保留在当前页面内存，不自动迁移到新目标。首版不写 localStorage/IndexedDB，不提供原始录音回放或整段离线重试。

### 4.2 音频格式与背压

`getUserMedia` 请求单声道及回声消除/降噪能力，但约束不保证设备实际输出采样率；以实际 AudioContext 采样率进行有状态重采样，支持 44.1/48 kHz 输入并正确处理滤波、分块边界和尾帧。输出 16 kHz 单声道 PCM16LE，不以改 MIME、改文件扩展名或直接抽取样本代替转换。[麦克风接口](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)、[AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet)

每 200 ms 发 3200 samples，即 6400 音频字节；末帧允许不足 3200 samples。带 8 字节协议头时常规帧为 6408 字节。音频每秒 32000 字节，120 秒上限为 3840000 音频字节；服务器用实际接收样本计时，不信任客户端时长。

浏览器 `bufferedAmount` 与服务端待发送音频各限制为 2 秒量级；上游阻塞超限即结束为 `BACKPRESSURE_LIMIT`，不静默丢帧、不把数十秒音频突发补发。保留已收到的稳定文字为“未完整结束的候选”，必须经用户显式复制/编辑后才可作为普通文字使用。

### 4.3 服务端状态

| 状态 | 允许的下一步与退出语义 |
| --- | --- |
| `created` | 创建成功，等待唯一 WS；15 秒内未连接则 `expired` |
| `connecting` | 上游连接与启动；10 秒内未就绪则 `failed`，不启动采集 |
| `streaming` | 接收顺序音频及结果；停止转 `draining`，取消转 `cancelled` |
| `draining` | 不再接受音频；排空队列后仅发送一次上游 finish；15 秒内无完成则 `failed` |
| `completed` | 收到上游正常完成且没有悬而未决的非空片段，返回完整最终文字；空文字返回 `NO_SPEECH` 的失败结果 |
| `failed / cancelled / expired` | 终态，忽略迟到结果；不能复用本轮继续录音 |

状态转换在单会话串行控制器内执行；取消与完成竞争以服务端先提交的终态为准。客户端已取消则即便收到完成，也不自动插入或提交。重复 stop/cancel 不重复结束上游、不产生第二个终态。

## 5. 浏览器与语音服务协议 v1

所有 URL、字段和错误码均为拟定接口。HTTP JSON 使用 UTF-8、拒绝未知字段；时间使用 UTC ISO 8601，音频时长使用整数毫秒。目标授权失败对外不暴露其他目标是否存在。

### 5.1 HTTP 端点

| 方法与路径 | 输入/输出及约束 |
| --- | --- |
| `GET /api/v1/speech/capabilities` | 登录后返回 `protocolVersion=1`、enabled、audioSpec、limits、可用 profile 的脱敏 ID 及目标种类；不返回密钥、完整端点或工作区秘密 |
| `POST /api/v1/speech/sessions` | CSRF 校验；输入下方 Create；输出 sessionId、状态、profileRevision、固定目标、audioSpec、limits、expiresAt、相对 streamPath |
| `GET /api/v1/speech/sessions/{sessionId}` | 仅创建该会话的认证会话且仍有目标权限可读；返回最新 revision、状态与完整文字/失败信息，用于结果回包丢失后的查询 |
| `POST /api/v1/speech/sessions/{sessionId}/cancel` | CSRF 校验，空对象；幂等返回当前终态。已完成时不再退回取消状态，客户端仍可丢弃候选 |
| `WS /api/v1/speech/sessions/{sessionId}/stream` | 校验 Cookie、精确 Origin、绑定认证会话与目标权限；一个 session 只允许建立一次音频流，拒绝第二连接 |

~~~json
{
  "protocolVersion": 1,
  "clientRequestId": "uuid",
  "targetRef": "由宿主解析的输入目标引用",
  "targetRevision": "目标绑定修订",
  "profileId": "speech-default"
}
~~~

`clientRequestId` 在同一认证会话内去重，保留至会话 TTL 结束；同 ID 同载荷返回同 session，不重复开通上游；同 ID 不同载荷返回 `REQUEST_CONFLICT`。目标、用户、预算和实际模型由服务端固定；客户端不能自带 URL、密钥、角色或识别参数覆盖配置。

### 5.2 WebSocket 帧

| 方向/帧 | 结构与处理 |
| --- | --- |
| 服务端 JSON `ready` | 含 sessionId、eventSeq、audioSpec；收到后才能发音频 |
| 客户端二进制音频 | 头部为两个 uint32 little-endian：seq、sampleCount；随后 sampleCount×2 字节 PCM。seq 从 0 严格连续；sampleCount 为 1—3200，除尾帧外必须 3200；头部不转发给厂商 |
| 客户端 JSON `stop` | `{type:"stop",lastSeq:N}`；零帧时 N=-1。校验所有 0…N 已收齐后排空上游队列、发送 finish；重复同 N 幂等，不同 N 或 stop 后音频为协议错误 |
| 客户端 JSON `cancel` | 取消本轮；HTTP cancel 是 socket 故障时的同语义入口 |
| 服务端 JSON `transcript` | sessionId、eventSeq、segmentId、revision、text、isFinal；revision 单调增加，整段替换而非盲目追加 |
| 服务端 JSON `completed` | sessionId、eventSeq、text、audioDurationMs、usage；text 是最终聚合结果，只有此事件或 GET 的 completed 快照可自动进入候选 |
| 服务端 JSON `error / cancelled` | sessionId、eventSeq、稳定 code；可含明确标记 incomplete 的稳定片段，不冒充完整文字 |

JSON 控制帧上限 4 KiB，音频帧上限 6408 字节。服务端响应单事件上限 64 KiB；总文字上限为 `min(8000, AuthorizedTarget.maxTextChars)` 个 Unicode code points。超限报错，不静默截断规则条件。JSON 中不传音频 base64；内部合法 PCM 在适配器中按厂商协议编码。

收到不足 3200 samples 的帧后只允许 stop/cancel，后续再来音频即协议错误，以此验证它确为尾帧。WS 传输保持顺序，但 seq 仍用于发现实现中的漏发/重复及 stop 位置错误。首版不支持音频流断点续传：streaming 状态断连即失败并关闭上游；draining 时客户端断连可继续等待既有上游完成，之后通过 GET 查询。所有重录使用新 clientRequestId，不自动重放旧音频。

### 5.3 结果归并与厂商映射

阿里云 `sentence_id` 映射 segmentId，`sentence_end` 映射 isFinal；`heartbeat=true` 不产生文字。相同句子的中间结果只更新本句，最终片段按 ID 排序，以换行连接；仅统一换行格式及去除首尾空白，不再做润色或指令纠正。[服务端事件](https://help.aliyun.com/zh/model-studio/fun-asr-server-events)

对已 final 的片段，重复相同内容忽略，冲突内容报 `PROVIDER_PROTOCOL_ERROR`；task-finished 时仍有未 final 的非空片段报 `RESULT_INCOMPLETE`。事件总序号 eventSeq 只在本轮单调增长；GET 快照返回最新值，客户端丢弃已处理或属于其他 session 的消息。

`usage.duration` 是厂商报告的当前任务累计计费时长；同一任务多次出现时取最新有效累计值，不能逐句相加。与按样本计算的 audioDurationMs 分开记录。失败后实际计费不明时记为 unknown，并保守保留预算预留。

## 6. 与独立 AI 模块的对接契约

### 6.1 文本端口及职责

语音控件只向应用编辑器交付 `VoiceDraft`，不直接调用 AI。应用提供 `AiTextPort`，键盘和语音共用该端口；最终 HTTP 封套由 AI SDK/宿主适配器构造，语音包不引用 AI 的内部类。

| 契约 | 必需内容及语义 |
| --- | --- |
| `VoiceDraft` | `inputId=sessionId`、targetRef、targetRevision、text、`complete=true`；可选 model/profileRevision 仅作本地诊断，不送入提示词 |
| `AiTextPort.describe(targetRef)` | 返回当前 targetRevision、enabled、maxTextChars、支持的能力及不可用原因；能力为 `request`、`action`、`authoring` 的子集，由接收应用声明 |
| `AiTextPort.submit(input)` | 输入见下方；成功返回 `clientRequestId`、`taskId`、`status=accepted`。accepted 仅代表 AI 已持久接收请求 |
| `AiTextPort.lookup(clientRequestId,targetRef)` | 返回 accepted/taskId、rejected/code 或 unknown；用于提交回包丢失，不触发新任务 |
| `AiTextPort.cancel(taskId)` | 按 AI 模块自己的可取消状态及权限处理，不等同于取消录音；已经执行的动作或已发布配置不能据此自动撤销 |

拟定应用端口输入：

~~~json
{
  "clientRequestId": "同一次发送保持不变的 UUID",
  "targetRef": "已授权的房间需求入口或作者工作区",
  "targetRevision": "发送时复核的绑定修订",
  "text": "用户编辑确认后的完整文字"
}
~~~

该结构是桥接端口 DTO，**不是当前 AI HTTP API 的原样请求体**。源类型 voice、inputId、录音诊断等元数据保留在输入组件；只有 AI Schema 明确支持的字段才能通过桥接发送，不往拒绝未知字段的 AI Request 任意添加 audio、voice 或 actorRole。

### 6.2 已核对的 AI-0 契约与字段映射

2026-11-12 已只读核对 [AI 机器契约](../../engineering/contracts/ai.json) 的 `$defs.Request`（`urn:onlinecoc:ai:1`）。它是完整领域记录，不是创建请求的 HTTP 入参：12 个字段全部必需，拒绝未知字段；text 上限为 16000，sourceKind 仅允许 manual/chat/external-text，intent 仅允许 consult/invoke/configure。下表给出本设计的桥接映射建议；机器字段已存在不等于 HTTP 入口、去重或执行器已实现。

| 语音/应用侧信息 | 对接规则 |
| --- | --- |
| `VoiceDraft.text` → `Request.text` | 先进入普通编辑器；发送时使用编辑器最新全文，不能退回原始识别文本。录音结果限 8000 字符，最终编辑全文另按接收端声明的上限验证，不能静默截断 |
| 已确认的编辑器输入 → `sourceKind` | 本桥接建议统一为 `manual`，键盘与语音一致；`external-text` 留给另行定义的外部文本导入，录音来源只留在本地输入组件 |
| 一次冻结的提交 → `sourceId/sourceRevision` | 宿主以账号和 clientRequestId 建立稳定 sourceId；新手动提交 sourceRevision=1。发送前修改只是本地草稿；发送后改文须新建请求，不伪造 chat 消息或修订 |
| `targetRef`、`targetRevision` → `scopeId` | 宿主解析授权的实际 scope 并复核目标绑定修订；作者工具使用其自己的授权适配。不能把客户端字符串直接用作服务器路径、账号或可信 scope |
| `clientRequestId` → 创建命令封套 `requestId` | 映射接收去重标识；同 ID 同目标、来源、意图与文本返回同结果，不同载荷冲突。领域 `Request.requestId`、任务 ID 由接收端返回，不假定与命令封套 ID 相同 |
| 当前登录用户 → `initiator` | AI 接收端从认证会话取得；不接受客户端指定账号，不依赖提示词里的“我是 KP”作授权 |
| 输入入口的能力/模式 → `intent` | 普通需求默认 consult；规则/内容编写入口使用 configure；invoke 仅在实际动作能力开放时可用。采用与键盘相同的选择与校验，不由 ASR 擅自推断 |
| `schemaVersion/dedupKey/status/createdAt` | 均由 AI 接收端生成：版本为 1，dedupKey 符合既有 64 位十六进制契约；初始状态 received，时间沿用 AI 的 number 约定。语音包不自定去重算法、不填任务状态或将 UTC 字符串塞入该字段 |

房间适配拟调用 AI 计划中的 `POST /api/v1/ai/commands`，封套为 `requestId=clientRequestId`、当前 `authorityEpoch`、`op=ai.request.create` 与 `args`；账号及 scope 仍由主机绑定。`args` 的公共 Schema 尚未在已核对资料中冻结，因此上表不等于允许浏览器上传整个 Request；SI-0 由 AI 方确定哪些来源/意图字段可提交、哪些由服务端补齐。targetRevision 必须在接收时有等价的服务端校验，缺失则作为接口待补项，不能仅靠前端检查。

`AiTextPort.cancel` 对接 `ai.request.cancel`；任务进度对接 `GET /api/v1/ai/tasks/{id}`。两者的具体 args/响应同样以 AI 公共契约为准。`accepted` 是桥接接收回执状态，**不是** Request.status 的新增枚举，也不表示已排队生成；当前 AI 设计中，received 还需 KP 派发或房间自动模式才进入 queued。

### 6.3 两个场景及接收端缺口

| 场景 | 接收端职责与完成条件 |
| --- | --- |
| 场景 A 的需求 | 对接房间 AI 的显式需求创建入口；AI 决定咨询、提案或转交 KP |
| 场景 A 的行动 | 只有 describe 声明 action 且 AI 已提供受控现有动作调用时开放端到端验收；识别器不直接调用 `/commands` 执行动作 |
| 场景 B 的 KP 配置需求 | 对接同一房间 AI 需求入口，继续生成提案、检查和 KP 审批；不把“发送”当作批准 |
| 场景 B 的开发者编写 | 由作者侧 `authoring` 适配器接收，按作者工作区权限保存草稿；不能伪装为运行房间 KP 或直接回写包文件 |

已核对的 AI 应用接口仍标注待实现，且仅列出按 taskId 查询，未定义按 clientRequestId 恢复创建回执的公共入口。SI-0 必须补齐持久创建回执及查询，或明确同 ID 同载荷重放返回原 taskId 的等价协议；`lookup` 是本设计提出的逻辑能力，本文不虚构已存在的查询 URL。接收结果丢失时没有 taskId，不能仅靠任务查询或按钮禁用声称防重复。

目前房间 AI 首版重点是需求、配置提案和审批；其 `invocation.suggest` 仅是建议，不随配置发布执行。Request 中存在 invoke 枚举不能证明玩家动作执行链已具备；独立作者入口也不能假定已覆盖。公共 args/回执、目标修订校验、动作入口与作者入口由 AI/宿主负责补齐，语音包不代为实现。语音侧可以先用契约替身验收，正式场景验收须使用真实接收端。

### 6.4 一次发送与重试

编辑器在点击发送时冻结目标、文字及 clientRequestId。超时则显示“接收结果待确认”并 lookup；同请求重发只用相同 ID 和载荷。unknown 时不自动生成新 ID 重复发送，先由接收端对账或向用户说明未确认状态。修改文字视为新请求，须先处理此前结果不明的请求，避免同一行动重复执行。

语音转写会话的 idempotency 只防止重复创建录音任务；AI 请求的 idempotency 防止重复接收文本；游戏命令与配置发布仍有自己的幂等和审批语义。三者分别验收，不把上游成功或取消推断为下游执行结果。

## 7. 限额、错误、清理与用量

以下为可调整初值，不是已测性能或厂商上限；调整必须同步 capability 和验收夹具。

| 项目 | 首版默认 |
| --- | --- |
| 单轮音频 | 最长 120 秒；客户端和服务端分别按样本/时限限制 |
| 并发 | 每认证用户 1 轮，主机总计 4 轮；无排队等待录音，上限取账号配额与配置较小者 |
| 日预算 | 主机默认 60 音频分钟，按 Asia/Shanghai 日界；开始前原子预留最多 120 秒，防止并发超支 |
| 排队/发送缓冲 | 客户端和服务端各最多约 2 秒音频；超限失败，不丢帧续录 |
| 连接与尾部超时 | 创建后等待 WS 15 秒，上游就绪 10 秒，draining 最多 15 秒；3 秒未收到音频且未 stop 视为输入停滞 |
| 认证复核 | 创建、连接、读取及提交必须复核；活跃流每 1 秒复核，发现失效后立即关闭上游并清理；已外发字节无法撤回 |
| 临时会话 | 终态起 5 分钟可查询完整结果；之后过期；已编辑草稿由前端持有 |
| 音频与文本 | 音频仅存有界发送缓冲，不落盘；临时转写只在会话内存；不写入普通运行日志或错误遥测 |

预算记录采用语音模块独立的持久日聚合账本，至少存 profileRevision、日期、已结算/预留秒数及未对账请求 ID，不保存音频、文字、角色名或目标内容。结算用供应商累计计费时长；没有可靠用量时保留整轮预留，不自行按零成本释放。启动发现遗留预留时保守计入当日已用并标 unknown，避免重启清空预算。删除/改账只能通过明确管理操作。

| 稳定错误码 | 处理 |
| --- | --- |
| `MIC_DENIED / MIC_UNAVAILABLE / INSECURE_CONTEXT` | 前端错误；不创建收费任务，保留键盘入口 |
| `SPEECH_UNAVAILABLE / PROFILE_INVALID / PROVIDER_AUTH` | 配置或凭据问题；本轮不自动重试，提示管理员处理 |
| `TARGET_UNAVAILABLE / TARGET_STALE / AUTH_EXPIRED` | 停止采集及上游；不把结果写入新目标，发送前再授权 |
| `REQUEST_CONFLICT / STREAM_ALREADY_USED / PROTOCOL_INVALID` | 拒绝冲突或非法帧；不复用流、不静默修正 seq |
| `BUDGET_EXCEEDED / CONCURRENCY_LIMIT / AUDIO_LIMIT / TEXT_LIMIT` | 明确限额；正常到达录音时限用 stop，超过已授权音频字节才报 AUDIO_LIMIT |
| `PROVIDER_RATE_LIMIT / PROVIDER_TIMEOUT / PROVIDER_UNAVAILABLE` | 可稍后新开一轮；不自动重放旧音频或切换供应商 |
| `BACKPRESSURE_LIMIT / INPUT_STALLED / STREAM_LOST` | 本轮失败；可保存不完整稳定候选供人工编辑，不标完整 |
| `NO_SPEECH / RESULT_INCOMPLETE / PROVIDER_PROTOCOL_ERROR` | 无有效完整文字；不自动发送 AI |

HTTP 错误使用 `{code, retryable, sessionId?}`，状态按 400/401/403/409/413/429/503/504 分类；WS 就绪后用相同 code 事件再关闭。retryable 表示修复后可新建会话，不授权自动重放。供应商响应原文、密钥和内部端点不透传用户。

取消/终态/服务退出必须关闭上游连接，停止队列生产和消费，清除音频缓冲并结算或保留预算。进程重启不恢复音频流；GET 对已不存在的会话返回 `SESSION_EXPIRED`，前端保留已输入的文字。服务停止不得牵连现有房间或 AI 文本通道。

## 8. 本机与 LAN 部署

现有[后端](../../engineering/backend/src/onlinecoc/server.py)只允许本机 Host/Origin，普通 HTTP 请求 64 KiB；现有[LAN 网关](../../engineering/network-lan/src/onlinecoc_lan/gateway.py)只对 `/api/v1/connect` 转发 WS，且拒绝二进制帧。新增语音端点是独立路径，原房间通道限制保持原义，不能全局放开二进制或任意路由。

首批本机入口使用 localhost。LAN 阶段拟为独立网关增加可选 TLS 配置，提供受信任 HTTPS 页面与 WSS；宿主上游仍限回环 HTTP。网关必须配置精确 externalOrigin/Host 并校验后再改写上游 Origin，拒绝不匹配 Host、Origin 和任意转发头。不因用户使用了局域网地址就跳过麦克风安全上下文要求。

证书与私钥由部署者准备，域名/IP 必须匹配证书且受客户端信任；本计划不要求自动安装根证书，也不建议通过关闭浏览器安全检查验收。未满足证书条件时只交付“本机可用”，不能宣称 LAN 玩家场景已通过。

网关新增 capability、create/get/cancel、speech WS 和 `/speech-ui/` 静态资源的精确白名单，校验 Cookie/CSRF/Origin，分别限制音频帧与控制帧。CSP 只增同源控件/Worklet 所需规则；音频不直连厂商。浏览器真实加载 worklet、混合内容、TLS 信任及多客户端身份都属于 LAN 验收。

## 9. 首版验收门槛与待确认项

完整矩阵、任务分工和施工顺序唯一维护在[施工计划](speech-input-construction-plan.md)。建议质量目标为：安静普通话字符错误率不高于 10%，目标术语召回不低于 90%，数字及否定条件完整正确率不低于 95%；停止到完整结果可编辑的 p95 不超过 5 秒。这些是待 SI-0 锁定的产品目标，不是服务商承诺；不通过时修复、换型或公开缩小支持范围，不临时降低阈值冒充通过。

仍需在相应阶段前确认：供应商账号/配额与试测预算、目标设备和麦克风、人工标注语料、LAN 域名/证书，以及第 6 节的 AI 公共 args/回执、目标修订校验和动作/作者入口责任者。AI-0 字段已核对，桥接选择仍需在 SI-0 与接收端契约共同冻结；缺少相应条件时只能交付对应阶段的部分证据。

## 10. 文档关系与来源

调研保留方案市场比较与价格依据；本文是推荐架构、协议和边界的唯一来源；施工计划是任务及验收的唯一来源。后续更改服务商、帧协议或 AI 端口须同时更新本文和相关契约测试计划，已验证能力才进入当前工程文档。

本次官方接口及浏览器文档查阅日期均为 **2026-11-12**：

- [Fun-ASR-Realtime WebSocket 接入](https://help.aliyun.com/zh/model-studio/fun-asr-realtime-websocket-api)
- [客户端事件与参数](https://help.aliyun.com/zh/model-studio/fun-asr-client-events)
- [服务端事件与计费时长字段](https://help.aliyun.com/zh/model-studio/fun-asr-server-events)
- [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)、[MDN AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet)

上述资料支持厂商协议和浏览器前提；本文自己的 URL、状态机、限额、目标阈值和 AI 文本端口均为项目设计建议。
