"""Deterministic, dependency-free bundling of the package's fixed module graph.

Each module retains its lexical scope. This is deliberately not a general JS bundler.
Only explicitly listed public UI/resources enter the export source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from integrations import PACK, ROOT, export_tree, write_json


UI_MODULES = ('messageformat.js','i18n.js','reference-view.js','chat.js','dice.js','effects.js','map.js','ai-recovery.js','ruling-card.js','batch-details.js','keeper-rulings.js','keeper-queue.js','ai.js','ai-embedded.js','app.js')


def ai_modules():
    """Compile the declared public component graph, with CSS inside shadow roots."""
    base=ROOT/'engineering/ai/web/components'
    declared=json.loads((base/'pack-manifest.json').read_text(encoding='utf-8'))['runtimeFiles']
    names=['styles.js','client.js','guard.js','debug.js','settings.js','reference-commands.js','reference-editor.js','reference-details.js','markdown.js','reference-input.js','tools.js','choices.js','chat.js','rulings.js','room-panel.js','sessions.js','session-manager.js','usage.js','views.js']
    output='const aiModules={};\n'
    for name in names:
        assert name in declared
        code=(base/name).read_text(encoding='utf-8')
        # A missing upstream dependency would otherwise compile successfully and
        # only fail while evaluating the exported page in the player sandbox.
        dependencies=re.findall(r"import\s+\{[^}]+\}\s+from\s+'\./([^']+)';",code)
        assert all(dep in names[:names.index(name)] for dep in dependencies), (name, dependencies)
        exports=re.findall(r'export\s+(?:async\s+)?(?:const|function|class)\s+(\w+)',code)
        code=re.sub(r"import\s+\{([^}]+)\}\s+from\s+'\./([^']+)';",lambda m:'const {'+re.sub(r'\b([\w$]+)\s+as\s+([\w$]+)\b',r'\1:\2',m[1])+'}=aiModules['+json.dumps(m[2])+'];',code)
        def style(match):
            filename=match[1];assert filename in declared
            return "mountStyle(root,"+json.dumps('inline:'+filename)+","+json.dumps((base/filename).read_text(encoding='utf-8'))+");"
        code=re.sub(r"mountStyle\(root,new URL\('\./([^']+)',import.meta.url\)\);",style,code)
        code=re.sub(r'\bexport (?=(const|function|async|class)\b)','',code)
        assert 'import.meta' not in code
        output+='aiModules['+json.dumps(name)+']=(()=>{'+code+'\nreturn {'+','.join(exports)+'};})();\n'
    return output+'web.aiModules=Object.assign({},...Object.values(aiModules));\n'


_last_build = None


def build_cached(output):
    """Reuse only a verified build of the current UI, AI components and compiler."""
    global _last_build
    inputs = [Path(__file__), PACK/'manifest.json', PACK/'web/bridge.js', PACK/'assets/runtime/mouse.png']
    inputs.extend(PACK/'ui'/name for name in (*UI_MODULES, 'styles.css', 'index.html'))
    inputs.extend(PACK/'locales'/name/'ui.json' for name in ('zh-CN', 'en', 'meta/catalog'))
    base = ROOT/'engineering/ai/web/components'
    manifest = base/'pack-manifest.json'
    inputs.append(manifest)
    inputs.extend(base/name for name in json.loads(manifest.read_text(encoding='utf8'))['runtimeFiles'])
    digest = hashlib.sha256()
    for path in inputs:
        digest.update(str(path).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    key = (str(Path(output).resolve()), digest.digest())
    if _last_build and _last_build[0] == key and Path(output).is_dir():
        if export_tree(Path(output)) == _last_build[1]:
            return Path(output)
    result = build(output)
    _last_build = key, export_tree(result)
    return result


def build(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))
    sources={name:(PACK/'ui'/name).read_text(encoding='utf-8') for name in UI_MODULES}
    sources['ai-client.js']=(ROOT/'engineering/ai/web/components/client.js').read_text(encoding='utf-8')
    public={name:json.loads((PACK/name).read_text(encoding='utf-8')) for name in ('locales/zh-CN/ui.json','locales/meta/catalog/ui.json')}
    script='const STUMPSVILLE_STARTUP='+json.dumps(public,ensure_ascii=False)+';\n'+(PACK/'web/bridge.js').read_text(encoding='utf-8')
    script+='\n(async()=>{const web=await connectStumpsville();globalThis.stumpsvilleWeb=web;const localStorage=web.storage,sessionStorage=web.storage;\n'
    script+=ai_modules()
    for name,imports,exports in [('messageformat.js','',['IntlMessageFormat']),('i18n.js','const {IntlMessageFormat}=modules["messageformat.js"];',['t','setLocale','locale','initLocale']),('reference-view.js','const {t}=modules["i18n.js"];',['characterStatsHTML','itemDetailsHTML','renderPackageReference']),('chat.js','const {t}=modules["i18n.js"];',['chatUI']),('dice.js','',['diceUI']),('effects.js','',['effectsUI','effectSnapshot','effectChanges']),('map.js','',['mapPositions','mapRoutes','mapRoutePath']),('ai-client.js','',['AiClient','HttpTransport']),('ai.js','const {t}=modules["i18n.js"];',['aiUI']),('ai-recovery.js','',['definiteAIRejection','packageAITransport','explainAIError']),('ruling-card.js','',['rulingCard','rulingEscape','mountRulingTimeline']),('batch-details.js','const {rulingEscape:esc}=modules["ruling-card.js"];',['batchActionTitle','batchDetailsHTML','batchNoticeSnapshot']),('keeper-rulings.js','const {rulingCard,rulingEscape:esc}=modules["ruling-card.js"],{explainAIError}=modules["ai-recovery.js"],{batchDetailsHTML,batchNoticeSnapshot}=modules["batch-details.js"];',['mountPackageRulings','rulingIsArchived']),('keeper-queue.js','const {mountPackageRulings,rulingIsArchived}=modules["keeper-rulings.js"],{rulingCard}=modules["ruling-card.js"];const {t,locale}=modules["i18n.js"],{definiteAIRejection}=modules["ai-recovery.js"];',['mountKeeperAIQueue']),('ai-embedded.js','const {t}=modules["i18n.js"],{mountKeeperAIQueue}=modules["keeper-queue.js"],{definiteAIRejection,packageAITransport}=modules["ai-recovery.js"];',['embeddedAI'])]:
        code=sources[name];code=re.sub(r'^import .*?;\s*','',code,flags=re.M);code=re.sub(r'^export \{.*?\};\s*','',code,flags=re.M);code=re.sub(r'\bexport (?=(const|function|async|class)\b)','',code);code=re.sub(r'^//# sourceMappingURL=.*','',code,flags=re.M)
        script+=('const modules={};\n' if name=='messageformat.js' else '')+'modules['+json.dumps(name)+']=(()=>{'+imports+'\n'+code+'\nreturn {'+','.join(exports)+'};})();\n'
    app=re.sub(r'^import .*?;\s*','',sources['app.js'],flags=re.M).replace('src="art/mouse.png"', 'data-web-image="mouse"')
    script+='web.aiClient=modules["ai-client.js"];const {rulingCard,mountRulingTimeline}=modules["ruling-card.js"],{explainAIError}=modules["ai-recovery.js"];const {batchDetailsHTML}=modules["batch-details.js"];const {characterStatsHTML,itemDetailsHTML,renderPackageReference}=modules["reference-view.js"];const {chatUI}=modules["chat.js"],{diceUI}=modules["dice.js"],{effectsUI}=modules["effects.js"],{mapPositions,mapRoutes,mapRoutePath}=modules["map.js"],{aiUI}=modules["ai.js"],{embeddedAI}=modules["ai-embedded.js"],{t,setLocale,locale,initLocale}=modules["i18n.js"];\n'+app+'\n})().catch(e=>{document.querySelector("#app").textContent="网页连接失败 · "+e.message;});'
    # Resource groups may be served at blob URLs; avoid any direct network request.
    css=(PACK/'ui/styles.css').read_text(encoding='utf-8');css=re.sub(r"url\('art/welcome.png'\)",'none',css)
    html=(PACK/'ui/index.html').read_text(encoding='utf-8').replace('<link rel="stylesheet" href="styles.css">','<style>'+css+'</style>').replace('<script type="module" src="app.js"></script>','')
    html=html.replace('</body>','<script>'+script.replace('</script','<\\/script')+'</script></body>')
    (output/'index.html').write_text(html,encoding='utf-8')
    for name in ('locales/en/ui.json','art/mouse.png'):
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(PACK/('assets/runtime/mouse.png' if name.startswith('art/') else name),target)
    descriptor={'webVersion':2,'package':{'id':'stumpsville','name':'树桩镇','version':manifest['version'],'source':'Mausritter / Stumpsville；包侧适配详见来源说明','description':'两次登录；房主本机KP在线运行自动裁决，玩家在浏览器探索树桩镇。'},
        'rules':'仅玩家网页接入；使用房主提供的游戏账号。场景行动、资源与线索由房主宿主裁决。KP管理台离线时预设行动等待恢复。AI咨询由玩家提交，KP明确转交与审阅，不自动修改游戏。',
        'modules':{'required':['network-web'],'optional':[]},
        'groups':[{'id':'startup','access':'members','entry':'index.html','files':['index.html']},{'id':'locale-en','access':'members','entry':None,'files':['locales/en/ui.json']},{'id':'portraits','access':'members','entry':None,'files':['art/mouse.png']}],
        'routes':[{'method':'GET','path':p} for p in ('view','chat/members')]+[{'method':'POST','path':'chat/history'}],
        'bridge':{'version':1,'service':[{'method':'GET','path':'package/state','query':{'locale':['zh-CN','en']}},{'method':'GET','path':'package/chat/state','query':{}},{'method':'POST','path':'package/action','query':{'locale':['zh-CN','en']}},{'method':'POST','path':'package/chat/history','query':{}},{'method':'POST','path':'package/ai','query':{}}],
                  'storage':['sv.locale','sv.font','sv.desktop.*','stumpsville.pending.*']}}
    write_json(output/'web.json',descriptor)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=PACK/'web/dist');args=parser.parse_args();print(build(args.output))
