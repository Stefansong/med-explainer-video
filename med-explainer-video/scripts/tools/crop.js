// 跟踪裁切条带（QA）：按舞台坐标点逐帧裁切，跟着镜头漂移 / 角色移动看脸、手、接触点的细节。
//   node tools/crop.js <player | page.html[?query]> <t0:t1> <out.png> --at=x,y,w,h [--fps=30] [--cols=0] [--w=300] [--png=dir] [--nolabel]
//   x、y 为舞台坐标，或页内 JS 表达式（t 可用），如 --at="DEMO.head(t)[0],DEMO.head(t)[1],520,520"；每帧经页面的 window.stageToScreen(t, x, y)（没有则视为画布坐标）映射后以其为中心裁 w×h
// 与 strip.js 共用页面协议（renderAt / prepareAt / title==='ready'）。
'use strict';
const { strip, parse } = require('./strip.js');
(async () => {
  const { pos, opt } = parse(process.argv.slice(2));
  if (pos.length < 3 || !opt.at) { console.log('node tools/crop.js <player | page.html> <t0:t1> <out.png> --at=x,y,w,h [--fps=30] [--cols=0] [--w=300] [--png=dir] [--nolabel]'); process.exit(1); }
  const [a, b] = pos[1].split(':').map(Number); const r = await strip(pos[0], a, b, pos[2], { w: 300, ...opt });
  console.log(`${r.out}  frames ${r.f0}–${r.f1} (${r.n})  ${r.cols}×${r.rows} cells ${r.w}×${r.h}  tracking ${opt.at}`);
})().catch(require('./_common.js').die);
