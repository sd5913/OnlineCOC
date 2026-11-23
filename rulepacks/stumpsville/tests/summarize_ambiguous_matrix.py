"""Build a readable transcript and compressed tool evidence from matching live runs."""
import argparse
import gzip
import json
from pathlib import Path

from ambiguous_suite import DECISIONS, TITLES, appended_rain, describes_drop

def metrics(r):
    turns=r['turns']
    calls=r['providerCalls'][:r.get('goalProviderCallCount')]
    humans=sum(not t['automatic'] for t in turns)
    tech_followups=0
    for old,new in zip(turns,turns[1:]):
        bad_approval=(old.get('approval') or {}).get('resultStatus') in ('blocked','failed','unknown','partial')
        if not new['automatic'] and (old.get('error') or old.get('status') in ('blocked','failed','interrupted') or bad_approval):
            tech_followups+=1
    budget=1+int(r['case'] in DECISIONS)
    verified=bool(r['complete'])
    if r['case']=='options':
        reply=str(turns[-1].get('reply',''))
        verified=verified and describes_drop(reply)
    goal_round=humans if verified else None
    if r['case']=='courtyard':
        initial=None
        for turn in turns:
            changes=turn.get('actualChanges',[])
            if len(changes)!=1 or not changes[0]['path'].endswith('/description'):
                continue
            change=changes[0]
            if initial is None:
                initial=change['before']
            if turn.get('overallPaths')==[change['path']] and appended_rain(initial,change['after']):
                goal_round=turn['humanRound']
                break
    return {'completed':int(r['complete']),'verified':int(verified),'verifiedWithinBudget':int(verified and humans<=budget),'goalRound':goal_round,'firstGoalWithinBudget':int(verified and goal_round is not None and goal_round<=budget),'withinBudget':int(r['complete'] and humans<=budget),'human':humans,
            'extra':max(0,humans-budget),'techFollowups':tech_followups,
            'nonDecisionNeedsInput':sum(t.get('status')=='needs_input' and not (r['case'] in DECISIONS and t['humanRound']==1) for t in turns),'auto':sum(t['automatic'] for t in turns),
            'approvals':sum('approval' in t for t in turns),'cases':1,
            'calls':len(calls),'http200':sum(c.get('httpStatus')==200 for c in calls),
            'tokens':sum(c.get('usage',{}).get('total_tokens',0) for c in calls)}

def inline(x,limit=210):
    if not isinstance(x,str):
        x=json.dumps(x,ensure_ascii=False,separators=(',',':'))
    x=' '.join(x.split())
    return x if len(x)<=limit else x[:limit]+'…'

def quotation(s):
    return '\n'.join('> '+line for line in str(s).splitlines())

def tools_read(t):
    lines=[]
    for call in t.get('tools',[]):
        name=call['name'];args=call.get('arguments',{});result=call.get('result')
        arg=inline(args,185)
        if name=='room_read_data':
            arg=f"{len(args.get('refs',[]))} 条引用，字段 "+inline(args.get('fields') or '可见字段')
        summary=''
        if isinstance(result,dict):
            if result.get('error'):summary='错误 '+inline(result['error'],120)
            elif 'file' in result and 'value' in result:
                v=result['value'];summary=(f"返回 {len(v)} 项" if isinstance(v,list) else '返回 '+inline(v,125))
                if result.get('total') is not None:summary+=f" / 共 {result['total']} 项"
            elif isinstance(result.get('items'),list):
                it=result['items'];summary=f'返回 {len(it)} 项'
                labels=[inline(x.get('label') or x.get('name') or x.get('title'),45) for x in it if isinstance(x,dict) and (x.get('label') or x.get('name') or x.get('title'))]
                if labels:summary+='（'+'、'.join(labels[:4])+'）'
            else:summary='返回 '+', '.join(list(result)[:6])
        else:summary='本次模型输入没有对应工具返回'
        lines.append(f'- `{name}`　{arg}。{summary}。')
    return lines

