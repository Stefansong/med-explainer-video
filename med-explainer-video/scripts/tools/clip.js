// 出片：node tools/clip.js <page.html[?query]> <out.mp4> [--fps=30] [--t0=0] [--t1=<页面 window.DUR>] [--crf=18] [--W=1080 --H=1920] [--audio=mix.wav]
// 逐帧 renderAt(T) → 画布 PNG（无损）→ ffmpeg image2pipe → libx264 yuv420p，RGB→BT.709 电视范围并打标签；x264 单线程，两次编码逐位相同。
// 与 bph/tools/render.js 同一思路（那边多页并行、分段 concat、混音），这里是单页单段的模板版，6–60 s 的演示和单场景预演够用。
'use strict';
const { spawn } = require('child_process'); const fs = require('fs'); const path = require('path');
const { parse, open, b64 } = require('./strip.js');
(async () => {
  const { pos, opt } = parse(process.argv.slice(2)); if (pos.length < 2) { console.log('node tools/clip.js <page.html> <out.mp4> [--fps=30] [--t0=0] [--t1=DUR] [--crf=18] [--audio=wav]'); process.exit(1); }
  const fps = +(opt.fps || 30), W = +(opt.W || 1080), H = +(opt.H || 1920), out = pos[1]; fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  const { b, p } = await open(pos[0], W, H);
  const t0 = +(opt.t0 || 0), t1 = opt.t1 != null ? +opt.t1 : await p.evaluate(() => window.DUR);
  if (!(t1 > t0)) throw new Error('t1 unknown: pass --t1 or expose window.DUR in the page');
  const F0 = Math.round(t0 * fps), F1 = Math.round(t1 * fps);
  const args = ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-'];
  if (opt.audio) args.push('-ss', String(t0), '-i', opt.audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '192k', '-shortest');
  args.push('-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', String(opt.crf || 18), '-threads', '1', '-x264-params', 'threads=1:colorprim=bt709:transfer=bt709:colormatrix=bt709', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', '-r', String(fps), '-movflags', '+faststart', out);
  const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'inherit', 'inherit'] }); const started = Date.now();
  for (let f = F0; f < F1; f++) {
    const url = await p.evaluate(async (T) => { if (window.prepareAt) await window.prepareAt(T); window.renderAt(T); return (document.getElementById('cv') || document.querySelector('canvas')).toDataURL('image/png'); }, f / fps);
    if (!ff.stdin.write(b64(url))) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end(); const code = await new Promise((r) => ff.on('close', r)); await b.close();
  if (code) throw new Error('ffmpeg exited ' + code);
  console.log(`→ ${out}  ${F1 - F0} frames @ ${fps} fps  ${((Date.now() - started) / 1000).toFixed(1)} s`);
})();
