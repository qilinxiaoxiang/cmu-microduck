// Minimal Chrome DevTools Protocol driver over --remote-debugging-pipe (no npm deps).
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export async function launch({ chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', profile, headless = true, extraArgs = [] } = {}) {
  fs.mkdirSync(profile, { recursive: true });
  const args = [
    headless ? '--headless=new' : null, '--remote-debugging-pipe', `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars',
    '--allow-file-access-from-files', '--enable-webgl', '--ignore-gpu-blocklist', ...extraArgs, 'about:blank'
  ].filter(Boolean);
  const proc = spawn(chrome, args, { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'] });
  let stderr = '';
  proc.stderr.on('data', (d) => { stderr += d; });
  const out = proc.stdio[3]; const inp = proc.stdio[4];
  let id = 0; const pending = new Map(); const listeners = [];
  let buf = '';
  inp.on('data', (chunk) => {
    buf += chunk.toString('utf8');
    let i;
    while ((i = buf.indexOf('\0')) >= 0) {
      const msg = JSON.parse(buf.slice(0, i)); buf = buf.slice(i + 1);
      if (msg.id && pending.has(msg.id)) { const { res, rej } = pending.get(msg.id); pending.delete(msg.id); msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result); }
      else for (const l of listeners) l(msg);
    }
  });
  const send = (method, params = {}, sessionId) => new Promise((res, rej) => {
    const msg = { id: ++id, method, params }; if (sessionId) msg.sessionId = sessionId;
    pending.set(msg.id, { res, rej }); out.write(JSON.stringify(msg) + '\0');
  });
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const page = (m, p) => send(m, p, sessionId);
  const events = [];
  listeners.push((msg) => { if (msg.sessionId === sessionId) events.push(msg); });
  await page('Page.enable'); await page('Runtime.enable'); await page('Log.enable');
  return {
    proc, send, page, events, sessionId, stderr: () => stderr,
    async eval(expr, { awaitPromise = true } = {}) {
      const r = await page('Runtime.evaluate', { expression: expr, awaitPromise, returnByValue: true });
      if (r.exceptionDetails) throw new Error('eval failed: ' + JSON.stringify(r.exceptionDetails).slice(0, 600));
      return r.result.value;
    },
    async waitFor(expr, timeoutMs = 60000) {
      const t0 = Date.now();
      while (Date.now() - t0 < timeoutMs) {
        try { if (await this.eval(expr)) return true; } catch (e) { /* page loading */ }
        await new Promise((r) => setTimeout(r, 200));
      }
      throw new Error('timeout waiting for ' + expr);
    },
    async screenshot(file) {
      const r = await page('Page.captureScreenshot', { format: 'png' });
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
      return file;
    },
    async click(x, y) {
      for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) {
        await page('Input.dispatchMouseEvent', { type, x, y, button: type === 'mouseMoved' ? 'none' : 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1 });
      }
    },
    async hover(x, y) { await page('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none', buttons: 0 }); },
    async key(key, code, keyCode) {
      await page('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode });
      await page('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode });
    },
    consoleProblems() {
      const out = [];
      for (const e of events) {
        if (e.method === 'Runtime.exceptionThrown') out.push({ type: 'exception', text: JSON.stringify(e.params.exceptionDetails).slice(0, 400) });
        if (e.method === 'Runtime.consoleAPICalled' && (e.params.type === 'error' || e.params.type === 'warning' || e.params.type === 'assert')) out.push({ type: 'console.' + e.params.type, text: e.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 400) });
        if (e.method === 'Log.entryAdded' && (e.params.entry.level === 'error' || e.params.entry.level === 'warning')) out.push({ type: 'log.' + e.params.entry.level, text: (e.params.entry.source + ': ' + e.params.entry.text).slice(0, 400) });
      }
      return out;
    },
    async close() { try { await send('Browser.close'); } catch (e) { /* ignore */ } setTimeout(() => proc.kill('SIGKILL'), 1500); }
  };
}
