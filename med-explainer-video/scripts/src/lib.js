// 扁平元素风 · 可爱版绘图库：缓动 + 几何原语 + 通用脸。角色在 chars.js，解剖在 anat.js。
// 颜色全部取自 storyboard.style.palette（L.P）。画面层不画任何文字。
'use strict';
const L = {};
L.P = null;
L.init = (palette) => { L.P = palette; };
L.ART = false;   // true：角色改用 S3 定稿的矢量木偶（src/puppets.js），接口不变；引擎按 ?art=0 可切回代码版

// ---------- easing ----------
L.clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
L.lerp = (a, b, t) => a + (b - a) * t;
L.seg = (t, a, b) => L.clamp((t - a) / (b - a));
L.easeOut = (x) => 1 - Math.pow(1 - x, 3);
L.easeIn = (x) => x * x * x;
L.easeInOut = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
L.backOut = (x) => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
L.elastic = (x) => (x === 0 || x === 1 ? x : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * (2 * Math.PI) / 3) + 1);
L.pop = (t, a, d = 0.45) => (t < a ? 0 : L.backOut(L.seg(t, a, a + d)));
L.fin = (t, a, d = 0.45) => L.easeOut(L.seg(t, a, a + d));
L.vis = (t, a, b, d = 0.35) => Math.min(L.fin(t, a, d), 1 - L.seg(t, b - d, b));
L.wob = (t, f = 1, a = 1, ph = 0) => Math.sin((t * f + ph) * Math.PI * 2) * a;
L.blink = (t, ph = 0) => { const k = (t + ph) % 3.3; return k < 0.14 ? Math.sin((k / 0.14) * Math.PI) : 0; };
L.squash = (t, t0, amp = 0.25, f = 26, k = 6) => (t < t0 ? 1 : 1 + amp * Math.exp(-(t - t0) * k) * Math.sin((t - t0) * f));
// 阻尼弹簧：x 跟随 target(τ)。每帧从 t-3s 起以 1/240 s 步长积分（帧与帧之间无状态，可并行渲染）
L.spring = (target, t, { k = 160, c = 11, back = 3 } = {}) => { const t0 = Math.max(0, t - back), dt = 1 / 240; let x = target(t0), v = 0; for (let tau = t0; tau < t; tau += dt) { const a = k * (target(tau) - x) - c * v; v += a * dt; x += v * dt; } return x; };
// 事件后的余震：t0 时刻受到一下冲击后的衰减振荡（落地、弹出、碰撞）
L.jolt = (t, t0, amp = 1, f = 3.2, d = 5) => (t < t0 ? 0 : amp * Math.exp(-(t - t0) * d) * Math.sin((t - t0) * f * Math.PI * 2));
L.rand = (seed) => { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; };
L.mix = (c1, c2, t) => { const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)); const a = p(c1), b = p(c2); return '#' + a.map((v, i) => Math.round(L.lerp(v, b[i], L.clamp(t))).toString(16).padStart(2, '0')).join(''); };
L.alpha = (hex, a) => { const v = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)); return `rgba(${v[0]},${v[1]},${v[2]},${a})`; };

// ---------- primitives ----------
L.rr = (c, x, y, w, h, r) => { r = Math.max(0, Math.min(r, w / 2, h / 2)); c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); };
L.circle = (c, x, y, r, fill) => { c.beginPath(); c.arc(x, y, Math.max(0, r), 0, Math.PI * 2); if (fill) { c.fillStyle = fill; c.fill(); } };
L.ring = (c, x, y, r, w, col) => { c.beginPath(); c.arc(x, y, Math.max(0, r), 0, Math.PI * 2); c.lineWidth = w; c.strokeStyle = col; c.stroke(); };
L.ellipse = (c, x, y, rx, ry, fill, rot = 0) => { c.beginPath(); c.ellipse(x, y, Math.max(0, rx), Math.max(0, ry), rot, 0, Math.PI * 2); if (fill) { c.fillStyle = fill; c.fill(); } };
L.fillRR = (c, x, y, w, h, r, fill) => { L.rr(c, x, y, w, h, r); c.fillStyle = fill; c.fill(); };
// 位图插图（Servier 等）：以 (x,y) 为中心、高 h 画出；flip 水平镜像；grey 0..1 渐变成灰（叠一张预先算好的灰度版）。
// 不用 ctx.filter：逐帧变化的滤镜参数会让 Chrome 的 GPU 进程越积越多直到卡死（v9 渲染 8 个页面同时挂起）
L._grey = new WeakMap();
L.greyOf = (im) => { let g = L._grey.get(im); if (g) return g; g = document.createElement('canvas'); g.width = im.width; g.height = im.height; const x = g.getContext('2d'); x.drawImage(im, 0, 0);
  const d = x.getImageData(0, 0, g.width, g.height), p = d.data; for (let i = 0; i < p.length; i += 4) { const v = (0.299 * p[i] + 0.587 * p[i + 1] + 0.114 * p[i + 2]) * 0.92; p[i] = p[i + 1] = p[i + 2] = v; } x.putImageData(d, 0, 0); L._grey.set(im, g); return g; };
