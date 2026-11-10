// 手绘风格层：不改任何场景代码，在 Canvas 路径层统一换“笔触”。
// 开启后（SK.on = true）：所有路径先展平成折线 → 按屏幕空间的平滑噪声抖动（铅笔手抖）→ 填色；
// 不透明的填色形状再用“同色系加深”的彩铅描一道粗细变化的轮廓（与填色略错位）；细线描两遍。
// 抖动噪声每 2 帧换一次（线条“呼吸”，line boil）。文字（fillText）不受影响，字幕保持清晰。
'use strict';
const SK = { on: false, amp: 1.6, seed: 0, outline: true, W: 1080, H: 1920 };
(() => {
  const P = CanvasRenderingContext2D.prototype;
  const N = {}; for (const k of ['beginPath', 'moveTo', 'lineTo', 'quadraticCurveTo', 'bezierCurveTo', 'arc', 'arcTo', 'ellipse', 'rect', 'closePath', 'fill', 'stroke', 'clip', 'fillRect']) N[k] = P[k];
  // ---------- 平滑值噪声（屏幕空间） ----------
  const hash = (x, y, s) => { let h = (x * 374761393 + y * 668265263 + s * 2147483647) | 0; h = (h ^ (h >>> 13)) * 1274126177 | 0; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
  const sm = (t) => t * t * (3 - 2 * t);
  const vn = (x, y, s) => { const xi = Math.floor(x), yi = Math.floor(y), xf = sm(x - xi), yf = sm(y - yi);
    const a = hash(xi, yi, s), b = hash(xi + 1, yi, s), c = hash(xi, yi + 1, s), d = hash(xi + 1, yi + 1, s);
    return (a + (b - a) * xf + (c - a) * yf + (a - b - c + d) * xf * yf) * 2 - 1; };
  const noise = (X, Y, s) => vn(X / 46, Y / 46, s) * 0.75 + vn(X / 13, Y / 13, s + 7) * 0.25;
  // ---------- 记录路径（用户坐标），同时记下当时的变换 ----------
  const sc = (ctx) => { const m = ctx.getTransform(); return Math.max(1e-6, Math.sqrt(Math.abs(m.a * m.d - m.b * m.c))); };
  const st = (ctx) => (ctx.__sk || (ctx.__sk = { subs: [], cur: null }));
  const push = (ctx, x, y) => { const s = st(ctx); if (!s.cur) { s.cur = { pts: [], closed: false }; s.subs.push(s.cur); } s.cur.pts.push([x, y]); };
  const last = (ctx) => { const s = st(ctx); return s.cur && s.cur.pts.length ? s.cur.pts[s.cur.pts.length - 1] : null; };
  const segN = (ctx, len) => Math.max(2, Math.min(80, Math.ceil(len * sc(ctx) / 7)));
  P.beginPath = function () { if (SK.on) { this.__sk = { subs: [], cur: null }; } return N.beginPath.call(this); };
  P.moveTo = function (x, y) { if (!SK.on) return N.moveTo.call(this, x, y); const s = st(this); s.cur = { pts: [[x, y]], closed: false }; s.subs.push(s.cur); };
  P.lineTo = function (x, y) { if (!SK.on) return N.lineTo.call(this, x, y); const p = last(this); if (!p) return push(this, x, y); const n = segN(this, Math.hypot(x - p[0], y - p[1])); for (let i = 1; i <= n; i++) push(this, p[0] + (x - p[0]) * i / n, p[1] + (y - p[1]) * i / n); };
  P.quadraticCurveTo = function (cx, cy, x, y) { if (!SK.on) return N.quadraticCurveTo.call(this, cx, cy, x, y); const p = last(this) || [cx, cy]; const n = segN(this, Math.hypot(cx - p[0], cy - p[1]) + Math.hypot(x - cx, y - cy)); for (let i = 1; i <= n; i++) { const t = i / n, u = 1 - t; push(this, u * u * p[0] + 2 * u * t * cx + t * t * x, u * u * p[1] + 2 * u * t * cy + t * t * y); } };
  P.bezierCurveTo = function (c1x, c1y, c2x, c2y, x, y) { if (!SK.on) return N.bezierCurveTo.call(this, c1x, c1y, c2x, c2y, x, y); const p = last(this) || [c1x, c1y]; const n = segN(this, Math.hypot(c1x - p[0], c1y - p[1]) + Math.hypot(c2x - c1x, c2y - c1y) + Math.hypot(x - c2x, y - c2y)); for (let i = 1; i <= n; i++) { const t = i / n, u = 1 - t; push(this, u * u * u * p[0] + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * x, u * u * u * p[1] + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * y); } };
  const arcPts = (ctx, cx, cy, rx, ry, rot, a0, a1, ccw) => {
    if (rx <= 0 || ry <= 0) return; let sw = a1 - a0;
    if (!ccw) { if (sw >= Math.PI * 2) sw = Math.PI * 2; else { sw %= Math.PI * 2; if (sw < 0) sw += Math.PI * 2; } }
    else { if (-sw >= Math.PI * 2) sw = -Math.PI * 2; else { sw %= Math.PI * 2; if (sw > 0) sw -= Math.PI * 2; } }
    const n = segN(ctx, Math.abs(sw) * Math.max(rx, ry)); const cr = Math.cos(rot), sr = Math.sin(rot);
    for (let i = 0; i <= n; i++) { const a = a0 + sw * i / n, ex = Math.cos(a) * rx, ey = Math.sin(a) * ry; const x = cx + ex * cr - ey * sr, y = cy + ex * sr + ey * cr; if (i === 0 && last(ctx)) ctx.lineTo(x, y); else push(ctx, x, y); }
  };
  P.arc = function (x, y, r, a0, a1, ccw = false) { if (!SK.on) return N.arc.call(this, x, y, r, a0, a1, ccw); arcPts(this, x, y, r, r, 0, a0, a1, ccw); };
  P.ellipse = function (x, y, rx, ry, rot, a0, a1, ccw = false) { if (!SK.on) return N.ellipse.call(this, x, y, rx, ry, rot, a0, a1, ccw); arcPts(this, x, y, rx, ry, rot, a0, a1, ccw); };
  P.arcTo = function (x1, y1, x2, y2, r) {
    if (!SK.on) return N.arcTo.call(this, x1, y1, x2, y2, r);
    const p = last(this); if (!p) return push(this, x1, y1);
    const v1x = p[0] - x1, v1y = p[1] - y1, v2x = x2 - x1, v2y = y2 - y1; const l1 = Math.hypot(v1x, v1y), l2 = Math.hypot(v2x, v2y);
    if (l1 < 1e-6 || l2 < 1e-6 || r <= 0) return this.lineTo(x1, y1);
    const cos = (v1x * v2x + v1y * v2y) / (l1 * l2); const ang = Math.acos(Math.max(-1, Math.min(1, cos))); if (ang < 1e-3 || Math.abs(ang - Math.PI) < 1e-3) return this.lineTo(x1, y1);
    const d = r / Math.tan(ang / 2); const t1 = [x1 + v1x / l1 * d, y1 + v1y / l1 * d], t2 = [x1 + v2x / l2 * d, y1 + v2y / l2 * d];
    const bx = v1x / l1 + v2x / l2, by = v1y / l1 + v2y / l2, bl = Math.hypot(bx, by); const dc = r / Math.sin(ang / 2); const cx = x1 + bx / bl * dc, cy = y1 + by / bl * dc;
    this.lineTo(t1[0], t1[1]); const s0 = Math.atan2(t1[1] - cy, t1[0] - cx), s1 = Math.atan2(t2[1] - cy, t2[0] - cx); const cross = v1x * v2y - v1y * v2x;
    arcPts(this, cx, cy, r, r, 0, s0, s1, cross > 0);
  };
  P.rect = function (x, y, w, h) { if (!SK.on) return N.rect.call(this, x, y, w, h); this.moveTo(x, y); this.lineTo(x + w, y); this.lineTo(x + w, y + h); this.lineTo(x, y + h); this.closePath(); };
  P.closePath = function () { if (!SK.on) return N.closePath.call(this); const s = st(this); if (s.cur) { s.cur.closed = true; const f = s.cur.pts[0]; s.cur = { pts: [[f[0], f[1]]], closed: false }; s.subs.push(s.cur); } };
  // ---------- 把记录的路径按噪声抖动后交给原生绘制 ----------
  const emit = (ctx, seedOff, ampMul = 1) => {
    const m = ctx.getTransform(), k = sc(ctx), A = SK.amp * ampMul / k; N.beginPath.call(ctx);
    for (const sp of st(ctx).subs) { if (sp.pts.length < 2) continue;
      sp.pts.forEach(([x, y], i) => { const X = m.a * x + m.c * y + m.e, Y = m.b * x + m.d * y + m.f; const jx = x + A * noise(X, Y, SK.seed + seedOff), jy = y + A * noise(X + 917, Y - 331, SK.seed + seedOff); i ? N.lineTo.call(ctx, jx, jy) : N.moveTo.call(ctx, jx, jy); });
      if (sp.closed) N.closePath.call(ctx); }
  };
  const parse = (s) => { if (typeof s !== 'string') return null; let m = s.match(/^#([0-9a-f]{6})/i); if (m) { const v = parseInt(m[1], 16); return [v >> 16, (v >> 8) & 255, v & 255, 1]; }
    m = s.match(/rgba?\(([^)]+)\)/); if (m) { const q = m[1].split(',').map(Number); return [q[0], q[1], q[2], q.length > 3 ? q[3] : 1]; } return null; };
  const bbox = (ctx) => { const m = ctx.getTransform(); let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const sp of st(ctx).subs) for (const [x, y] of sp.pts) { const X = m.a * x + m.c * y + m.e, Y = m.b * x + m.d * y + m.f; if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y; } return [x1 - x0, y1 - y0]; };
  // 彩铅排线：在形状内用“正片叠底”铺一层斜向铅笔线（屏幕空间，不随物体缩放）
  let hatchPat = null;
  const hatch = (ctx, a) => {
    if (!hatchPat) { const cv = document.createElement('canvas'); cv.width = cv.height = 192; const g = cv.getContext('2d'); const was = SK.on; SK.on = false; g.fillStyle = '#FFFFFF'; g.fillRect(0, 0, 192, 192);
      for (let k = 0; k < 70; k++) { const o = hash(k, 1, 11) * 192 * 2 - 192, l = 30 + hash(k, 2, 11) * 90, y = hash(k, 3, 11) * 192; g.strokeStyle = `rgba(90,70,60,${0.18 + 0.22 * hash(k, 4, 11)})`; g.lineWidth = 1 + hash(k, 5, 11) * 1.2; g.lineCap = 'round';
        for (const dx of [-192, 0, 192]) for (const dy of [-192, 0, 192]) { g.beginPath(); g.moveTo(o + dx + y * 0.6, y + dy); g.lineTo(o + dx + y * 0.6 + l * 0.8, y + dy - l * 0.6); g.stroke(); } }
      hatchPat = ctx.createPattern(cv, 'repeat'); SK.on = was; }
    ctx.save(); emit(ctx, 0); N.clip.call(ctx); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'multiply'; ctx.globalAlpha = Math.min(1, a) * 0.55; ctx.fillStyle = hatchPat; N.fillRect.call(ctx, 0, 0, SK.W, SK.H); ctx.restore();
  };
  // 彩铅轮廓：同色系加深、与填色略错位、按段改变笔压（线宽）
  const outline = (ctx, rgb) => {
    const k = sc(ctx), ink = [59, 47, 74]; const col = rgb.slice(0, 3).map((v, i) => Math.round(v * 0.5 * 0.7 + ink[i] * 0.3));
    const m = ctx.getTransform(); ctx.save(); ctx.strokeStyle = `rgba(${col[0]},${col[1]},${col[2]},0.82)`; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.setLineDash([]);
    for (const sp of st(ctx).subs) { const pts = sp.pts; if (pts.length < 2) continue; const all = sp.closed ? [...pts, pts[0]] : pts;
      for (let i = 0; i < all.length - 1; i += 5) { const seg = all.slice(i, Math.min(all.length, i + 6)); const [x, y] = seg[0]; const X = m.a * x + m.c * y + m.e, Y = m.b * x + m.d * y + m.f;
        ctx.lineWidth = (2.6 + 1.5 * noise(X * 3, Y * 3, SK.seed + 55)) / k; N.beginPath.call(ctx);
        seg.forEach(([px, py], j) => { const PX = m.a * px + m.c * py + m.e, PY = m.b * px + m.d * py + m.f; const A = SK.amp * 1.15 / k; const jx = px + A * noise(PX, PY, SK.seed + 101), jy = py + A * noise(PX + 917, PY - 331, SK.seed + 101); j ? N.lineTo.call(ctx, jx, jy) : N.moveTo.call(ctx, jx, jy); });
        N.stroke.call(ctx); } }
    ctx.restore();
  };
  // ================= 多风格：hand 手绘彩铅 / paper 剪纸拼贴 / clay 黏土 / chalk 黑板粉笔 / ink 国风水墨 =================
  SK.mode = 'hand';
  const rgbS = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
  const mixc = (c, d, t) => [0, 1, 2].map((i) => c[i] + (d[i] - c[i]) * t);
  const lum = (c) => 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];
  const desat = (c, t) => { const l = lum(c); return [0, 1, 2].map((i) => c[i] + (l - c[i]) * t); };
  const hsl = (c) => { const r = c[0] / 255, g = c[1] / 255, b = c[2] / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2; if (mx === mn) return [0, 0, l]; const d = mx - mn, s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn); const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; return [h * 60, s, l]; };
  const rgbOf = (h, s, l) => { h = ((h % 360) + 360) % 360 / 360; const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q; const f = (t) => { t = (t + 1) % 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; }; return [f(h + 1 / 3) * 255, f(h) * 255, f(h - 1 / 3) * 255]; };
  const kzBg = (rgb) => { const [h, s, l] = hsl(rgb); if (s < 0.25 || (h >= 20 && h < 70)) return 232; if (h < 20 || h >= 320) return 335; if (h >= 70 && h < 175) return 178; if (h >= 175 && h < 255) return 214; return 268; };   // 背景色相 → 深色夜空的色相
  const pats = {};
  const pat = (ctx, key, size, draw) => { if (!pats[key]) { const cv = document.createElement('canvas'); cv.width = cv.height = size; const g = cv.getContext('2d'); const was = SK.on; SK.on = false; draw(g, size); SK.on = was; pats[key] = ctx.createPattern(cv, 'repeat'); } return pats[key]; };
  const noiseTex = (g, n, f, col, a0, a1) => { const id = g.getImageData(0, 0, n, n); for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) { const i = (y * n + x) * 4; const v = (vn(x / f, y / f, 5) + vn(x / (f / 4), y / (f / 4), 6) * 0.5 + 1.5) / 3; const a = a0 + (a1 - a0) * v; id.data[i] = col[0]; id.data[i + 1] = col[1]; id.data[i + 2] = col[2]; id.data[i + 3] = a * 255; } g.putImageData(id, 0, 0); };
  const overlayIn = (ctx, p, comp, alpha) => { ctx.save(); emit(ctx, 0); N.clip.call(ctx); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = comp; ctx.globalAlpha = alpha; ctx.fillStyle = p; N.fillRect.call(ctx, 0, 0, SK.W, SK.H); ctx.restore(); };
  const bbox4 = (ctx) => { const m = ctx.getTransform(); let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const sp of st(ctx).subs) for (const [x, y] of sp.pts) { const X = m.a * x + m.c * y + m.e, Y = m.b * x + m.d * y + m.f; if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y; } return [x0, y0, x1 - x0, y1 - y0]; };
  // 通用“笔刷描边”：按段变粗细
  const brush = (ctx, col, w0, w1, seedOff = 101, ampMul = 1.15) => {
    const k = sc(ctx), m = ctx.getTransform(); ctx.save(); ctx.strokeStyle = col; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.setLineDash([]); ctx.shadowBlur = 0; ctx.shadowColor = 'transparent';
    for (const sp of st(ctx).subs) { const pts = sp.pts; if (pts.length < 2) continue; const all = sp.closed ? [...pts, pts[0]] : pts;
      for (let i = 0; i < all.length - 1; i += 5) { const seg = all.slice(i, Math.min(all.length, i + 6)); const [x, y] = seg[0]; const X = m.a * x + m.c * y + m.e, Y = m.b * x + m.d * y + m.f;
        ctx.lineWidth = (w0 + w1 * (0.5 + 0.5 * noise(X * 3, Y * 3, SK.seed + 55))) / k; N.beginPath.call(ctx);
        seg.forEach(([px, py], j) => { const PX = m.a * px + m.c * py + m.e, PY = m.b * px + m.d * py + m.f; const A = SK.amp * ampMul / k; const jx = px + A * noise(PX, PY, SK.seed + seedOff), jy = py + A * noise(PX + 917, PY - 331, SK.seed + seedOff); j ? N.lineTo.call(ctx, jx, jy) : N.moveTo.call(ctx, jx, jy); });
        N.stroke.call(ctx); } }
    ctx.restore();
  };
  const plainFill = (ctx, args, style) => { if (style) { ctx.save(); ctx.fillStyle = style; emit(ctx, 0); N.fill.apply(ctx, args); ctx.restore(); } else { emit(ctx, 0); N.fill.apply(ctx, args); } };
  P.fill = function (...args) {
    if (!SK.on || !this.__sk || !this.__sk.subs.length) return N.fill.apply(this, args);
    const rgb = parse(this.fillStyle); const mode = SK.mode;
    if (!rgb) return plainFill(this, args);
    const a = rgb[3] * this.globalAlpha; const [bx, by, bw, bh] = bbox4(this); const size = Math.max(bw, bh);
    const opaque = a >= 0.66 && size >= 22 && !(bw > SK.W * 0.9 && bh > SK.H * 0.5); const tinyWhite = rgb[0] > 245 && rgb[1] > 245 && rgb[2] > 245 && size < 40;
    if (mode === 'hand') { plainFill(this, args); if (!opaque || !SK.outline) return; if (Math.min(bw, bh) > 70) hatch(this, a); if (!tinyWhite) outline(this, rgb); return; }
    if (mode === 'paper') {   // 剪纸：纸片投影 + 纸纤维，无描边
      if (!opaque) return plainFill(this, args);
      this.save(); this.shadowColor = 'rgba(70,45,25,0.32)'; this.shadowBlur = 8; this.shadowOffsetX = 2; this.shadowOffsetY = 5; emit(this, 0); N.fill.apply(this, args); this.restore();
      if (size > 40) overlayIn(this, pat(this, 'fiber', 256, (g, n) => { noiseTex(g, n, 18, [120, 100, 80], 0.0, 0.35); for (let k = 0; k < 160; k++) { g.strokeStyle = `rgba(110,90,70,${0.08 + 0.1 * hash(k, 1, 8)})`; g.lineWidth = 0.7; const x = hash(k, 2, 8) * n, y = hash(k, 3, 8) * n, an = hash(k, 4, 8) * 3.14, l = 4 + hash(k, 5, 8) * 18; g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(an) * l, y + Math.sin(an) * l); g.stroke(); } }), 'multiply', 0.55);
      return; }
    if (mode === 'clay') {    // 黏土：柔和投影 + 左上高光、边缘压暗 + 指纹颗粒
      if (!opaque) return plainFill(this, args);
      this.save(); this.shadowColor = 'rgba(40,25,20,0.30)'; this.shadowBlur = 14; this.shadowOffsetY = 7; emit(this, 0); N.fill.apply(this, args); this.restore();
      this.save(); emit(this, 0); N.clip.call(this); this.setTransform(1, 0, 0, 1, 0, 0);
      const cx = bx + bw * 0.34, cy = by + bh * 0.28, R = Math.max(bw, bh) * 0.8; const g = this.createRadialGradient(cx, cy, 0, cx, cy, R); g.addColorStop(0, 'rgba(255,255,255,0.42)'); g.addColorStop(0.45, 'rgba(255,255,255,0.06)'); g.addColorStop(1, 'rgba(30,15,10,0.30)');
      this.fillStyle = g; N.fillRect.call(this, bx - 2, by - 2, bw + 4, bh + 4); this.restore();
      if (size > 40) overlayIn(this, pat(this, 'clay', 192, (g, n) => noiseTex(g, n, 7, [80, 60, 50], 0.0, 0.28)), 'multiply', 0.6);
      return; }
    if (mode === 'chalk') {   // 黑板粉笔：粉彩色 + 粉笔颗粒缺口 + 粉笔描边；大面积半透明背景块不画
      if (a < 0.66 && size > 200) return;
      const pc = mixc(rgb, [255, 255, 255], 0.38);
      plainFill(this, args, rgbS(pc, Math.min(1, rgb[3]) * 0.9));
      if (!opaque) return;
      if (size > 30) overlayIn(this, pat(this, 'chalkgap', 192, (g, n) => noiseTex(g, n, 3, [46, 74, 62], 0.0, 0.75)), 'source-over', 0.55);
      if (!tinyWhite) brush(this, rgbS(mixc(rgb, [255, 255, 255], 0.75), 0.85), 2.0, 2.0, 101, 1.3);
      return; }
    if (mode === 'ink') {     // 国风水墨：淡彩晕染 + 墨线
      const wc = mixc(desat(rgb, 0.35), [250, 245, 232], 0.22);
      this.save(); this.fillStyle = rgbS(wc, Math.min(1, rgb[3]) * 0.92); if (opaque) { this.shadowColor = rgbS(wc, 0.55); this.shadowBlur = 9; } emit(this, 0); N.fill.apply(this, args); this.restore();
      if (!opaque || tinyWhite) return;
      if (size > 50) overlayIn(this, pat(this, 'wash', 256, (g, n) => noiseTex(g, n, 22, [90, 80, 70], 0.0, 0.32)), 'multiply', 0.5);
      brush(this, 'rgba(28,24,22,0.86)', 1.6, 3.6, 101, 1.0);
      return; }
    if (mode === 'kz') {      // Kurzgesagt 式：高饱和纯色 + 左上亮边 + 上亮下暗渐变 + 发光元素辉光；不勾线
      const [h, sa, l] = hsl(rgb);
      if (SK.inBg && a < 0.66 && size > 200) { const hh = (h >= 15 && h < 75) ? 262 : h; const lc = l < 0.35 ? [255, 255, 255] : rgbOf(hh, 0.7, 0.6); this.save(); this.filter = 'blur(36px)'; plainFill(this, args, rgbS(lc, Math.min(0.11, rgb[3] * 0.2))); this.restore(); return; }   // 大块半透明 → 虚化的冷色星云微光
      if (a < 0.3 && l < 0.35) return plainFill(this, args, rgbS([4, 4, 20], Math.min(0.5, rgb[3] * 2.2)));                                                                    // 小阴影 → 更深
      let S = Math.min(0.95, sa * 1.3 + 0.06), L2 = l;
      if (bw > 300 && bh > 300 && l > 0.72) { L2 = 0.3; S = Math.min(0.55, S); }          // 大面积浅色（地板、沙盘、卷轴）压暗，融进夜色
      else if (l > 0.95 && size > 150) { L2 = 0.9; S = 0.3; }                              // 大白卡片降一点亮度
      const hB = l > 0.95 && size > 150 ? 225 : h, base = rgbOf(hB, S, L2);
      if (!opaque) return plainFill(this, args, rgbS(base, rgb[3]));
      const glow = (h >= 38 && h < 72 && L2 > 0.55 && S > 0.5) || (L2 > 0.9 && size < 120);   // 只让尿液、结石高光、星光这类“亮的东西”发光
      this.save(); if (glow) { this.shadowColor = rgbS(base, 0.75); this.shadowBlur = 22; } plainFill(this, args, rgbS(rgbOf(hB, S * 0.85, Math.min(0.93, L2 + 0.17)), rgb[3])); this.restore();
      this.save(); emit(this, 0); N.clip.call(this); const m = this.getTransform(); const off = Math.max(2, Math.min(6, size * 0.025));
      this.setTransform(m.a, m.b, m.c, m.d, m.e + off * 0.7, m.f + off); this.fillStyle = rgbS(base, rgb[3]); emit(this, 0); N.fill.apply(this, args);
      this.setTransform(1, 0, 0, 1, 0, 0); const gr = this.createLinearGradient(0, by, 0, by + bh); gr.addColorStop(0, 'rgba(255,255,255,0.08)'); gr.addColorStop(0.5, 'rgba(255,255,255,0)'); gr.addColorStop(1, 'rgba(8,8,40,0.30)'); this.fillStyle = gr; N.fillRect.call(this, bx - 2, by - 2, bw + 4, bh + 4);
      this.restore(); return; }
    plainFill(this, args);
  };
  P.stroke = function () {
    if (!SK.on || !this.__sk || !this.__sk.subs.length) return N.stroke.call(this);
    const k = sc(this), w = this.lineWidth * k, mode = SK.mode; const rgb = parse(this.strokeStyle);
    if (mode === 'hand') { emit(this, 31, w > 8 ? 0.8 : 1); N.stroke.call(this); if (w <= 8) { this.save(); this.globalAlpha *= 0.45; this.lineWidth *= 0.7; emit(this, 63, 1.3); N.stroke.call(this); this.restore(); } return; }
    this.save();
    if (mode === 'paper') { if (w > 6) { this.shadowColor = 'rgba(70,45,25,0.28)'; this.shadowBlur = 6; this.shadowOffsetY = 4; } emit(this, 31, 0.6); N.stroke.call(this); }
    else if (mode === 'clay') { if (w > 6) { this.shadowColor = 'rgba(40,25,20,0.28)'; this.shadowBlur = 10; this.shadowOffsetY = 5; } emit(this, 31, 0.8); N.stroke.call(this); }
    else if (mode === 'chalk') { if (rgb) this.strokeStyle = rgbS(mixc(rgb, [255, 255, 255], 0.45), rgb[3]); emit(this, 31, 1.1); N.stroke.call(this); if (w <= 10) { this.globalAlpha *= 0.5; this.lineWidth *= 0.6; emit(this, 63, 1.5); N.stroke.call(this); } }
    else if (mode === 'kz') { if (rgb) { const [h, sa, l] = hsl(rgb); const c2 = l < 0.3 && rgb[3] < 0.5 ? [255, 255, 255] : rgbOf(h, Math.min(0.95, sa * 1.3 + 0.06), l); this.strokeStyle = rgbS(c2, rgb[3]); if ((h >= 38 && h < 72 && l > 0.55) || l > 0.92) { this.shadowColor = rgbS(c2, 0.8); this.shadowBlur = 16; } } emit(this, 31, 0); N.stroke.call(this); }
    else if (mode === 'ink') { if (rgb) this.strokeStyle = lum(rgb) < 100 ? 'rgba(28,24,22,0.9)' : rgbS(mixc(desat(rgb, 0.35), [250, 245, 232], 0.22), rgb[3]); emit(this, 31, 1); N.stroke.call(this); }
    else { emit(this, 31); N.stroke.call(this); }
    this.restore();
  };
  P.clip = function (...args) { if (!SK.on || !this.__sk || !this.__sk.subs.length) return N.clip.apply(this, args); emit(this, 0); return N.clip.apply(this, args); };
  P.fillRect = function (x, y, w, h) {
    if (!SK.on) return N.fillRect.call(this, x, y, w, h);
    const k = sc(this), full = Math.abs(w) * k > SK.W * 0.9 && Math.abs(h) * k > SK.H * 0.5;
    if (SK.mode === 'kz' && full && typeof this.fillStyle === 'string') { const hue = kzBg(parse(this.fillStyle) || [255, 244, 226]); this.save(); this.setTransform(1, 0, 0, 1, 0, 0); const g = this.createLinearGradient(0, 0, 0, SK.H); g.addColorStop(0, rgbS(rgbOf(hue, 0.45, 0.10))); g.addColorStop(0.6, rgbS(rgbOf(hue + 12, 0.48, 0.17))); g.addColorStop(1, rgbS(rgbOf(hue + 24, 0.5, 0.22))); this.fillStyle = g; N.fillRect.call(this, 0, 0, SK.W, SK.H);
      this.fillStyle = pat(this, 'stars', 512, (g2, n) => { for (let k = 0; k < 120; k++) { const x = hash(k, 1, 21) * n, y = hash(k, 2, 21) * n, r = 0.6 + hash(k, 3, 21) * 1.6; g2.fillStyle = `rgba(255,255,255,${0.25 + 0.6 * hash(k, 4, 21)})`; g2.beginPath(); g2.arc(x, y, r, 0, 7); g2.fill(); } }); N.fillRect.call(this, 0, 0, SK.W, SK.H); this.restore(); return; }
    if (SK.mode === 'kz' && typeof this.fillStyle !== 'string' && Math.abs(w) * k > 600) return;
    if (SK.mode === 'chalk' && full) { if (typeof this.fillStyle !== 'string') return; this.save(); this.fillStyle = '#2E4A3E'; N.fillRect.call(this, x, y, w, h); this.restore(); return; }   // 黑板底
    if (SK.mode === 'chalk' && typeof this.fillStyle !== 'string' && Math.abs(w) * k > 600) return;                                                             // 顶部纸色渐变在黑板上不要
    if (typeof this.fillStyle !== 'string' || full) return N.fillRect.call(this, x, y, w, h);
    this.beginPath(); this.rect(x, y, w, h); this.fill();
  };
  // ---------- 水彩纸：纤维纹理 + 颜料沉积斑 + 暗角（整帧叠一次） ----------
  let paperCv = null;
  SK.finish = (c, W, H) => {
    const was = SK.on; SK.on = false;
    if (SK.mode === 'hand') { SK.on = was; return SK.paper(c, W, H); }
    c.save();
    if (SK.mode === 'paper' || SK.mode === 'ink' || SK.mode === 'clay') { const cv = getPaper(W, H); c.globalCompositeOperation = 'multiply'; c.globalAlpha = SK.mode === 'clay' ? 0.45 : SK.mode === 'ink' ? 0.8 : 1; c.drawImage(cv, 0, 0); }
    if (SK.mode === 'kz') { c.globalCompositeOperation = 'screen'; c.globalAlpha = 0.28; c.filter = 'blur(16px)'; c.drawImage(c.canvas, 0, 0); c.filter = 'none'; c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1; const vg = c.createRadialGradient(W / 2, H * 0.42, H * 0.3, W / 2, H * 0.42, H * 0.85); vg.addColorStop(0, 'rgba(0,0,10,0)'); vg.addColorStop(1, 'rgba(0,0,10,0.45)'); c.fillStyle = vg; c.fillRect(0, 0, W, H); }
    if (SK.mode === 'chalk') { c.globalCompositeOperation = 'screen'; c.globalAlpha = 0.5; c.fillStyle = pat(c, 'dust', 256, (g, n) => noiseTex(g, n, 2, [255, 255, 255], 0.0, 0.18)); c.fillRect(0, 0, W, H); c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1; const vg = c.createRadialGradient(W / 2, H * 0.45, H * 0.3, W / 2, H * 0.45, H * 0.8); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,0.35)'); c.fillStyle = vg; c.fillRect(0, 0, W, H); L.fillRR(c, 0, 1700, W, 40, 0, '#7A5A3A'); }
    if (SK.mode === 'ink') { c.globalCompositeOperation = 'source-over'; c.globalAlpha = 0.9; L.fillRR(c, 930, 1080, 92, 92, 10, '#C8332E'); c.globalAlpha = 1; OV.txt(c, '肾', 976, 1128, 62, '#FBEFE2', null, OV.F_TITLE); }
    c.restore(); SK.on = was;
  };
  const getPaper = (W, H) => { SK.paper({ save() {}, restore() {}, drawImage() {}, set globalCompositeOperation(v) {} }, W, H); return paperCv; };
  SK.paper = (c, W, H) => {
    if (!paperCv) { paperCv = document.createElement('canvas'); paperCv.width = W; paperCv.height = H; const g = paperCv.getContext('2d'); const was = SK.on; SK.on = false;
      const id = g.createImageData(W, H); for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = (y * W + x) * 4; const n = 0.55 * vn(x / 3, y / 3, 3) + 0.3 * vn(x / 11, y / 11, 9) + 0.15 * vn(x / 60, y / 60, 17); const v = 236 + n * 16; id.data[i] = v + 4; id.data[i + 1] = v; id.data[i + 2] = v - 10; id.data[i + 3] = 255; }
      g.putImageData(id, 0, 0);
      for (let k = 0; k < 900; k++) { const x = hash(k, 1, 5) * W, y = hash(k, 2, 5) * H, l = 6 + hash(k, 3, 5) * 26, a = hash(k, 4, 5) * Math.PI; g.strokeStyle = `rgba(150,130,110,${0.05 + 0.08 * hash(k, 6, 5)})`; g.lineWidth = 0.8; g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke(); }
      const vg = g.createRadialGradient(W / 2, H * 0.45, H * 0.35, W / 2, H * 0.45, H * 0.8); vg.addColorStop(0, 'rgba(120,90,60,0)'); vg.addColorStop(1, 'rgba(120,90,60,0.22)'); g.fillStyle = vg; g.fillRect(0, 0, W, H);
      SK.on = was; }
    const was = SK.on; SK.on = false; c.save(); c.globalCompositeOperation = 'multiply'; c.drawImage(paperCv, 0, 0); c.restore(); SK.on = was;
  };
})();
if (typeof module !== 'undefined') module.exports = SK; else window.SK = SK;
