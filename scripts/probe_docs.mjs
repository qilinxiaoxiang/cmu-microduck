// Render every page under docs/ in local headless Chrome at desktop (1280x900) and phone (390x844) width and report
// horizontal overflow, broken images, console errors and inputs under 16 px. No npm dependencies; uses probe/cdp.mjs.
//   node scripts/probe_docs.mjs            -> writes scripts/probe/results.json and prints one line per page and width
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch } from './probe/cdp.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const DOCS = path.join(ROOT, 'docs');
const pages = [
  ...fs.readdirSync(DOCS).filter((f) => f.endsWith('.html')).map((f) => path.join(DOCS, f)),
  ...fs.readdirSync(path.join(DOCS, 'parts-sheets')).filter((f) => f.endsWith('.html')).map((f) => path.join(DOCS, 'parts-sheets', f)),
];
const SIZES = [[1280, 900], [390, 844]];
const CHECK = `(() => {
  const d = document, de = d.documentElement;
  const imgs = [...d.images];
  const broken = imgs.filter((i) => i.getAttribute('src') && i.complete && i.naturalWidth === 0 && !i.src.startsWith('data:image/svg')).map((i) => (i.getAttribute('src') || '').slice(0, 80));
  const small = [...d.querySelectorAll('input,textarea,select,button,[contenteditable]')]
    .filter((e) => e.offsetParent !== null && parseFloat(getComputedStyle(e).fontSize) < 16).length;
  return { scrollWidth: de.scrollWidth, innerWidth: innerWidth, images: imgs.length, broken, smallInputs: small, title: d.title };
})()`;

const profile = path.join(process.env.TMPDIR || '/tmp', 'cmu-microduck-probe-profile');
const b = await launch({ profile });
const results = [];
for (const p of pages) {
  for (const [w, h] of SIZES) {
    b.events.length = 0;
    await b.page('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: w < 768 });
    await b.page('Page.navigate', { url: 'file://' + p });
    await b.waitFor('document.readyState === "complete"', 120000);
    await b.eval('new Promise(r => setTimeout(r, 1500))');
    const r = await b.eval(CHECK);
    const errors = b.events.filter((e) => (e.method === 'Runtime.exceptionThrown') || (e.method === 'Log.entryAdded' && e.params.entry.level === 'error') || (e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error'))
      .map((e) => e.method === 'Runtime.exceptionThrown' ? e.params.exceptionDetails.text + ' ' + (e.params.exceptionDetails.exception?.description || '').slice(0, 120) : e.method === 'Log.entryAdded' ? e.params.entry.text.slice(0, 160) : (e.params.args || []).map((a) => a.value || a.description).join(' ').slice(0, 160));
    const overflow = r.scrollWidth > r.innerWidth + 1;
    const ok = !overflow && r.broken.length === 0 && errors.length === 0 && (w >= 768 || r.smallInputs === 0); // 16 px controls are a phone-width rule
    const row = { page: path.relative(ROOT, p), width: w, ok, overflow, scrollWidth: r.scrollWidth, images: r.images, broken: r.broken, smallInputs: r.smallInputs, errors: errors.slice(0, 5) };
    results.push(row);
    console.log(`${ok ? 'PASS' : 'FAIL'} ${row.page} @${w}: scrollWidth ${r.scrollWidth} images ${r.images} broken ${r.broken.length} smallInputs ${r.smallInputs} errors ${errors.length}${errors.length ? ' :: ' + errors[0] : ''}`);
  }
}
fs.writeFileSync(path.join(HERE, 'probe', 'results.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), results }, null, 1));
await b.close();
console.log(`${results.filter((r) => r.ok).length}/${results.length} pass`);
