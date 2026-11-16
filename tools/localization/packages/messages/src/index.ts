import {IntlMessageFormat} from 'intl-messageformat';
import {parse, TYPE, type MessageFormatElement} from '@formatjs/icu-messageformat-parser';
import {LIMITS, type Params, type FormatResult} from '@localizer/contracts';

export function inspectMessage(text: string, params: Params = {}) {
  if (new TextEncoder().encode(text).length > LIMITS.messageBytes) throw new Error('消息超过 32 KiB');
  if (Object.keys(params).length > LIMITS.params) throw new Error('参数超过 32 个');
  const ast = parse(text, {ignoreTag: true, requiresOtherClause: true});
  const used = new Set<string>();
  function walk(nodes: MessageFormatElement[], depth: number) {
    if (depth > LIMITS.depth) throw new Error('消息嵌套超过 16 层');
    for (const n of nodes) {
      if (n.type === TYPE.literal || n.type === TYPE.pound) continue;
      if (![TYPE.argument, TYPE.select, TYPE.plural].includes(n.type)) throw new Error('仅支持命名参数、select 和基数 plural');
      const name = 'value' in n ? n.value : '';
      if (!Object.hasOwn(params, name)) throw new Error(`未声明参数 ${name}`);
      used.add(name);
      if (n.type === TYPE.plural && (n.pluralType !== 'cardinal' || params[name].type !== 'number' || n.offset !== 0)) throw new Error(`plural 参数 ${name} 必须为 number，且不支持 offset/ordinal`);
      if (n.type === TYPE.select && params[name].type === 'number') throw new Error(`select 参数 ${name} 必须为 string/enum`);
      if (n.type === TYPE.plural || n.type === TYPE.select) for (const option of Object.values(n.options)) walk(option.value, depth + 1);
    }
  }
  walk(ast, 0);
  for (const key of Object.keys(params)) if (!used.has(key)) throw new Error(`模板缺少参数 ${key}`);
  return ast;
}

export function formatMessage(text: string, locale: string, contract: Params = {}, values: Record<string, unknown> = {}): FormatResult {
  try {
    const ast = inspectMessage(text, contract);
    for (const [name, p] of Object.entries(contract)) {
      const v = values[name];
      if (p.type === 'number' ? typeof v !== 'number' || !Number.isFinite(v) : typeof v !== 'string') throw new Error(`参数 ${name} 类型错误`);
      if (p.type === 'enum' && !p.values?.includes(v as string)) throw new Error(`参数 ${name} 不在允许值中`);
    }
    const value = new IntlMessageFormat(ast, locale).format(values as Record<string, string | number>);
    if (typeof value !== 'string') throw new Error('格式化未返回文本');
    return {ok: true, text: value};
  } catch (e) {
    return {ok: false, code: 'MESSAGE_INVALID', message: e instanceof Error ? e.message : '消息不可用'};
  }
}
