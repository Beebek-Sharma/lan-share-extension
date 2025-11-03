// Helper: fetch with timeout
function fetchWithTimeout(url, opts = {}, timeout = 1000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('timeout'));
    }, timeout);
    fetch(url, opts).then(res => {
      clearTimeout(timer);
      resolve(res);
    }).catch(err => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

// Helper: promise wrapper for sendNativeMessage
function sendNativeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage('lan_share_host', message, response => {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
        return;
      }
      resolve(response);
    });
  });
}

// Poll localhost until it responds or timeout (ms)
async function waitForServer(url = 'http://localhost:5000', timeout = 5000, interval = 300) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      // Use short timeout per attempt
      await fetchWithTimeout(url, { method: 'GET', mode: 'no-cors' }, 800);
      return true;
    } catch (e) {
      // wait and retry
      await new Promise(r => setTimeout(r, interval));
    }
  }
  return false;
}

// Quick ping helper that returns boolean
function getPort() {
  const el = document.getElementById('port');
  const p = parseInt(el && el.value, 10);
  return Number.isFinite(p) && p > 0 ? p : 5000;
}

async function isServerUp() {
  try {
    const port = getPort();
    await fetchWithTimeout(`http://localhost:${port}`, { method: 'GET', mode: 'no-cors' }, 500);
    return true;
  } catch {
    return false;
  }
}

// Wire Open Web App and Stop buttons
const openBtn = document.getElementById('openApp');
const stopBtn = document.getElementById('stopServer');
if (openBtn) {
  openBtn.onclick = () => {
    const port = getPort();
    chrome.tabs.create({ url: `http://localhost:${port}` });
  };
}
if (stopBtn) {
  stopBtn.onclick = async () => {
    const status = document.getElementById('status');
    stopBtn.disabled = true;
    status.innerText = 'Stopping server...';
    try {
      const resp = await sendNativeMessage({ action: 'stop' });
      if (resp && resp.stopped) {
        status.innerText = 'Server stopped.';
      } else {
        status.innerText = 'Could not stop server.';
        console.warn('Stop response:', resp);
      }
    } catch (e) {
      console.error('stop error:', e && (e.message || e.toString()), e);
      status.innerText = 'Failed to contact native host for stop.';
    }
    const up = await isServerUp();
    if (openBtn) openBtn.disabled = !up;
    stopBtn.disabled = !up;
  };
}

// Initialize button enabled states
isServerUp().then(up => {
  if (openBtn) openBtn.disabled = !up;
  if (stopBtn) stopBtn.disabled = !up;
});

// Re-evaluate when port changes
const portInput = document.getElementById('port');
if (portInput) {
  portInput.addEventListener('input', async () => {
    const up = await isServerUp();
    if (openBtn) openBtn.disabled = !up;
    if (stopBtn) stopBtn.disabled = !up;
  });
}

document.getElementById('startServer').onclick = async () => {
  const status = document.getElementById('status');
  const btn = document.getElementById('startServer');
  const portInput = document.getElementById('port');
  const originalLabel = btn.innerText;
  btn.disabled = true;
  btn.innerText = 'Working...';
  status.innerText = 'Checking for running server...';

  // Quick check: if server already up, open it
  const port = getPort();
  try {
    await fetchWithTimeout(`http://localhost:${port}`, { method: 'GET', mode: 'no-cors' }, 700);
    chrome.tabs.create({ url: `http://localhost:${port}` });
  status.innerText = 'Server already running — opened web app.';
  btn.disabled = false;
  btn.innerText = originalLabel;
  return;
  } catch (e) {
    // Not running (or short timeout), proceed to start
  }

  status.innerText = 'Starting server via native host...';
  try {
    if (portInput) portInput.disabled = true;
    const resp = await sendNativeMessage({ action: 'start', port });
    if (!resp || !resp.started) {
      status.innerText = 'Native host responded but did not start the server.';
  console.warn('Native host response:', resp);
  btn.disabled = false;
  btn.innerText = originalLabel;
      if (portInput) portInput.disabled = false;
  return;
    }

    status.innerText = 'Server starting — waiting for it to become available...';
    const up = await waitForServer(`http://localhost:${port}`, 8000, 300);
    if (up) {
      status.innerText = 'Server ready — opening web app.';
      chrome.tabs.create({ url: `http://localhost:${port}` });
      btn.disabled = false;
      btn.innerText = originalLabel;
    } else {
      status.innerText = 'Server did not respond within timeout. Try checking the native host logs.';
      console.warn('Server not responding after native host start.');
      btn.disabled = false;
      btn.innerText = originalLabel;
    }
  } catch (err) {
    status.innerText = 'Failed to contact native host — make sure it is installed and registered.';
    console.error('sendNativeMessage error:', err && (err.message || err.toString()), err);
    btn.disabled = false;
    btn.innerText = originalLabel;
  }
  if (portInput) portInput.disabled = false;
};
