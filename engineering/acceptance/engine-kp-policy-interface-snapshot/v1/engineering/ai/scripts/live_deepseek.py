"""Explicit live acceptance using a hidden stdin credential and an isolated demo.

Never run this from pytest or normal startup. It makes billable provider calls.
The supplied key is held only in this process; reports contain public fixtures,
usage, digests and stable errors, never credentials or raw HTTP diagnostics.
"""
import asyncio
import copy
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'ai/src'), str(ROOT / 'backend/src'), str(ROOT / 'data-management')]
from onlinecoc.host import Host
from onlinecoc_ai.context import Context
from onlinecoc_ai.contracts import canonical, digest, loads, validate
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.pack import Pack
from onlinecoc_ai.profiles import load_profiles
from onlinecoc_ai.proposals import Proposals
from onlinecoc_ai.providers import create_provider


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def hidden_credential():
    """Fail closed if the Windows terminal cannot disable input echo."""
    if os.name != 'nt':
        import getpass
        if not sys.stdin.isatty():raise RuntimeError('SECURE_STDIN_REQUIRED')
        return getpass.getpass('DeepSeek test credential: ')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.argtypes = [ctypes.c_ulong]
    kernel.GetStdHandle.restype = ctypes.c_void_p
    kernel.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    handle = kernel.GetStdHandle(-10 & 0xffffffff)
    mode = ctypes.c_ulong()
    if not kernel.GetConsoleMode(handle, ctypes.byref(mode)) or not kernel.SetConsoleMode(handle, mode.value & ~4):
        raise RuntimeError('SECURE_STDIN_REQUIRED')
    try:
        emit({'status': 'credential-input-ready', 'echo': False})
        return sys.stdin.readline().strip()
    finally:
        kernel.SetConsoleMode(handle, mode.value)


