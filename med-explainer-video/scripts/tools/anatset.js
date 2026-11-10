// 解剖/关键画面抽帧清单：由 storyboard 每场的 check_frames 声明（单一真源，不在代码里写时刻）。输出 "sXX+T"，喂给 frames.js（同 checkset.js）。
//   scene.check_frames 的每一项：
//     4.5                 场内秒
//     "cue:zoom+0.5"      某个 cue 之后 dt 秒
//     "label:2+0.8"       第 k 张字卡出现后 dt 秒
//     "line:1@夹住+1.2"   第 i 句台词里“夹住”一词开口后 dt 秒
//     "end-1.0"           场末前 1 秒
//   node tools/anatset.js > render/anat/list.txt && node tools/frames.js render/anat --list render/anat/list.txt
// 来源：hematuria/tools/anatset.js（手写的 lab/ln/at 时刻表），改为从 storyboard 读声明。
const C = require('./_common.js');
const SB = C.loadSB(), TL = C.loadTL(); const S = (id) => TL.scenes.find((s) => s.id === id);
const out = [];
for (const sb of SB.scenes) {
  const sc = S(sb.id); if (!sc) continue;
  for (const spec of sb.check_frames || []) {
    let t = null, m;
    if (typeof spec === 'number') t = spec;
    else if ((m = spec.match(/^cue:(\w+)([+-][\d.]+)?$/))) t = (sc.cues[m[1]] ?? NaN) + (+m[2] || 0);
    else if ((m = spec.match(/^label:(\d+)([+-][\d.]+)?$/))) t = (sc.labels[+m[1]] ? sc.labels[+m[1]].t : NaN) + (+m[2] || 0);
    else if ((m = spec.match(/^line:(\d+)@(.+?)([+-][\d.]+)?$/))) { const l = sc.lines[+m[1]]; const k = l ? l.text.indexOf(m[2]) : -1; t = l && k >= 0 ? l.start + l.ct[k] + (+m[3] || 0) : NaN; }
    else if ((m = spec.match(/^end([+-][\d.]+)?$/))) t = sc.end - sc.start + (+m[1] || 0);
    if (t == null || isNaN(t)) { console.error(`!! ${sb.id} check_frames 解析失败：${spec}`); continue; }
    out.push(`${sb.id}+${Math.max(0, t).toFixed(2)}`);
  }
}
console.log(out.join('\n'));