L.img = (c, im, x, y, h, o = {}) => { if (!im) return false; const w = (h * im.width) / im.height; c.save(); c.translate(x, y); if (o.flip) c.scale(-1, 1); c.imageSmoothingEnabled = true; c.imageSmoothingQuality = 'high'; c.drawImage(im, -w / 2, -h / 2, w, h);
  if (o.grey > 0) { c.globalAlpha *= Math.min(1, o.grey); c.drawImage(L.greyOf(im), -w / 2, -h / 2, w, h); } c.restore(); return true; };
L.line = (c, pts, w, col, cap = 'round') => { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); c.lineWidth = w; c.strokeStyle = col; c.lineCap = cap; c.lineJoin = 'round'; c.stroke(); };
L.poly = (c, pts, fill) => { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); c.closePath(); if (fill) { c.fillStyle = fill; c.fill(); } };
L.bez = (c, p0, p1, p2, p3, w, col) => { c.beginPath(); c.moveTo(...p0); c.bezierCurveTo(...p1, ...p2, ...p3); c.lineWidth = w; c.strokeStyle = col; c.lineCap = 'round'; c.stroke(); };
L.bezPt = (p0, p1, p2, p3, t) => { const u = 1 - t; return [0, 1].map((k) => u * u * u * p0[k] + 3 * u * u * t * p1[k] + 3 * u * t * t * p2[k] + t * t * t * p3[k]); };
L.shadow = (c, x, y, rx, a = 0.13) => L.ellipse(c, x, y, rx, rx * 0.18, `rgba(59,47,74,${a})`);
L.with = (c, fn, { x = 0, y = 0, s = 1, sx, sy, r = 0, a = 1 } = {}) => { if (a <= 0.001 || (sx ?? s) === 0 || (sy ?? s) === 0) return; c.save(); c.translate(x, y); c.rotate(r); c.scale(sx ?? s, sy ?? s); c.globalAlpha *= Math.min(1, a); fn(c); c.restore(); };
L.star = (c, x, y, r1, r2, n, fill, rot = 0) => { c.beginPath(); for (let i = 0; i < n * 2; i++) { const r = i % 2 ? r2 : r1, a = rot + (i * Math.PI) / n; c.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); } c.closePath(); c.fillStyle = fill; c.fill(); };
// 折线路径：按弧长取点
L.path = (pts) => { const seg = []; let tot = 0; for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); tot += d; }
  return { pts, tot, at: (u) => { let d = L.clamp(u) * tot; for (let i = 0; i < seg.length; i++) { if (d <= seg[i] || i === seg.length - 1) { const k = seg[i] ? d / seg[i] : 0; return [L.lerp(pts[i][0], pts[i + 1][0], k), L.lerp(pts[i][1], pts[i + 1][1], k), Math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0])]; } d -= seg[i]; } return pts[pts.length - 1]; } }; };
L.bezPath = (p0, p1, p2, p3, n = 40) => L.path([...Array(n + 1).keys()].map((i) => L.bezPt(p0, p1, p2, p3, i / n)));

