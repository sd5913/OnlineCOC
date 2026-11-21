"""Isolated browser acceptance host with a deterministic provider and WAN guard."""
import sys
import socket
import ipaddress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'ai/src'), str(ROOT / 'backend/src'), str(ROOT / 'data-management')]


def network_guard(event, args):
    address = args[-1][0] if event in ('socket.connect', 'socket.sendto') and isinstance(args[-1], tuple) else args[0] if event == 'socket.getaddrinfo' else None
    if address is None or address in ('localhost', b'localhost'):return
    try:local = ipaddress.ip_address(address).is_loopback
    except ValueError:local = False
    if not local:raise PermissionError('WAN denied by AI acceptance guard')


sys.addaudithook(network_guard)

if __name__ == '__main__':
    import uvicorn
    from onlinecoc.host import Host
    from onlinecoc.server import create_app
    from onlinecoc_ai.pack import Pack, fixture_state
    from onlinecoc_ai.sandbox import stage
    from onlinecoc_ai.contracts import canonical, digest, loads
    from onlinecoc_ai.providers.base import Completion
    from onlinecoc_ai.runtime import Runtime
    directory, port = Path(sys.argv[1]), int(sys.argv[2])
    host = Host(directory, bootstrap='test-password')
    pack = Pack(Path(__file__).parent / 'fixtures/pack')
    artifact = stage(pack.sources, pack.data)
    world = fixture_state(pack.json(pack.scenarios[0]['fixtureRef']), pack.configurations)
    state = host.state()
    for key in ('entities', 'relations', 'configurations', 'members', 'progress', 'collectionRevision'):state[key] = world[key]
    state['artifacts'][artifact['revision']] = artifact;state['activeRuleset'] = artifact['revision'];host.commit(state)
    config = directory / 'offline-providers.json'
    config.write_bytes((ROOT / 'ai/examples/ai-providers.json').read_bytes())
    runtime = Runtime(host, config, pack.root)
    runtime.coordinator.profiles['deepseek-main']['enabled'] = True

    class OfflineProvider:
        async def complete(self, messages, tools):
            delta = loads((ROOT / 'ai/examples/bonus-15.json').read_bytes())
            value = {'kind': 'draft', 'text': '离线验收：有限次数道具；需要 KP 审核风险。', 'changeSet': delta}
            return Completion({'role': 'assistant', 'content': canonical(value).decode()},
                {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}, 'stop', digest(value))
        async def close(self):pass
    runtime.coordinator.provider_factory = lambda profile: OfflineProvider()
    try:uvicorn.run(create_app(host, port, ai_runtime=runtime), host='127.0.0.1', port=port, log_level='warning')
    finally:host.close()
