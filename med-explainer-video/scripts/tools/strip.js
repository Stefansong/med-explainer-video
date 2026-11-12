// 逐帧条带（QA）：把 [t0, t1] 内每一帧渲染出来，拼成一张图，看一个动作各阶段各占哪几帧（眯眼 / 换脸 / 睁眼 / 过冲、口型切换、转场）。
//   node tools/strip.js <player | page.html[?query]> <t0:t1> <out.png> [--fps=30] [--cols=0] [--w=240] [--crop=x,y,w,h] [--at=x,y,w,h] [--png=dir] [--nolabel] [--W=1080 --H=1920]
//   cols=0 全部一行；w 每格宽（像素，高按裁切比例）；crop 画布像素区域；at 舞台坐标点（x、y 可以是页内 JS 表达式，t 可用），经页面 window.stageToScreen(t, x, y)（若有）映射后以其为中心裁 w×h
//   png=dir 同时把每帧整幅 PNG 存到 dir/f%05d.png（无损，用于 md5 复现性核对 / 交给 ffmpeg）
//   第一个参数写 player（或 src/player.html，不带参数）= 本专题的播放页，分镜 / 版式 / 时间轴 / 画幅自动带上；别的自检页写它的路径和参数。
// 页面协议：window.renderAt(T) 把 T 秒那一帧画到 #cv（或页内第一个 <canvas>）；可选 async window.prepareAt(T)；document.title === 'ready' 表示可渲染。
'use strict';
const puppeteer = require('puppeteer-core'); const path = require('path'); const fs = require('fs');
const C = require('./_common.js'); const CHROME = C.CHROME;
const parse = (argv) => { const pos = [], opt = {}; for (const a of argv) { if (a.startsWith('--')) { const i = a.indexOf('='); if (i < 0) opt[a.slice(2)] = true; else opt[a.slice(2, i)] = a.slice(i + 1); } else pos.push(a); } return { pos, opt }; };
// 逗号分隔、括号内逗号不拆（"DEMO.head(t)[0],DEMO.head(t)[1],500,500"）；能转成数的转成数
const fields = (s) => { const out = []; let d = 0, cur = ''; for (const ch of String(s)) { if (ch === ',' && !d) { out.push(cur); cur = ''; continue; } d += ch === '(' ? 1 : ch === ')' ? -1 : 0; cur += ch; } out.push(cur); return out.map((v) => (v.trim() !== '' && !isNaN(+v) ? +v : v)); };
const isPlayer = (src) => src === 'player' || /(^|[\\/])player\.html$/.test(src);   // 本专题的播放页（不带参数）：参数由 C.playerUrl() 带上
const open = async (src, W, H) => {
  const [file, q] = src.split('?');
  const b = await C.launch({ protocolTimeout: 600000 });
  const p = await b.newPage(); await p.setViewport({ width: W, height: H });
  p.on('pageerror', (e) => console.log('PAGEERR', e.message)); p.on('console', (m) => m.type() === 'error' && console.log('CONSOLE', m.text()));
  await p.goto(isPlayer(src) ? C.playerUrl() : C.fileUrl(file) + (q ? '?' + q : '')); await p.waitForFunction('document.title==="ready"', { timeout: 120000 });
  return { b, p };
};
// 页内：渲染第 i 格并画进条带画布；返回整帧 PNG（opt.png 时）
const cell = async (T, i, opt) => {
  const cv = document.getElementById('cv') || document.querySelector('canvas');
  if (window.prepareAt) await window.prepareAt(T); window.renderAt(T);
  let st = window.__strip; if (!st) { st = window.__strip = document.createElement('canvas'); st.width = opt.cols * opt.w; st.height = opt.rows * opt.h; const g0 = st.getContext('2d'); g0.fillStyle = '#222'; g0.fillRect(0, 0, st.width, st.height); }
  let [sx, sy, sw, sh] = opt.crop || [0, 0, cv.width, cv.height];
  if (opt.at) { const ev = (v) => (typeof v === 'string' ? new Function('t', 'return (' + v + ')')(T) : v); let x = ev(opt.at[0]), y = ev(opt.at[1]); if (window.stageToScreen) [x, y] = window.stageToScreen(T, x, y); sw = opt.at[2]; sh = opt.at[3]; sx = x - sw / 2; sy = y - sh / 2; }
  const g = st.getContext('2d'), X = (i % opt.cols) * opt.w, Y = Math.floor(i / opt.cols) * opt.h;
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high'; g.drawImage(cv, sx, sy, sw, sh, X, Y, opt.w, opt.h);
  g.strokeStyle = '#222'; g.lineWidth = 1; g.strokeRect(X + 0.5, Y + 0.5, opt.w - 1, opt.h - 1);
  if (opt.label) { g.fillStyle = 'rgba(0,0,0,0.6)'; g.fillRect(X, Y, Math.min(opt.w, 96), 20); g.fillStyle = '#fff'; g.font = '12px sans-serif'; g.fillText(opt.label, X + 4, Y + 14); }
  return opt.png ? cv.toDataURL('image/png') : null;
};
const b64 = (url) => Buffer.from(url.slice(url.indexOf(',') + 1), 'base64');
async function strip(src, t0, t1, out, opt = {}) {
  const fps = +(opt.fps || 30), f0 = Math.round(t0 * fps), f1 = Math.round(t1 * fps), n = f1 - f0 + 1;
  const crop = opt.crop ? fields(opt.crop) : null, at = opt.at ? fields(opt.at) : null;
  let tl = null; if (isPlayer(src)) { try { tl = C.loadTL(); } catch (e) { throw new Error('还没有时间轴：先跑 timeline（没有录音时 timeline --estimate）'); } }
  const W = +(opt.W || (tl ? tl.width : 1080)), H = +(opt.H || (tl ? tl.height : 1920));
  const cw = at ? at[2] : crop ? crop[2] : W, ch = at ? at[3] : crop ? crop[3] : H;
  const w = +(opt.w || 240), h = Math.round(w * ch / cw), cols = +(opt.cols || 0) || n, rows = Math.ceil(n / cols);
  const { b, p } = await open(src, W, H);
  if (opt.png) fs.mkdirSync(opt.png, { recursive: true });
  for (let i = 0; i < n; i++) { const f = f0 + i, T = f / fps, label = opt.nolabel ? null : `f${f} ${T.toFixed(3)}s`;
    const url = await p.evaluate(cell, T, i, { cols, rows, w, h, crop, at, label, png: !!opt.png });
    if (url) fs.writeFileSync(path.join(opt.png, `f${String(f).padStart(5, '0')}.png`), b64(url)); }
  const url = await p.evaluate(() => window.__strip.toDataURL('image/png'));
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true }); fs.writeFileSync(out, b64(url));
  await b.close(); return { n, f0, f1, out, w, h, cols, rows };
}
module.exports = { strip, parse, fields, open, b64 };
if (require.main === module) (async () => {
  const { pos, opt } = parse(process.argv.slice(2)); if (pos.length < 3) { console.log('node tools/strip.js <player | page.html> <t0:t1> <out.png> [--fps=30] [--cols=0] [--w=240] [--crop=x,y,w,h] [--at=x,y,w,h] [--png=dir] [--nolabel]'); process.exit(1); }
  const [a, bb] = pos[1].split(':').map(Number); const r = await strip(pos[0], a, bb, pos[2], opt); console.log(`${r.out}  frames ${r.f0}–${r.f1} (${r.n})  ${r.cols}×${r.rows} cells ${r.w}×${r.h}`);
})().catch(C.die);
