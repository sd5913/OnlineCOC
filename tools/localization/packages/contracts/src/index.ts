export const VERSION = '0.1.0';
export const SCHEMA_VERSION = 1;
export const LIMITS = Object.freeze({fileBytes: 8 * 1024 * 1024, projectBytes: 64 * 1024 * 1024, messageBytes: 32768, params: 32, depth: 16, filesPerChange: 500});
export type Param = {type: 'string' | 'number' | 'enum'; values?: string[]; example?: string | number};
export type Params = Record<string, Param>;
export type Diagnostic = {severity: 'error' | 'warning'; code: string; file: string; jsonPointer: string; namespace?: string; key?: string; locale?: string; message: string; fixHint?: string};
export type FormatResult = {ok: true; text: string} | {ok: false; code: string; message: string};
