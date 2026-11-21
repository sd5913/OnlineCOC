"""Local account tab. The public host CLI owns identity and member changes."""
import json
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import uuid

from processes import run_owned


MESSAGES = {
    'ACCOUNT_EXISTS': '账号已存在，请使用其他账号名。',
    'LAST_ACTIVE_KP': '不能删除最后一个可登录的 KP，请先创建另一个 KP。',
    'LAST_KP_REQUIRED': '不能删除最后一个可登录的 KP，请先创建另一个 KP。',
    'INPUT_INVALID': '账号或密码格式不正确，请检查输入。',
    'HOST_NOT_RUNNING': '房间尚未运行，请先在房间启动页启动所选房间。',
    'HOST_CONTROL_UNAVAILABLE': '本机账号管理暂不可用，请检查宿主运行状态。',
    'HOST_CONTROL_OUTCOME_UNKNOWN': '宿主未返回完整结果，账号操作可能已经完成。',
    'HOST_CONTROL_TIMEOUT': '等待宿主处理账号操作超时。',
    'HOST_CONTROL_RESPONSE_INVALID': '宿主返回的账号结果无法读取。',
    'COMMAND_ID_CONFLICT': '该请求编号对应另一项操作，请核对原回执。',
}


class AccountError(Exception):
    def __init__(self, code, *, uncertain=False):
        self.code, self.uncertain = code, uncertain
        super().__init__(MESSAGES.get(code, '账号操作未完成')+'（'+code+'）')


