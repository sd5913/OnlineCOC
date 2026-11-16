import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {formatMessage} from '@localizer/messages';
import './style.css';
declare global {interface Window {localizer: {chooseProject(): Promise<{handle: string; name: string; version: string} | null>}}}
function App() {
  const [project, setProject] = useState('尚未选择项目');
  const [locale, setLocale] = useState('en');
  const [count, setCount] = useState(3);
  const [template, setTemplate] = useState('{count, plural, one {# slot remaining} other {# slots remaining}}');
  const result = formatMessage(template, locale, {count: {type: 'number'}}, {count});
  return <main><header><span className="brand">L / LOCALIZER</span><span className="badge">开发预览 · L10N-0</span></header><section className="intro"><p className="eyebrow">文件协作 / 独立运行</p><h1>让每一条文案，<br/>都有清楚的来处。</h1><p className="muted">英文原文 → 中文翻译。项目文件属于你，编辑工具独立运行。</p><button onClick={async () => {const p = await window.localizer.chooseProject(); if (p) setProject(p.name);}}>选择项目目录</button><output className="project">{project}</output></section><section className="preview"><h2>共享文本解析试验</h2><p className="muted">此阶段仅验证窗口与解析链路；正式文件编辑将在事务验收后接入。</p><label>ICU 模板<textarea aria-label="ICU 模板" value={template} onChange={e => setTemplate(e.target.value)}/></label><div className="row"><label>预览语言<select aria-label="预览语言" value={locale} onChange={e => setLocale(e.target.value)}><option>en</option><option>zh-CN</option></select></label><label>count<input aria-label="count" type="number" value={count} onChange={e => setCount(Number(e.target.value))}/></label></div><output aria-label="解析结果" className={result.ok ? 'result' : 'result error'}>{result.ok ? result.text : `${result.code}：${result.message}`}</output></section><footer>独立开发工具 · 无游戏服务连接 · 本地文件为协作基础</footer></main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
