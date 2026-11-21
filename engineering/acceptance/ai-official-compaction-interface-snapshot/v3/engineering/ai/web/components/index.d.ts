export type Json = null | boolean | number | string | Json[] | {[key: string]: Json};
export interface Transport {
  request(path: string, options?: {method?: 'GET' | 'POST'; body?: Json; csrf?: string}): Promise<any>;
}
export class HttpTransport implements Transport {
  constructor(base?: string);
  request: Transport['request'];
}
export interface AiReceipt<T = Json> {
  requestId: string;
  status: 'pending' | 'committed' | 'rejected' | 'unknown';
  result?: T;
  code?: string;
  resultUnavailable?: boolean;
}
export interface SessionAccess {
  knowledge: {mode: 'strict-known'; status: 'ready' | 'blocked' | 'unavailable'; code?: string; notice: string};
  role: 'kp' | 'player'; canChat: boolean; defaultLevel: 'administrator' | 'player'; revision: number;
  allowAdminRoomRead: boolean; allowDataQueries: boolean; allowRuntimeChanges: boolean; allowConfigurationChanges: boolean; allowKnowledgeRequests: boolean; allowPlayerRequests: boolean;
  allowPlayerChat: boolean; autoApproveBatches: boolean; autoApproveConfigurations: boolean;
}
export interface Session {
  sessionId: string; owner: string; title: string; revision: number; archived: boolean;
  accessLevel: 'administrator' | 'player'; deleted?: boolean;
  createdAt: number; updatedAt: number;
  pinned: boolean; historyTurns: number; renderMode: 'formatted' | 'plain'; showDiagnostics: boolean;
}
export interface ResponseOption {id: string; label: string; text: string}
export interface ResponseChoices {prompt: string; options: ResponseOption[]}
export function mountChoices(target: HTMLElement, choices: ResponseChoices | null, options?: {onSelect?: ((option: ResponseOption) => void) | null; disabled?: boolean; hintText?: string | null}): {update(choices: ResponseChoices | null, options?: {onSelect?: ((option: ResponseOption) => void) | null; disabled?: boolean; hintText?: string | null}): void; destroy(): void};
export interface KnowledgeRequest {rulingId: string; sessionId: string; requestId: string; status: string; createdAt: number; digest: string}
export interface QueueItem {queueTargetId: string; queueDigest: string; queueStatus: 'active' | 'history' | 'superseded' | 'archived'; correlationId: string; canArchive: boolean; canRestore: boolean; archived: boolean; archiveReason?: string; supersededBy?: string; supersedes: string[]; resolution?: {targetId: string; correlationId: string; goalDigest: string; receiptRefs: {target: 'host' | 'ai'; account: string; commandId: string}[]; completedAt: number | null}}
export interface ReviewSource {correlationKey?: string; kind: "ruling" | "package" | "request"; sourceId?: string; category?: string; id?: string; revision?: string; rulingId?: string; digest?: string; sessionId?: string; requestId?: string; title?: string; requestedBy?: string; summary?: string; context?: Record<string,Json>}
export interface DebugQuery {sessionId?: string; requestId?: string; rulingId?: string; includeContent?: boolean}
export interface Task extends Partial<QueueItem> {
  events?: {seq:number; at:number; stage:string; status:'running'|'completed'|'failed'; summary:string; durationMs?:number; tool?:string; operation?:string; receiptStatus?:string; code?:string}[];
  dependencyCheck?: {snapshotAt:number; checkedAt:number; status:'changed'|'unchanged'; totalChanges:number; canRegenerate:boolean; changes:{kind:string; id:string; code:string; summary:string}[]};
  sourceState?: 'fresh' | 'stale' | 'denied';
  sourceError?: string;
  sourceNotice?: string;
  historicalReadOnly?: boolean;
  sentAt?: number;
  responseAt?: number | null;
  referenceLabels?: Record<string,string>;
  /** KP review: original player from explicit stored provenance, if known. */
  recipientAccountId?: string;
 reviewSource?: ReviewSource; modelCalls?: {requestedModel?: string; returnedModel?: string | null; systemFingerprint?: string | null; usage?: Record<string,number>; profileRevision?: number}[];
  knowledgeRequest?: KnowledgeRequest;
  playerRequest?: KnowledgeRequest;
  sessionId?: string | null;
  choices?: ResponseChoices;
  requestId: string; status: string; createdAt: number;
  text?: string; response?: string; proposalId?: string; batchId?: string; taskId?: string; error?: string;
  /** KP only. No raw arguments, exception text, credentials or local file paths. */
  diagnostics?: {
    schemaVersion: 1; stage: string; turn: number;
    compression?: {round:number;kind?:'prune'|'summary';trigger?:'pressure'|'overflow';beforeBytes:number;afterBytes?:number;afterPruneBytes?:number;afterExtractionBytes?:number;recordCount:number;summaryDigest?:string;status:string;code?:string;repairCount?:number;cacheHits?:number;recordLocators?:number;prunedResults?:number;retainedBytes?:number;checkpointReplaced?:boolean;summaryCalls?:number;summaryDurationMs?:number;repairs?:{attempt:number;code:string}[]}[];
    contextPolicy?: {contextWindowTokens:number;compressAtBytes:number;retainBytes:number;headroomTokens:number;modelTriggerTokens:number;measurement:'conservative-utf8-bytes'};
    contextOverflow?: {retries:number;status:string};
    contextBudget?: {bytes:number;limitBytes:number;toolSchemaBytes:number;toolMessageBytes:number};
    toolCalls: {name: string; status: string; turn: number; argumentsDigest: string;
      keys: string[]; unknownKeys: boolean; types?: string[]; referenceCount?: number; hasQuery?: boolean; code?: string}[];
    errors: {stage: string; code: string; exceptionType: string; httpStatus?: number;
      frames: {module: string; function: string; line: number}[]}[];
  };
}
export class AiClient {
  constructor(transport?: Transport);
  readonly transport: Transport;
  connected: boolean;
  view: any;
  subscribe(listener: (client: AiClient) => void): () => void;
  login(loginName: string, password: string): Promise<void>;
  resume(): Promise<void>;
  sync(): Promise<void>;
  logout(): Promise<unknown>;
  stop(): void;
  destroy(): void;
  aiCommand<T = Json>(op: string, args: Json, id?: string): Promise<AiReceipt<T>>;
  aiReceipt<T = Json>(id: string): Promise<AiReceipt<T>>;
  aiTasks(options?: {before?: string; limit?: number}): Promise<{items: Task[]; nextBefore: string | null}>;
  aiSessions(archived?: boolean): Promise<{items: (Session & {requestCount: number})[]; access: SessionAccess}>;
  aiSession(id: string): Promise<{session: Session; items: Task[]}>;
  aiProposal(id: string): Promise<any>;
  aiSettings(): Promise<any>;
  aiAccess(): Promise<SessionAccess>;
  aiRulings(): Promise<{items: AIRuling[]}>;
  aiBatches(): Promise<{items: ExecutionBatch[]}>;
  aiDebug(options: DebugQuery): Promise<Json>;
  aiReview(source: ReviewSource, instruction?: string): Promise<AiReceipt>;
  aiUsage(options?: UsageQuery): Promise<UsageReport>;
  aiContracts(): Promise<{version: number; operations: Record<string, Json>; $defs: Record<string, Json>}>;
  aiReferences(kind?: 'config' | 'entity' | 'data' | 'chat' | 'event' | 'ruling' | 'knowledge', q?: string): Promise<{items: DataReference[]; hasMore: boolean}>;
  aiData(operation: 'search' | 'read' | 'chat' | 'case', args: Record<string, Json>): Promise<EvidencePage>;
  aiResolve(tokens: string[]): Promise<{items: (DataReference & {value: Json})[]}>;
  command(op: string, args: Json, id?: string): Promise<any>;
  receipt(id: string): Promise<any>;
}
export interface Panel {refresh(): Promise<void>; destroy(): void}
export interface SessionManager extends Panel {select(id: string): Promise<void>; suspend(): void; resume(): Promise<void>}
export function mountSessionManager(target: HTMLElement, client: AiClient, options?: {
  title?: string; onOpen?: ((id: string) => void | Promise<void>) | null;
  onChange?: (session: Session) => void | Promise<void>;
}): SessionManager;
/** Synchronous, trusted package renderer. Receives an authorized full DTO; null uses the common view. */
export type ReferenceRenderer = (item: DataReference, context: {audience: "player" | "administrator"; readOnly: true}) => Node | null;
export interface MarkdownOptions {
  renderReference?: ReferenceRenderer | null;
  /** Display mode only; data must already be authorized. Default: player. */
  audience?: "player" | "administrator";
  plainText?: boolean;
  resolveReferences?: (tokens: string[]) => Promise<{items: DataReference[]}>;
}
/** DOM-only Markdown subset; use hydrateReferences after rendering to resolve labels. */
export function renderMarkdown(target: HTMLElement, text: string, options?: MarkdownOptions): void;
export function mountMarkdown(target: HTMLElement, text: string, options?: MarkdownOptions): {update(text: string, options?: MarkdownOptions): void; destroy(): void};
export interface RoomPanel extends Panel {showBatches(): Promise<void>; review(id: string): Promise<void>; reloadSettings(): Promise<void>}
export function mountAI(client: AiClient, options: {target: HTMLElement; onReceipt?: (id: string) => void}): RoomPanel;
export function mountSessions(target: HTMLElement, client: AiClient, options?: {
  onReview?: (id: string) => void; onError?: (error: Error) => void;
  t?: (key: string, fallback: string) => string;
}): Panel;
/** Requires the local manager API, not a room's transport. Never expose it to PL. */
export function mountProviders(target: HTMLElement, api: {request(path: string, body?: Json): Promise<any>}, options?: {onChange?: () => void}): Panel;
export function requestId(): string;
export interface DataReference {kind: 'config' | 'entity' | 'data' | 'chat' | 'event' | 'ruling' | 'knowledge'; id: string; label: string; revision: string; visibility: string; token?: string; value?: Json}
export function mountChat(target: HTMLElement, client: AiClient, options?: {listTarget?: HTMLElement; debugTarget?: HTMLElement; renderReference?: ReferenceRenderer | null; onOpenSource?: ((source: ReviewSource) => void | Promise<void>) | null; onReview?: ((id: string | null) => void | Promise<void>) | null; onChange?: (sessions: Session[]) => void; onSelect?: (session: Session | null) => void}): Panel & {newChat(): Promise<void>; select(id: string): Promise<void>; showDebug(requestId?: string): void; showArchived(): Promise<boolean>; applySessionChange(session: Session): Promise<void>; suspend(): void; resume(options?: {sessionId?: string}): Promise<void>; setDraft(text: string, references?: DataReference[]): void; insertReference(item: DataReference): void};
export function bindReferenceInput(input: HTMLTextAreaElement | HTMLElement, container: HTMLElement, client: AiClient, options?: {editor?: ReferenceEditor}): {reset(): void; destroy(): void};