def host_request(runtime, body):
    """Passwords travel over stdin, never command arguments or shell text."""
    control_dir = getattr(runtime.args, 'host_control_dir', None)
    command = runtime.command+['host-account-request']+(['--host-control-dir', str(control_dir)] if control_dir else [])
    try:
        result = run_owned(command, input=json.dumps(body, ensure_ascii=False),
            text=True, encoding='utf-8', env=runtime.env, capture_output=True, timeout=25,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired:
        raise AccountError('HOST_CONTROL_TIMEOUT', uncertain=True) from None
    except OSError:
        raise AccountError('HOST_CONTROL_UNAVAILABLE', uncertain=True) from None
    try:
        value = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise AccountError('HOST_CONTROL_RESPONSE_INVALID', uncertain=True) from None
    if not isinstance(value, dict):
        raise AccountError('HOST_CONTROL_RESPONSE_INVALID', uncertain=True)
    if value.get('status') == 'pending':
        return value
    if value.get('error') or value.get('status') == 'rejected' or result.returncode:
        code = value.get('code') or (value['error'].get('code') if isinstance(value.get('error'), dict) else None) or 'HOST_CONTROL_FAILED'
        # Only a definite server rejection establishes that the write failed.
        uncertain = value.get('status') != 'rejected' and code not in {'INPUT_INVALID', 'ACCOUNT_EXISTS', 'LAST_KP_REQUIRED'}
        raise AccountError(code, uncertain=uncertain)
    return value


class AccountsTab(ttk.Frame):
    def __init__(self, notebook, panel, *, request=host_request):
        super().__init__(notebook, padding=24)
        self.panel, self.request = panel, request
        self.events = queue.Queue()
        self.busy = False
        self.pending = None
        self.context = None
        self.records = {}
        self.last_receipt = ''
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text='账号管理', font=('Microsoft YaHei UI', 18, 'bold')).grid(row=0, column=0, sticky='w')
        self.room = tk.StringVar(self)
        ttk.Label(self, textvariable=self.room, wraplength=740).grid(row=1, column=0, sticky='w', pady=(8, 12))
        table = ttk.Frame(self)
        table.grid(row=2, column=0, sticky='nsew')
        self.tree = ttk.Treeview(table, columns=('account', 'name', 'role', 'state'), show='headings', height=9, selectmode='browse')
        for column, title, width in [('account', '账号', 185), ('name', '显示名称', 185), ('role', '房间角色', 110), ('state', '状态', 130)]:
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, minwidth=75)
        scroll = ttk.Scrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y'); self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.controls())
        commands = ttk.Frame(self)
        commands.grid(row=3, column=0, sticky='ew', pady=10)
        self.refresh_button = ttk.Button(commands, text='刷新账号', command=self.refresh)
        self.refresh_button.pack(side='left')
        self.delete_button = ttk.Button(commands, text='删除所选账号', command=self.delete)
        self.delete_button.pack(side='left', padx=8)
        self.retry_button = ttk.Button(commands, text='核对／重试原请求', command=self.retry)
        self.retry_button.pack(side='right')
        create = ttk.LabelFrame(self, text='增加账号', padding=12)
        create.grid(row=4, column=0, sticky='ew', pady=(0, 12))
        create.columnconfigure(1, weight=1)
        self.login = tk.StringVar(self); self.password = tk.StringVar(self); self.role = tk.StringVar(self, '玩家')
        ttk.Label(create, text='账号').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.login_entry = ttk.Entry(create, textvariable=self.login)
        self.login_entry.grid(row=0, column=1, sticky='ew')
        ttk.Label(create, text='角色').grid(row=0, column=2, padx=10)
        self.role_input = ttk.Combobox(create, textvariable=self.role, values=['玩家', 'KP'], state='readonly', width=10)
        self.role_input.grid(row=0, column=3)
        ttk.Label(create, text='密码').grid(row=1, column=0, sticky='w', pady=(10, 0))
        self.password_entry = ttk.Entry(create, textvariable=self.password, show='●')
        self.password_entry.grid(row=1, column=1, sticky='ew', pady=(10, 0))
        self.create_button = ttk.Button(create, text='创建账号', command=self.create)
        self.create_button.grid(row=1, column=3, padx=(10, 0), pady=(10, 0))
        reset = ttk.Frame(self)
        reset.grid(row=5, column=0, sticky='ew')
        ttk.Label(reset, text='所选账号的新密码').pack(side='left')
        self.new_password = tk.StringVar(self)
        self.reset_entry = ttk.Entry(reset, textvariable=self.new_password, show='●')
        self.reset_entry.pack(side='left', padx=10, fill='x', expand=True)
        self.password_button = ttk.Button(reset, text='修改密码', command=self.reset_password)
        self.password_button.pack(side='right')
        self.status = tk.StringVar(self, '启动所选房间后可管理账号。')
        ttk.Label(self, textvariable=self.status, wraplength=740).grid(row=6, column=0, sticky='w', pady=16)
        ttk.Label(self, text='新房间默认账号：kp、player1、player2；默认密码：12345678。\n删除账号后无法再登录，已有角色与历史记录保留。', wraplength=740).grid(row=7, column=0, sticky='w')
        self.controls()

    def runtime(self):
        runtime = self.panel.service.runtime
        return runtime if self.panel.url and runtime and not self.panel.closing else None

    def selected(self):
        selected = self.tree.selection()
        return self.records.get(selected[0]) if selected else None

    def controls(self):
        ready = bool(self.runtime()) and not self.busy
        editable = ready and not self.pending
        selected = bool(self.selected())
        self.refresh_button.configure(state='normal' if ready else 'disabled')
        self.create_button.configure(state='normal' if editable else 'disabled')
        self.delete_button.configure(state='normal' if editable and selected else 'disabled')
        self.password_button.configure(state='normal' if editable and selected else 'disabled')
        self.retry_button.configure(state='normal' if ready and self.pending else 'disabled')
        for widget in (self.login_entry, self.password_entry, self.reset_entry):
            widget.configure(state='normal' if editable else 'disabled')
        self.role_input.configure(state='readonly' if editable else 'disabled')

    def send(self, body):
        runtime = self.runtime()
        if not runtime or self.busy:
            return
        self.busy = True
        context = str(runtime.host_data)
        if body['operation'] != 'list':
            self.pending = {'context': context, 'body': body}
        self.controls()
        self.status.set('正在读取账号…' if body['operation'] == 'list' else '正在处理账号操作…')
        def work():
            try:
                self.events.put((context, body, self.request(runtime, body), None))
            except AccountError as error:
                self.events.put((context, body, None, error))
            except Exception:
                self.events.put((context, body, None, AccountError('HOST_CONTROL_UNAVAILABLE', uncertain=True)))
        threading.Thread(target=work, daemon=True).start()

    def refresh(self):
        self.send({'operation': 'list'})

    def create(self):
        name, password = self.login.get().strip(), self.password.get()
        if not name or len(name) > 80 or any(ord(c) < 32 for c in name) or not 8 <= len(password) <= 1024:
            self.status.set('账号应为1–80个字符，密码应为8–1024个字符。'); return
        self.send({'requestId': str(uuid.uuid4()), 'operation': 'create', 'accountId': name,
                   'password': password, 'role': 'kp' if self.role.get() == 'KP' else 'player'})
        self.password.set('')

    def delete(self):
        record = self.selected()
        if record and messagebox.askyesno('删除账号', '删除账号“'+record['accountId']+'”？\n该账号将无法登录，已有角色和历史记录保留。', parent=self):
            self.send({'requestId': str(uuid.uuid4()), 'operation': 'delete', 'accountId': record['accountId']})

    def reset_password(self):
        record, password = self.selected(), self.new_password.get()
        if not record:return
        if not 8 <= len(password) <= 1024:
            self.status.set('新密码应为8–1024个字符。'); return
        self.send({'requestId': str(uuid.uuid4()), 'operation': 'password', 'accountId': record['accountId'], 'password': password})
        self.new_password.set('')

    def retry(self):
        if self.pending and self.runtime() and str(self.runtime().host_data) == self.pending['context']:
            self.send(self.pending['body'])

    def tick(self):
        runtime = self.runtime()
        context = str(runtime.host_data) if runtime else None
        if context != self.context and not self.busy:
            self.context = context
            self.last_receipt = ''
            for row in self.tree.get_children():self.tree.delete(row)
            self.records.clear()
            if self.pending and context and self.pending['context'] != context:self.pending = None
            self.room.set('当前房间：'+self.panel.current_slot['name'] if self.panel.current_slot else '尚未选择房间')
            if context:self.refresh()
            else:self.status.set('启动所选房间后可管理账号。')
        while True:
            try: source, body, value, error = self.events.get_nowait()
            except queue.Empty:break
            self.busy = False
            if source != context:continue
            locator = ' · 请求 '+body['requestId'] if body.get('requestId') else ''
            if error:
                if body['operation'] != 'list' and not error.uncertain:self.pending = None
                self.status.set(str(error)+('；结果待核对，请重试原请求。' if error.uncertain and body['operation'] != 'list' else '')+locator)
            elif body['operation'] == 'list':
                selected = self.selected()
                for row in self.tree.get_children():self.tree.delete(row)
                self.records.clear()
                for index, row in enumerate(value.get('accounts', value.get('items', []))):
                    key = str(index); self.records[key] = row
                    role = row.get('role', row.get('roomRole'))
                    state = '处理中' if row.get('pending') else '已删除' if row.get('deleted') else '已停用' if row.get('disabled') else '未加入房间' if row.get('roomActive') is False else '可登录'
                    self.tree.insert('', 'end', iid=key, values=(row['accountId'], row.get('nickname', row.get('displayName', '')), {'kp': 'KP', 'player': '玩家'}.get(role, '未加入房间'), state))
                    if selected and selected['accountId'] == row['accountId']:self.tree.selection_set(key)
                self.status.set('已读取 '+str(len(self.records))+' 个账号。'+('有操作结果待核对，请重试原请求。' if self.pending else self.last_receipt))
            elif value.get('status') != 'committed':
                self.status.set('操作尚未完成，请核对／重试原请求。'+locator)
            else:
                self.pending = None
                self.last_receipt = {'create': '账号已创建', 'delete': '账号已删除', 'password': '密码已修改，原登录会话已失效'}[body['operation']]+locator
                self.status.set(self.last_receipt)
                self.refresh()
        self.controls()
