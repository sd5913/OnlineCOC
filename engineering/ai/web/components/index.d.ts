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
export interface Session {
  sessionId: string; owner: string; title: string; revision: number; archived: boolean;
  createdAt: number; updatedAt: number;
  pinned: boolean; historyTurns: number; renderMode: 'formatted' | 'plain'; showDiagnostics: boolean;
}
export interface Task {
  requestId: string; status: string; createdAt: number;
  text?: string; response?: string; proposalId?: string; taskId?: string; error?: string;
  /** KP only. No raw arguments, exception text, credentials or local file paths. */
  diagnostics?: {
    schemaVersion: 1; stage: string; turn: number;
    toolCalls: {name: string; status: string; turn: number; argumentsDigest: string;
      keys: string[]; unknownKeys: boolean; types?: string[]; referenceCount?: number; hasQuery?: boolean; code?: string}[];
    errors: {stage: string; code: string; exceptionType: string;
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
  aiSessions(archived?: boolean): Promise<{items: (Session & {requestCount: number})[]}>;
  aiSession(id: string): Promise<{session: Session; items: Task[]}>;
  aiProposal(id: string): Promise<any>;
  aiSettings(): Promise<any>;
  aiUsage(options?: UsageQuery): Promise<UsageReport>;
  aiContracts(): Promise<{version: number; operations: Record<string, Json>; $defs: Record<string, Json>}>;
  aiReferences(kind?: 'config' | 'entity' | 'data' | 'chat' | 'event' | 'ruling', q?: string): Promise<{items: DataReference[]; hasMore: boolean}>;
  aiData(operation: 'search' | 'read' | 'chat' | 'case', args: Record<string, Json>): Promise<EvidencePage>;
  aiResolve(tokens: string[]): Promise<{items: (DataReference & {value: Json})[]}>;
  command(op: string, args: Json, id?: string): Promise<any>;
  receipt(id: string): Promise<any>;
}
export interface Panel {refresh(): Promise<void>; destroy(): void}
export interface SessionManager extends Panel {select(id: string): Promise<void>; suspend(): void; resume(): Promise<void>}
export function mountSessionManager(target: HTMLElement, client: AiClient, options?: {
  title?: string; onOpen?: ((id: string) => void | Promise<void>) | null;
  onChange?: (session: Session) => void;
}): SessionManager;
export interface MarkdownOptions {plainText?: boolean; resolveReferences?: (tokens: string[]) => Promise<{items: DataReference[]}>}
/** DOM-only Markdown subset; use hydrateReferences after rendering to resolve labels. */
export function renderMarkdown(target: HTMLElement, text: string, options?: MarkdownOptions): void;
export function mountMarkdown(target: HTMLElement, text: string, options?: MarkdownOptions): {update(text: string, options?: MarkdownOptions): void; destroy(): void};
export interface RoomPanel extends Panel {review(id: string): Promise<void>; reloadSettings(): Promise<void>}
export function mountAI(client: AiClient, options: {target: HTMLElement; onReceipt?: (id: string) => void}): RoomPanel;
export function mountSessions(target: HTMLElement, client: AiClient, options?: {
  onReview?: (id: string) => void; onError?: (error: Error) => void;
  t?: (key: string, fallback: string) => string;
}): Panel;
/** Requires the local manager API, not a room's transport. Never expose it to PL. */
export function mountProviders(target: HTMLElement, api: {request(path: string, body?: Json): Promise<any>}, options?: {onChange?: () => void}): Panel;
export function requestId(): string;
export interface DataReference {kind: 'config' | 'entity' | 'data' | 'chat' | 'event' | 'ruling'; id: string; label: string; revision: string; visibility: string; token?: string}
export function mountChat(target: HTMLElement, client: AiClient, options?: {listTarget?: HTMLElement; onReview?: ((id: string) => void) | null; onChange?: (sessions: Session[]) => void; onSelect?: (session: Session) => void}): Panel & {newChat(): Promise<void>; select(id: string): Promise<void>; showArchived(): Promise<void>; suspend(): void; resume(): Promise<void>; setDraft(text: string, references?: DataReference[]): void; insertReference(item: DataReference): void};
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

export interface ReferenceCommand {readonly kind: 'config' | 'entity' | 'data' | 'chat' | 'event' | 'ruling'; readonly label: string; readonly hint: string}
export const REFERENCE_COMMANDS: readonly ReferenceCommand[];
export function referenceCommands(role?: string): readonly ReferenceCommand[];
export function referenceToken(item: DataReference): string;
export interface AIViewOptions {
  title?: string; review?: boolean; onReview?: (proposalId?: string) => void | Promise<void>;
  onReceipt?: (id: string) => void; onSessions?: (sessions: Session[]) => void; onSession?: (session: Session) => void;
}
export interface AIView extends Panel {
  select(id: string): Promise<void>; newChat(): Promise<void>;
  setDraft(text: string, references?: DataReference[]): void; insertReference(item: DataReference): void;
  review(id?: string): Promise<void>; manageSessions(): Promise<void>; showUsage(): Promise<void>; suspend(): void; resume(): Promise<void>;
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
  data: {search(args: Record<string, Json>): Promise<EvidencePage>; read(args: Record<string, Json>): Promise<EvidencePage>; chat(args: Record<string, Json>): Promise<EvidencePage>; case(args: Record<string, Json>): Promise<EvidencePage>};
  sessions: {
    list(archived?: boolean): Promise<{items: (Session & {requestCount: number})[]}>;
    get(id: string): Promise<{session: Session; items: Task[]}>;
    create(title: string, commandId?: string): Promise<AiReceipt<Session>>;
    update(sessionId: string, revision: number, changes: Partial<Pick<Session, 'title' | 'archived' | 'pinned' | 'historyTurns' | 'renderMode' | 'showDiagnostics'>>, commandId?: string): Promise<AiReceipt<Session>>;
    submit(sessionId: string, text: string, commandId?: string): Promise<AiReceipt<{requestId: string; sessionId: string}>>;
  };
  requests: {
    list(options?: {before?: string; limit?: number}): ReturnType<AiClient['aiTasks']>;
    submit(text: string, commandId?: string): Promise<AiReceipt>;
    dispatch(requestId: string, commandId?: string): Promise<AiReceipt>;
    cancel(requestId: string, commandId?: string): Promise<AiReceipt>;
  };
  references: {commands(): readonly ReferenceCommand[]; token(item: DataReference): string;
    search(kind: 'config' | 'entity' | 'data' | 'chat' | 'event' | 'ruling', q?: string): ReturnType<AiClient['aiReferences']>;
    resolve(tokens: string[]): ReturnType<AiClient['aiResolve']>};
  review: {get(id: string): Promise<any>; validate(proposalId: string, revision: number, commandId?: string): Promise<AiReceipt>;
    approve(proposalId: string, proposalRevision: number, riskDecisions: Record<string, string>, commandId?: string): Promise<AiReceipt>;
    apply(approvalId: string, commandId?: string): Promise<AiReceipt>; revoke(approvalId: string, commandId?: string): Promise<AiReceipt>};
  settings: {get(): Promise<any>; update(settings: Json, commandId?: string): Promise<AiReceipt>};
  receipts: {ai(id: string): Promise<AiReceipt>; host(id: string): Promise<any>};
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
