// 场景代码检查（不渲染，1 秒内出结果）：把 src/scenes.js、src/anat.js 里写错的地方用人话指出来。pipeline 的 check / frames / animatic / render 会先跑它。
//   node tools/lint_scenes.js          在专题目录下跑（或设 KEPU_PROJECT）；有错误退出码 1
// 错误：语法错误（给出行号）；用了 Math.random / Date（每帧必须只由时间决定）；调用了不存在的 SH.* / PR.* / L.* / AN.* 函数；
//       用了 storyboard.assets 里没登记的图；A.cue('名字') 在那一场没声明；storyboard 里的场景没有对应的 SC.<id>；画面里写字（fillText）。
// 提醒：声明了 cue 但场景代码没用；全片只用了一张立绘；s01 的主体要等到某个时刻才出现。
'use strict';
const fs = require('fs'); const path = require('path'); const vm = require('vm');
const C = require('./_common.js');
const E = [], W = [];
const SRC = path.join(C.ROOT, 'src');
const read = (f) => (fs.existsSync(path.join(SRC, f)) ? fs.readFileSync(path.join(SRC, f), 'utf8') : null);
const lineOf = (code, idx) => code.slice(0, idx).split('\n').length;
const strip = (code) => code.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' ')).replace(/(^|[^:'"`\\])\/\/[^\n]*/g, (m, p) => p + ' '.repeat(m.length - p.length));   // 去注释，保留行号
// 编辑距离：给“你是不是想写 …”用
const dist = (a, b) => { const d = Array.from({ length: a.length + 1 }, (_, i) => [i]); for (let j = 1; j <= b.length; j++) d[0][j] = j; for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); return d[a.length][b.length]; };
const near = (name, pool, n = 3) => [...pool].map((p) => [dist(name.toLowerCase(), p.toLowerCase()), p]).sort((a, b) => a[0] - b[0]).filter(([d]) => d <= Math.max(2, name.length / 2)).slice(0, n).map(([, p]) => p);

let SB;
try { SB = C.loadSB(); } catch (e) { console.log('✗ 读不了分镜：' + e.message.split('\n')[0] + '（先跑 pipeline.py check 看分镜哪里错了）'); process.exit(1); }

// ---------- 1. 语法 ----------
const files = { 'scenes.js': read('scenes.js'), 'anat.js': read('anat.js') };
if (files['scenes.js'] == null) { console.log('✗ 没有 src/scenes.js'); process.exit(1); }
for (const [f, code] of Object.entries(files)) {
  if (code == null) continue;
  try { new vm.Script(code, { filename: f }); }
  catch (e) { const m = /:(\d+)/.exec((e.stack || '').split('\n')[0]) || []; const ln = +m[1] || 0; const src = code.split('\n');
    E.push(`src/${f} 第 ${ln} 行附近有语法错误：${e.message}\n    第 ${ln} 行：${(src[ln - 1] || '').trim().slice(0, 140)}\n    常见原因：括号 / 花括号没配对、少了逗号或引号、箭头函数 => 写错。错误也可能在上一行。`); }
}
if (E.length) { for (const e of E) console.log('✗ ' + e); console.log(`场景代码检查：${E.length} 个错误（先改语法错误，其余检查暂时跳过）`); process.exit(1); }

// ---------- 2. 可用的函数名 ----------
const defs = (code, ns) => new Set([...(code || '').matchAll(new RegExp(`\\b${ns}\\.([A-Za-z_]\\w*)\\s*=[^=]`, 'g'))].map((m) => m[1]));
const shots = read('shots.js') || '', lib = read('lib.js') || '', props = read('props.js') || '';
const NS = { SH: defs(shots, 'SH'), L: defs(lib, 'L'), PR: defs(props, 'PR'), AN: defs(files['anat.js'], 'AN') };
for (const m of shots.matchAll(/Object\.assign\(SH,\s*\{([^}]*)\}/g)) for (const k of m[1].split(',')) NS.SH.add(k.split(':')[0].trim());
for (const k of ['P', 'EXT', 'ART', 'HIDE', 'PIXBG', 'NOFOOT']) NS.L.add(k);
const code = strip(files['scenes.js']); const raw = files['scenes.js'];

// 解构出来的名字：const { a, b: c } = SH;
for (const m of code.matchAll(/const\s*\{([^}]*)\}\s*=\s*(SH|L|PR|AN)\b/g)) {
  for (const part of m[1].split(',')) { const k = part.split(':')[0].trim(); if (!k) continue;
    if (!NS[m[2]].has(k)) E.push(`src/scenes.js 第 ${lineOf(code, m.index)} 行：从 ${m[2]} 里取了不存在的 "${k}"` + (near(k, NS[m[2]]).length ? `（相近的有：${near(k, NS[m[2]]).join('、')}）` : '') + `。可用的函数见 references/api.md`); }
}
for (const m of code.matchAll(/\b(SH|L|PR|AN)\.([A-Za-z_]\w*)/g)) {
  const [, ns, k] = m; if (NS[ns].has(k)) continue;
  if (code.slice(m.index + m[0].length).match(/^\s*=[^=]/)) continue;   // 自己在场景文件里给它赋值
  const sug = near(k, NS[ns]);
  E.push(`src/scenes.js 第 ${lineOf(code, m.index)} 行：${ns}.${k} 不存在` + (sug.length ? `（相近的有：${sug.map((s) => ns + '.' + s).join('、')}）` : '') + (ns === 'AN' ? '。解剖函数要先在 src/anat.js 里写' : '。可用的函数见 references/api.md'));
}

// ---------- 3. 每帧只由时间决定、画面不写字 ----------
for (const [re, why] of [[/\bMath\.random\s*\(/g, '用了 Math.random()：每次渲染结果会不一样。换成 const R = L.rand(种子数); R()'], [/\bDate\.now\s*\(|\bnew\s+Date\b|\bperformance\.now\s*\(/g, '用了系统时间：画面必须只由 A.t 决定，把它换成 A.t'],
  [/\.(fillText|strokeText)\s*\(/g, '在画面里写了字（fillText）：画面里不许有文字、数字、字母，文字都放 storyboard 的字卡（labels）里'], [/\bsetTimeout\s*\(|\bsetInterval\s*\(|\brequestAnimationFrame\s*\(/g, '用了定时器：场景函数每帧被调用一次，按 A.t 直接画当前这一帧，不要自己计时']]) {
  for (const m of code.matchAll(re)) E.push(`src/scenes.js 第 ${lineOf(code, m.index)} 行：${why}`);
}

// ---------- 4. 逐场：场景函数、cue、素材 ----------
const marks = [...code.matchAll(/\bSC\.([A-Za-z_]\w*)\s*=/g)].map((m) => ({ id: m[1], at: m.index }));
const body = {}; marks.forEach((m, i) => { body[m.id] = { text: code.slice(m.at, i + 1 < marks.length ? marks[i + 1].at : code.length), at: m.at }; });
const assets = new Set(Object.keys(SB.assets || {}).filter((k) => !k.startsWith('_')));
const sprites = new Map();
for (const sc of SB.scenes || []) {
  const b = body[sc.id];
  if (!b) { E.push(`分镜里有场景 ${sc.id}，但 src/scenes.js 里没有 SC.${sc.id}：加上 SC.${sc.id} = (c, A) => { … }`); continue; }
  const cues = new Set(Object.keys(sc.cues || {})); const used = new Set();
  for (const m of b.text.matchAll(/\bA\.cue\(\s*(['"`])([^'"`]+)\1\s*\)/g)) { used.add(m[2]);
    if (!cues.has(m[2])) E.push(`src/scenes.js 第 ${lineOf(code, b.at + m.index)} 行（${sc.id}）：A.cue('${m[2]}') 在分镜的 ${sc.id} 里没有声明` + (cues.size ? `（这场声明了：${[...cues].join('、')}）` : '（这场一个 cue 都没声明）') + `。没声明的 cue 永远不会发生，那一步画面不会出现。在 storyboard 的 scenes[${sc.id}].cues 里加上 "${m[2]}": [第几句, "那句里的词"]`); }
  for (const k of cues) if (!used.has(k) && !new RegExp(`['"\`]${k}['"\`]`).test(b.text)) W.push(`${sc.id} 声明了 cue "${k}"，但场景代码没用它（A.cue('${k}')）：那句话讲到的内容，画面上没有对应的变化`);
  const nlab = (sc.labels || []).length;
  for (const m of b.text.matchAll(/\bA\.lab\(\s*(\d+)\s*\)/g)) if (+m[1] >= nlab) E.push(`src/scenes.js 第 ${lineOf(code, b.at + m.index)} 行（${sc.id}）：A.lab(${m[1]})，但这场只有 ${nlab} 张字卡（从 0 数）`);
  for (const m of b.text.matchAll(/\bA\.ln\(\s*(\d+)\s*\)/g)) if (+m[1] >= (sc.lines || []).length) E.push(`src/scenes.js 第 ${lineOf(code, b.at + m.index)} 行（${sc.id}）：A.ln(${m[1]})，但这场只有 ${(sc.lines || []).length} 句台词（从 0 数）`);
}
for (const id of Object.keys(body)) if (!/^(s99|outro|cover|cover_land|cover_art|refs_bg)$/.test(id) && !(SB.scenes || []).some((s) => s.id === id)) W.push(`src/scenes.js 里有 SC.${id}，但分镜里没有场景 ${id}（不会被用到）`);
// 素材 id：SP / IC / full / xf / A.img 的字符串参数
const useAsset = (id, idx, how) => { if (!assets.has(id)) { const sug = near(id, assets); E.push(`src/scenes.js 第 ${lineOf(code, idx)} 行：${how} 用了图 '${id}'，但 storyboard.assets 里没登记` + (sug.length ? `（相近的有：${sug.join('、')}）` : assets.size ? `（已登记：${[...assets].join('、')}）` : '（assets 里还没有任何图）') + `。没登记的图不会画出来。先出图，再用 tools/cutout.py 抠底登记；或改成已登记的 id`); } };
for (const m of code.matchAll(/\b(?:SH\.)?(SP|IC|full|spX|spW)\s*\(\s*c?\s*,?\s*A\s*,\s*(['"`])([^'"`]+)\2/g)) { useAsset(m[3], m.index, m[1]); if (m[1] === 'SP') sprites.set(m[3], (sprites.get(m[3]) || 0) + 1); }
for (const m of code.matchAll(/\b(?:SH\.)?xf\s*\(\s*c\s*,\s*A\s*,\s*(['"`])([^'"`]+)\1\s*,\s*(['"`])([^'"`]+)\3/g)) { useAsset(m[2], m.index, 'xf'); useAsset(m[4], m.index, 'xf'); sprites.set(m[2], 1); sprites.set(m[4], 1); }
for (const m of code.matchAll(/\bA\.img\(\s*(['"`])([^'"`]+)\1\s*\)/g)) useAsset(m[2], m.index, 'A.img');
for (const k of assets) if (!new RegExp(`['"\`]${k}['"\`]`).test(code)) W.push(`图 ${k} 登记了但场景代码没用到`);
const nsc = (SB.scenes || []).length;
if (sprites.size === 1 && nsc >= 3) W.push(`全片 ${nsc} 场只用了一张人物立绘（${[...sprites.keys()][0]}）：人物从头到尾一个姿势，画面没有在演示内容。每场按台词内容出不同动作的立绘（做示范、指给你看、皱眉、点头…），或用 SH.steps / SH.spot / SH.arrow 把要点画出来`);
// s01 开场是不是空的：第一场里所有东西都挂在 cue / 字卡时刻上
const b1 = body[(SB.scenes[0] || {}).id];
if (b1 && !/\b(SP|IC|full)\s*\([^;]*pop:\s*\(?\s*t\s*\/|(\bfull|\bSP|\bIC|PR\.\w+|AN\.\w+)\s*\((?![^;]*pop:)[^;]*\)\s*;/.test(b1.text)) W.push(`${SB.scenes[0].id} 开场：所有主体都要等到某个 cue 才出现，开头几秒可能是空画面。开场第一秒就要有主体（立绘 / 满幅图 / 道具用 pop: t / 0.45 从 0 秒弹入）`);

const uniq = (a) => [...new Set(a)];
for (const e of uniq(E)) console.log('✗ ' + e);
for (const w of uniq(W)) console.log('! ' + w);
console.log(`场景代码检查：${uniq(E).length} 个错误，${uniq(W).length} 条提醒` + (E.length ? '' : '（没有错误）'));
process.exit(E.length ? 1 : 0);
