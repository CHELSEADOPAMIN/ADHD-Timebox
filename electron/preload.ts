import { contextBridge, ipcRenderer  } from "electron";
 
contextBridge.exposeInMainWorld("electronAPI", {
  saveSession: (session: any) => 
    ipcRenderer.invoke('save-session', session),
  loadSessions: () => 
    ipcRenderer.invoke('load-sessions'),
});