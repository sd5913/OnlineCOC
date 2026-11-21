"""Native Python room panel. Minimizing keeps the room; closing owns shutdown."""
import argparse
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

sys.dont_write_bytecode = True
from lan import PACK, Adapter, LanService, LanWindow
from slots import RoomSlots
from accounts import AccountsTab

ROOT = PACK.parents[1]
MODES = {'local': '本机游玩', 'lan': '局域网联机', 'web': '网页联机', 'p2p': '旧 P2P（基础功能）'}


class PanelWindow(LanWindow):
    def __init__(self, root, data=PACK/'runtime', open_browser=True, *, mode='local', ai=True,
                 port=None, bind=None, ai_config=None, web_config=None, p2p_config=None):
        self.mode = tk.StringVar(root, MODES[mode])
        self.ai = tk.BooleanVar(root, ai)
        self.configs = {'ai_config': ai_config or ROOT/'engineering/ai/config/ai-providers.json',
                        'web_config': web_config or ROOT/'engineering/network-p2p/local/client-config.json',
                        'p2p_config': p2p_config or ROOT/'engineering/network-p2p/local/client-config.json'}
        self.last_url = self.share_url = ''
        self.slots = RoomSlots(data)
        self.current_slot = self.slots.selected()
        self.slot_rows = []
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)
        viewport = ttk.Frame(self.notebook)
        self.notebook.add(viewport, text='房间启动')
        self.canvas = tk.Canvas(viewport, highlightthickness=0)
        scrollbar = ttk.Scrollbar(viewport, orient='vertical', command=self.canvas.yview)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        initial_data = self.slots.path(self.current_slot['id']) if self.current_slot else self.slots.directory/'_unselected'
        super().__init__(root, initial_data, open_browser, container=self.canvas)
        self.frame.pack_forget()
        self.canvas_window = self.canvas.create_window((0, 0), window=self.frame, anchor='nw')
        self.frame.bind('<Configure>', lambda _: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfigure(self.canvas_window, width=event.width))
        root.bind('<MouseWheel>', lambda event: self.canvas.yview_scroll(-int(event.delta/120), 'units') if not isinstance(event.widget, ttk.Combobox) else None)
        self.service = LanService(self.data, self.events, allow_local=True)
        root.title('树桩镇 · 房间管理')
        root.geometry('870x'+str(min(900, root.winfo_screenheight()-100)))
        root.minsize(790, 600)
        self.heading.configure(text='树桩镇 · 房间管理')
        self.subtitle.grid_remove()
        self.controls = ttk.Frame(self.frame)
        self.controls.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(0, 16))
        self.mode_input = ttk.Combobox(self.controls, textvariable=self.mode, values=list(MODES.values()), state='readonly', width=22)
        self.mode_input.pack(side='left')
        self.mode_input.bind('<<ComboboxSelected>>', lambda _: self.scan())
        self.ai_input = ttk.Checkbutton(self.controls, text='加载 AI 助手', variable=self.ai)
        self.ai_input.pack(side='left', padx=16)
        ttk.Button(self.controls, text='最小化', command=root.iconify).pack(side='right')
        self.start_button.configure(text='启动房间')
        self.footer.configure(text='最小化后房间继续运行；关闭此面板会停止房间和分享，正常退出保留存档。\n自动裁决仍需一个已登录的 KP 网页在线。AI 调用与外发权限在 KP 助手中设置。')
        extras = ttk.Frame(self.frame)
        extras.grid(row=10, column=0, columnspan=3, sticky='ew', pady=(8, 0))
        ttk.Button(extras, text='查看运行日志', command=self.logs).pack(side='left')
        ttk.Button(extras, text='打开存档目录', command=self.open_data).pack(side='left', padx=8)
        self.manage_button = ttk.Button(extras, text='打开房间管理页', command=self.open_management, state='disabled')
        self.manage_button.pack(side='left')
        self.network_button = ttk.Button(extras, text='联机控制页', command=self.open_network, state='disabled')
        self.network_button.pack(side='left', padx=8)
        self.share = tk.StringVar(value='选择启动方式，确认端口后点击“启动房间”。')
        ttk.Label(self.frame, textvariable=self.share, wraplength=755).grid(row=11, column=0, columnspan=3, sticky='w', pady=12)
        self.share_button = ttk.Button(self.frame, text='复制联机信息', command=self.copy_share, state='disabled')
        self.share_button.grid(row=12, column=0, columnspan=3, sticky='w')
        for widget in self.frame.grid_slaves():
            row = int(widget.grid_info()['row'])
            if row >= 2:
                widget.grid_configure(row=row+1)
        self.slot_frame = ttk.LabelFrame(self.frame, text='房间数据 · 存档槽位', padding=10)
        self.slot_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(0, 12))
        self.slot_frame.columnconfigure(0, weight=1)
        self.slot_choice = tk.StringVar(root)
        self.slot_input = ttk.Combobox(self.slot_frame, textvariable=self.slot_choice, state='readonly')
        self.slot_input.grid(row=0, column=0, sticky='ew')
        self.slot_input.bind('<<ComboboxSelected>>', lambda _: self.choose_slot())
        self.slot_refresh = ttk.Button(self.slot_frame, text='刷新槽位', command=self.refresh_slots)
        self.slot_refresh.grid(row=0, column=1, padx=(8, 0))
        self.slot_name = tk.StringVar(root)
        name_row = ttk.Frame(self.slot_frame)
        name_row.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        ttk.Label(name_row, text='新槽位名称').pack(side='left', padx=(0, 8))
        self.slot_entry = ttk.Entry(name_row, textvariable=self.slot_name)
        self.slot_entry.pack(side='left', fill='x', expand=True)
        self.slot_create = ttk.Button(self.slot_frame, text='创建新槽位', command=self.create_slot)
        self.slot_create.grid(row=1, column=1, padx=(8, 0), pady=(8, 0))
        self.slot_entry.bind('<Return>', lambda _: self.create_slot())
        self.slot_info = tk.StringVar(root)
        ttk.Label(self.slot_frame, textvariable=self.slot_info, wraplength=740).grid(row=2, column=0, columnspan=2, sticky='w', pady=(8, 0))
        self.refresh_slots()
        self.accounts_tab = AccountsTab(self.notebook, self)
        self.notebook.add(self.accounts_tab, text='账号管理')
        if port is not None:
            self.port.set(str(port))
        if bind:
            self.preferred = bind

    def setup_visibility(self):
        if not self.current_slot:
            self.setup_frame.grid_remove()
        else:
            super().setup_visibility()
            if not (self.data/'host').exists() and not self.password.get() and not self.confirm.get():
                self.password.set('12345678'); self.confirm.set('12345678')

    def slots_locked(self):
        return self.busy or self.service.active or self.closing or bool(getattr(self, 'accounts_tab', None) and self.accounts_tab.busy)

    def refresh_slots(self):
        if self.slots_locked():
            return
        try:
            self.slot_rows = self.slots.list()
            selected = next((row for row in self.slot_rows if self.current_slot and row['id'] == self.current_slot['id']), None)
            selected = selected or self.slots.selected()
            self.slot_input.configure(values=[row['name'] for row in self.slot_rows])
            self.apply_slot(selected)
        except (OSError, ValueError) as error:
            self.status.set(str(error))

    def choose_slot(self):
        if self.slots_locked():
            self.slot_choice.set(self.current_slot['name'] if self.current_slot else '')
            return
        try:
            index = self.slot_input.current()
            if index < 0:
                return
            row = self.slots.select(self.slot_rows[index]['id'])
            self.apply_slot(row)
        except (OSError, ValueError) as error:
            self.status.set(str(error))

    def create_slot(self):
        if self.slots_locked():
            return
        try:
            self.current_slot = self.slots.create(self.slot_name.get())
            self.slot_name.set('')
            self.refresh_slots()
            self.status.set('槽位已创建。可直接使用默认账号密码启动，也可修改初始密码。')
        except (OSError, ValueError) as error:
            self.status.set(str(error))

    def apply_slot(self, row):
        self.current_slot = row
        self.data = self.slots.path(row['id']) if row else self.slots.directory/'_unselected'
        self.service = LanService(self.data, self.events, allow_local=True)
        self.slot_choice.set(row['name'] if row else '')
        initial_password = '' if row and (self.data/'host').exists() else '12345678'
        self.password.set(initial_password); self.confirm.set(initial_password)
        self.failed = False
        self.invalidate_url()
        self.last_url = self.share_url = ''
        self.setup_visibility()
        self.data_label.configure(text='当前存档：'+str(self.data) if row else '数据根目录：'+str(self.slots.root))
        ready = row and (self.data/'host').exists()
        self.slot_info.set(('已选择：'+row['name']+' · '+('已有房间数据' if ready else '新槽位：默认账号 kp、player1、player2，密码 12345678')+'。停止房间后可切换。') if row else '尚无槽位。先在上方输入名称，再点击“创建新槽位”。')
        self.status.set(('已选择槽位“'+row['name']+'”。') if row else '请创建房间槽位。')
        self.start_button.configure(state='normal' if row and self.adapters and not self.scanning else 'disabled')

    def selected_mode(self):
        return next(key for key, label in MODES.items() if label == self.mode.get())

    def scan(self):
        if getattr(self, 'busy', False) or getattr(self, 'scanning', False):
            return
        if self.selected_mode() == 'lan':
            super().scan()
        else:
            self.scanning = True
            self.start_button.configure(state='disabled')
            self.events.put(('adapters', [Adapter('本机管理入口', '127.0.0.1')]))

    def start(self):
        if self.busy or self.service.active:
            return
        if not self.current_slot:
            self.status.set('请先创建并选择房间槽位。')
            return
        mode = self.selected_mode()
        modules = {}
        if self.ai.get():
            modules['ai_config'] = self.configs['ai_config']
        if mode in ('web', 'p2p'):
            modules[mode+'_config'] = self.configs[mode+'_config']
        missing = next((key for key, path in modules.items() if not Path(path).is_file()), None)
        if missing:
            self.status.set(('AI服务商配置不存在，请先使用 start-ai-manager.cmd 完成配置。' if missing == 'ai_config'
                             else '联网配置不存在，请先按网页联机文档配置目录服务器。'))
            return
        self.service.modules = modules
        super().start()
        if self.busy:
            self.mode_input.configure(state='disabled')
            self.ai_input.configure(state='disabled')

    def copy(self):
        super().copy()
        if self.url and self.selected_mode() != 'lan':
            self.status.set('已复制本机入口；其他设备请使用下方联机信息。')

    def copy_share(self):
        if self.share_url:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.share_url)
            self.status.set('联机信息已复制。')

    def open_management(self):
        if self.url:
            webbrowser.open(self.url+'sessions/kp/#/gm/room')

    def open_network(self):
        if self.url and self.service.runtime:
            modules = self.service.runtime.modules
            if self.selected_mode() == 'p2p' and modules.entry:
                webbrowser.open(modules.entry)
            elif self.selected_mode() == 'web':
                value = modules.web_status()
                if value.get('running') and value.get('url'):
                    webbrowser.open(value['url'].rstrip('/')+'/manage')

    def open_data(self):
        if self.current_slot and self.data.is_dir():
            os.startfile(self.data.resolve())
        else:
            self.status.set('首次启动成功后才会创建存档目录。')

    def logs(self):
        sections = []
        for name in ('host.log', 'request-errors.log', 'web.log', 'p2p.log', 'panel.log'):
            path = self.data/name
            if path.is_file():
                # Bounded local display; no automatic upload or credential/config display.
                with path.open('rb') as file:
                    file.seek(max(0, path.stat().st_size-16000))
                    body = file.read().decode('utf-8', errors='replace')
                sections.append(name+'\n'+body)
        self.show_report('\n\n'.join(sections) if sections else '尚无运行日志；首次启动失败原因会显示在面板状态栏。', title='运行日志')

    def tick(self):
        super().tick()
        if self.closing:
            return
        locked = self.slots_locked()
        if self.current_slot:
            slot_status = '运行中' if self.url else '已有房间数据' if (self.data/'host').exists() else '新槽位：默认账号 kp、player1、player2，密码 12345678'
            self.slot_info.set('已选择：'+self.current_slot['name']+' · '+slot_status+'。停止房间后可切换。')
        self.slot_input.configure(state='disabled' if locked else 'readonly')
        for widget in (self.slot_create, self.slot_entry, self.slot_refresh):
            widget.configure(state='disabled' if locked else 'normal')
        if not self.current_slot:
            self.start_button.configure(state='disabled')
        self.mode_input.configure(state='disabled' if self.busy or self.scanning else 'readonly')
        self.ai_input.configure(state='disabled' if self.busy else 'normal')
        self.manage_button.configure(state='normal' if self.url else 'disabled')
        self.network_button.configure(state='normal' if self.url and self.selected_mode() in ('web', 'p2p') else 'disabled')
        self.copy_button.configure(text='复制玩家地址' if self.selected_mode() == 'lan' else '复制本机地址')
        if self.url and self.url != self.last_url:
            self.status.set('房间已运行。可最小化面板；关闭面板会停止房间。')
            initialized = getattr(self.service.runtime, 'bootstrap_ai', None)
            if initialized:
                extra = {'profile_unavailable': 'AI 权限已初始化；请在 AI 服务设置中配置可用模型。',
                         'profile_selection_required': 'AI 权限已初始化；请在 AI 服务设置中选择模型。',
                         'initialization_failed': '房间已创建，AI 初始化未完成：'+str(initialized.get('code', ''))+'。请在 AI 服务设置中检查。'}.get(initialized.get('serviceStatus'))
                if extra:self.status.set('房间已运行。'+extra)
        self.last_url = self.url
        self.share_url = ''
        if self.url and self.service.runtime:
            mode = self.selected_mode()
            self.links.configure(text='局域网玩家与主持入口' if mode == 'lan' else '本机主持入口（不向其他设备分享）')
            if mode == 'web':
                value = self.service.runtime.modules.web_status(private=True)
                if value.get('running') and value.get('roomCode'):
                    self.share_url = value['url'].rstrip('/')+'/join\n房间代号：'+value['roomCode']
                    self.share.set('网页分享已启动 · '+self.share_url.replace('\n', ' · ')+'\n首次认领：打开房间管理页 → 网页分享，复制开房串。')
                elif value.get('error'):
                    self.share.set('网页分享失败，本机房间仍可用：'+value['error']+'\n'+value.get('hint', '请查看 web.log。'))
                else:
                    self.share.set('网页分享已停止；本机房间仍可用。')
            elif mode == 'lan':
                self.share_url = self.url
                self.share.set('玩家用浏览器打开：'+self.url+'\n同一 Wi-Fi 无法访问时，使用“检查连接 / 启动问题”。')
            elif mode == 'p2p':
                self.share.set('点击“联机控制页”发布旧 P2P 房间。仅支持基础宿主功能；完整游玩请选择“网页联机”。')
            else:
                self.share.set('本机房间运行中。其他设备加入前，请停止房间并切换到局域网或网页联机。')
        elif not self.busy:
            self.share.set('请先创建并选择槽位。' if not self.current_slot else '房间已停止；再次启动使用所选槽位。' if (self.data/'host').exists() else '全新房间：默认账号和密码已准备，点击启动即可。')
        self.share_button.configure(state='normal' if self.share_url else 'disabled')
        self.accounts_tab.tick()


