const { contextBridge, ipcRenderer, shell } = require('electron')

contextBridge.exposeInMainWorld('api', {
  fetchComment:    (id)               => ipcRenderer.invoke('fetch-comment', id),
  fetchArtifact:   (id)               => ipcRenderer.invoke('fetch-artifact', id),
  dismissComment:  (id)               => ipcRenderer.invoke('dismiss-comment', id),
  submitFeedback:  (id, key, preview) => ipcRenderer.invoke('submit-feedback', id, key, preview),
  updateSlider:    (v)                => ipcRenderer.invoke('update-slider', v),
  // format: 'json' | 'events' | 'states'
  exportSession:   (format)           => ipcRenderer.invoke('export-session', format),
  manualCapture:   ()                 => ipcRenderer.send('manual-capture'),
  drag:            (d)                => ipcRenderer.send('window-drag', d),
  close:           ()                 => ipcRenderer.send('window-close'),
  minimize:        ()                 => ipcRenderer.send('window-minimize'),
  on:       (ch, cb) => ipcRenderer.on(ch, (_, data) => cb(data)),
  openLink: (url)    => shell.openExternal(url),
  resize:   (h)      => ipcRenderer.send('window-resize', h),
})