// 纸面底：暖色 + 柔和色块 + 小点点
// 横屏延伸区（engine 在横屏时设 L.EXT = {x0, x1}，设计坐标；竖屏为 null）：背景要铺到的左右边界。场景代码可用 L.XR() / L.XL() 取边界。
L.EXT = null;
L.XR = (W = 1080) => (L.EXT ? L.EXT.x1 : W);                    // 右边界：横屏时 > W
L.XL = () => (L.EXT && L.EXT.x0 < -400 ? L.EXT.x0 : 0);          // 左边界：只在舞台移到右侧时为负（舞台居左时保持原画面）
// 视频人物层（engine 每帧设置；本技能不带口型视频的生成流程，接口保留）：L.HIDE = {who: 'skip'|'faceless'} 让代码画的同一角色让位；L.PIXBG = under 模式的片段画法（L.bg 末尾调用）；
//   L.NOFOOT 场景自己画整幅片段时置 1（页脚淡出不叠）。角色函数开头：const h = L.hide('laozhang'); if (h === 'skip') return; if (h === 'faceless') o = { ...o, noFace: true };
L.HIDE = null; L.PIXBG = null; L.NOFOOT = 0;
L.hide = (who) => ((L.HIDE && L.HIDE[who]) || null);
// 3D 立绘（透明底，tools/cutout.py 抠底裁边并登记 storyboard.assets → A.img）：脚底中点 (x, yFeet)、高 h，脚下一块柔和阴影；呼吸 0.22 Hz、纵向 ±0.5%（慢，不哆嗦）。
// o: a 透明度、flip 水平镜像、bob 上浮 px、sway 轻摆幅度（弧度，0.18 Hz）、pop 出场弹入进度 0..1、shadow:false 不画影。返回立绘矩形 {x0, y0, w, h}；没图返回 null。代替 2D 木偶 / 贴图卡片（10-23 用户：2D 和 3D 混着、卡片像画中画）
L.sprite3d = (c, A, id, x, yFeet, h, o = {}) => { const im = A.img && A.img(id); if (!im) return null; const t = A.t || 0, w = h * im.width / im.height, s = o.pop == null ? 1 : L.backOut(L.clamp(o.pop)); if (s <= 0.001) return null;
  const br = 1 + 0.005 * Math.sin(t * Math.PI * 2 * 0.22 + x * 0.01); c.save(); c.globalAlpha *= o.a ?? 1; c.translate(x, yFeet - (o.bob || 0));
  if (o.shadow !== false) { c.beginPath(); c.ellipse(0, 2, w * 0.34 * s, 16 * s, 0, 0, Math.PI * 2); c.fillStyle = 'rgba(59,47,74,0.15)'; c.fill(); }
  c.rotate((o.sway || 0) * Math.sin(t * Math.PI * 2 * 0.18)); c.scale(s * (o.flip ? -1 : 1), s * br); c.drawImage(im, -w / 2, -h, w, h); c.restore(); return { x0: x - w / 2, y0: yFeet - h, w, h }; };
// 3D 道具图标（透明底，tools/cutout.py 抠底裁边并登记 storyboard.assets → A.img）：中心 (x, y)、长边 size；o: a 透明度、r 旋转、pop 弹入进度 0..1、flip、shadow 底下一块淡影。返回矩形；没图返回 null。
// 解剖（器官、剖面、肾小球等）不许用这个——仍由代码画；只给杯子、试纸、药盒这类道具（10-23 用户：“小素材的 3D 卡通试试”）
const ICT = {};   // icon3d 着色缓存：id|颜色|强度 → 画布
L.icon3d = (c, A, id, x, y, size, o = {}) => { let im = A.img && A.img(id); if (!im) return null;
  if (o.tint) { const key = id + '|' + o.tint + '|' + (o.tintA ?? 0.55); if (!ICT[key]) { const cv = document.createElement('canvas'); cv.width = im.width; cv.height = im.height; const g = cv.getContext('2d'); g.drawImage(im, 0, 0); g.globalCompositeOperation = 'source-atop'; g.globalAlpha = o.tintA ?? 0.55; g.fillStyle = o.tint; g.fillRect(0, 0, cv.width, cv.height); ICT[key] = cv; } im = ICT[key]; }   // o.tint：整体染色（同一个小人棋子染成不同颜色）
  const k = size / Math.max(im.width, im.height), w = im.width * k, h = im.height * k, s = o.pop == null ? 1 : L.backOut(L.clamp(o.pop)); if (s <= 0.001) return null;
  c.save(); c.globalAlpha *= o.a ?? 1; c.translate(x, y); if (o.shadow) { c.beginPath(); c.ellipse(0, h / 2 * s, w * 0.36 * s, 10 * s, 0, 0, Math.PI * 2); c.fillStyle = 'rgba(59,47,74,0.12)'; c.fill(); }
  c.rotate(o.r || 0); c.scale(s * (o.flip ? -1 : 1), s); c.drawImage(im, -w / 2, -h / 2, w, h); c.restore(); return { x0: x - w / 2, y0: y - h / 2, w, h }; };