def arguments(argv=None):
    parser = argparse.ArgumentParser(description='树桩镇 Python 房间管理面板')
    parser.add_argument('--mode', choices=MODES, default='local')
    parser.add_argument('--data-dir', '-DataDir', type=Path, default=PACK/'runtime', help='房间槽位根目录；各槽位存于其 slots 子目录')
    parser.add_argument('--port', '-Port', type=int)
    parser.add_argument('--bind', '-Bind')
    parser.add_argument('--no-browser', '-NoBrowser', action='store_true')
    ai_group = parser.add_mutually_exclusive_group()
    ai_group.add_argument('--ai', '-AI', dest='ai', action='store_true')
    ai_group.add_argument('--no-ai', '-NoAI', dest='ai', action='store_false')
    parser.set_defaults(ai=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-Web', action='store_true')
    group.add_argument('-P2P', action='store_true')
    for name in ('ai', 'web', 'p2p'):
        parser.add_argument('--'+name+'-config', type=Path)
    args = parser.parse_args(argv)
    if args.Web:
        args.mode = 'web'
    if args.P2P:
        args.mode = 'p2p'
    if args.bind and args.bind != '127.0.0.1':
        if args.mode in ('web', 'p2p'):
            parser.error('网页和旧 P2P 的管理页必须绑定 127.0.0.1')
        args.mode = 'lan'
    return args


def main():
    args = arguments()
    root = tk.Tk()
    window = None
    try:
        window = PanelWindow(root, args.data_dir, not args.no_browser, mode=args.mode, ai=args.ai,
                             port=args.port, bind=args.bind, ai_config=args.ai_config,
                             web_config=args.web_config, p2p_config=args.p2p_config)
        root.mainloop()
    except Exception as error:
        messagebox.showerror('树桩镇面板错误', str(error), parent=root)
    finally:
        if window:
            window.service.stop()
            if window.service.thread:
                window.service.thread.join()
        try:
            root.destroy()
        except tk.TclError:
            pass


if __name__ == '__main__':
    main()
