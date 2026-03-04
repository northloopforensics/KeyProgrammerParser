console.debug('renderer.js loaded');
const inputPathEl = document.getElementById('inputPath');
const reportPathEl = document.getElementById('reportPath');
const browseInputBtn = document.getElementById('browseInput');
const browseReportBtn = document.getElementById('browseReport');
const startBtn = document.getElementById('startBtn');
const helpBtn = document.getElementById('helpBtn');
// We no longer keep a scrolling console; show only the current action below the progress bar
const outputArea = null;
const currentActionEl = document.getElementById('currentAction');
const progressEl = document.getElementById('progress');
const outputMeta = document.getElementById('outputMeta');

let running = false;

const spinnerEl = document.getElementById('spinner');
function showSpinner() {
  if (spinnerEl) spinnerEl.classList.add('active');
}
function hideSpinner() {
  if (spinnerEl) spinnerEl.classList.remove('active');
}

// Responsive sizing: ensure the output area and report iframe fill the available right-column height
function adjustLayoutHeights() {
  try {
    const content = document.querySelector('.content');
    if (!content) return;
    const contentRect = content.getBoundingClientRect();
    const tabs = document.querySelector('.tabs');
    const tabsH = tabs ? tabs.getBoundingClientRect().height : 0;

    const available = Math.max(120, Math.floor(contentRect.height - tabsH - 24));

  // iframe sizing is handled by CSS flex; no direct pixel sizing here

    const outputHeader = document.querySelector('.output-header');
    const headerH = outputHeader ? outputHeader.getBoundingClientRect().height : 0;
    const progH = progressEl ? progressEl.getBoundingClientRect().height : 0;
    const outAvail = Math.max(80, available - headerH - progH - 20);
    if (outputArea) {
      outputArea.style.height = outAvail + 'px';
      outputArea.style.minHeight = '80px';
    }
  } catch (e) {
    console.warn('adjustLayoutHeights failed', e);
  }
}

window.addEventListener('resize', adjustLayoutHeights);
document.addEventListener('DOMContentLoaded', adjustLayoutHeights);

// ResizeObserver fallback: watch the main layout element and recalc heights when it changes
try {
  const layoutEl = document.querySelector('.layout');
  if (layoutEl && typeof ResizeObserver !== 'undefined') {
    const ro = new ResizeObserver(() => {
      setTimeout(adjustLayoutHeights, 40);
    });
    ro.observe(layoutEl);
  }
} catch (e) {
  console.warn('ResizeObserver not available or failed', e);
}

// Electron: attempt to re-run layout adjustment after a short delay when window is focused (covers maximize)
window.addEventListener('focus', () => { setTimeout(adjustLayoutHeights, 80); });

browseInputBtn.addEventListener('click', async () => {
  try {
    const radio = document.querySelector('input[name="inputType"]:checked');
    const type = radio ? radio.value : 'zip';
    if (!window.api || !window.api.selectInput) {
      appendError('Error: IPC API not available (selectInput).');
      console.error('window.api.selectInput not available');
      return;
    }
    const res = await window.api.selectInput(type);
    if (res) inputPathEl.value = res;
  } catch (e) {
    appendError('Failed to open input selector: ' + (e && e.message ? e.message : String(e)));
    console.error(e);
  }
});

browseReportBtn.addEventListener('click', async () => {
  try {
    if (!window.api || !window.api.selectReportDir) {
      appendError('Error: IPC API not available (selectReportDir).');
      console.error('window.api.selectReportDir not available');
      return;
    }
    const res = await window.api.selectReportDir();
    if (res) reportPathEl.value = res;
  } catch (e) {
    appendError('Failed to open report folder selector: ' + (e && e.message ? e.message : String(e)));
    console.error(e);
  }
});

helpBtn.addEventListener('click', () => {
  // Show modal help
  const modal = document.getElementById('helpModal');
  if (modal) modal.setAttribute('aria-hidden', 'false');
});

// Close modal handlers (delegated to work even if modal is added after script runs)
document.addEventListener('click', (e) => {
  const modal = document.getElementById('helpModal');
  if (!modal) return;
  // close when clicking the X, Close button, or backdrop
  if (e.target.closest('#closeHelp') || e.target.closest('#closeHelp2') || e.target.closest('#modalBackdrop') || e.target.closest('.modal-close')) {
    modal.setAttribute('aria-hidden', 'true');
  }
});

// Allow Escape to close the modal
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const modal = document.getElementById('helpModal');
    if (modal && modal.getAttribute('aria-hidden') === 'false') {
      modal.setAttribute('aria-hidden', 'true');
    }
  }
});

startBtn.addEventListener('click', async () => {
  if (running) return;
  const input = inputPathEl.value;
  const reportDir = reportPathEl.value;
  if (!input) return alert('Please select an input file or folder.');
  if (!reportDir) return alert('Please select a report folder.');

  // Build default report filename
  const now = new Date();
  const pad = (n) => n.toString().padStart(2, '0');
  const fname = `KeyProgrammerReport_${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.html`;
  // Build a report path by joining with a backslash (Windows-friendly).
  const sep = reportDir.endsWith('\\') || reportDir.endsWith('/') ? '' : '\\';
  const reportPath = `${reportDir}${sep}${fname}`;

  // Ensure the preload API is available
  if (!window.api) {
    appendError('Error: window.api (preload) is not available.');
    running = false;
    startBtn.disabled = false;
    return;
  }

  // Informational Python check
  const python = await window.api.checkPython();
  if (python) {
    appendLine(`Using Python: ${python.path || python.cmd} ${python.version || ''}`);
  }

  running = true;
  startBtn.disabled = true;
  if (currentActionEl) { currentActionEl.textContent = 'Starting...'; currentActionEl.classList.remove('err','warn'); }
  outputMeta.textContent = 'starting...';
  progressEl.removeAttribute('value'); // indeterminate
  showSpinner();

  const res = await window.api.runParser(input, reportPath, null);
  if (res && res.success === false) {
    const err = res.error || JSON.stringify(res);
    if (currentActionEl) { currentActionEl.textContent = `Error starting parser: ${err}`; currentActionEl.classList.add('err'); }
    console.error('Run parser error:', res);
    running = false;
    startBtn.disabled = false;
    progressEl.value = 0;
    outputMeta.textContent = 'idle';
  hideSpinner();
    return;
  }

});

