const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('api', {
  fetchComment:   (id) => ipcRenderer.invoke('fetch-comment', id),
  fetchArtifact:  (id) => ipcRenderer.invoke('fetch-artifact', id),
  dismissComment: (id) => ipcRenderer.invoke('dismiss-comment', id),
  updateSlider:   (v)  => ipcRenderer.invoke('update-slider', v),
  exportSession:  ()   => ipcRenderer.invoke('export-session'),
  manualCapture:  ()   => ipcRenderer.send('manual-capture'),
  drag:           (d)  => ipcRenderer.send('window-drag', d),
  close:          ()   => ipcRenderer.send('window-close'),
  minimize:       ()   => ipcRenderer.send('window-minimize'),
  on: (ch, cb) => ipcRenderer.on(ch, (_, data) => cb(data)),
})
