'use strict';
// 镜头函数库 SH.*（2026-10-31 从 foam_3d / nocturia_3d / psa_3d / aur_3d / torsion_3d 的 scenes.js 抽出：这些函数在 4–5 集里各写了一遍、大多逐字相同）。
// 专题 scenes.js 开头解构使用：const { W, H, P, bg, seg, segX, lerpT, pop, fin, ring, inRing, fillAll, band, floor, home, clinic, IC, SP, spX, xf, drop, card } = SH;
// 约定同各集：竖屏 1080×1920，按主舞台设计 y 236–1236；画面零文字（叹号 / 叉 / 对勾都是图形）；颜色只取 L.P（storyboard.style.palette）。
// 人物只用 3D：立绘 SP（L.sprite3d）、道具 IC（L.icon3d）；解剖剖面走 AN.*（代码手绘），这里不画人物、不画解剖。
const SH = {};
(() => {
  const W = 1080, H = 1920;
  // 立绘 / 图标 / 卡片 / 圆窗右缘：设计 x ≤ 885（engine 画面呼吸最坏 1.02 倍 + 6 px 后屏幕 ≤ layout.safe.right_x 900）
  const RX = 885;
  const P = () => L.P;
  Object.assign(SH, { W, H, RX, TAU: Math.PI * 2, P });

  // ---------- 时间 ----------
  SH.lerpT = (t, a, b) => L.easeInOut(L.seg(t, a, b));
  SH.pop = (t, a, d = 0.45) => L.pop(t, a, d);
  SH.fin = (t, a, d = 0.45) => L.fin(t, a, d);
  // 场内镜头：a 起用 d 秒淡入、盖在上一个镜头上；上一个镜头不淡出，保持不透明画到 b + d（被新镜头完全盖住）——每个镜头自己铺满底色。
  // 不要两边同时淡（换镜暗谷：前后两镜都半透明会透出底色发灰，QA stage_dips 判失败）
  SH.seg = (c, t, a, b, fn, d = 0.3) => { if (t >= b + d) return; const al = L.fin(t, a, d); if (al <= 0.001) return; c.save(); c.globalAlpha *= al; fn(al); c.restore(); };
  // 同一底色上的内容叠化（旧内容淡出、新内容淡入；不铺底色的段落用）
  SH.segX = (c, t, a, b, fn, d = 0.35) => { const al = Math.min(L.fin(t, a, d), 1 - L.seg(t, b - d, b)); if (al <= 0.001) return; c.save(); c.globalAlpha *= al; fn(al); c.restore(); };
  // 台词里某个词开口的场内时刻（与 timeline.py 的 cue 同一算法：line.start + ct[字下标]）；找不到返回 1e9
  SH.at = (A, li, sub) => { const l = A.lines[li]; const k = l && l.text ? l.text.indexOf(sub) : -1; return k < 0 ? 1e9 : l.start + (l.ct ? l.ct[k] || 0 : 0); };
  SH.lnS = (A, i) => A.ln(i).start;

  // ---------- 底色与地面 ----------
  // 横屏投稿版：engine 在横屏把 L.EXT 设成背景要铺到的左右边界；竖屏 L.EXT = null → FX0 / FX1 = −300 / W+300
  SH.FX0 = () => (L.EXT ? Math.min(-300, L.EXT.x0 - 100) : -300);
  SH.FX1 = () => (L.EXT ? Math.max(W + 300, L.EXT.x1 + 100) : W + 300);
  SH.fillAll = (c) => c.fillRect(SH.FX0(), -300, SH.FX1() - SH.FX0(), H + 600);
  SH.band = (c, y0, y1, col) => { c.fillStyle = col; c.fillRect(SH.FX0(), y0, SH.FX1() - SH.FX0(), y1 - y0); };
  SH.bg = (c, t, col1, col2, seed) => L.bg(c, W, H, col1 || P().paper, col2 || P().paper2, seed, t);
  SH.paper = (c, t, seed = 23) => SH.bg(c, t, P().paper, P().paper2, seed);
  SH.home = (c, t, seed = 29) => { SH.bg(c, t, '#FFF4E2', '#FFE7C7', seed); SH.band(c, 1100, 1700, '#EBD3B4'); };
  SH.clinic = (c, t, seed = 17) => { SH.bg(c, t, '#EAF4F8', '#D7EBF3', seed); SH.band(c, 1100, 1700, '#CFE0EA'); L.fillRR(c, 60, 300, 20, 760, 10, L.alpha('#9EC9E8', 0.5)); };
  SH.nightBg = (c, t, seed = 31) => { c.fillStyle = P().night; SH.fillAll(c); const R = L.rand(seed); for (let k = 0; k < 36; k++) L.circle(c, R() * W, 236 + R() * 760, 2 + R() * 3, `rgba(255,240,200,${0.25 + 0.25 * Math.sin(t * 2 + k)})`); };
  SH.floor = (c, y, col = '#2A3150', col2 = '#333B5E') => { c.fillStyle = col; c.fillRect(SH.FX0(), y, SH.FX1() - SH.FX0(), 1920 - y + 300); for (let i = -1; i < 10; i++) L.fillRR(c, i * 120 + 10, y + 20, 104, 60, 8, col2); };
  SH.paperFloor = (c, y = 1180) => L.fillRR(c, 60, y, 960, 56, 28, L.alpha(P().stone || '#D9B98F', 0.42));

  // ---------- 圆窗（放大镜 / 剖面窗）----------
  SH.ring = (c, x, y, r, col, w = 12) => { L.circle(c, x + 8, y + 12, r + w, 'rgba(59,47,74,0.10)'); L.circle(c, x, y, r + w, col || P().ink); L.circle(c, x, y, r, '#FFF8EC'); };
  SH.inRing = (c, x, y, r, col, fn, w = 12) => { SH.ring(c, x, y, r, col, w); c.save(); c.beginPath(); c.arc(x, y, r, 0, 7); c.clip(); fn(); c.restore(); };

  // ---------- 3D 立绘 / 图标 ----------
  SH.IC = (c, A, id, x, y, size, o) => L.icon3d(c, A, id, x, y, size, o);
  SH.SP = (c, A, id, x, yF, h, o) => L.sprite3d(c, A, id, x, yF, h, o);
  SH.spW = (A, id, h) => { const im = A.img && A.img(id); return im ? h * im.width / im.height : h * 0.5; };   // 立绘按高 h 画时的宽
  SH.spX = (A, id, x, h) => Math.min(x, RX - 7 - SH.spW(A, id, h) / 2);   // 立绘中心 x 收进右安全线（再留 7 px：扫描实测 885 时屏幕右缘到 895）
  // 表情变化：两张立绘交叉淡化（k 0→1，调用方让它在 0.3 s 内走完）
  SH.xf = (c, A, idA, idB, k, x, yF, h, o = {}) => { const a = o.a ?? 1; if (k < 1) SH.SP(c, A, idA, x, yF, h, { ...o, a: a * (1 - k) }); if (k > 0) SH.SP(c, A, idB, x, yF, h, { ...o, a: a * k, shadow: k >= 0.5 && o.shadow !== false }); };

  // ---------- 满幅 3D 镜头：一张带场景的竖版图铺满整个画面（顶栏、字卡、字幕叠在上面）----------
  // id = storyboard.assets 里的图（建议 9:16、宽 ≥ 1080）。o: a 透明度；zoom 基础放大（默认 1.04，盖住画面呼吸）；push 整场缓慢推近的幅度（如 0.06）；ax / ay 裁切锚点 0–1（默认居中；人物偏上就把 ay 调小）。
  // 人物的脸放在画面中部（屏幕 y 约 350–1200），别让头顶钻到顶部章节名下面、下巴被字卡盖住。没图返回 null。
  SH.full = (c, A, id, o = {}) => { const im = A.img && A.img(id); if (!im) return null; const St = OV.LAYOUT.stage, k = ENGINE.stageK(), land = St.x != null;
    const x0 = land ? 0 : W / 2 - W / 2 / k, y0 = land ? St.design_top : St.design_bottom - St.bottom / k, w = land ? W : W / k, h = land ? St.design_bottom - St.design_top : H / k;
    const z = (o.zoom || 1.04) * (1 + (o.push || 0) * L.clamp(A.t / Math.max(1, A.T))), s = Math.max(w / im.width, h / im.height) * z, a = o.a ?? 1;
    c.save(); c.globalAlpha *= a; if (land) { c.beginPath(); c.rect(x0, y0, w, h); c.clip(); } c.imageSmoothingQuality = 'high';
    c.drawImage(im, x0 + (w - im.width * s) * (o.ax ?? 0.5), y0 + (h - im.height * s) * (o.ay ?? 0.5), im.width * s, im.height * s); c.restore();
    if (!land) L.NOFOOT = Math.max(L.NOFOOT || 0, a); return true; };
  // ---------- 警报：整屏红色闪动（危险信号场）。ta 起、tb 止（场内秒）----------
  SH.alarm = (c, t, ta, tb = 1e9, strength = 0.18) => { const a = L.vis(t, ta, tb, 0.3); if (a <= 0) return; c.save(); c.globalAlpha *= strength * a * (0.7 + 0.3 * Math.sin(t * 6)); c.fillStyle = P().red; SH.fillAll(c); c.restore(); };
  // ---------- 一排警示牌：times = 各牌落下的时刻（场内秒），自动排开；画面零文字，文字在字卡 ----------
  SH.flags = (c, t, times, y = 560, size = 170) => { const n = times.length, gap = Math.min(200, 760 / n), x0 = 540 - gap * (n - 1) / 2 - 20;
    times.forEach((ta, i) => SH.drop(c, t, ta, x0 + i * gap, y, () => { PR.card(c, 0, 0, size, size, '#FFFFFF', 30); SH.bang(c, 0, 0, size * 0.3); })); };

  // ---------- 日历（3D 图标 ic_calendar：6 列 × 5 行，四角按原图像素量，双线性插值到格心）----------
  SH.calCell = (A, x, y, size, i, j) => { const im = A.img && A.img('ic_calendar'); if (!im) return [x, y]; const u = (i + 0.5) / 6, v = (j + 0.5) / 5, k = size / Math.max(im.width, im.height), sx = im.width / 1173, sy = im.height / 1071;
    const px = ((1 - u) * (1 - v) * 271 + u * (1 - v) * 980 + (1 - u) * v * 364 + u * v * 1091) * sx, py = ((1 - u) * (1 - v) * 331 + u * (1 - v) * 264 + (1 - u) * v * 909 + u * v * 807) * sy;
    return [x + (px - im.width / 2) * k, y + (py - im.height / 2) * k]; };
  SH.calDots = (c, A, x, y, size, n, col, row = 1) => { for (let k = 0; k < n; k++) { const q = SH.calCell(A, x, y, size, k % 6, row + Math.floor(k / 6)); L.circle(c, q[0], q[1], Math.max(4, size * 0.022), col || P().red); } };

  // ---------- 卡片（图标卡、危险信号卡）：从上方落下 ----------
  SH.drop = (c, t, ta, x, y, fn, dy = 140, s = 1) => { const a = L.easeOut(L.seg(t, ta - 0.12, ta + 0.32)); if (a <= 0) return; L.with(c, fn, { x, y: y - (1 - a) * dy, s: s * (0.7 + 0.3 * L.backOut(a)), a: Math.min(1, a * 1.6) }); };
  SH.card = (c, t, ta, x, y, w, h, col, fn, dy = 120) => SH.drop(c, t, ta, x, y, () => { PR.card(c, 0, 0, w, h, '#FFFFFF', 30); L.fillRR(c, -w / 2, -h / 2, w, 14, 7, col); fn(); }, dy);

  // ---------- 图形符号（不是文字）----------
  const INK = '#3B2F4A';
  SH.bang = (c, x, y, r, col) => { L.circle(c, x, y, r, col || P().red); L.fillRR(c, x - r * 0.13, y - r * 0.6, r * 0.26, r * 0.72, r * 0.13, '#FFFFFF'); L.circle(c, x, y + r * 0.42, r * 0.15, '#FFFFFF'); };
  SH.cross = (c, x, y, r, col) => { for (const a of [0.785, -0.785]) L.with(c, () => L.fillRR(c, -r, -r * 0.16, 2 * r, r * 0.32, r * 0.16, col || P().red), { x, y, r: a }); };
  SH.tick = (c, x, y, r, col) => L.line(c, [[x - r * 0.6, y], [x - r * 0.15, y + r * 0.45], [x + r * 0.7, y - r * 0.5]], r * 0.28, col || P().green);
  SH.upArrow = (c, x, y, s, a = 1) => { if (a <= 0.01) return; c.save(); c.globalAlpha *= a; c.translate(x, y); c.scale(s, s); L.fillRR(c, -9, -10, 18, 58, 7, P().ink2); L.poly(c, [[0, -44], [-26, -6], [26, -6]], P().ink2); c.restore(); };
  // 小脸（拟人器官 / 细菌 / 小球）：点眼 + 一道嘴，表情用形状不用字。mood: smile | happy | pain | worried | frown | surprised | whistle；o.blink、o.blush、o.shades
  SH.face = (c, x, y, r, o = {}) => { const m = o.mood || 'smile', blink = o.blink ? 0.15 : 1;
    if (o.shades) { for (const sx of [-1, 1]) L.fillRR(c, x + sx * r * 0.42 - r * 0.3, y - r * 0.3, r * 0.6, r * 0.34, r * 0.14, INK); L.line(c, [[x - r * 0.15, y - r * 0.16], [x + r * 0.15, y - r * 0.16]], r * 0.07, INK); }
    else for (const sx of [-1, 1]) {
      if (m === 'happy') { c.beginPath(); c.arc(x + sx * r * 0.38, y - r * 0.1, r * 0.17, 1.15 * Math.PI, 1.85 * Math.PI); c.lineWidth = r * 0.09; c.strokeStyle = INK; c.lineCap = 'round'; c.stroke(); }
      else if (m === 'pain') L.line(c, [[x + sx * r * 0.24, y - r * 0.24], [x + sx * r * 0.48, y - r * 0.1], [x + sx * r * 0.24, y + r * 0.04]], r * 0.08, INK);
      else L.ellipse(c, x + sx * r * 0.38, y - r * 0.12, r * 0.1, r * 0.14 * blink, INK); }
    if (m === 'worried' || m === 'frown') for (const sx of [-1, 1]) L.line(c, [[x + sx * r * 0.22, y - r * 0.4], [x + sx * r * 0.56, y - r * 0.32 + (m === 'frown' ? -r * 0.1 : r * 0.06)]], r * 0.07, INK);
    c.beginPath();
    if (m === 'worried' || m === 'frown' || m === 'pain') c.arc(x, y + r * 0.42, r * 0.22, 1.15 * Math.PI, 1.85 * Math.PI);
    else if (m === 'surprised') { L.ellipse(c, x, y + r * 0.3, r * 0.13, r * 0.18, INK); return; }
    else if (m === 'whistle') { L.circle(c, x + r * 0.16, y + r * 0.3, r * 0.09, INK); return; }
    else c.arc(x, y + r * 0.1, r * 0.26, 0.15 * Math.PI, 0.85 * Math.PI);
    c.lineWidth = r * 0.08; c.strokeStyle = INK; c.lineCap = 'round'; c.stroke();
    if (o.blush) for (const sx of [-1, 1]) L.ellipse(c, x + sx * r * 0.62, y + r * 0.16, r * 0.16, r * 0.09, 'rgba(255,120,130,0.45)'); };
})();
