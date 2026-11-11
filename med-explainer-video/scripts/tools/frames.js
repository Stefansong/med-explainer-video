// 抽帧：node tools/frames.js <out_dir> t1 t2 ...   （t 为绝对秒；也可 s03+4.5 表示场内时间，s03@slide+0.5 表示 cue 后）
//       node tools/frames.js <out_dir> --list <file>   从文件读时刻列表（每行一个；checkset.js / anatset.js 的输出可直接重定向进来）
// 也输出 <out_dir>/overlay_check.json：这些帧上的叠字层自检计数（逐场动画时先看这个，别等成片）
const puppeteer = require('puppeteer-core'); const path = require('path'); const fs = require('fs');
const C = require('./_common.js');
(async () => {
  process.chdir(C.ROOT);
  const argv = process.argv.slice(2); const out = argv[0]; let ts = argv.slice(1);
  const li = ts.indexOf('--list'); if (li >= 0) { ts = ts.slice(0, li).concat(fs.readFileSync(ts[li + 1], 'utf8').split('\n').map((s) => s.trim()).filter(Boolean)); }
  if (!out || !ts.length) { console.log('node tools/frames.js <out_dir> t1 t2 ... | --list file'); process.exit(1); }
  fs.mkdirSync(out, { recursive: true });
  const b = await puppeteer.launch({ executablePath: C.CHROME, args: ['--allow-file-access-from-files'] });
  const TL = C.loadTL(); const p = await b.newPage(); await p.setViewport({ width: TL.width, height: TL.height });
  const perr = []; p.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) perr.push(m.text()); }); p.on('pageerror', (e) => perr.push('页面脚本出错：' + e.message));
  await p.goto(C.playerUrl()); await p.waitForFunction('document.title==="ready"', { timeout: 120000 });
  await p.evaluate(() => OV.resetCheck());
  const marks = [];
  for (const s of ts) {
    const T = C.parseT(TL, s);
    const am = await p.evaluate(async (T) => { await prepareAt(T); renderAt(T); return OV.lastAiMark; }, T); const el = await p.$('canvas'); await el.screenshot({ path: `${out}/${s.replace(/[+@]/g, '_')}.png` });
    if (am) marks.push({ at: s, ...am });
  }
  const ck = await p.evaluate(() => OV.CHECK); ck.fonts = await p.evaluate(() => window.FONTS_STATUS || null); ck.refs = await p.evaluate(() => OV.refInfo || null); ck.ai_mark = { per_frame: marks, need: marks[0] && marks[0].need, size: marks[0] && marks[0].size, ink: marks[0] && marks[0].ink, shown_frames: marks.filter((m) => m.shown).map((m) => m.at) };
  fs.writeFileSync(path.join(out, 'overlay_check.json'), JSON.stringify(ck, null, 1));
  ck.unique = Object.fromEntries(Object.entries(ck.items || {}).map(([k, v]) => [k, Object.keys(v).length]));
  if (Object.keys(ck.counts).length) console.log('!! 叠字层自检（去重张数）：', JSON.stringify(ck.unique), '帧数', JSON.stringify(ck.counts));
  console.log(`→ ${out}: ${ts.length} frames`);
  const eng = await p.evaluate(() => (typeof ENGINE !== 'undefined' && ENGINE.ERRS) || {});
  await b.close();
  const all = [...new Set(Object.keys(eng).concat(perr))];
  if (all.length) { console.log(`\n✗ 画面代码有 ${all.length} 种错误（出错的场景画面是空的，左上角有品红色小方块）：`); for (const m of all.slice(0, 12)) console.log('  - ' + m); process.exit(1); }
})();
