import {contextBridge, ipcRenderer} from 'electron';
contextBridge.exposeInMainWorld('localizer', Object.freeze({chooseProject: () => ipcRenderer.invoke('localizer:choose-project')}));
