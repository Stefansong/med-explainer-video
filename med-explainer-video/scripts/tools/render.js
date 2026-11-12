// 全片渲染：N 个无头页面并行，各渲一段 → libx264 分段 → concat + 混音 → render/{project}_{tag}.mp4（project 取自 storyboard.project；ORIENT=land 时全部在 render/land/，画幅按 timeline 的 width/height）
// node tools/render.js <tag> [workers=8] [t0] [t1]      环境：FPS=60 SUB=4（60 帧 + 4 子帧运动模糊，正式版）；STYLE / ART / STORYBOARD / LAYOUT 见 _common.js
// 叠字层渲染期自检（OV.CHECK）每段收集一次，汇总写 render/{project}_{tag}.overlay.json，并追加到 render/pipeline.log；qa.py 读它。
const puppeteer = require('puppeteer-core'); const path = require('path'); const fs = require('fs'); const { spawn, execFileSync } = require('child_process');
const C = require('./_common.js');
(async () => {
  process.chdir(C.ROOT);
  // 长渲染防睡眠（10-21：凌晨渲染时机器睡眠，8 段全部 'Execution context was destroyed' + protocolTimeout）：caffeinate 跟随本进程，退出即解除
  if (process.platform === 'darwin') { try { spawn('caffeinate', ['-dimsu', '-w', String(process.pid)], { stdio: 'ignore', detached: true }).unref(); } catch (_) {} }
  const tag = process.argv[2] || 'v1', NW = +(process.argv[3] || 8);
  const SB = C.loadSB(), TL = C.loadTL(); const fps = +(process.env.FPS || TL.fps), SUB = +(process.env.SUB || 1), W = TL.width, H = TL.height, project = SB.project;
  const t0 = +(process.argv[4] || 0), t1 = +(process.argv[5] || TL.duration);
  const F0 = Math.round(t0 * fps), F1 = Math.floor(t1 * fps); const per = Math.ceil((F1 - F0) / NW);
  // 每段独立的浏览器实例：一个浏览器卡死只影响这一段，重试时换新浏览器
  const launch = () => C.launch({ protocolTimeout: 600000 });
  const RD = C.renderRel(); fs.mkdirSync(`${RD}/seg`, { recursive: true });
  const started = Date.now(); let done = 0, errs = 0; const checks = [], amSeg = [], fontsW = [], refsW = [];
  const W2B = {}, FF = {}, prog = [], ERRMSG = {}; let lastPrint = 0;
  const job = async (w, attempt = 0) => {
    const a = F0 + w * per, e = Math.min(F1, a + per); const out = `${RD}/seg/${tag}_${String(w).padStart(2, '0')}.mp4`;
    if (!attempt) await new Promise((r) => setTimeout(r, w * 4000));   // 各页错开 4 s 启动，避免同时加载拖慢
    const b = await launch(); W2B[w] = b; const p = await b.newPage(); await p.setViewport({ width: W, height: H });
    p.on('pageerror', (er) => { errs++; ERRMSG[er.message] = (ERRMSG[er.message] || 0) + 1; console.log('PAGEERR', er.message); }); p.on('console', (m) => { if (m.type() === 'error') { errs++; ERRMSG[m.text()] = (ERRMSG[m.text()] || 0) + 1; if (errs < 20) console.log('CONSOLE', m.text()); } });
    await p.goto(C.playerUrl({ strict: '1' })); await p.waitForFunction('document.title==="ready"', { timeout: 600000 });   // 正式渲染：素材缺失直接报错，不静默回退
    await p.evaluate(() => OV.resetCheck());
    // JPEG 帧是全范围 BT.601：编码时转成标准电视范围 BT.709 并打标签，避免播放器偏色
    prog[w] = 0;
    const ff = (FF[w] = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-', '-vf', 'scale=in_range=full:out_range=limited:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', '-r', String(fps), out]));
    for (let f = a; f < e; f++) {
      const rr = await p.evaluate(async (T, o) => { await prepareAt(T, o.shutter / o.fps); renderFrame(T, o); const m = OV.lastAiMark; return { url: document.getElementById('cv').toDataURL('image/jpeg', 0.93), am: m && m.alpha > 0 ? m : null }; }, f / fps, { sub: SUB, shutter: 0.5, fps });
      if (rr.am) { const M = (amSeg[w] = amSeg[w] || { first: null, lastFull: null, full: 0, any: 0, size: rr.am.size, ink: rr.am.ink, need: rr.am.need, x: rr.am.x, y: rr.am.y, w: rr.am.w, h: rr.am.h }); M.any++; if (rr.am.shown) { M.full++; if (M.first == null) M.first = f; M.lastFull = f; } }
      const buf = Buffer.from(rr.url.slice(rr.url.indexOf(',') + 1), 'base64');
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
      prog[w] = f - a + 1; done = prog.reduce((x, v) => x + (v || 0), 0);
      if (done - lastPrint >= 900) { lastPrint = done; console.log(`${done}/${F1 - F0} frames, ${((Date.now() - started) / 1000).toFixed(0)} s`); }
    }
    ff.stdin.end(); await new Promise((r) => ff.on('close', r));
    const eng = await p.evaluate(() => (typeof ENGINE !== 'undefined' && ENGINE.ERRS) || {}); for (const [m, n] of Object.entries(eng)) { ERRMSG[m] = (ERRMSG[m] || 0) + n; errs += n - 1; }   // 引擎同一条错误只打印一次：按实际帧数补计
    checks[w] = await p.evaluate(() => OV.CHECK); fontsW[w] = await p.evaluate(() => window.FONTS_STATUS || null); refsW[w] = await p.evaluate(() => OV.refInfo || null); await b.close(); return out;
  };
  // 单段失败（页面崩溃/超时）整段重渲，最多 2 次；不让一个页面拖垮整次渲染
  const safe = async (w) => { for (let k = 0; ; k++) { try { return await job(w, k); } catch (er) { console.log(`segment ${w} failed (${er.message.split('\n')[0]}), attempt ${k + 1}`); try { W2B[w].process()?.kill('SIGKILL'); } catch (_) {} try { if (FF[w]) { FF[w].stdin.destroy(); FF[w].kill('SIGKILL'); } } catch (_) {} if (k >= 2) throw er; } } };
  const segs = await Promise.all([...Array(NW).keys()].map(safe));
  fs.writeFileSync(`${RD}/seg/list.txt`, segs.map((s) => `file '${path.resolve(s).split(path.sep).join('/')}'`).join('\n'));
  const out = `${RD}/${project}_${tag}.mp4`;
  const mix = fs.existsSync(`${RD}/mix.wav`) ? `${RD}/mix.wav` : null;
  if (!mix) console.log(`!! ${RD}/mix.wav 不存在：用静音轨合成（预演/演示可以，正式版必须先跑 mix.py）`);
  const audioIn = mix ? ['-ss', String(t0), '-i', mix] : ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'];
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', `${RD}/seg/list.txt`, ...audioIn, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', ...((C.ORIENT === 'land' && (SB.cover || {}).file_comment_land) || (SB.cover || {}).file_comment ? ['-metadata', `comment=${(C.ORIENT === 'land' && SB.cover.file_comment_land) || SB.cover.file_comment}`] : []), out]);   // 成片元数据写 AI 生成内容说明（cover.file_comment；10-24 竖屏也写，不只投稿版）
  // 叠字层自检汇总（各段计数相加，样本取前 12 条）
  // counts：帧数；items：按 (scene, text) 去重的卡/字幕块（frames 累加、min_size 取最小、first_T 取最早）；unique：每类去重后的张数
  const sum = { counts: {}, items: {}, unique: {}, frames: F1 - F0, fps, sub: SUB, orient: C.ORIENT, width: W, height: H, page_errors: errs, page_error_samples: Object.entries(ERRMSG).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([m, n]) => `${m}（${n} 次）`), silent_audio: !mix, fonts: fontsW.find(Boolean) || null, refs: refsW.find(Boolean) || null };
  for (const ch of checks) { if (!ch) continue; for (const [k, v] of Object.entries(ch.counts)) sum.counts[k] = (sum.counts[k] || 0) + v;
    for (const [k, items] of Object.entries(ch.items || {})) { const I = (sum.items[k] = sum.items[k] || {}); for (const [key, it] of Object.entries(items)) { const o = I[key]; if (!o) I[key] = { ...it }; else { o.frames += it.frames; if (it.min_size != null) o.min_size = Math.min(o.min_size ?? it.min_size, it.min_size); o.first_T = Math.min(o.first_T, it.first_T); } } } }
  for (const [k, I] of Object.entries(sum.items)) sum.unique[k] = Object.keys(I).length;
  // AI 标识（GB 45438）：首帧、最后一帧完整显示、持续秒数、字号、实测字高、要求字高
  const segs2 = amSeg.filter(Boolean);
  if (segs2.length) { const firsts = segs2.map((m) => m.first).filter((v) => v != null), lasts = segs2.map((m) => m.lastFull).filter((v) => v != null), full = segs2.reduce((s, m) => s + m.full, 0);
    sum.ai_mark = { text: null, size: segs2[0].size, ink: segs2[0].ink, need: segs2[0].need, x: segs2[0].x, y: segs2[0].y, w: segs2[0].w, h: segs2[0].h, first_frame: firsts.length ? Math.min(...firsts) : null, last_full_frame: lasts.length ? Math.max(...lasts) : null, full_frames: full, full_seconds: Math.round(full / fps * 1000) / 1000, fps }; }
  else sum.ai_mark = null;
  fs.writeFileSync(`${RD}/${project}_${tag}.overlay.json`, JSON.stringify(sum, null, 1));
  const line = `render ${out} ${((Date.now() - started) / 1000).toFixed(0)}s frames=${F1 - F0} fps=${fps} sub=${SUB} page_errors=${errs} overlay_check(unique)=${JSON.stringify(sum.unique)} frames=${JSON.stringify(sum.counts)}${mix ? '' : ' audio=silent'}`;
  C.log(line); console.log('→', line);
  if (Object.keys(sum.counts).length) console.log('!! 叠字层自检有记录（不中断渲染，qa.py 会按 layout.qa_gate 判定）：去重', JSON.stringify(sum.unique), '帧数', JSON.stringify(sum.counts));
})().then(() => setTimeout(() => process.exit(0), 500), (e) => { console.error('render.js 失败：', (e && e.message) || e); setTimeout(() => process.exit(1), 500); });
