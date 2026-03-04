const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  selectInput: (type) => ipcRenderer.invoke('select-input', type),
  selectReportDir: () => ipcRenderer.invoke('select-report-dir'),
  selectPython: () => ipcRenderer.invoke('select-python'),
  checkPython: () => ipcRenderer.invoke('check-python'),
  checkPackages: (pythonPath, packages) => ipcRenderer.invoke('check-packages', pythonPath, packages),
  installPackages: (pythonPath, packages) => ipcRenderer.invoke('install-packages', pythonPath, packages),
  runParser: (inputPath, reportPath, pythonPath) => ipcRenderer.invoke('run-parser', inputPath, reportPath, pythonPath),
  onOutput: (cb) => ipcRenderer.on('parser-output', (e, data) => cb(data)),
  onDone: (cb) => ipcRenderer.on('parser-done', (e, payload) => cb(payload)),
  openPath: (p) => ipcRenderer.invoke('open-path', p)
});
