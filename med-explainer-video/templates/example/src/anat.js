// 解剖图（本集自有，代码手绘，不用生图）：右肾冠状剖面 + 输尿管 + 膀胱，正面观。
// 约定：AN.xxx(c, x, y, s, o)，(x, y) = 肾的中心，s = 1 时肾高约 400；颜色取 L.P（storyboard.style.palette），画面零文字。
// 核对清单见 storyboard.anatomy_checks：肾门朝内侧（画面右）；肾盏 → 肾盂 → 输尿管；输尿管向下略向内进膀胱；梗阻以上扩张、以下不扩张。
'use strict';
const AN = {};
(() => {
  // 肾轮廓：蚕豆形，外侧缘（左）凸，内侧缘（右）中部凹进去 = 肾门
  const kidneyPath = (c, k = 1) => { c.beginPath(); c.moveTo(10 * k, -200 * k);
    c.bezierCurveTo(-120 * k, -205 * k, -150 * k, -80 * k, -150 * k, 0); c.bezierCurveTo(-150 * k, 90 * k, -115 * k, 205 * k, 5 * k, 200 * k);
    c.bezierCurveTo(95 * k, 197 * k, 120 * k, 120 * k, 92 * k, 62 * k); c.bezierCurveTo(74 * k, 30 * k, 74 * k, -30 * k, 92 * k, -62 * k);
    c.bezierCurveTo(122 * k, -120 * k, 100 * k, -196 * k, 10 * k, -200 * k); c.closePath(); };
  // 肾锥体（尖朝肾窦）与对应的肾盏杯口：[锥体底中心 x, y, 尖端 x, y]
  const PYR = [[-52, -150, -8, -92], [-112, -82, -42, -46], [-126, 4, -50, 4], [-112, 88, -42, 50], [-50, 152, -8, 96]];
  const PELVIS = [58, 4];      // 肾盂中心（肾门处）
  const UPJ = [108, 62];       // 肾盂输尿管连接处
  // 输尿管中线：从 UPJ 向下、略向内，进膀胱（三段贝塞尔的控制点，肾坐标系）
  const URE = [UPJ, [118, 170], [168, 270], [178, 392]];
  const BLAD = [222, 462];     // 膀胱中心（输尿管从后上方斜着进膀胱壁）
  AN.STUCK = L.bezPt(URE[0], URE[1], URE[2], URE[3], 0.3);   // 嵌顿点：输尿管上段
  AN.CALYX = [PYR[4][2] + 14, PYR[4][3] - 4];                 // 下肾盏（结石形成处）
  // 结石路径 u：0 = 下肾盏，0.5 = 肾盂，1 = 输尿管上段嵌顿点
  AN.stonePos = (u) => { u = L.clamp(u); if (u < 0.5) { const k = L.easeInOut(u / 0.5); return [L.lerp(AN.CALYX[0], PELVIS[0] + 6, k), L.lerp(AN.CALYX[1], PELVIS[1] + 14, k)]; }
    const k = L.easeInOut((u - 0.5) / 0.5), a = [PELVIS[0] + 6, PELVIS[1] + 14]; const m = [(a[0] + UPJ[0]) / 2 + 8, (a[1] + UPJ[1]) / 2];
    return k < 0.5 ? [L.lerp(a[0], m[0], k * 2), L.lerp(a[1], m[1], k * 2)] : [L.lerp(m[0], AN.STUCK[0], k * 2 - 1), L.lerp(m[1], AN.STUCK[1], k * 2 - 1)]; };

  // o: dilate 0–1 梗阻以上（肾盏、肾盂、嵌顿点以上的输尿管）扩张程度；urine 尿液颜色（浓 → 深黄）；t 时间（只用于轻微的蠕动）
  AN.tract = (c, x, y, s = 1, o = {}) => L.with(c, () => { const P = L.P, d = L.clamp(o.dilate || 0), ur = o.urine || P.tube;
    // 膀胱
    c.beginPath(); c.moveTo(BLAD[0] - 92, BLAD[1] - 30); c.bezierCurveTo(BLAD[0] - 96, BLAD[1] - 96, BLAD[0] + 96, BLAD[1] - 96, BLAD[0] + 92, BLAD[1] - 30);
    c.bezierCurveTo(BLAD[0] + 96, BLAD[1] + 44, BLAD[0] + 52, BLAD[1] + 86, BLAD[0], BLAD[1] + 88); c.bezierCurveTo(BLAD[0] - 52, BLAD[1] + 86, BLAD[0] - 96, BLAD[1] + 44, BLAD[0] - 92, BLAD[1] - 30); c.closePath();
    c.fillStyle = P.bladder; c.fill(); c.lineWidth = 10; c.strokeStyle = L.mix(P.bladder, P.kidney_dark, 0.45); c.stroke();
    L.ellipse(c, BLAD[0], BLAD[1] + 8, 62, 48, L.alpha(P.tube, 0.75)); L.ellipse(c, BLAD[0] - 26, BLAD[1] - 44, 30, 12, 'rgba(255,255,255,0.35)', -0.3);
    // 输尿管：嵌顿点以下正常粗细，以上随 d 变粗
    const wN = 13, wUp = wN + 15 * d, cut = 0.3;
    const seg = (t0, t1, w, col) => { const pts = []; for (let k = 0; k <= 24; k++) pts.push(L.bezPt(URE[0], URE[1], URE[2], URE[3], L.lerp(t0, t1, k / 24))); L.line(c, pts, w, col); };
    seg(cut, 1, wN + 8, P.tube_dark); seg(cut, 1, wN, P.tube); seg(0, cut, wUp + 8, P.tube_dark); seg(0, cut, wUp, ur);
    // 肾：包膜 → 皮质 → 锥体 → 肾窦脂肪 → 肾盏肾盂
    kidneyPath(c, 1); c.fillStyle = P.kidney_dark; c.fill(); kidneyPath(c, 0.955); c.fillStyle = P.kidney; c.fill();
    c.save(); kidneyPath(c, 0.955); c.clip();
    c.beginPath(); c.moveTo(96, -70); c.bezierCurveTo(20, -120, -70, -70, -70, 2); c.bezierCurveTo(-70, 76, 20, 124, 96, 72); c.closePath(); c.fillStyle = P.sinus; c.fill();   // 肾窦
    for (const [bx, by, ax, ay] of PYR) { const dx = ax - bx, dy = ay - by, n = Math.hypot(dx, dy), px = -dy / n, py = dx / n, hw = 40;   // 锥体：底宽 80 的圆角三角
      c.beginPath(); c.moveTo(bx + px * hw, by + py * hw); c.quadraticCurveTo(bx - dx * 0.16, by - dy * 0.16, bx - px * hw, by - py * hw); c.lineTo(ax, ay); c.closePath(); c.fillStyle = P.medulla; c.fill();
      for (let k = -2; k <= 2; k++) L.line(c, [[bx + px * k * 13, by + py * k * 13], [ax + px * k * 2, ay + py * k * 2]], 2, L.alpha(P.kidney, 0.35)); }
    c.restore();
    // 肾盏（杯口朝锥体尖）+ 漏斗 → 肾盂 → UPJ；扩张时整体变粗、杯口变钝
    const cw = 10 + 13 * d;
    for (const [, , ax, ay] of PYR) { L.line(c, [[ax + 6, ay + (ay < 0 ? 4 : ay > 0 ? -4 : 0)], PELVIS], cw + 8, P.tube_dark); }
    L.ellipse(c, PELVIS[0], PELVIS[1], 30 + 14 * d, 27 + 15 * d, P.tube_dark); L.line(c, [PELVIS, [86, 32], UPJ], wUp + 10, P.tube_dark);
    for (const [, , ax, ay] of PYR) { L.line(c, [[ax + 6, ay + (ay < 0 ? 4 : ay > 0 ? -4 : 0)], PELVIS], cw, ur); L.circle(c, ax + 3, ay, cw * 0.9, P.tube_dark); L.circle(c, ax + 3, ay, cw * 0.9 - 3.5, ur); }
    L.ellipse(c, PELVIS[0], PELVIS[1], 26 + 14 * d, 23 + 15 * d, ur); L.line(c, [PELVIS, [86, 32], UPJ], wUp + 3, ur);
    L.ellipse(c, -96, -92, 16, 44, 'rgba(255,255,255,0.22)', 0.5);   // 皮质高光
  }, { x, y, s });

  // 结石：不规则多面小块。r 半径（肾坐标系），画在 AN.tract 同一坐标系里：L.with(c, () => AN.stone(c, px, py, r), {x, y, s})
  AN.stone = (c, px, py, r, seed = 7) => { if (r <= 0.5) return; const R = L.rand(seed), pts = []; for (let k = 0; k < 9; k++) { const a = k / 9 * Math.PI * 2, rr = r * (0.78 + 0.34 * R()); pts.push([px + Math.cos(a) * rr, py + Math.sin(a) * rr]); }
    L.poly(c, pts.map(([u, v]) => [u + 2, v + 3]), 'rgba(59,47,74,0.25)'); L.poly(c, pts, L.P.crystal); L.poly(c, pts.slice(0, 4).concat([[px, py]]), L.alpha('#FFFFFF', 0.22)); };
})();
if (typeof module !== 'undefined') module.exports = AN; else window.AN = AN;