// 无脸半透明人体轮廓（背面 / 正面通用，不画五官）：以两肾中点 (x, y) 为原点、缩放 s（单位：肾到脚 365、肾到头顶 640）；体内的解剖由场景代码另画。代替“2D 角色身体里画器官”
L.ghostBody = (c, x, y, s, o = {}) => L.with(c, () => { const col = o.col || 'rgba(59,47,74,0.08)', ln = o.line || 'rgba(59,47,74,0.10)';
  c.beginPath(); c.ellipse(0, -545, 92, 104, 0, 0, Math.PI * 2); c.fillStyle = col; c.fill();
  c.beginPath(); c.moveTo(-46, -450); c.lineTo(-46, -410); c.quadraticCurveTo(-210, -400, -232, -330); c.lineTo(-250, 40); c.quadraticCurveTo(-246, 150, -200, 200); c.lineTo(-170, 365); c.lineTo(-30, 365); c.lineTo(-14, 230); c.lineTo(14, 230); c.lineTo(30, 365); c.lineTo(170, 365); c.lineTo(200, 200); c.quadraticCurveTo(246, 150, 250, 40); c.lineTo(232, -330); c.quadraticCurveTo(210, -400, 46, -410); c.lineTo(46, -450); c.closePath(); c.fillStyle = col; c.fill();
  c.lineWidth = 10; c.strokeStyle = ln; c.beginPath(); c.moveTo(-190, -250); c.quadraticCurveTo(0, -60, 190, -250); c.stroke(); c.beginPath(); c.moveTo(-200, 120); c.quadraticCurveTo(-170, 230, -50, 245); c.moveTo(200, 120); c.quadraticCurveTo(170, 230, 50, 245); c.stroke();
  c.fillStyle = ln; c.fillRect(-9, -420, 18, 640); }, { x, y, s });
// 3D 片段画成圆角卡片，替换场景里某个贴图 / 木偶的位置（media 条目 pix.layout 'none'，由场景代码按自己的出场条件调用）：脚底 (x, yFeet)、高 h；有帧返回卡片矩形 {x0, y0, w, h}（右缘不越 safe.right_x，场景里跟卡片走的道具按它定位），没帧返回 false
// 右安全线（layout.json safe.right_x，屏幕像素）换算到画布当前坐标系的 x：按 c 的当前变换（舞台映射、L.with 嵌套缩放都算进去，假定没旋转），先扣掉本帧画面呼吸（ENGINE.drift）再按最坏呼吸（缩放 1.02、平移 6 px，见 engine.js）留边——卡片不越线，也不跟着呼吸反向漂。横屏或没配 safe 时不限；镜像坐标系里不限
L.safeRight = (c) => { const LY = typeof OV !== 'undefined' && OV.LAYOUT, rx = LY && LY.safe && LY.safe.right_x; if (rx == null || !LY.stage || LY.stage.x != null) return 1e9;
  const W = LY.width || 1080, E = typeof ENGINE !== 'undefined' ? ENGINE : {}, [ds, dx] = E.drift || [1, 0], R = W / 2 + (rx - 6 - W / 2) / 1.02;   // R：未呼吸画面里的安全线
  if (c && c.getTransform) { const M = c.getTransform(), k = c.canvas.width / W, a = M.a / k / ds, e = (M.e / k - W / 2 - dx) / ds + W / 2; return a > 1e-6 ? (R - e) / a : 1e9; }
  return E.stageK ? W / 2 + (R - W / 2) / E.stageK() : 1e9; };
