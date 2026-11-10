// 道具图标（扁平元素风，画面零文字：钟只有指针、日历只有格子、倒计时用圆环）。
// 约定：PR.xxx(c, x, y, s, o)，(x,y) 为图标中心，s=1 时约 200 px 见方。
'use strict';
const PR = {};
(() => {
  const P = () => L.P;
  const W = (c, fn, x, y, s, r = 0, a = 1) => L.with(c, fn, { x, y, s, r, a });
  const card = (c, w, h, col = '#FFFFFF', r = 28) => { L.fillRR(c, -w / 2 + 6, -h / 2 + 10, w, h, r, 'rgba(59,47,74,0.12)'); L.fillRR(c, -w / 2, -h / 2, w, h, r, col); };
  PR.card = (c, x, y, w, h, col, r) => W(c, () => card(c, w, h, col, r), x, y, 1);

  // 指针钟：hh:mm；spin 让分针飞转（等待）
  PR.clock = (c, x, y, s, o = {}) => W(c, () => { const p = P(), hh = o.h ?? 3, mm = o.m ?? 7;
    L.circle(c, 0, 0, 100, o.rim || '#E9D9B8'); L.circle(c, 0, 0, 88, '#FFFDF5');
    for (let k = 0; k < 12; k++) { const a = k / 12 * 6.283; L.line(c, [[Math.sin(a) * 70, -Math.cos(a) * 70], [Math.sin(a) * 80, -Math.cos(a) * 80]], k % 3 ? 4 : 8, p.ink2); }
    const ah = (hh % 12 + mm / 60) / 12 * 6.283, am = mm / 60 * 6.283;
    L.line(c, [[0, 0], [Math.sin(ah) * 44, -Math.cos(ah) * 44]], 11, p.ink); L.line(c, [[0, 0], [Math.sin(am) * 68, -Math.cos(am) * 68]], 6, p.ink); L.circle(c, 0, 0, 9, p.red); }, x, y, s);
  PR.window = (c, x, y, s, o = {}) => W(c, () => { const p = P(), day = o.day || 0;
    L.fillRR(c, -170, -190, 340, 380, 30, '#24294A'); const sky = L.mix('#3B4A80', '#9FD6F2', day); L.fillRR(c, -154, -174, 308, 348, 22, sky);
    if (day < 1) { c.save(); c.globalAlpha *= 1 - day; L.circle(c, 50, -80, 54, p.moon); L.circle(c, 72, -94, 50, sky); const R = L.rand(4); for (let k = 0; k < 12; k++) L.sparkle(c, -130 + R() * 260, -150 + R() * 300, 0.25 + R() * 0.3, 'rgba(255,240,200,0.85)'); c.restore(); }
    if (day > 0) { c.save(); c.globalAlpha *= day; L.circle(c, -40, 60 - 120 * day, 60, '#FFD45E'); c.restore(); }
    L.line(c, [[0, -174], [0, 174]], 10, '#24294A'); L.line(c, [[-154, 0], [154, 0]], 10, '#24294A'); }, x, y, s);
  PR.bed = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -430, -40, 860, 250, 40, '#6D5A8C'); L.fillRR(c, -450, -120, 90, 360, 30, '#58477A'); L.fillRR(c, -380, -60, 280, 110, 50, '#F3EDF9'); }, x, y, s);
  PR.blanket = (c, x, y, s, o = {}) => W(c, () => { c.beginPath(); c.moveTo(-360, 20); c.bezierCurveTo(-200, -40, 200, -40, 400, 20); c.lineTo(400, 200); c.lineTo(-360, 200); c.closePath(); c.fillStyle = o.col || '#9B87C4'; c.fill(); L.ellipse(c, 0, 40, 300, 34, 'rgba(255,255,255,0.12)'); }, x, y, s);
  // 马桶：正面（back=false）/ 人站在前面挡住时只露水箱和座圈
  PR.toilet = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -110, -260, 220, 150, 26, '#EEF2F6'); L.fillRR(c, -96, -248, 192, 22, 10, '#D5DCE5'); L.ellipse(c, 0, -60, 150, 70, '#E3E9F0'); L.ellipse(c, 0, -66, 120, 48, '#C9D5E2'); L.fillRR(c, -70, -40, 140, 140, 30, '#EEF2F6'); }, x, y, s);
  PR.door = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -120, -300, 240, 600, 14, '#8A6E58'); L.fillRR(c, -100, -280, 200, 560, 10, o.light ? '#FFD68C' : '#A3866F'); L.circle(c, 70, 20, 12, '#E9C46A'); }, x, y, s);
  // 日历（无字）：flip 0..1 翻页；n 页
  PR.calendar = (c, x, y, s, o = {}) => W(c, () => { const p = P(); card(c, 220, 240, '#FFFFFF', 24); L.fillRR(c, -110, -120, 220, 60, 24, o.col || p.red); L.fillRR(c, -110, -84, 220, 24, 0, o.col || p.red);
    for (const sx of [-50, 50]) L.fillRR(c, sx - 8, -138, 16, 40, 8, p.ink2);
    for (let r = 0; r < 3; r++) for (let k = 0; k < 4; k++) L.fillRR(c, -88 + k * 46, -36 + r * 46, 34, 32, 6, (r * 4 + k) < (o.mark || 0) ? L.alpha(o.col || p.red, 0.75) : '#EEE7DD');
    const f = o.flip || 0; if (f > 0 && f < 1) { c.save(); c.scale(1, 1 - Math.sin(f * Math.PI) * 0.9); L.fillRR(c, -110, -120, 220, 240, 24, 'rgba(255,255,255,0.9)'); c.restore(); } }, x, y, s);
  PR.pillBox = (c, x, y, s, o = {}) => W(c, () => { const col = o.col || '#5A8DEE'; L.fillRR(c, -90, -110, 180, 220, 18, '#FFFFFF'); L.fillRR(c, -90, -110, 180, 70, 18, col); L.fillRR(c, -90, -60, 180, 20, 0, col); L.circle(c, 0, 30, 40, L.alpha(col, 0.25)); L.fillRR(c, -26, 18, 52, 24, 12, col); }, x, y, s);
  PR.blister = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -110, -70, 220, 140, 16, '#D8DEE8'); for (let r = 0; r < 2; r++) for (let k = 0; k < 4; k++) L.ellipse(c, -75 + k * 50, -30 + r * 60, 18, 18, k + r * 4 < (o.taken || 0) ? '#B9C1CE' : (o.col || '#FFFFFF')); }, x, y, s);
  PR.beer = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -50, -90, 100, 180, 14, 'rgba(255,255,255,0.6)'); L.fillRR(c, -44, -60 + 60 * (1 - (o.level ?? 1)), 88, 140 - 60 * (1 - (o.level ?? 1)), 10, '#F4B740'); L.ellipse(c, 0, -66, 50, 22, '#FFFFFF'); c.lineWidth = 12; c.strokeStyle = 'rgba(255,255,255,0.8)'; c.beginPath(); c.arc(60, 0, 34, -1.2, 1.2); c.stroke(); }, x, y, s);
  PR.coffee = (c, x, y, s) => W(c, () => { L.fillRR(c, -60, -50, 120, 110, 26, '#FFFFFF'); L.ellipse(c, 0, -50, 60, 16, '#6B4A33'); c.lineWidth = 12; c.strokeStyle = '#FFFFFF'; c.beginPath(); c.arc(66, 0, 26, -1.3, 1.3); c.stroke(); for (const k of [-20, 10]) L.bez(c, [k, -80], [k - 14, -100], [k + 14, -120], [k, -140], 6, 'rgba(110,97,120,0.4)'); }, x, y, s);
  PR.glass = (c, x, y, s, o = {}) => W(c, () => { const p = P(); c.beginPath(); c.moveTo(-60, -90); c.lineTo(60, -90); c.lineTo(48, 90); c.lineTo(-48, 90); c.closePath(); c.fillStyle = 'rgba(255,255,255,0.75)'; c.fill(); const lv = o.level ?? 0.7; c.save(); c.clip(); c.fillStyle = p.water; c.fillRect(-70, 90 - 180 * lv, 140, 200); c.restore(); }, x, y, s);
  PR.tea = (c, x, y, s) => W(c, () => { L.fillRR(c, -60, -40, 120, 100, 30, '#7FB9A6'); L.ellipse(c, 0, -40, 60, 14, '#C8A35E'); c.lineWidth = 10; c.strokeStyle = '#7FB9A6'; c.beginPath(); c.arc(66, 6, 24, -1.3, 1.3); c.stroke(); }, x, y, s);
  PR.thermo = (c, x, y, s, o = {}) => W(c, () => { const p = P(); L.fillRR(c, -22, -120, 44, 200, 22, '#FFFFFF'); L.circle(c, 0, 90, 40, '#FFFFFF'); L.circle(c, 0, 90, 30, p.red); L.fillRR(c, -10, -100 + 160 * (1 - (o.level ?? 0.85)), 20, 190 - 160 * (1 - (o.level ?? 0.85)), 10, p.red); }, x, y, s);
  PR.drop = (c, x, y, s, col) => W(c, () => { c.beginPath(); c.moveTo(0, -60); c.bezierCurveTo(40, -10, 44, 40, 0, 50); c.bezierCurveTo(-44, 40, -40, -10, 0, -60); c.fillStyle = col || P().red; c.fill(); L.ellipse(c, -12, 10, 8, 14, 'rgba(255,255,255,0.5)'); }, x, y, s);
  PR.urineCup = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -60, -80, 120, 160, 18, 'rgba(255,255,255,0.85)'); L.fillRR(c, -54, -10, 108, 84, 12, o.blood ? '#E8806E' : P().urine); L.fillRR(c, -66, -96, 132, 26, 10, '#9AA3B2'); }, x, y, s);
  PR.tube = (c, x, y, s) => W(c, () => { L.fillRR(c, -22, -110, 44, 200, 22, 'rgba(255,255,255,0.85)'); L.fillRR(c, -18, -20, 36, 106, 18, '#C93C46'); L.fillRR(c, -28, -130, 56, 40, 10, '#5A8DEE'); }, x, y, s);
  PR.glove = (c, x, y, s) => W(c, () => { const col = '#BFE3F2'; L.fillRR(c, -60, -10, 120, 120, 40, col); for (let k = 0; k < 4; k++) L.fillRR(c, -56 + k * 30, -110 + Math.abs(k - 1.5) * 14, 26, 120, 13, col); L.fillRR(c, 40, -30, 26, 90, 13, col); }, x, y, s);
  PR.clipboard = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -90, -120, 180, 240, 18, '#C9A36B'); L.fillRR(c, -74, -100, 148, 206, 10, '#FFFFFF'); L.fillRR(c, -36, -132, 72, 30, 10, '#8A8F99');
    for (let k = 0; k < 4; k++) { L.fillRR(c, -56, -70 + k * 46, 22, 22, 5, '#E3E9F0'); if (k < (o.checks ?? 4)) L.line(c, [[-52, -60 + k * 46], [-45, -52 + k * 46], [-32, -70 + k * 46]], 6, P().green); L.fillRR(c, -20, -64 + k * 46, 76, 10, 5, '#E3E9F0'); } }, x, y, s);
  PR.usMachine = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -130, -120, 260, 180, 18, '#5E6778'); L.fillRR(c, -114, -104, 228, 148, 10, '#14171F');
    L.ellipse(c, -20, -40, 56, 40, 'rgba(220,230,240,0.55)'); L.ellipse(c, -20, 14, 40, 28, 'rgba(220,230,240,0.35)'); L.ellipse(c, -20, -44, 40, 24, (o.residual ?? 0.4) > 0 ? 'rgba(15,18,25,0.95)' : 'rgba(0,0,0,0)');
    L.fillRR(c, -40, 60, 80, 70, 10, '#8D97A8'); L.fillRR(c, 90, 40, 40, 90, 14, '#C3CAD6'); }, x, y, s);
  PR.uroflow = (c, x, y, s, o = {}) => W(c, () => { const p = P(); L.fillRR(c, -120, -110, 240, 150, 16, '#FFFFFF'); c.beginPath(); for (let k = 0; k <= 40; k++) { const u = k / 40, v = Math.sin(u * Math.PI) * (o.peak ?? 0.35); c.lineTo(-100 + u * 200, 20 - v * 110); } c.lineWidth = 7; c.strokeStyle = p.water_dark; c.stroke(); L.line(c, [[-100, 20], [100, 20]], 4, p.ink2); L.ellipse(c, 0, 90, 90, 36, '#E3E9F0'); }, x, y, s);
  PR.glucometer = (c, x, y, s) => W(c, () => { L.fillRR(c, -60, -90, 120, 180, 26, '#7A93B8'); L.fillRR(c, -42, -66, 84, 60, 8, '#DFF1E8'); L.circle(c, 0, 40, 18, '#E3E9F0'); L.fillRR(c, -8, -130, 16, 50, 4, '#FFFFFF'); }, x, y, s);
  PR.pipe = (c, x, y, s) => W(c, () => { const p = P(); c.beginPath(); c.moveTo(-120, -30); c.lineTo(-30, -30); c.quadraticCurveTo(0, -6, 30, -30); c.lineTo(120, -30); c.lineTo(120, 30); c.lineTo(30, 30); c.quadraticCurveTo(0, 6, -30, 30); c.lineTo(-120, 30); c.closePath(); c.fillStyle = p.urethra; c.fill(); }, x, y, s);
  PR.doctor = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -90, -40, 180, 220, 60, '#FFFFFF'); L.fillRR(c, -14, -40, 28, 160, 8, '#E3E9F0'); L.circle(c, 0, -110, 70, '#FCC7A1'); L.ellipse(c, 0, -160, 72, 34, '#3A3044'); L.fillRR(c, -70, -112, 140, 14, 7, '#3A3044');
    for (const sx of [-1, 1]) L.circle(c, sx * 26, -104, 8, '#463C4A'); c.beginPath(); c.arc(0, -84, 18, 0.15 * Math.PI, 0.85 * Math.PI); c.lineWidth = 6; c.strokeStyle = '#B4555C'; c.stroke();
    L.bez(c, [-40, -20], [-60, 40], [10, 60], [30, 30], 8, '#5E6778'); L.circle(c, 30, 30, 14, '#8D97A8'); }, x, y, s);
  PR.ambulance = (c, x, y, s, o = {}) => W(c, () => { const p = P(), t = o.t || 0; L.fillRR(c, -200, -110, 400, 180, 30, '#FFFFFF'); L.fillRR(c, 90, -80, 100, 80, 16, '#9FD6F2'); L.fillRR(c, -200, -10, 400, 30, 0, p.red);
    L.fillRR(c, -90, -80, 30, 90, 6, p.red); L.fillRR(c, -120, -50, 90, 30, 6, p.red); for (const wx of [-120, 120]) { L.circle(c, wx, 80, 42, '#3A3044'); L.circle(c, wx, 80, 18, '#C3CAD6'); }
    const on = Math.sin(t * 16) > 0; L.fillRR(c, -40, -140, 80, 30, 10, on ? p.red : '#5A8DEE'); }, x, y, s);
  PR.scalpel = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -12, -20, 24, 160, 10, '#8D97A8'); c.beginPath(); c.moveTo(-12, -20); c.quadraticCurveTo(-40, -110, 10, -150); c.lineTo(12, -20); c.closePath(); c.fillStyle = '#D9DEE6'; c.fill();
    if (o.cross > 0) { const k = o.cross; L.line(c, [[-110, -150], [L.lerp(-110, 110, k), L.lerp(-150, 150, k)]], 22, P().red); if (k > 0.5) L.line(c, [[110, -150], [L.lerp(110, -110, (k - 0.5) * 2), L.lerp(-150, 150, (k - 0.5) * 2)]], 22, P().red); } }, x, y, s);
  PR.loop = (c, x, y, s) => W(c, () => { L.fillRR(c, -10, -20, 20, 170, 8, '#8D97A8'); c.beginPath(); c.arc(0, -40, 36, Math.PI, 0); c.lineWidth = 9; c.strokeStyle = '#F4C54D'; c.stroke(); }, x, y, s);
  // 橘子：whole（整只）/ half（剖面）；peel 0..1 剥开的一卷皮
  PR.orange = (c, x, y, s, o = {}) => W(c, () => { const p = P();
    if (!o.half) { L.circle(c, 0, 0, 120, p.orange_peel); L.circle(c, -30, -36, 40, 'rgba(255,255,255,0.18)'); L.ellipse(c, 6, -120, 22, 12, '#5E8C4A'); return; }
    L.circle(c, 0, 0, 160, p.orange_peel); L.circle(c, 0, 0, 142, p.orange_pith);
    for (let k = 0; k < 10; k++) { const a0 = k / 10 * 6.283 + 0.05, a1 = (k + 1) / 10 * 6.283 - 0.05; c.beginPath(); c.moveTo(Math.cos((a0 + a1) / 2) * 12, Math.sin((a0 + a1) / 2) * 12); c.arc(0, 0, 132, a0, a1); c.closePath(); c.fillStyle = k % 2 ? p.orange : '#F8B04C'; c.fill(); }
    L.circle(c, 0, 0, 14, p.orange_pith);
    if (o.peel > 0) { c.save(); c.translate(130, -100); c.rotate(0.6); c.scale(1, o.peel); L.fillRR(c, -18, -60, 36, 110, 18, p.orange_peel); L.fillRR(c, -10, -54, 20, 98, 10, p.orange_pith); c.restore(); } }, x, y, s);
  // 白色蒸汽（不用绿色）
  PR.steam = (c, x, y, s, o = {}) => W(c, () => { const t = o.t || 0; for (let k = 0; k < 7; k++) { const a = k / 7 * 6.283 + t * 0.7; L.circle(c, Math.cos(a) * 60, Math.sin(a) * 40 - 10, 62 + 10 * Math.sin(t * 2 + k), 'rgba(255,255,255,0.9)'); } L.circle(c, 0, -10, 70, P().steam_blue); }, x, y, s);
  PR.timerRing = (c, x, y, s, o = {}) => W(c, () => { const p = P(), u = L.clamp(o.u ?? 0); L.circle(c, 0, 0, 70, '#FFFFFF'); c.beginPath(); c.moveTo(0, 0); c.arc(0, 0, 60, -Math.PI / 2, -Math.PI / 2 + 6.283 * (1 - u)); c.closePath(); c.fillStyle = L.alpha(p.laser, 0.8); c.fill(); L.circle(c, 0, 0, 22, '#FFFFFF'); }, x, y, s);
  PR.microscope = (c, x, y, s) => W(c, () => { L.fillRR(c, -90, 90, 180, 30, 10, '#5E6778'); L.fillRR(c, -20, -40, 40, 140, 10, '#8D97A8'); c.save(); c.rotate(-0.4); L.fillRR(c, -22, -150, 44, 120, 14, '#C3CAD6'); c.restore(); L.fillRR(c, -60, 20, 120, 16, 6, '#5E6778'); }, x, y, s);
  PR.jar = (c, x, y, s) => W(c, () => { L.fillRR(c, -50, -60, 100, 130, 18, 'rgba(255,255,255,0.85)'); L.fillRR(c, -56, -76, 112, 26, 8, '#5A8DEE'); L.ellipse(c, 0, 20, 30, 24, P().adenoma); }, x, y, s);
  // 天平：o.tilt 弧度，横梁按 canvas 顺时针转 → tilt > 0 右盘下沉、左盘上翘；tilt < 0 左盘下沉（psa s09 照着写反了的注释画反过）。o.draw(c, sx) 在盘上画东西，sx = −1 左盘 / +1 右盘（盘心坐标）
  PR.scale =(c, x, y, s, o = {}) => W(c, () => { const p = P(), tilt = o.tilt || 0; L.fillRR(c, -14, -180, 28, 280, 10, '#8A6E58'); L.fillRR(c, -90, 90, 180, 30, 12, '#8A6E58');
    c.save(); c.translate(0, -170); c.rotate(tilt); L.fillRR(c, -260, -10, 520, 20, 10, '#A3866F');
    for (const sx of [-1, 1]) { L.line(c, [[sx * 250, 0], [sx * 250 - 60, 130]], 4, '#8A6E58'); L.line(c, [[sx * 250, 0], [sx * 250 + 60, 130]], 4, '#8A6E58'); c.save(); c.translate(sx * 250, 130); c.rotate(-tilt); L.ellipse(c, 0, 0, 90, 22, '#C9A36B'); if (o.draw) o.draw(c, sx); c.restore(); }
    c.restore(); L.circle(c, 0, -170, 16, '#C9A36B'); }, x, y, s);
  PR.share = (c, x, y, s) => W(c, () => { const p = P(); L.circle(c, 0, 0, 90, p.red); for (const [a, b] of [[[-30, 0], [30, -34]], [[-30, 0], [30, 34]]]) L.line(c, [a, b], 10, '#FFFFFF'); for (const q of [[-30, 0], [30, -34], [30, 34]]) L.circle(c, q[0], q[1], 16, '#FFFFFF'); }, x, y, s);
  PR.oldman = (c, x, y, s, o = {}) => W(c, () => { const col = o.lit ? (o.col || '#C27A4E') : 'rgba(110,97,120,0.25)'; L.circle(c, 0, -60, 30, col); L.fillRR(c, -34, -24, 68, 90, 30, col); if (o.bubble) { L.circle(c, 34, -100, 18, '#FFFFFF'); PR.drop(c, 34, -100, 0.22, P().water_dark); } }, x, y, s);
  PR.kidney = (c, x, y, s, o = {}) => W(c, () => { const p = P(), sw = o.swell || 0; c.save(); c.scale(0.4, 0.4); AN_bean(c); c.fillStyle = L.mix(p.kidney, '#A9A3A8', o.grey || 0); c.fill(); c.restore(); if (sw > 0) L.ellipse(c, 10, 0, 34 * sw, 70 * sw, L.alpha(p.urine, 0.9)); }, x, y, s);
  const AN_bean = (c) => { c.beginPath(); c.moveTo(40, -320); c.bezierCurveTo(150, -322, 205, -215, 172, -115); c.bezierCurveTo(150, -55, 102, -58, 96, 0); c.bezierCurveTo(102, 58, 150, 55, 172, 115); c.bezierCurveTo(205, 215, 150, 322, 40, 320); c.bezierCurveTo(-120, 318, -225, 190, -225, 0); c.bezierCurveTo(-225, -190, -120, -318, 40, -320); c.closePath(); };
  PR.ankle = (c, x, y, s, o = {}) => W(c, () => { const k = 1 + 0.4 * (o.swell || 0); L.fillRR(c, -40 * k, -140, 80 * k, 160, 30, '#FCC7A1'); L.fillRR(c, -50, 10, 150, 50, 24, '#FCC7A1'); if (o.swell > 0) { c.save(); c.globalAlpha *= o.swell; c.lineWidth = 5; c.strokeStyle = '#E8A884'; c.beginPath(); c.arc(0, -40, 50 * k, 2.2, 4.1); c.stroke(); c.restore(); } }, x, y, s);
  PR.pants = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -90, -100, 180, 70, 16, '#42475D'); for (const sx of [-1, 1]) L.fillRR(c, sx * 46 - 40, -40, 80, 150, 16, '#42475D'); if (o.wet > 0) L.ellipse(c, -10, -20, 40 * o.wet, 30 * o.wet, '#2E3243'); }, x, y, s);
  PR.bladder = (c, x, y, s, o = {}) => W(c, () => { const p = P(), d = o.distend || 0; L.ellipse(c, 0, 0, 90 + 30 * d, 80 + 30 * d, p.bladder_dark); L.ellipse(c, 0, 0, 78 + 30 * d, 68 + 30 * d, p.bladder_wall); L.ellipse(c, 0, 10, 62 + 30 * d, 52 + 30 * d, L.alpha(p.urine, 0.9)); L.fillRR(c, -12, 70 + 30 * d, 24, 60, 10, p.urethra); }, x, y, s);
  PR.germ = (c, x, y, s, o = {}) => W(c, () => { const col = o.col || '#8FBF5A'; for (let k = 0; k < 8; k++) { const a = k / 8 * 6.283 + (o.t || 0); L.line(c, [[Math.cos(a) * 40, Math.sin(a) * 40], [Math.cos(a) * 62, Math.sin(a) * 62]], 8, col); L.circle(c, Math.cos(a) * 64, Math.sin(a) * 64, 8, col); } L.circle(c, 0, 0, 46, col); for (const sx of [-1, 1]) L.circle(c, sx * 16, -6, 7, '#3B2F4A'); }, x, y, s);
  PR.stone = (c, x, y, s) => W(c, () => { L.ellipse(c, 0, 0, 40, 32, '#D9A066'); L.ellipse(c, -10, -10, 14, 8, 'rgba(255,255,255,0.4)'); }, x, y, s);
  // 巨噬细胞“小清洁工”：圆滚滚的淡紫色团子 + 小眼睛
  PR.cleaner = (c, x, y, s, o = {}) => W(c, () => { const t = o.t || 0; c.beginPath(); for (let k = 0; k <= 24; k++) { const a = k / 24 * 6.283, r = 50 + 6 * Math.sin(a * 4 + t * 5); c.lineTo(Math.cos(a) * r, Math.sin(a) * r); } c.closePath(); c.fillStyle = '#C9B8E0'; c.fill(); L.circle(c, 0, 4, 22, '#9B7BE0'); for (const sx of [-1, 1]) L.circle(c, sx * 16, -16, 6, '#3B2F4A'); }, x, y, s);
  // 三级台阶：从左往右逐级升高，(x,y) 为底边中点
  PR.stairs = (c, x, y, s, o = {}) => W(c, () => { const cols = ['#F6D9A8', '#F2C285', '#EAA96A']; for (let k = 0; k < 3; k++) { const a = L.clamp((o.reveal ?? 3) - k); if (a <= 0) continue; c.save(); c.globalAlpha *= a; const h = 120 * (k + 1); L.fillRR(c, -480 + k * 320, -h, 320, h, 14, cols[k]); L.fillRR(c, -480 + k * 320, -h, 320, 18, 9, 'rgba(255,255,255,0.35)'); c.restore(); } }, x, y, s);
  PR.alert = (c, x, y, s, o = {}) => W(c, () => { const p = P(), t = o.t || 0; L.fillRR(c, -80, -20, 160, 90, 20, '#3A3044'); c.beginPath(); c.arc(0, -20, 70, Math.PI, 0); c.closePath(); c.fillStyle = p.red; c.fill(); const g = 0.5 + 0.5 * Math.sin(t * 14); L.circle(c, 0, -40, 120, `rgba(240,96,93,${0.18 * g})`); L.ellipse(c, -24, -50, 18, 26, 'rgba(255,255,255,0.45)'); }, x, y, s);
  PR.pillAction = (c, x, y, s, o = {}) => W(c, () => { const p = P(); L.fillRR(c, -60, -24, 120, 48, 24, o.col || p.blue); L.fillRR(c, 0, -24, 60, 48, 24, '#FFFFFF'); c.save(); L.rr(c, -60, -24, 120, 48, 24); c.lineWidth = 4; c.strokeStyle = 'rgba(59,47,74,0.15)'; c.stroke(); c.restore(); }, x, y, s);
  PR.check = (c, x, y, s, col) => W(c, () => { L.circle(c, 0, 0, 40, col || P().green); L.line(c, [[-18, 0], [-4, 14], [20, -14]], 9, '#FFFFFF'); }, x, y, s);
  PR.bang = (c, x, y, s, col) => W(c, () => { L.circle(c, 0, 0, 40, col || '#F4B740'); L.fillRR(c, -6, -24, 12, 30, 6, '#FFFFFF'); L.circle(c, 0, 18, 7, '#FFFFFF'); }, x, y, s);
  PR.cross = (c, x, y, s, k = 1) => W(c, () => { const col = P().red; L.line(c, [[-60, -60], [L.lerp(-60, 60, L.clamp(k * 2)), L.lerp(-60, 60, L.clamp(k * 2))]], 16, col); if (k > 0.5) L.line(c, [[60, -60], [L.lerp(60, -60, (k - 0.5) * 2), L.lerp(-60, 60, (k - 0.5) * 2)]], 16, col); }, x, y, s);
  PR.qmark = (c, x, y, s, col) => W(c, () => { c.lineWidth = 22; c.strokeStyle = col || P().water_dark; c.lineCap = 'round'; c.beginPath(); c.arc(0, -30, 38, Math.PI * 1.1, Math.PI * 2.35); c.lineTo(0, 26); c.stroke(); L.circle(c, 0, 66, 13, col || P().water_dark); }, x, y, s);
  PR.zzz = (c, x, y, t) => { for (let k = 0; k < 3; k++) { const f = (t * 0.5 + k / 3) % 1; L.with(c, () => { L.line(c, [[-14, -14], [14, -14], [-14, 14], [14, 14]], 6, 'rgba(255,255,255,0.8)'); }, { x: x + f * 50, y: y - f * 90, s: 0.5 + f * 0.6, a: 1 - f }); } };
  // 麻醉：闭眼的脸 + 透明面罩 + Zzz
  PR.anesthesia = (c, x, y, s, o = {}) => W(c, () => { const p = P(); L.circle(c, 0, 0, 90, '#FCC7A1'); L.ellipse(c, 0, -62, 80, 36, '#D5D7DD');
    for (const sx of [-1, 1]) { c.beginPath(); c.arc(sx * 30, -10, 14, 0.15 * Math.PI, 0.85 * Math.PI); c.lineWidth = 6; c.strokeStyle = '#463C4A'; c.stroke(); }
    L.ellipse(c, 0, 40, 46, 36, 'rgba(207,239,255,0.85)'); c.lineWidth = 5; c.strokeStyle = '#8D97A8'; c.beginPath(); c.ellipse(0, 40, 46, 36, 0, 0, 7); c.stroke(); L.line(c, [[40, 54], [120, 90]], 10, '#8D97A8');
    PR.zzz(c, 80, -70, o.t || 0); }, x, y, s);
  PR.heart = (c, x, y, s, o = {}) => W(c, () => { const k = 1 + 0.06 * Math.sin((o.t || 0) * 6); c.save(); c.scale(k, k); c.beginPath(); c.moveTo(0, 60); c.bezierCurveTo(-90, 0, -70, -80, 0, -40); c.bezierCurveTo(70, -80, 90, 0, 0, 60); c.fillStyle = P().red; c.fill(); L.ellipse(c, -30, -30, 14, 9, 'rgba(255,255,255,0.45)', -0.5); c.restore(); }, x, y, s);
  PR.tree = (c, x, y, s) => W(c, () => { L.fillRR(c, -20, -40, 40, 200, 12, '#8A6E58'); L.circle(c, 0, -120, 120, '#7DBE7A'); L.circle(c, -70, -70, 80, '#6AAE6A'); L.circle(c, 70, -80, 90, '#88C784'); }, x, y, s);
  PR.bench = (c, x, y, s) => W(c, () => { L.fillRR(c, -200, -20, 400, 30, 10, '#A3866F'); L.fillRR(c, -200, -90, 400, 26, 10, '#A3866F'); for (const sx of [-170, 160]) L.fillRR(c, sx, 0, 14, 80, 6, '#5E6778'); }, x, y, s);
  PR.bag = (c, x, y, s, o = {}) => W(c, () => { L.fillRR(c, -60, -90, 120, 170, 24, 'rgba(255,255,255,0.85)'); L.fillRR(c, -54, -90 + 170 * (1 - (o.level ?? 0.6)), 108, 160 * (o.level ?? 0.6), 20, L.alpha(P().urine, 0.95)); L.fillRR(c, -8, -150, 16, 70, 8, '#E9C38F'); }, x, y, s);
  PR.glassClink = (c, x, y, s, o = {}) => W(c, () => { PR.beer(c, -70, 0, 0.8, { level: o.level }); PR.beer(c, 70, 0, 0.8, { level: o.level }); }, x, y, s);
  PR.wind = (c, x, y, s, t) => W(c, () => { for (let k = 0; k < 4; k++) { const f = (t * 0.6 + k / 4) % 1; c.save(); c.globalAlpha *= Math.sin(f * Math.PI); L.bez(c, [-200 + f * 300, -60 + k * 40], [-120 + f * 300, -90 + k * 40], [-40 + f * 300, -30 + k * 40], [40 + f * 300, -60 + k * 40], 7, 'rgba(255,255,255,0.8)'); c.restore(); } }, x, y, s);
  PR.retro = (c, x, y, s, o = {}) => W(c, () => { const p = P(), u = o.u ?? 1; // 逆行射精示意：膀胱 + 尿道，箭头掉头流进膀胱（不画生殖器）
    L.ellipse(c, 0, -80, 120, 90, p.bladder_wall); L.ellipse(c, 0, -76, 100, 72, '#FBE3DA'); L.fillRR(c, -14, -6, 28, 200, 14, p.urethra);
    if (u > 0) { const pts = [[60, 160], [24, 90], [0, 40], [0, -20], [0, -70]]; const q = L.path(pts); c.save(); c.beginPath(); const n = 30; for (let i = 0; i <= n * u; i++) { const a = q.at(i / n); i ? c.lineTo(a[0], a[1]) : c.moveTo(a[0], a[1]); } c.lineWidth = 12; c.strokeStyle = '#F4B740'; c.lineCap = 'round'; c.stroke(); c.restore();
      const a = q.at(u); L.with(c, () => L.poly(c, [[0, -22], [18, 10], [-18, 10]], '#F4B740'), { x: a[0], y: a[1], r: a[2] + Math.PI / 2 }); } }, x, y, s);
})();
if (typeof module !== 'undefined') module.exports = PR; else window.PR = PR;