async def live(profile, output):
    observations = []
    def provider_factory(selected):
        provider = create_provider(selected)
        original = provider.complete
        async def observed(messages, tools=(), **kwargs):
            result = await original(messages, tools, **kwargs)
            observation = {'requestDigest': digest({'messages': messages, 'tools': list(tools)}),
                'responseDigest': result.response_digest, 'finishReason': result.finish_reason,
                'usage': result.usage, 'tools': [c['function']['name'] for c in result.message.get('tool_calls', [])]}
            observations.append(observation)
            if result.message.get('content') and not result.message.get('tool_calls'):
                # Diagnostic paths only; no raw response text is logged.
                value = loads(result.message['content'])
                observation['outputKeys'] = sorted(value)
                if value.get('kind') == 'draft':
                    try:validate('ChangeSet', value.get('changeSet'))
                    except Exception as exc:
                        observation['contractError'] = {'code': getattr(exc, 'code', type(exc).__name__), 'path': getattr(exc, 'path', '')}
            emit({'call': len(observations), 'finishReason': result.finish_reason, 'tools': observation['tools'], 'tokens': result.usage['total_tokens']})
            return result
        provider.complete = observed
        return provider

    result = {'testedAt': datetime.now().astimezone().isoformat(), 'provider': 'DeepSeek', 'endpoint': profile['baseUrl'],
        'model': profile['model'], 'profileId': profile['profileId'], 'profileRevision': profile['revision'],
        'status': 'running', 'calls': observations, 'credentialPersisted': False, 'gamePublished': False,
        'scope': 'Isolated host demo; public fixture context only; configured provider remains disabled.'}
    try:
        provider = provider_factory(profile)
        try:result['probe'] = await provider.probe()
        finally:await provider.close()
        emit({'probe': 'passed'})
        directory = ROOT / 'ai/.test-output' / ('deepseek-live-' + uuid.uuid4().hex)
        host = Host(directory, bootstrap=uuid.uuid4().hex)
        service = None;coordinator = None
        try:
            pack = Pack(ROOT / 'rulepacks/demo')
            service = Proposals(host, pack)
            state = host.state()
            state['aiControl']['settings'].update(enabled=True, profileId=profile['profileId'])
            state['aiControl']['settings']['externalSources'].update(public=True, kp=False, private=False)
            host.commit(state)
            baseline = {key: copy.deepcopy(state[key]) for key in ('entities', 'relations', 'configurations', 'activeRuleset')}
            coordinator = Coordinator(service, {profile['profileId']: profile}, provider_factory=provider_factory, context=Context(service))
            await coordinator.start()
            text = ('这是隔离测试房间。请先调用 room_read_context 和 pack_read_contract 核实事实与扩展规则，再生成 draft。'
                    '将 demo.skill 配置的新建技能 defaults.value 调整为 15，使用当前 expectedRevision 和新的 revision。'
                    '保留其他配置字段，不修改 Lua、数据文件或现有实例；解释新技能概率收益和旧技能仍为 60 的区别。'
                    '只提交一个配置替换；不要执行批准或发布。')
            task = coordinator.enqueue('kp', 'live-deepseek-demo', text)
            async with asyncio.timeout(210):
                while True:
                    current = service.repository.state()['tasks'][task['taskId']]
                    if current['status'] not in ('queued', 'generating', 'validating'):break
                    await asyncio.sleep(.1)
            result['task'] = {key: current[key] for key in ('taskId', 'status', 'error', 'usage', 'proposalId')}
            result['packDigest'] = pack.digest
            result['liveGameUnchanged'] = all(host.state()[key] == value for key, value in baseline.items())
            result['approvalsCreated'] = len(host.state()['aiControl']['approvals'])
            result['publicationsCreated'] = len(host.state()['aiControl']['publications'])
            if current['proposalId']:
                proposal = service.get('kp', current['proposalId'])
                reports = [service.repository.state()['reports'][key] for key in proposal['reportRefs']]
                result['proposal'] = {key: proposal[key] for key in ('proposalId', 'revision', 'status', 'summary', 'changeSet', 'candidateDigest')}
                result['reports'] = reports
            generation_tools = {name for call in observations[2:] for name in call['tools']}
            result['generationTools'] = sorted(generation_tools)
            result['status'] = 'passed' if (current['status'] == 'review_ready' and current['proposalId'] and
                len(result.get('reports', [])) == 3 and all(r['status'] == 'pass' for r in result['reports']) and
                {'room_read_context', 'pack_read_contract'} <= generation_tools and result['liveGameUnchanged'] and
                not result['approvalsCreated'] and not result['publicationsCreated']) else 'incomplete'
        finally:
            if coordinator:await coordinator.close()
            if service:service.close()
            host.close()
    except Exception as exc:
        result.update(status='failed', error=getattr(exc, 'code', type(exc).__name__))
        import traceback
        result['errorFrames'] = [{'file': Path(frame.filename).name, 'function': frame.name, 'line': frame.lineno}
                                 for frame in traceback.extract_tb(exc.__traceback__)]
        if getattr(exc, 'http_status', None):result['httpStatus'] = exc.http_status
    finally:
        result['totalTokens'] = sum(c['usage']['total_tokens'] for c in observations)
        output.write_bytes(canonical(result) + b'\n')
    emit({key: result[key] for key in ('status', 'model', 'totalTokens')} | {'error': result.get('error'), 'httpStatus': result.get('httpStatus')})
    return 0 if result['status'] == 'passed' else 1


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    profile = copy.deepcopy(load_profiles()['deepseek-main'])
    if profile['baseUrl'] != 'https://api.deepseek.com' or profile['adapter'] != 'deepseek-chat':
        emit({'error': 'EXPECTED_OFFICIAL_DEEPSEEK_ENDPOINT'});return 2
    profile['enabled'] = True
    profile['request']['maxOutputTokens'] = 1024
    profile['limits'].update(maxToolRounds=4, maxRepairAttempts=1, maxTransportRetries=0, taskTimeoutMs=180000)
    name = profile['credentialRef'][4:]
    try:
        value = hidden_credential()
        if not value:raise RuntimeError('CREDENTIAL_MISSING')
        os.environ[name] = value
        value = None
        return asyncio.run(live(profile, ROOT / 'acceptance/ai-runtime/deepseek-live.json'))
    except Exception as exc:
        emit({'status': 'failed', 'error': str(exc) if str(exc) in ('SECURE_STDIN_REQUIRED', 'CREDENTIAL_MISSING') else type(exc).__name__})
        return 2
    finally:
        os.environ.pop(name, None)


if __name__ == '__main__':raise SystemExit(main())
