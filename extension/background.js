// Keep background service worker minimal - we rely on popup.js + native messaging
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.action === 'ping') sendResponse({ pong: true });
});