L.pixCard = (c, A, id, x, yFeet, h, o = {}) => { const pv = A.media && A.media(id); if (!pv) return false;
  const w = h * (o.aspect || 0.8); x = Math.min(x, (o.right ?? L.safeRight(c)) - w / 2 - 3); const x0 = x - w / 2, y0 = yFeet - h * 1.02, k = Math.max(w / pv.width, h / pv.height) * (o.zoom || 1.12), R = o.rr ?? 36;
  L.fillRR(c, x0 + 8, y0 + 12, w, h, R, 'rgba(59,47,74,0.14)'); c.save(); L.rr(c, x0, y0, w, h, R); c.clip(); c.drawImage(pv, x - pv.width * k / 2, y0 - pv.height * k * (o.top ?? 0.03), pv.width * k, pv.height * k); c.restore();
  L.rr(c, x0, y0, w, h, R); c.lineWidth = 6; c.strokeStyle = o.ring || '#FFFFFF'; c.stroke(); return { x0, y0, w, h }; };
// 背景：纯色底 + 几道很淡的斜向光带（缓慢平移）+ 规则点阵。col1 底色、col2 花纹色；seed 决定光带的位置和宽窄（每场给不同的 seed，画面不重样）
const DOTS = {};   // 点阵图案缓存：颜色 → CanvasPattern
L.bg = (c, W, H, col1, col2, seed = 3, t = 0) => {
  if (typeof SK !== 'undefined') SK.inBg = true;
  c.fillStyle = col1; c.fillRect(-2000, -2000, W + 4000, H + 4000);   // 多铺：场景层会被整体缩放 / 平移（engine），底色要盖满画布（横屏铺满整幅）
  const R = L.rand(seed), x0 = L.EXT ? Math.min(-400, L.EXT.x0 - 200) : -400, x1 = L.EXT ? Math.max(W + 400, L.EXT.x1 + 200) : W + 400;
  c.save(); c.translate(W / 2, H / 2); c.rotate(-0.44);   // 斜向光带：以画面中心为轴转 25°，带子足够长，横屏两侧也盖得到
  for (let i = 0; i < 5; i++) { const off = -1180 + i * 520 + R() * 200 + 16 * Math.sin(t * 0.22 + i * 1.7), wd = 70 + R() * 170; c.fillStyle = L.alpha(col2, 0.42 + 0.3 * R()); c.fillRect(-4000, off, 8000, wd); }
  c.restore();
  if (typeof document !== 'undefined') {   // 点阵：每 56 px 一个小圆点
    if (!DOTS[col2]) { const cv = document.createElement('canvas'); cv.width = cv.height = 56; const g = cv.getContext('2d'); g.fillStyle = col2; g.beginPath(); g.arc(28, 28, 3, 0, 7); g.fill(); DOTS[col2] = cv; }
    c.save(); c.globalAlpha *= 0.8; c.fillStyle = c.createPattern(DOTS[col2], 'repeat'); c.fillRect(x0, -400, x1 - x0, H + 800); c.restore();
  }
  if (L.PIXBG) L.PIXBG(c);   // 口型视频 under 模式：画在背景之上、场景前景之下
  if (typeof SK !== 'undefined') SK.inBg = false;
};
L.grain = (() => { let cache = null; return (c, W, H) => {
  if (!cache) { cache = document.createElement('canvas'); cache.width = 256; cache.height = 256; const g = cache.getContext('2d'); const id = g.createImageData(256, 256); const R = L.rand(11); for (let i = 0; i < id.data.length; i += 4) { const v = R() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 12; } g.putImageData(id, 0, 0); }
  c.save(); c.fillStyle = c.createPattern(cache, 'repeat'); c.fillRect(0, 0, W, H); c.restore(); }; })();

