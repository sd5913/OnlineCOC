import {app, BrowserWindow, dialog, ipcMain, session} from 'electron';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {VERSION} from '@localizer/contracts';

const settingsFlag = process.argv.indexOf('--settings-dir');
if (settingsFlag >= 0 && process.argv[settingsFlag + 1]) app.setPath('userData', path.resolve(process.argv[settingsFlag + 1]));
else app.setPath('userData', path.join(app.getPath('appData'), 'IndependentLocalizer'));
const handles = new Map<string, string>();
let win: BrowserWindow;
app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  session.defaultSession.webRequest.onBeforeRequest({urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*']}, (_details, callback) => callback({cancel: true}));
  win = new BrowserWindow({width: 1280, height: 800, minWidth: 800, minHeight: 600, title: 'Localizer · 独立本地化工具', show: false, webPreferences: {preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, sandbox: true, nodeIntegration: false}});
  win.setMenuBarVisibility(false);
  win.webContents.setWindowOpenHandler(() => ({action: 'deny'}));
  win.webContents.on('will-navigate', e => e.preventDefault());
  const html = path.join(__dirname, 'renderer', 'index.html');
  ipcMain.handle('localizer:choose-project', async event => {
    if (event.sender !== win.webContents || event.senderFrame !== win.webContents.mainFrame) throw new Error('非法调用来源');
    const result = await dialog.showOpenDialog(win, {title: '选择本地化项目目录', properties: ['openDirectory', 'createDirectory']});
    if (result.canceled || !result.filePaths[0]) return null;
    const handle = randomUUID();
    handles.set(handle, result.filePaths[0]);
    return {handle, name: path.basename(result.filePaths[0]), version: VERSION};
  });
  win.once('ready-to-show', () => win.show());
  void win.loadFile(html);
});
app.on('window-all-closed', () => app.quit());
