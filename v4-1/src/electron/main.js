const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { shell } = require('electron');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

function findPythonExecutable() {
  const candidates = ['python', 'py', 'python3'];
  for (const c of candidates) {
    try {
      const res = spawnSync(c, ['--version']);
      if (res && res.status === 0) {
        return c;
      }
    } catch (e) {
      // continue
    }
  }
  return null;
}

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 720,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

ipcMain.handle('select-input', async (event, type) => {
  if (type === 'zip') {
    const res = await dialog.showOpenDialog(mainWindow, { properties: ['openFile'], filters: [{ name: 'Zip', extensions: ['zip'] }] });
    if (res.canceled) return null;
    return res.filePaths[0];
  } else {
    const res = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
    if (res.canceled) return null;
    return res.filePaths[0];
  }
});

ipcMain.handle('select-report-dir', async () => {
  const res = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
  if (res.canceled) return null;
  return res.filePaths[0];
});

ipcMain.handle('select-python', async () => {
  const res = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [{ name: 'Executables', extensions: ['exe'] }]
  });
  if (res.canceled) return null;
  return res.filePaths[0];
});

// Check whether a list of Python packages can be imported by the given python executable.
ipcMain.handle('check-packages', async (event, pythonPath, packages) => {
  try {
    if (!pythonPath) {
      // try to auto-detect
      pythonPath = findPythonExecutable();
    }
    if (!pythonPath) return { success: false, error: 'No python executable provided or detected.' };

    const script = `import json\npkgs=${JSON.stringify(packages)}\nmiss=[]\nfor p in pkgs:\n    try:\n        __import__(p)\n    except Exception:\n        miss.append(p)\nprint(json.dumps(miss))`;
    const res = spawnSync(pythonPath, ['-c', script]);
    if (res.error) {
      return { success: false, error: res.error.message };
    }
    const out = (res.stdout || '').toString().trim();
    try {
      const miss = JSON.parse(out || '[]');
      return { success: true, missing: miss };
    } catch (e) {
      return { success: false, error: `Failed to parse python output: ${out}` };
    }
  } catch (e) {
    return { success: false, error: e.message };
  }
});

// Install packages into the chosen python using pip --user. This runs synchronously and returns output.
ipcMain.handle('install-packages', async (event, pythonPath, packages) => {
  try {
    if (!pythonPath) {
      pythonPath = findPythonExecutable();
    }
    if (!pythonPath) return { success: false, error: 'No python executable provided or detected.' };
    const args = ['-m', 'pip', 'install', '--user', ...packages];
    const res = spawnSync(pythonPath, args, { encoding: 'utf8' });
    const stdout = res.stdout || '';
    const stderr = res.stderr || '';
    const code = res.status !== undefined ? res.status : (res.error ? 1 : 0);
    return { success: code === 0, code, stdout, stderr };
  } catch (e) {
    return { success: false, error: e.message };
  }
});

ipcMain.handle('check-python', async () => {
  // Return a richer object: which command was found, the resolved executable path, and version
  const candidates = ['python', 'py', 'python3'];
  for (const c of candidates) {
    try {
      const which = spawnSync(c, ['-c', "import sys; print(sys.executable)"]);
      if (which && which.status === 0 && which.stdout) {
        const exePath = which.stdout.toString().trim();
        const ver = spawnSync(exePath, ['--version']);
        const version = ver && ver.stdout ? ver.stdout.toString().trim() : (ver && ver.stderr ? ver.stderr.toString().trim() : 'unknown');
        return { cmd: c, path: exePath, version };
      }
    } catch (e) {
      // continue
    }
  }
  return null;
});