export interface ReferenceEditor {
  readonly element: HTMLElement; readonly value: string; readonly displayText: string; readonly composing: boolean;
  cursor(): {start: number; end: number};
  replace(start: number, end: number, text: string, reference?: DataReference): void;
  setValue(text: string, references?: DataReference[]): void;
  insertReference(item: DataReference): void;
  destroy(): void;
}
export function createReferenceEditor(element: HTMLElement, options?: {resolveReferences?: (tokens: string[]) => Promise<{items: DataReference[]}>}): ReferenceEditor;
export function renderReferenceText(target: HTMLElement, text: string): void;
export function hydrateReferences(target: HTMLElement, resolve: (tokens: string[]) => Promise<{items: DataReference[]}>, valid?: () => boolean): Promise<void>;

export interface ReferenceCommand {readonly kind: 'config' | 'entity' | 'data' | 'chat' | 'event' | 'ruling' | 'knowledge'; readonly label: string; readonly hint: string}
export const REFERENCE_COMMANDS: readonly ReferenceCommand[];
export function referenceCommands(role?: string): readonly ReferenceCommand[];
export function referenceToken(item: DataReference): string;
export interface AIViewOptions {
 renderReference?: ReferenceRenderer | null;
 onOpenSource?: ((source: ReviewSource) => void | Promise<void>) | null;
  title?: string; review?: boolean; onReview?: (proposalId?: string | null) => void | Promise<void>;
  onReceipt?: (id: string) => void; onSessions?: (sessions: Session[]) => void; onSession?: (session: Session | null) => void;
}
export interface AIView extends Panel {
  select(id: string): Promise<void>; newChat(): Promise<void>;
  setDraft(text: string, references?: DataReference[]): void; insertReference(item: DataReference): void;
  review(id?: string): Promise<void>; manageSessions(): Promise<void>; showUsage(): Promise<void>; suspend(): void; resume(options?: {sessionId?: string}): Promise<void>;
}
export interface AICollapsible extends AIView {open(): void; close(): void; toggle(): void; readonly isOpen: boolean}
export function mountAIPage(target: HTMLElement, client: AiClient, options?: AIViewOptions): AIView;
export function mountAIConversation(target: HTMLElement, client: AiClient, options?: AIViewOptions): AIView;
export function mountAICollapsible(target: HTMLElement, client: AiClient, options?: AIViewOptions & {open?: boolean; onToggle?: (open: boolean) => void}): AICollapsible;
export interface EvidencePage {
  schemaVersion: number;
  snapshotId: string;
  items: {ref: {sourceId: string; kind: string; id: string; revision: string; digest: string; scopeId: string}; label: string; visibility: string; authority: string; data?: Json}[];
  page: {nextCursor: string | null};
  coverage: {status: 'complete' | 'partial'; within: string};
}
export interface AITools {
 debug(options: DebugQuery): Promise<Json>;
 review(source: ReviewSource, instruction?: string, id?: string): Promise<Json>;
  data: {search(args: Record<string, Json>): Promise<EvidencePage>; read(args: Record<string, Json>): Promise<EvidencePage>; chat(args: Record<string, Json>): Promise<EvidencePage>; case(args: Record<string, Json>): Promise<EvidencePage>};
  sessions: {
    list(archived?: boolean): Promise<{items: (Session & {requestCount: number})[]; access: SessionAccess}>;
    get(id: string): Promise<{session: Session; items: Task[]}>;
    create(title: string, commandId?: string, accessLevel?: 'administrator' | 'player'): Promise<AiReceipt<Session>>;
    update(sessionId: string, revision: number, changes: Partial<Pick<Session, 'title' | 'archived' | 'pinned' | 'historyTurns' | 'renderMode' | 'showDiagnostics'>>, commandId?: string): Promise<AiReceipt<Session>>;
    delete(sessionId: string, revision: number, commandId?: string): Promise<AiReceipt<Session>>;
    submit(sessionId: string, text: string, commandId?: string, options?: {submissionKey?: string; replyToRequestId?: string}): Promise<AiReceipt<{requestId: string; sessionId: string; taskId?: string; dispatchError?: string; awaitingKnowledge?: boolean}>>;
  };
  requests: {
    list(options?: {before?: string; limit?: number}): ReturnType<AiClient['aiTasks']>;
    submit(text: string, commandId?: string): Promise<AiReceipt>;
    dispatch(requestId: string, commandId?: string): Promise<AiReceipt>;
    cancel(requestId: string, commandId?: string): Promise<AiReceipt>;
  };
  references: {commands(): readonly ReferenceCommand[]; token(item: DataReference): string;
    search(kind: 'config' | 'entity' | 'data' | 'chat' | 'event' | 'ruling' | 'knowledge', q?: string): ReturnType<AiClient['aiReferences']>;
    resolve(tokens: string[]): ReturnType<AiClient['aiResolve']>};
  review: {get(id: string): Promise<any>; validate(proposalId: string, revision: number, commandId?: string): Promise<AiReceipt>;
    approve(proposalId: string, proposalRevision: number, riskDecisions: Record<string, string>, commandId?: string): Promise<AiReceipt>;
    apply(approvalId: string, commandId?: string): Promise<AiReceipt>; revoke(approvalId: string, commandId?: string): Promise<AiReceipt>};
  settings: {get(): Promise<any>; update(settings: Json, commandId?: string): Promise<AiReceipt>};
  receipts: {ai(id: string): Promise<AiReceipt>; host(id: string): Promise<any>};
  access: {get(): Promise<SessionAccess>; update(value: Pick<SessionAccess, 'revision' | 'allowPlayerChat' | 'autoApproveBatches'> & Partial<Pick<SessionAccess,'autoApproveConfigurations' | 'allowAdminRoomRead' | 'allowDataQueries' | 'allowRuntimeChanges' | 'allowConfigurationChanges' | 'allowKnowledgeRequests' | 'allowPlayerRequests'>>, commandId?: string): Promise<AiReceipt>};
  playerRequests: {submit(value: {sessionId: string} & ({text: string; submissionKey?: string; requestId?: never} | {requestId: string; text?: never}), commandId?: string): Promise<AiReceipt<KnowledgeRequest>>};
  knowledgeRequests: {submit(sessionId: string, requestId: string, commandId?: string): Promise<AiReceipt<KnowledgeRequest>>; reconcile(value: {rulingId: string; digest: string}, commandId?: string): Promise<AiReceipt<KnowledgeRequest>>};
  queue: {archive(value: {targetId: string; digest: string; archived: boolean; reason?: string}, commandId?: string): Promise<AiReceipt<QueueItem>>};
  rulings: {list(): ReturnType<AiClient["aiRulings"]>; decide(value: RulingDecision, commandId?: string): Promise<AiReceipt<AIRuling>>};
  batches: {list(): Promise<{items: ExecutionBatch[]}>; approve(batchId: string, digest: string, commandId?: string): Promise<AiReceipt>; reject(batchId: string, digest: string, commandId?: string): Promise<AiReceipt>; reconcile(batchId: string, digest: string, commandId?: string): Promise<AiReceipt>};
  usage(options?: UsageQuery): Promise<UsageReport>;
  contracts(): ReturnType<AiClient['aiContracts']>; destroy(): void;
}
export function createAITools(client: AiClient): AITools;