// 通用小表情：汗滴、星星、怒气、问号泡泡
L.sweat = (c, x, y, s = 1, col) => L.with(c, () => { c.beginPath(); c.moveTo(0, -22); c.bezierCurveTo(16, -2, 16, 18, 0, 18); c.bezierCurveTo(-16, 18, -16, -2, 0, -22); c.fillStyle = col || '#8FD3F0'; c.fill(); L.ellipse(c, -5, 4, 4, 7, 'rgba(255,255,255,0.6)'); }, { x, y, s });
L.sparkle = (c, x, y, s = 1, col = '#FFFFFF', rot = 0) => L.star(c, x, y, 26 * s, 7 * s, 4, col, rot);
L.anger = (c, x, y, s = 1, col) => L.with(c, () => { c.lineWidth = 9; c.strokeStyle = col || L.P.red; c.lineCap = 'round'; for (const r of [0, 1, 2, 3]) { c.save(); c.rotate(r * Math.PI / 2); c.beginPath(); c.moveTo(6, 6); c.quadraticCurveTo(22, 6, 22, 22); c.stroke(); c.restore(); } }, { x, y, s });
L.zigzag = (c, x, y, len, amp, n, w, col) => { const pts = []; for (let i = 0; i <= n; i++) pts.push([x + (i / n) * len, y + (i % 2 ? -amp : amp)]); L.line(c, pts, w, col); };