window.api.onOutput((data) => {
  // Detect CLI progress tokens like 'PROGRESS:45' and update the progress bar
  const lines = data.split(/\r?\n/);
  for (const line of lines) {
    if (!line) continue;
    const m = line.match(/^PROGRESS:(\d{1,3})$/);
    if (m) {
      const val = parseInt(m[1], 10);
      progressEl.value = Math.min(100, Math.max(0, val));
      continue;
    }
    // Update the single-line current action status
    if (currentActionEl) {
      if (line.startsWith('Traceback') || line.startsWith('Traceback') || line.startsWith('ERROR') || line.includes('ModuleNotFoundError')) {
        currentActionEl.textContent = 'Error: ' + line;
        currentActionEl.classList.add('err');
      } else if (line.startsWith('WARNING') || line.startsWith('Warning')) {
        currentActionEl.textContent = 'Warning: ' + line;
        currentActionEl.classList.add('warn');
      } else {
        currentActionEl.textContent = line;
        currentActionEl.classList.remove('err','warn');
      }
    }
  }
  adjustLayoutHeights();
});

window.api.onDone((payload) => {
  running = false;
  startBtn.disabled = false;
  hideSpinner();
  const code = payload.code !== undefined ? payload.code : (payload || 1);
  const reportPath = payload.reportPath;
  const reportExists = payload.reportExists === true;
  progressEl.value = 100;
  if (code === 0) {
  if (currentActionEl) currentActionEl.textContent = `Processing finished successfully (exit code ${code}).`;
  } else {
  if (currentActionEl) { currentActionEl.textContent = `Processing finished with exit code ${code}.`; currentActionEl.classList.add('err'); }
  }
  if (reportPath) {
    console.log('parser-done payload', { code, reportPath, payload });
  if (currentActionEl) currentActionEl.textContent = `Report: ${reportPath} (exists: ${reportExists})`;
    // create or reuse an Open Report button
    let openBtn = document.getElementById('openReportBtn');
    if (!openBtn) {
      openBtn = document.createElement('button');
      openBtn.id = 'openReportBtn';
      openBtn.textContent = 'Open Report';
      openBtn.className = 'secondary';
      openBtn.addEventListener('click', async (e) => { e.preventDefault(); await window.api.openPath(reportPath); });
      const header = document.querySelector('.output-header');
      if (header) header.appendChild(openBtn);
    }

    // Load report into iframe (use file:// protocol). Make iframe visible and allow loading.
    try {
      const iframe = document.getElementById('reportIframe');
  if (iframe) {
        iframe.style.display = 'block';
        iframe.style.minHeight = '200px';
        iframe.removeAttribute('sandbox');
        const src = 'file:///' + reportPath.replace(/\\/g, '/');
        iframe.src = src;
        setTimeout(adjustLayoutHeights, 120);
      }
    } catch (e) {
      console.warn('Failed to load report into iframe', e);
      if (currentActionEl) currentActionEl.textContent = `Report ready: ${reportPath} (open externally)`;
    }
    // If the report file wasn't created, surface the parser output and any candidates
    if (!reportExists) {
      // show parser output in the currentAction area (brief)
      if (currentActionEl) {
        const short = (payload && payload.output) ? payload.output.split(/\r?\n/).slice(-6).join(' \u23B5 ') : '';
        currentActionEl.textContent = `Report not found. Recent output: ${short}`;
        currentActionEl.classList.add('err');
      }
      // show candidate files list
      const header = document.querySelector('.output-header');
      if (header && payload && payload.reportCandidates && payload.reportCandidates.length > 0) {
        let list = document.getElementById('candidateList');
        if (!list) {
          list = document.createElement('div');
          list.id = 'candidateList';
          list.style.marginTop = '8px';
          list.style.display = 'flex';
          list.style.flexDirection = 'column';
          list.style.gap = '6px';
          header.appendChild(list);
        }
        list.innerHTML = '';
        for (const f of payload.reportCandidates) {
          const row = document.createElement('div');
          row.style.display = 'flex'; row.style.gap = '8px'; row.style.alignItems = 'center';
          const p = document.createElement('div'); p.textContent = f; p.style.fontSize = '12px'; p.style.color = '#cfe9ff'; p.style.flex = '1';
          const b = document.createElement('button'); b.textContent = 'Open'; b.className = 'secondary';
          b.addEventListener('click', async (e) => { e.preventDefault(); await window.api.openPath(f); });
          row.appendChild(p); row.appendChild(b);
          list.appendChild(row);
        }
      }
    }
  }
  outputMeta.textContent = 'idle';
});

// Tabs removed in this layout

function appendLine(text) {
  if (currentActionEl) { currentActionEl.textContent = text; currentActionEl.classList.remove('err','warn'); }
}

function appendError(text) {
  if (currentActionEl) { currentActionEl.textContent = text; currentActionEl.classList.add('err'); }
}

function appendWarn(text) {
  if (currentActionEl) { currentActionEl.textContent = text; currentActionEl.classList.add('warn'); }
}