export interface UsageQuery {from?: string; to?: string; scope?: 'mine' | 'room'; profileId?: string; sessionId?: string; before?: string; limit?: number}
export interface UsageMetrics {calls: number; settledCalls: number; pendingCalls: number; uncertainCalls: number; confirmedTokens: number; promptTokens: number; completionTokens: number; missingBreakdownCalls: number; pendingReservedTokens: number; uncertainReservedTokens: number; accountedTokens: number}
export interface UsageReport {
 schemaVersion: 1; scopeId: string; scope: 'mine' | 'room'; timezone: 'UTC'; from: string; to: string; totals: UsageMetrics;
 byDay: (UsageMetrics & {date: string})[];
 byProfile: (UsageMetrics & {profileId: string; model: string | null})[];
 budgetsToday: {profileId: string; date: string; dailyTokenBudget: number | null; enabled: boolean; accountedTokens: number; remainingTokens: number | null}[];
 items: (UsageMetrics & {callId: string; date: string; profileId: string; model: string | null; requestId: string | null; sessionId: string | null; status: 'confirmed' | 'pending' | 'uncertain'; taskStatus: string | null; createdAt: number | null})[];
 nextBefore: string | null;
}
export interface UsagePanel extends Panel {setSession(id: string | null): Promise<void>; suspend(): void; resume(): Promise<void>}
export function mountUsage(target: HTMLElement, client: AiClient, options?: {sessionId?: string | null; scope?: 'mine' | 'room'}): UsagePanel;