// ---------- 通用脸：mood = smile | grin | shock | pain | whine | smug | grumpy | happy | worried | cry ----------
// 以 (0,0) 为脸中心，r 为脸的尺度。col 为五官颜色。矢量木偶用：es 眼睛放大倍数，ex/ey/my 改眼距、眼高、嘴高（单位 r）。
L.face = (c, r, o = {}) => {
  const P = L.P, ink = o.ink || P.ink, m = o.mood || 'smile', bl = 1 - (o.blink || 0) * 0.92;
  const lx = (o.look?.[0] || 0) * r * 0.1, ly = (o.look?.[1] || 0) * r * 0.1, ex = r * (o.ex ?? 0.36), ey = -r * (o.ey ?? 0.08), es = o.es || 1;
  c.save(); c.lineCap = 'round'; c.lineJoin = 'round';
  // 腮红
  if (!o.noBlush) for (const s of [-1, 1]) L.ellipse(c, s * r * 0.58, r * 0.22, r * 0.15, r * 0.09, 'rgba(255,120,130,0.42)');
  const dotEye = (s, rx = r * 0.11 * es, ry = r * 0.14 * es) => { L.ellipse(c, s * ex + lx, ey + ly, rx, ry * bl, ink); if (bl > 0.5) L.circle(c, s * ex + lx + rx * 0.35, ey + ly - ry * 0.4, rx * 0.38, '#FFFFFF'); };
  const arcEye = (s, up = true) => { c.beginPath(); if (up) c.arc(s * ex, ey + r * 0.06 * es, r * 0.13 * es, 1.1 * Math.PI, 1.9 * Math.PI); else c.arc(s * ex, ey - r * 0.06 * es, r * 0.13 * es, 0.1 * Math.PI, 0.9 * Math.PI); c.lineWidth = r * 0.07 * Math.sqrt(es); c.strokeStyle = ink; c.stroke(); };
  const xEye = (s) => { const k = r * 0.1; L.line(c, [[s * ex - k, ey - k], [s * ex + k, ey + k]], r * 0.065, ink); L.line(c, [[s * ex + k, ey - k], [s * ex - k, ey + k]], r * 0.065, ink); };
  const by = ey - r * (0.13 + 0.14 * es), bw = r * 0.14 * Math.sqrt(es);
  const brow = (s, tilt, dy = 0) => L.line(c, [[s * ex - bw, by + dy - s * tilt * r * 0.08], [s * ex + bw, by + dy + s * tilt * r * 0.08]], r * 0.06 * Math.sqrt(es), ink);
  if (m === 'smile' || m === 'happy') { if (m === 'happy') { arcEye(-1); arcEye(1); } else { dotEye(-1); dotEye(1); } }
  else if (m === 'grin' || m === 'smug') { for (const s of [-1, 1]) { L.ellipse(c, s * ex + lx, ey + ly + r * 0.02 * es, r * 0.12 * es, r * 0.1 * es * bl, ink); L.fillRR(c, s * ex - r * 0.17 * es, ey - r * 0.12 * es, r * 0.34 * es, r * 0.1 * es, r * 0.04 * es, o.skin || P.stone); L.circle(c, s * ex + lx + r * 0.04 * es, ey + ly, r * 0.035 * es, '#FFFFFF'); } brow(-1, -1, -r * 0.02); brow(1, -1, -r * 0.02); }
  else if (m === 'shock') { for (const s of [-1, 1]) { L.circle(c, s * ex, ey, r * 0.17 * es, '#FFFFFF'); L.circle(c, s * ex, ey, r * 0.17 * es * 0.999, null); c.lineWidth = r * 0.04 * Math.sqrt(es); c.strokeStyle = ink; c.stroke(); L.circle(c, s * ex + lx * 0.5, ey + ly * 0.5, r * 0.07 * es, ink); } brow(-1, 1, -r * 0.1); brow(1, 1, -r * 0.1); }
  else if (m === 'pain') { for (const s of [-1, 1]) { c.beginPath(); c.moveTo(s * ex - s * r * 0.13 * es, ey - r * 0.1 * es); c.lineTo(s * ex + s * r * 0.1 * es, ey); c.lineTo(s * ex - s * r * 0.13 * es, ey + r * 0.1 * es); c.lineWidth = r * 0.07 * Math.sqrt(es); c.strokeStyle = ink; c.stroke(); } brow(-1, 1.6, 0); brow(1, 1.6, 0); }
  else if (m === 'whine' || m === 'cry') { arcEye(-1, false); arcEye(1, false); brow(-1, 1.4, 0); brow(1, 1.4, 0); if (m === 'cry') for (const s of [-1, 1]) L.sweat(c, s * ex, ey + r * 0.3, r * 0.006, '#8FD3F0'); }
  else if (m === 'grumpy') { for (const s of [-1, 1]) { if (o.sclera) L.ellipse(c, s * ex, ey + r * 0.03 * es, r * 0.16 * es, r * 0.11 * es * Math.max(bl, 0.15), '#FFFFFF'); L.ellipse(c, s * ex + lx, ey + ly + r * 0.03 * es, r * (o.sclera ? 0.065 : 0.1) * es, r * (o.sclera ? 0.075 : 0.08) * es * bl, ink); } const gw = es; L.line(c, [[-ex - r * 0.18 * gw, ey - r * 0.22 * gw], [-ex + r * 0.14 * gw, ey - r * 0.1 * gw]], r * 0.11 * Math.sqrt(es), ink); L.line(c, [[ex + r * 0.18 * gw, ey - r * 0.22 * gw], [ex - r * 0.14 * gw, ey - r * 0.1 * gw]], r * 0.11 * Math.sqrt(es), ink); }
  else if (m === 'worried') { dotEye(-1); dotEye(1); brow(-1, 1.3, 0); brow(1, 1.3, 0); }
  // 嘴
  const my = r * (o.my ?? 0.3), open = o.talk ? (0.35 + 0.65 * Math.abs(Math.sin(o.talk * 18))) : 0;
  c.lineWidth = r * 0.065; c.strokeStyle = ink;
  // 按语音口型画嘴（A 啊 / E 诶 / I 衣 / O 哦 / U 乌 / M 闭），开合幅度跟配音音量
  if (o.mouth && o.mouth.shape && (o.mouth.shape !== 'M' || o.mouth.open === 0)) {
    const v = o.mouth.shape, q = Math.max(0.12, Math.min(1, o.mouth.open)), dk = '#7A2E3A';
    const dims = { A: [0.27, 0.10 + 0.26 * q], E: [0.30, 0.07 + 0.15 * q], I: [0.32, 0.04 + 0.08 * q], O: [0.17, 0.12 + 0.17 * q], U: [0.12, 0.09 + 0.10 * q], M: [0.22, 0] }[v] || [0.25, 0.1 * q];
    if (v === 'M') { c.beginPath(); c.moveTo(-r * dims[0], my); c.quadraticCurveTo(0, my + r * 0.05, r * dims[0], my); c.stroke(); }
    else { const w = r * dims[0], h = r * dims[1]; c.beginPath(); c.ellipse(0, my + h * 0.3, w, h, 0, 0, Math.PI * 2); c.fillStyle = dk; c.fill();
      if (v === 'A' || v === 'E') { c.save(); c.clip(); L.ellipse(c, 0, my + h * 1.0, w * 0.6, h * 0.5, '#F07A88'); if (o.teeth !== false) L.fillRR(c, -w * 0.7, my + h * 0.3 - h - 1, w * 1.4, h * 0.35, 3, '#FFFFFF'); c.restore(); }
      if (v === 'I') { c.save(); c.clip(); L.fillRR(c, -w, my + h * 0.3 - h, w * 2, h * 0.9, 2, '#FFFFFF'); c.restore(); } }
    c.restore(); return;
  }
  if (m === 'smile') { if (open > 0.05) { L.ellipse(c, 0, my + r * 0.02, r * 0.13, r * 0.11 * open, '#9A3A4A'); } else { c.beginPath(); c.arc(0, my - r * 0.08, r * 0.15, 0.2 * Math.PI, 0.8 * Math.PI); c.stroke(); } }
  else if (m === 'happy') { c.beginPath(); c.moveTo(-r * 0.2, my - r * 0.05); c.quadraticCurveTo(0, my + r * 0.3, r * 0.2, my - r * 0.05); c.closePath(); c.fillStyle = '#9A3A4A'; c.fill(); L.ellipse(c, 0, my + r * 0.12, r * 0.08, r * 0.05, '#F07A88'); }
  else if (m === 'grin' || m === 'smug') { c.beginPath(); c.moveTo(-r * 0.3, my - r * 0.08); c.quadraticCurveTo(0, my + r * (m === 'grin' ? 0.28 : 0.14), r * 0.3, my - r * 0.14); c.quadraticCurveTo(0, my + r * 0.04, -r * 0.3, my - r * 0.08); c.fillStyle = '#7A2E3A'; c.fill(); if (m === 'grin') { for (const k of [-1, 0, 1]) L.poly(c, [[k * r * 0.1 - r * 0.045, my - r * 0.05 - k * r * 0.01], [k * r * 0.1 + r * 0.045, my - r * 0.06 - k * r * 0.01], [k * r * 0.1, my + r * 0.04]], '#FFFFFF'); } }
  else if (m === 'shock') { L.ellipse(c, 0, my + r * 0.04, r * 0.11, r * (0.14 + 0.05 * open), '#7A2E3A'); }
  else if (m === 'pain') { L.fillRR(c, -r * 0.24, my - r * 0.06, r * 0.48, r * 0.16, r * 0.06, '#FFFFFF'); c.lineWidth = r * 0.045; L.rr(c, -r * 0.24, my - r * 0.06, r * 0.48, r * 0.16, r * 0.06); c.stroke(); L.line(c, [[-r * 0.24, my + r * 0.02], [r * 0.24, my + r * 0.02]], r * 0.03, ink); }
  else if (m === 'whine' || m === 'cry') { c.beginPath(); c.moveTo(-r * 0.22, my + r * 0.1); c.quadraticCurveTo(0, my - r * 0.18 - open * r * 0.08, r * 0.22, my + r * 0.1); c.quadraticCurveTo(0, my - r * 0.02, -r * 0.22, my + r * 0.1); c.fillStyle = '#7A2E3A'; c.fill(); }
  else if (m === 'grumpy') { c.beginPath(); c.moveTo(-r * 0.16, my + r * 0.04); c.quadraticCurveTo(0, my - r * 0.06, r * 0.16, my + r * 0.04); c.stroke(); }
  else if (m === 'worried') { c.beginPath(); c.moveTo(-r * 0.14, my + r * 0.02); c.quadraticCurveTo(-r * 0.05, my - r * 0.06, 0, my + r * 0.02); c.quadraticCurveTo(r * 0.05, my + r * 0.08, r * 0.14, my); c.stroke(); }
  c.restore();
};


if (typeof module !== 'undefined') module.exports = L; else window.L = L;