def checks(t):
    row=t.get('ruling') or {};out=[]
    for rep in row.get('reports',[]):
        codes=[v.get('code','') for v in rep.get('findings',[])]
        out.append(f"{rep.get('level')} 类 {rep.get('status')}（"+'、'.join(rep.get('coverage',[]))+'）'+('，'+'、'.join(codes) if codes else ''))
    for v in (row.get('preflight') or {}).get('items',[]):
        out.append(f"第 {v['index']+1} 项 {v.get('op')}：{v.get('status')} "+str(v.get('code','')))
    return out

def summarize_turn(t):
    lines=['','#### '+('自动续办' if t['automatic'] else '人工第 '+str(t['humanRound'])+' 轮'),'']
    if t['user']:lines+=['**KP**','',quotation(t['user']),'']
    else:lines+=['沿用原需求，系统在配置发布后继续。','']
    delivered=t.get('deliveredAnswer')
    lines+=['**AI 回复**' if delivered else '**未交付回复时的模型输出或错误**','',quotation(t.get('reply') or t.get('error') or '未获得正文'),'']
    reads=tools_read(t)
    if reads:lines+=['**读取与工具结果**','',*reads,'']
    row=t.get('ruling') or {}
    for x in t.get('proposedChanges',[]):lines.append('拟改 `'+x['path']+'`　'+inline(x.get('after')))
    for a in row.get('actions',[]):lines.append('拟执行 `'+a['op']+'`　'+inline(a.get('args',{}),400))
    inspected=checks(t)
    if inspected:lines+=['','**校验**','',*['- '+line for line in inspected],'']
    approval=t.get('approval')
    if approval:lines.append('KP 提交审批，宿主业务结果 `'+str(approval.get('resultStatus') or approval.get('code') or approval.get('status'))+'`。')
    if t.get('withheld'):lines.append('该候选未获准执行。'+t['withheld'])
    if t.get('error'):lines.append('会话错误 `'+str(t['error'])+'`。')
    for rc in (t.get('decisionEvidence') or {}).get('receipts',[]):
        if rc.get('code'):lines.append('回执 `'+str(rc['code'])+'`。')
    if t.get('actualChanges'):
        lines+=['','**生效差异**','']
        for x in t['actualChanges']:lines.append('- `'+x['path']+'`　'+inline(x.get('before'),100)+' → '+inline(x.get('after'),250))
    else:lines.append('本轮监测的配置、角色和通知无变化。')
    if t.get('ruleProbe'):lines+=['计算规则试跑：'+inline(t['ruleProbe'])]
    c=t.get('providerCallRange');lines+=['','本轮 API 调用 '+str(c[1]-c[0]+1)+' 次。' if c else '本轮未获得调用记录。','']
    return lines

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runs',type=Path);p.add_argument('destination',type=Path)
    args=p.parse_args();dest=args.destination;dest.mkdir(exist_ok=True,parents=True)
    phases={};summary={};totals={}
    folders={'before':'before','guide-only':'guide-only'}
    if (args.runs/'after-v2').is_dir():
        folders.update(first='after',after='after-v2')
    else:
        folders['after']='after'
    targeted_cases={f.parent.name for f in (args.runs/'targeted').glob('*/observations.json')}
    if (args.runs/'drop-check').is_dir():
        folders['drop-check']='drop-check'
    if (args.runs/'final-rest').is_dir():
        folders['final']=('targeted','final-rest')
    elif targeted_cases:
        folders['targeted']='targeted'
    for phase,folder in folders.items():
        runs={};sm={}
        roots=(folder,) if isinstance(folder,str) else folder
        files=[f for root in roots for f in sorted((args.runs/root).glob('*/observations.json'))]
        for f in files:
            r=json.loads(f.read_bytes())
            if 'finished' not in r:raise ValueError(f'未完成采样 {f}')
            key=r['case']
            if key in runs:raise ValueError(f'重复用例 {phase}/{key}')
            runs[key]=r;sm[key]=metrics(r)
        if phase not in ('guide-only','targeted','drop-check') and set(runs)!=set(TITLES):raise ValueError(f'{phase} 用例不全')
        phases[phase]=runs;summary[phase]=sm
        totals[phase]={col:sum(z[col] for z in sm.values()) for col in next(iter(sm.values()),{}) if col!='goalRound'}
    inventory={}
    for phase, runs in phases.items():
        calls=[call for run in runs.values() for call in run['providerCalls']]
        inventory[phase]={
            'rooms':len(runs),'calls':len(calls),'http200':sum(c.get('httpStatus')==200 for c in calls),
            'tokens':sum(c.get('usage',{}).get('total_tokens',0) for c in calls),
            'probeCalls':len(calls)-totals[phase]['calls'],
        }
    traces='ambiguous-suite-live-traces.json.gz';stats='ambiguous-suite-live-summary.json'
    (dest/traces).write_bytes(gzip.compress(json.dumps(phases,ensure_ascii=False,separators=(',',':')).encode(),compresslevel=9,mtime=0))
    (dest/stats).write_text(json.dumps({'totals':totals,'cases':summary,'includingDiagnostics':inventory,'targetedFirst':sorted(targeted_cases)},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    L=['# 16 项模糊需求真实 API 对照','', '2026-11-23 · Stumpsville · DeepSeek 官方 API · `deepseek-flash`','',
       '每个需求、每个版本均使用独立房间。脚本扮演 KP，每项目标最多四轮人工发言，每房最多 32 次模型调用。字段、编号、空槽、文案等细节委托给助手。两项预设的重大决定是路费的接收者和金额、伏笔是否向玩家公开。审批提交和自动续办单独计数。','',
       ]
    compared=[phase for phase in ('before','first','after','final') if phase in totals]
    names={'before':'优化前','first':'第一版模块修复','guide-only':'仅更新包指南','after':'第二版模块修复','targeted':'包指南定向复测','final':'第二版模块＋包指南全组','drop-check':'丢弃入口单项复测'}
    if 'final' in totals:
        base=totals['before']
        last=totals['final']
        L+=['最终全组按实际状态和只读答复复核达成 '+str(last['verified'])+'/16。优化前达成 '+str(base['verified'])+
            '/16。KP 实际发言从 '+str(base['human'])+' 次降到 '+str(last['human'])+
            ' 次，明确技术失败之后需要再发言从 '+str(base['techFollowups'])+' 次降到 '+str(last['techFollowups'])+
            ' 次。全部阶段共 '+str(sum(i['rooms'] for i in inventory.values()))+' 个隔离房间、'+str(sum(i['calls'] for i in inventory.values()))+
            ' 次官方 API 调用。各项首次达成所需轮数见下表。','']
    L+=['| 指标 | '+' | '.join(names[phase] for phase in compared)+' |','| --- |'+' ---: |'*len(compared)]
    for label,key in [('状态／只读回答自动核验达成','completed'),('加上背包咨询事实复核后达成','verified'),('事实复核通过且只需首次发言和必要决定','verifiedWithinBudget'),('首次已达目标且在必要轮数内（含雨景复核）','firstGoalWithinBudget'),('人工发言','human'),('超过必要轮数的人工发言','extra'),('技术失败后又发人工消息','techFollowups'),('预设重大决定以外的 needs_input 回复','nonDecisionNeedsInput'),('发布后自动续办','auto'),('审批提交','approvals'),('外部调用','calls'),('HTTP 200','http200'),('服务商 total_tokens 合计','tokens')]:
        L.append("| "+label+" | "+" | ".join(f"{totals[phase][key]:,}" for phase in compared)+" |")
    L+=['','背包比较用例的初始自动检查只验有答复、提及两种做法和无状态变更。人工阅读发现旧答复错误暗示丢弃后需另找补给，因此对各版最终答复均追加事实复核：是否说明物品落在现场并可再取。该用例没有因事后复核而追加人工提问。一次人工发言可触发多次模型调用。额外轮数按每例实际人工发言减去首次发言及预设重大决定计算，下限为零；未达标用例也计入总轮数。只读用例要求交付回答并核对无状态变更，写入用例按活动数据与玩家状态验收。技术失败后人工发言只计紧接明确错误或被阻断审批的情况，可能与额外轮数重叠。每项每个版本各采样一次，模型的随机性与固定脚本的回复方式均影响对照。','',
        '| 需求 | 前：达成／人工轮数 | 后：达成／人工轮数 | 首次达成所需人工轮数 | 后：审批 | 后：API 次数 |','| --- | --- | --- | ---: | ---: | ---: |']
    def outcome(x):return ('达成' if x['verified'] else '答复已交付，事实复核未通过' if x['completed'] else '未达成')+' / '+str(x['human'])
    for k,name in TITLES.items():
        a=summary['before'][k];b=summary.get('final',summary['after'])[k]
        L.append(f"| {name} | {outcome(a)} | {outcome(b)} | {b['goalRound'] or '—'} | {b['approvals']} | {b['calls']} |")
    L+=['','[完整逐轮工具请求、返回数据和执行证据（gzip JSON）]('+traces+') · [逐项统计 JSON]('+stats+')','']
    if phases.get('guide-only'):
        L+=['另做了仅更新包指南的诊断采样，未并入前后两组：'+ '；'.join(TITLES[k]+' '+outcome(v) for k,v in summary['guide-only'].items())+'。该组消耗 '+str(totals['guide-only']['calls'])+' 次调用。','']
    if 'first' in totals:
        a=totals['first']
        L+=['第一版模块修复的独立 16 项测试也保留在各项实录中。达成 '+str(a['verified'])+'/16，首次发言加必要决定即可达成 '+str(a['verifiedWithinBudget'])+'/16；共 '+str(a['calls'])+' 次官方调用。','']
    L+=['## 优化与仍需关注的情况','',
        '首次对照里，庭院修改在三检通过后被自身暂存的配置触发 SOURCE_STALE。引擎修正了房间来源查询对暂存工件的依赖。真正被外部修改的依据仍会在发布前复核。AI 模块增加同权限范围内的引用解析与格式修复，配置读取提供零基路径，允许独立的数组追加与已有条目编辑共存。包指南说明库存编号、双向出口和可重新拿取的丢弃物。','',
        '第一版复测发现三种遗漏。已有绳子不等于本次已经发放；地点编号不能直接作为数组下标；结账必须区分付款和补贴，并核对原操作回执。在饭钱用例中，脚本批准了错误方向的提案，随后反复说“继续”，导致多次扣款和通知。这些副作用发生在隔离房间，按每次申请和最终通知数量核验。','',
        '第二版向助手提供可见的原始请求、动作、运行前相关数值和回执状态。在已完成或待判定的同一意图上，简短“继续”会复核同一目标字段；明确的新开销仍可形成新候选。地图引用冲突进入有上限的技术修复，每次重新运行配置三检。','',
        '每次审批由脚本代表 KP 提交。表里的人工轮数统计聊天发言，单独列出的审批也需要 KP 操作。饭钱的口语表达可引起收付方向歧义，如无法判断，确认收付方向属于有业务意义的问题。','',
        '| 实际调用范围 | 房间数 | 全部 API 请求 | HTTP 200 | 其中探针请求数 | 总 tokens |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for phase, counts in inventory.items():
        L.append(f"| {names[phase]} | {counts['rooms']} | {counts['calls']} | {counts['http200']} | {counts['probeCalls']} | {counts['tokens']:,} |")
    L.append('')
    if targeted_cases:
        L+=['### 包指南定向复测','',
            '在完成第二版的 16 个独立房间后，按失败或额外对话选出以下五项。更新包指南对防护装备类别、增补原文、只读规则接口、成员定位和收付方向的说明。使用相同提示和核验条件，分别建立新房间复测。此表只统计定向样本，保留原 16 项的分母和结果。','',
            '| 需求 | 第二版全组中的结果／人工轮数 | 更新包指南后／人工轮数 |','| --- | --- | --- |']
        for case in sorted(targeted_cases):
            item=summary.get('final',summary.get('targeted',{}))[case]
            L.append('| '+TITLES[case]+' | '+outcome(summary['after'][case])+' | '+outcome(item)+' |')
        if 'final' in phases:
            L.append('其余 11 项随后在同一版本各运行一次，与这 5 项组成最终全组；每项只计一次。')
        L.append('')
    if 'final' in phases:
        L+=['庭院雨景的原脚本要求新增文字包含“雨”字。最终包的第一轮已经保留原文，并追加了“屋檐还在滴水，石板地上泛着一层湿亮的光。”脚本多发了一条消息并再次审批。保留实际发生的两轮和两次审批，同时把首次语义达成单列为一轮。后续脚本也识别这类明确的雨景描写。','',
            '最终全组的背包咨询答复把单独清槽的 sv.remove 错认成背包菜单的丢弃操作，并声称物品无法再捡回。复核同时检查肯定与否定语义，逐版使用相同标准。已在包指南、术语中补上 inventory/drop 成功回执如何登记为可拿取物品。','']
    if phases.get('drop-check'):
        x=summary['drop-check']['options']
        L+=['补充入口说明后，独立房间的同题单项复测结果为 '+outcome(x)+' 轮。该样本单列，保留此前全组的事实错误。补测核实的是丢弃后留在现场且可再取的核心结论；答复中“另有 1–20 格可用”的措辞仍容易与空槽数量混淆。','']
    probe=phases['after'].get('dinner',{}).get('receiptProbe',[])
    if probe:
        L+=['第二版模块测试中，已结算饭钱后的两次附加诊断使用同一会话。'+ '。'.join('“'+item['user']+'”'+('通过' if item['passed'] else '未通过')+'，产生 '+str(len(item['actualChanges']))+' 条实际差异' for item in probe)+'。'+
            '两次诊断的发言、审批和模型调用均单列。','']
    for k,name in TITLES.items():
        L+=['## '+name,'',phases['before'][k]['turns'][0]['user'],'']
        for phase,label in [('before','优化前'),('guide-only','仅更新包指南'),('first','第一版模块修复'),('after','第二版模块修复'),('targeted','包指南定向复测'),('final','包指南全组与第二版模块'),('drop-check','丢弃入口单项复测')]:
            if k not in phases.get(phase,{}):continue
            r=phases[phase][k];L+=['<details>','<summary>'+label+' · '+outcome(summary[phase][k])+' 轮</summary>','']
            for t in r['turns']:L+=summarize_turn(t)
            if r.get('receiptProbe'):
                L+=['','#### 已结算后的继续与明确追加（单列诊断）','']
                for x in r['receiptProbe']:
                    L+=['**KP**','',quotation(x['user']),'','**AI**','',quotation(x.get('reply') or '未交付正文'),'',
                        ('通过' if x['passed'] else '未通过')+'。调用 '+str(x['calls'])+' 次，产生的写入差异：'+inline(x['actualChanges'],800),'']
                    L+=tools_read(x)
                    for action in x.get('actions') or []:
                        L.append('拟执行 `'+action.get('op','')+'` '+inline(action.get('args',{}),380))
                    for check in (x.get('preflight') or {}).get('items',[]):
                        L.append('预检 '+str(check.get('op',''))+' '+str(check.get('status',''))+' '+str(check.get('code','')))
                    if x.get('approval'):
                        L.append('提交审批后宿主回执 `'+str(x['approval'].get('resultStatus'))+'`。')
                    L.append('')
            if r.get('runError'):L.append('测试执行错误：'+str(r['runError']))
            L+=['','</details>','']
    (dest/'ambiguous-suite-live-report.md').write_text('\n'.join(L),encoding='utf8')
    print(json.dumps(totals,ensure_ascii=False))

if __name__=='__main__':main()