/** AI candidate field only; execution resolves the approved earlier host action to sourceCommandId/sourceOp. */
export interface NotificationActionArgs {recipientAccountIds: string[]; text: string; sourceActionIndex: number}
export interface ExecutionBatch {batchId: string; sessionId: string; requestId: string; creator: string; summary: string; revision: number; digest: string; status: string; actions: {target: "host" | "ai"; op: string; args: Json}[]; receipts: Json[]; createdAt: number}

/** Resolve on every open; close/destroy when the caller changes identity. */
export function bindReferenceDetails(target: HTMLElement, resolveReferences: NonNullable<MarkdownOptions["resolveReferences"]>, options?: {container?: HTMLElement | ShadowRoot; valid?: () => boolean; renderReference?: ReferenceRenderer | null; audience?: "player" | "administrator" | (() => "player" | "administrator")}): {open(token: string, anchor?: HTMLElement | null): Promise<void> | undefined; refresh(): Promise<void>; close(): void; destroy(): void};

export interface AIRuling extends Partial<QueueItem> {consultationAssessment?: {requiresAcceptance:boolean;sourceCount:number;sourceDigest:string;notice:string};sourceState?: 'fresh' | 'stale' | 'denied'; sourceError?: string; sourceNotice?: string; sourceUnavailable?: boolean; sourceDetailsUnavailable?: boolean; historicalReadOnly?: boolean;reviewSessionId?: string; generationError?: string;createdAt: number; initiator?: string; rulingId: string; blockingReason?: string; kind: "runtime" | "configuration" | "knowledge_request" | "player_request"; highRisk?: boolean; riskTags?: string[]; diff?: Json[]; sessionId: string | null; requestId: string; summary: string; status: string; digest: string; canDecide: boolean; risks: {id: string; question: string; required: boolean}[]; receipts: Json[]; actions?: Json[]; changeSet?: Json; reports?: Json[]; publications?: Json[]}
export interface RulingDecision {consultationReview?: {sourceDigest:string};cReview?: {basisRevision:number;basisDigest:string;reportDigest:string};rulingId: string; digest: string; decision: "approve" | "reject"; riskDecisions?: Record<string,string>; explicitHighRiskDigest?: string; disclosures?: {op: 'knowledge.observe'; args: Record<string,Json>}[]}
export function mountRulings(target: HTMLElement, client: AiClient, options?: {compact?: boolean; onOpenSource?: ((source: ReviewSource) => void | Promise<void>) | null; onKnowledgeRequest?: (item: AIRuling) => void | Promise<void>; onOpenSession?: (sessionId: string) => void | Promise<void>; onChange?: (ruling: AIRuling) => void}): Panel;
export function mountAISettings(target: HTMLElement, client: AiClient, options?: {onChange?: (result: Json) => void; onReceipt?: (aiRequestId: string) => void}): Panel;

export function appendDebugTools(target: HTMLElement, client: AiClient, locator: DebugQuery | (() => DebugQuery), options?: {valid?: () => boolean}): HTMLDetailsElement;
export function appendReviewSource(target: HTMLElement, source: ReviewSource, options?: {onOpenSource?: ((source: ReviewSource) => void | Promise<void>) | null; onOpenSession?: ((sessionId: string) => void | Promise<void>) | null}): HTMLDetailsElement;
