"""Label-only reuse, publication invalidation and malformed-file boundaries."""
import json
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

PACK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACK/'tools'))
from ai_data import Adapter


def main():
    output=PACK/'tests/output'/('ai-binding-labels-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],
            'realSaveChanged':False,'externalModelCalls':0,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    path=output/'package.json';adapter=Adapter(path);reads=[];original=Path.open
    def counted(source,*args,**kwargs):
        if source==path and args and args[0]=='rb':reads.append(1)
        return original(source,*args,**kwargs)
    def publish(owner):
        target=output/'next.json'
        target.write_text(json.dumps({'format':2,'bindings':{owner:'actor'},'padding':'x'*350000}),encoding='utf-8')
        if path.exists():
            previous=path.stat();os.utime(target,ns=(previous.st_atime_ns,previous.st_mtime_ns))
        os.replace(target,path)
    try:
        publish('player1')
        with patch.object(Path,'open',counted):
            with ThreadPoolExecutor(max_workers=8) as pool:
                values=list(pool.map(lambda _:adapter.reference_label('entity','actor','木栗'),range(200)))
            assert all('player1' in v for v in values) and len(reads)==1,(len(reads),values[:2])
            report['checks'].append('200次并发角色标签读取仅解析一次约350KB文件，标签与账号绑定正确')
            publish('player2')
            assert 'player2' in adapter.reference_label('entity','actor','木栗') and len(reads)==2
            assert adapter.reference_label('entity','other','旁人')=='旁人'
            report['checks'].append('同大小且保留mtime的原子替换仍立即更新绑定，未知角色保持原名称')
            path.unlink()
            assert adapter.reference_label('entity','actor','木栗')=='木栗'
            path.write_text('{"format":1}',encoding='utf-8')
            assert adapter.reference_label('entity','actor','木栗')=='木栗'
            report['checks'].append('文件删除和非当前格式不会残留上次账号标签')
            for value,expected in (('bad json',json.JSONDecodeError),('x'*(8*1024*1024+1),ValueError)):
                path.write_text(value,encoding='utf-8')
                try:adapter.reference_label('entity','actor','木栗');raise AssertionError('invalid file accepted')
                except expected:pass
            report['checks'].append('损坏JSON与超8MiB仍报原有错误，缓存不掩盖文件边界')
        report['passed']=True
    except Exception as exc:report.update(passed=False,error=repr(exc))
    report['passedCount']=len(report['checks']);report['labelFileReads']=len(reads)
    canonical=PACK/'tests/ai-binding-labels-results.json'
    if canonical.exists():
        old=json.loads(canonical.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ('passed','error','evidenceDirectory')}]
    for p in (canonical,output/'report.json'):p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','passedCount','error','evidenceDirectory')}))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
