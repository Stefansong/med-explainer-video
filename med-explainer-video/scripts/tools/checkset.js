// 抽帧时刻清单（自动）：按 timeline 给每句台词 35% / 85% 两个点、每张字卡出现后 0.8 s、每个 cue 后 0.5 s、每场末尾（转场前）、无台词场 +2.5 s。
//   node tools/checkset.js [--lines] [--labels] [--cues] [--ends]   不带参数 = 全部；输出每行一个 "sXX+T"，喂给 frames.js：
//   node tools/checkset.js > render/check/list.txt && node tools/frames.js render/check --list render/check/list.txt && python3 tools/sheet.py render/check render/check_sheet.png
// 来源：hematuria/tools/checkset.js（台词 35%/85% + 场末），加上 bph 的“每个新素材出现时刻都要从成片抽帧核”（设计方案 v1 第八节）。
const C = require('./_common.js');
const TL = C.loadTL(); const a = process.argv.slice(2); const all = !a.length; const want = (k) => all || a.includes('--' + k);
const out = [];
for (const s of TL.scenes) {
  if (s.id === 's00') { out.push(`${s.id}+0.5`); continue; }
  if (!s.lines.length) { out.push(`${s.id}+2.5`); continue; }
  if (want('lines')) for (const l of s.lines) { out.push(`${s.id}+${(l.start + (l.end - l.start) * 0.35).toFixed(2)}`); out.push(`${s.id}+${(l.start + (l.end - l.start) * 0.85).toFixed(2)}`); }
  if (want('labels')) for (const lb of s.labels || []) out.push(`${s.id}+${(lb.t + 0.8).toFixed(2)}`);
  if (want('cues')) for (const t of Object.values(s.cues || {})) out.push(`${s.id}+${(t + 0.5).toFixed(2)}`);
  if (want('ends')) out.push(`${s.id}+${Math.max(0, s.end - s.start - 0.6).toFixed(2)}`);
}
// 去重 + 按场内时间排序（同一场内）
const seen = new Set(); const uniq = out.filter((x) => (seen.has(x) ? false : seen.add(x)));
uniq.sort((p, q) => { const [a1, t1] = p.split('+'), [a2, t2] = q.split('+'); return a1 === a2 ? +t1 - +t2 : a1 < a2 ? -1 : 1; });
console.log(uniq.join('\n'));