ipcMain.handle('run-parser', async (event, inputPath, reportPath, pythonPath) => {
  // If the renderer supplied an explicit pythonPath, prefer that (and verify it exists).
  let python = null;
  try {
    if (pythonPath) {
      if (require('fs').existsSync(pythonPath)) {
        python = pythonPath;
      } else {
        return { success: false, error: `Selected Python executable not found: ${pythonPath}` };
      }
    } else {
      python = findPythonExecutable();
    }
    if (!python) {
      return { success: false, error: 'Python executable not found on PATH. Please install Python or ensure it is on PATH.' };
    }
  } catch (e) {
    return { success: false, error: `Error resolving Python executable: ${e.message}` };
  }

  // Try to find the compiled .exe first, fallback to .py script
  let scriptPath = null;
  let usePython = false;
  
  // Search locations for the backend exe (packaged app puts extraResources in process.resourcesPath)
  const exeCandidates = [
    path.join(process.resourcesPath || '', 'KeyProgrammerParser-Backend.exe'),
    path.join(__dirname, 'KeyProgrammerParser-Backend.exe'),
    path.join(__dirname, '..', 'KeyProgrammerParser-Backend.exe'),
    path.join(__dirname, 'dist', 'KeyProgrammerParser-Backend.exe'),
  ];
  const pyCandidates = [
    path.join(process.resourcesPath || '', 'KeyProgrammerParser.py'),
    path.join(__dirname, 'KeyProgrammerParser.py'),
    path.join(__dirname, '..', 'KeyProgrammerParser.py'),
  ];

  try {
    const fs = require('fs');
    // Try exe first
    for (const candidate of exeCandidates) {
      if (candidate && fs.existsSync(candidate)) {
        scriptPath = candidate;
        break;
      }
    }
    // Fallback to Python script
    if (!scriptPath) {
      for (const candidate of pyCandidates) {
        if (candidate && fs.existsSync(candidate)) {
          scriptPath = candidate;
          usePython = true;
          break;
        }
      }
    }
  } catch (e) {
    return { success: false, error: `Error inspecting application files: ${e.message}` };
  }

  if (!require('fs').existsSync(scriptPath)) {
    return { success: false, error: `Cannot find KeyProgrammerParser-Backend.exe or KeyProgrammerParser.py in application directory.` };
  }

  return new Promise((resolve) => {
    // If using .exe, don't pass it through Python. If using .py, prepend python executable
    const args = usePython ? [scriptPath, '--cli', inputPath, reportPath] : ['--cli', inputPath, reportPath];
    // Prepare child environment: prefer TEMP on the same drive as the reportPath when possible.
    // If that drive is low on space, pick another drive with the most free space (uses WMIC on Windows).
    let childEnv = Object.assign({}, process.env);
    try {
      const fs = require('fs');
      const pathModule = require('path');
      const os = require('os');
      const { spawnSync } = require('child_process');

      const MIN_BYTES = 200 * 1024 * 1024; // 200 MB minimum free recommended

      // helper to parse wmic output and return array of {drive, free}
      function listWindowsDrivesFree() {
        try {
          const res = spawnSync('wmic', ['logicaldisk', 'get', 'Caption,FreeSpace'], { encoding: 'utf8' });
          const out = (res.stdout || '').toString();
          const lines = out.split(/\r?\n/).map(l => l.trim()).filter(l => l && !/^Caption/i.test(l));
          const arr = [];
          for (const line of lines) {
            // lines may be like: C: 123456789
            const m = line.match(/^([A-Z]:)\s+(\d+)$/i);
            if (m) arr.push({ drive: m[1], free: parseInt(m[2], 10) });
          }
          return arr;
        } catch (e) {
          return [];
        }
      }

      let chosenTemp = null;

      if (reportPath) {
        const reportDir = pathModule.dirname(reportPath);
        try {
          // prefer report drive if it has enough free space
          const reportRoot = pathModule.parse(reportDir).root; // e.g., 'C:\'
          const drives = listWindowsDrivesFree();
          const reportDriveLetter = reportRoot ? reportRoot.replace('\\', '').replace(':', ':') : null;
          let reportDriveInfo = null;
          if (reportDriveLetter) {
            reportDriveInfo = drives.find(d => d.drive.toUpperCase().startsWith(reportDriveLetter.toUpperCase()));
          }
          if (reportDriveInfo && reportDriveInfo.free > MIN_BYTES) {
            const tempOnReport = pathModule.join(reportDir, 'kp_tmp');
            try {
              if (!fs.existsSync(tempOnReport)) fs.mkdirSync(tempOnReport, { recursive: true });
              chosenTemp = tempOnReport;
              mainWindow.webContents.send('parser-output', `Using TEMP on report drive: ${chosenTemp} (free ${Math.round(reportDriveInfo.free/1024/1024)} MB)\n`);
            } catch (e) {
              mainWindow.webContents.send('parser-output', `Failed to create temp on report drive: ${e.message}\n`);
            }
          } else {
            // pick drive with most free space
            if (drives && drives.length > 0) {
              drives.sort((a,b) => b.free - a.free);
              const best = drives[0];
              if (best && best.free > MIN_BYTES) {
                const rootDrive = best.drive + pathModule.sep;
                const tempOnDrive = pathModule.join(rootDrive, 'kp_tmp');
                try {
                  if (!fs.existsSync(tempOnDrive)) fs.mkdirSync(tempOnDrive, { recursive: true });
                  chosenTemp = tempOnDrive;
                  mainWindow.webContents.send('parser-output', `Using TEMP on drive ${best.drive}: ${chosenTemp} (free ${Math.round(best.free/1024/1024)} MB)\n`);
                } catch (e) {
                  mainWindow.webContents.send('parser-output', `Failed to create temp on drive ${best.drive}: ${e.message}\n`);
                }
              } else {
                mainWindow.webContents.send('parser-output', `No drive with sufficient free space found (need > ${Math.round(MIN_BYTES/1024/1024)} MB). Using default TEMP.\n`);
              }
            }
          }
        } catch (e) {
          mainWindow.webContents.send('parser-output', `Error checking drives: ${e.message}\n`);
        }
      }

      if (chosenTemp) {
        childEnv.TEMP = chosenTemp;
        childEnv.TMP = chosenTemp;
      }
    } catch (e) {
      mainWindow.webContents.send('parser-output', `Temp-selection failure: ${e.message}\n`);
    }

    // If using compiled .exe, spawn it directly. If using .py, spawn python with the script.
    const proc = usePython 
      ? spawn(python, args, { cwd: path.dirname(scriptPath), env: childEnv })
      : spawn(scriptPath, args, { cwd: path.dirname(scriptPath), env: childEnv });
    let procOutput = '';

    proc.stdout.on('data', (data) => {
      const s = data.toString();
      procOutput += s;
      mainWindow.webContents.send('parser-output', s);
    });

    proc.stderr.on('data', (data) => {
      const s = data.toString();
      procOutput += s;
      mainWindow.webContents.send('parser-output', s);
    });

    proc.on('close', (code) => {
      // Check whether the report file was created
      let reportExists = false;
      let reportCandidates = [];
      try {
        const fs = require('fs');
        if (reportPath && fs.existsSync(reportPath)) reportExists = true;
        // if report missing, scan the target folder for html files with similar prefix
        try {
          const dir = reportPath ? require('path').dirname(reportPath) : null;
          if (dir && fs.existsSync(dir)) {
            const files = fs.readdirSync(dir);
            reportCandidates = files.filter(f => f.toLowerCase().endsWith('.html') && f.toLowerCase().includes('keyprogrammerreport')).map(f => require('path').join(dir, f));
          }
        } catch (e) {
          // ignore scanning errors
        }
      } catch (e) {
        reportExists = false;
      }
      // try to cleanup kp_tmp in the report folder if it exists and is empty
      try {
        const fs = require('fs');
        const pathModule = require('path');
        if (reportPath) {
          const ptemp = pathModule.join(pathModule.dirname(reportPath), 'kp_tmp');
          if (fs.existsSync(ptemp)) {
            const files = fs.readdirSync(ptemp);
            if (!files || files.length === 0) {
              fs.rmdirSync(ptemp);
            }
          }
        }
      } catch (e) {
        // ignore cleanup errors
      }
      mainWindow.webContents.send('parser-done', { code, reportPath, reportExists, output: procOutput, reportCandidates });
      resolve({ success: code === 0, code, reportPath, reportExists, output: procOutput, reportCandidates });
    });

    proc.on('error', (err) => {
      mainWindow.webContents.send('parser-output', `Process error: ${err.message}\n`);
      resolve({ success: false, error: err.message });
    });
  });
});

ipcMain.handle('open-path', async (event, p) => {
  try {
    await shell.openPath(p);
    return { success: true };
  } catch (e) {
    return { success: false, error: e.message };
  }
});
