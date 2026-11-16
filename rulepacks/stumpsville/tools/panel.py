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

ROOT = PACK.parents[1]
MODES = {'local': '本机游玩', 'lan': '局域网联机', 'web': '网页联机', 'p2p': '旧 P2P（基础功能）'}


class PanelWindow(LanWindow):
    def __init__(self, root, data=PACK/'runtime', open_browser=True, *, mode='local', ai=False,
                 port=None, bind=None, ai_config=None, web_config=None, p2p_config=None):
        self.mode = tk.StringVar(root, MODES[mode])
        self.ai = tk.BooleanVar(root, ai)
        self.configs = {'ai_config': ai_config or ROOT/'engineering/ai/config/ai-providers.json',
                        'web_config': web_config or ROOT/'engineering/network-p2p/local/client-config.json',
                        'p2p_config': p2p_config or ROOT/'engineering/network-p2p/local/client-config.json'}
        self.last_url = self.share_url = ''
        super().__init__(root, data, open_browser)
        self.service = LanService(self.data, self.events, allow_local=True)
        root.title('树桩镇 · 房间管理')
        root.geometry('820x770')
        root.minsize(790, 740)
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
        if port is not None:
            self.port.set(str(port))
        if bind:
            self.preferred = bind

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
        if self.busy:
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
        if self.data.is_dir():
            os.startfile(self.data.resolve())
        else:
            self.status.set('首次启动成功后才会创建存档目录。')

    def logs(self):
        sections = []
        for name in ('host.log', 'web.log', 'p2p.log', 'panel.log'):
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
        self.mode_input.configure(state='disabled' if self.busy or self.scanning else 'readonly')
        self.ai_input.configure(state='disabled' if self.busy else 'normal')
        self.manage_button.configure(state='normal' if self.url else 'disabled')
        self.network_button.configure(state='normal' if self.url and self.selected_mode() in ('web', 'p2p') else 'disabled')
        self.copy_button.configure(text='复制玩家地址' if self.selected_mode() == 'lan' else '复制本机地址')
        if self.url and self.url != self.last_url:
            self.status.set('房间已运行。可最小化面板；关闭面板会停止房间。')
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
            self.share.set('房间已停止；再次启动使用同一存档。' if (self.data/'host').exists() else '全新房间：设置初始密码后启动。')
        self.share_button.configure(state='normal' if self.share_url else 'disabled')


def arguments(argv=None):
    parser = argparse.ArgumentParser(description='树桩镇 Python 房间管理面板')
    parser.add_argument('--mode', choices=MODES, default='local')
    parser.add_argument('--data-dir', '-DataDir', type=Path, default=PACK/'runtime')
    parser.add_argument('--port', '-Port', type=int)
    parser.add_argument('--bind', '-Bind')
    parser.add_argument('--no-browser', '-NoBrowser', action='store_true')
    parser.add_argument('--ai', '-AI', action='store_true')
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
