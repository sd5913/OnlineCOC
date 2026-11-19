"""Real panel: named saves, account/data isolation, switching and lifecycle."""
from datetime import datetime
import hashlib
import json
import secrets
import tkinter as tk
import uuid
from playwright.sync_api import sync_playwright, expect

from harness import PACK, Account
from launch import free_port
from panel import PanelWindow
from slots import RoomSlots
from verify_lan import pump, screenshot
from verify_panel import close_window, port_closed


def main():
    output = PACK/'tests/output'/('slots-'+secrets.token_hex(4))
    output.mkdir(parents=True)
    data = output/'中文 槽位'
    checks = []
    slots = RoomSlots(data)
    assert slots.list() == [] and not data.exists()
    for name in ('', ' ', 'x'*41, 'bad\nname'):
        try:
            slots.create(name)
            raise AssertionError('invalid name accepted')
        except ValueError:
            pass
    for identifier in ('../outside', 'A'*32, '/', None):
        try:
            slots.path(identifier)
            raise AssertionError('unsafe identifier accepted')
        except ValueError:
            pass
    checks.append('empty library does not initialize a room; invalid names and path traversal are rejected')

    root = tk.Tk()
    window = PanelWindow(root, data, False, port=free_port())
    try:
        pump(root, lambda: not window.scanning)
        assert str(window.start_button['state']) == 'disabled'
        window.start();assert '槽位' in window.status.get() and not data.exists()
        window.slot_name.set('周末团 A');window.slot_create.invoke()
        root.update()
        first = window.current_slot['id'];first_path = window.data
        assert first_path.is_dir() and not (first_path/'host').exists()
        assert window.setup_frame.winfo_ismapped()
        password_a = secrets.token_urlsafe(18)
        window.password.set(password_a);window.confirm.set(password_a);window.start()
        pump(root, lambda: bool(window.url) or window.failed)
        assert window.url, window.status.get()
        account = Account(window.url.rstrip('/'), 'player1', password_a)
        account.action('note', {'text': 'ONLY-A'})
        pump(root, lambda: '运行中' in window.slot_info.get())
        assert str(window.slot_input['state']) == 'disabled'
        assert str(window.slot_create['state']) == 'disabled'
        window.slot_name.set('运行时不可创建');window.create_slot()
        assert len(slots.list()) == 1 and window.current_slot['id'] == first
        assert (first_path/'host/identity').is_dir()
        origin, backend = window.url, window.service.runtime.backend
        root.iconify();root.update();assert account.state()['note'] == 'ONLY-A'
        root.deiconify();root.update()
        window.stop();pump(root, lambda: not window.busy and not window.service.active)
        assert port_closed(origin) and port_closed(backend)
        checks.append('creating a named slot prepares its own real host; running locks slot management; minimizing keeps it alive and stopping releases ports')

        window.slot_name.set('周末团 A');window.create_slot()
        assert '同名' in window.status.get() and len(slots.list()) == 1
        window.slot_name.set('新冒险 B');window.create_slot()
        second = window.current_slot['id'];second_path = window.data
        assert second_path != first_path and not (second_path/'host').exists()
        assert window.password.get() == window.confirm.get() == ''
        password_b = secrets.token_urlsafe(18)
        window.password.set(password_b);window.confirm.set(password_b);window.start()
        pump(root, lambda: bool(window.url) or window.failed)
        assert window.url, window.status.get()
        b = Account(window.url.rstrip('/'), 'player1', password_b)
        assert b.state()['note'] != 'ONLY-A'
        b.action('note', {'text': 'ONLY-B'})
        import httpx
        with httpx.Client(trust_env=False, headers={'Origin':window.url.rstrip('/')}) as client:
            rejected = client.post(window.url+'api/v1/login', json={'loginName':'player1','password':password_a})
            assert rejected.status_code == 401, rejected.text
        window.stop();pump(root, lambda: not window.busy and not window.service.active)
        assert RoomSlots(data).selected()['id'] == second
        assert '已有房间数据' in window.slot_info.get()
        screenshot(root, output/'slots-panel.png')
        assert window.slot_frame.winfo_rooty() >= root.winfo_rooty()
        assert window.slot_frame.winfo_rooty()+window.slot_frame.winfo_height() <= root.winfo_rooty()+root.winfo_height()
        checks.append('two slots use different directories, passwords and notes; duplicate names rejected and selection remembered')
    finally:
        close_window(window)

    root = tk.Tk();window = PanelWindow(root, data, False, port=free_port())
    try:
        pump(root, lambda: not window.scanning)
        assert window.current_slot['id'] == second and not window.setup_frame.winfo_ismapped()
        window.slot_input.current(next(i for i,row in enumerate(window.slot_rows) if row['id'] == first))
        window.choose_slot();window.start()
        pump(root, lambda: bool(window.url) or window.failed)
        assert window.url, window.status.get()
        a = Account(window.url.rstrip('/'), 'player1', password_a)
        assert a.state()['note'] == 'ONLY-A'
        backend = window.service.runtime.backend
        window.stop();pump(root, lambda: not window.busy and not window.service.active)
        # Isolated fixture only: make the newest envelope a valid v3 snapshot,
        # retaining the storage chain so the startup diagnosis is meaningful.
        latest = sorted((first_path/'host/rooms/demo/generations').glob('*.json'))[-1]
        original = latest.read_bytes();envelope = json.loads(original)
        envelope['payload']['schemaVersion'] = 3
        payload = json.dumps(envelope['payload'], ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()
        envelope['digest'] = hashlib.sha256(payload).hexdigest();envelope['length'] = len(payload)
        latest.write_text(json.dumps(envelope, ensure_ascii=False), encoding='utf-8')
        try:
            window.start();pump(root, lambda: window.failed and not window.busy and not window.service.active)
            assert 'SCHEMA_UNSUPPORTED' in window.status.get() and '不兼容' in window.status.get()
            assert not window.url
        finally:
            latest.write_bytes(original)
        checks.append('reopening remembers the selection; switching back restores the original save; incompatible versions show an actionable error and no connection address')
        window.start();pump(root, lambda: bool(window.url) or window.failed)
        assert window.url, window.status.get()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page()
            errors = [];page.on('pageerror',lambda error:errors.append(str(error)))
            def login(password):
                page.goto(window.url+'sessions/slot-browser/')
                page.locator('[name=loginName]').fill('player1')
                page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='进入冒险',exact=True).click()
                page.locator('.identity').wait_for()
            login(password_a)
            scope_a = Account(window.url.rstrip('/'),'player1',password_a).state()['storageScope']
            key_a = 'stumpsville.pending./sessions/slot-browser/.player1.'+scope_a
            pending = {'id':str(uuid.uuid4()),'operation':'note','args':{'text':'RECOVERED-ONLY-A'}}
            page.evaluate('(a)=>localStorage.setItem(a.key,JSON.stringify(a.body))',{'key':key_a,'body':pending})
            page.reload();expect(page.locator('[data-action=recover]')).to_be_visible()
            def switch(identifier):
                window.stop();pump(root, lambda: not window.busy and not window.service.active)
                window.slot_input.current(next(i for i,row in enumerate(window.slot_rows) if row['id']==identifier))
                window.choose_slot();window.start()
                pump(root, lambda: bool(window.url) or window.failed)
                assert window.url,window.status.get()
            switch(second);login(password_b)
            expect(page.locator('[data-action=recover]')).to_have_count(0)
            current_b = Account(window.url.rstrip('/'),'player1',password_b).state()
            assert current_b['storageScope'] != scope_a and current_b['note']=='ONLY-B'
            assert page.evaluate('(k)=>!!localStorage.getItem(k)',key_a)
            switch(first);login(password_a)
            page.locator('[data-action=recover]').click()
            expect(page.locator('[data-action=recover]')).to_have_count(0)
            assert Account(window.url.rstrip('/'),'player1',password_a).state()['note']=='RECOVERED-ONLY-A'
            assert not errors,errors
            browser.close()
        checks.append('same browser, account and port keep pending recovery isolated per slot; returning to the original slot restores only its action')
        origin, backend = window.url, window.service.runtime.backend
        close_window(window)
        assert port_closed(origin) and port_closed(backend)
        assert (first_path/'package.json').exists() and (second_path/'package.json').exists()
        checks.append('closing the panel stops only its selected room and preserves both slots for later use')
    finally:
        close_window(window)
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'passed':len(checks), 'checks':checks,
              'realSaveModified':False, 'modelCalls':0, 'data':'isolated test rooms'}
    (PACK/'tests/slots-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':main()
