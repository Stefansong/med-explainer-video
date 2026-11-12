// 示意图（本集自有，代码手绘，不用生图）：坐着量血压的人，正面观，不画五官——躯干、心脏、绑着袖带的上臂、平放在桌面上的前臂、桌子和血压计。
// 约定：AN.xxx(c, x, y, s, o)，(x, y) = 胸口正中，s = 1 时肩宽约 320、上臂长约 233（按 30 cm 折算，1 cm ≈ 7.8）、整体高约 800（头顶 −370，桌子底 +450）；颜色取 L.P（storyboard.style.palette），画面零文字。
// 核对清单见 storyboard.anatomy_checks：正面观人物的左侧在画面右侧，心脏在中线偏画面右；袖带下缘在肘窝上方约两横指（2.5 cm ≈ 20）；上臂中点与心脏在同一条水平线上。
'use strict';
const AN = {};
(() => {
  const P = () => L.P;
  // 关键点（局部坐标），场景代码用它们叠加脉动圈、水平线：L.with(c, …, {x, y, s}) 或 x + AN.HEART[0] * s
  AN.SHOULDER = [-158, -118];   // 画面左侧的肩（人物的右肩）
  AN.ELBOW = [-196, 112];       // 肘（肘窝在它的内侧）
  AN.MID = [-177, -3];          // 上臂中点 = 肩和肘的中点
  AN.HEART = [46, -6];          // 心脏中心：胸部中线偏画面右（人物的左侧）
  AN.TABLE_Y = 142;             // 桌面的高度：前臂平放在上面
  const along = (k) => [L.lerp(AN.SHOULDER[0], AN.ELBOW[0], k), L.lerp(AN.SHOULDER[1], AN.ELBOW[1], k)];   // 上臂上从肩（0）到肘（1）的点
  const heart = (c, x, y, s, col, colD) => L.with(c, () => { c.beginPath(); c.moveTo(0, 62); c.bezierCurveTo(-92, 2, -72, -82, 0, -40); c.bezierCurveTo(72, -82, 92, 2, 0, 62); c.fillStyle = col; c.fill();
    c.lineWidth = 6; c.strokeStyle = colD; c.stroke(); L.ellipse(c, -30, -28, 14, 9, 'rgba(255,255,255,0.55)', -0.5); }, { x, y, s });
  // o: arm 0..1 手臂和袖带出现的进度；beat 心跳用的时间（秒）；monitor false 不画血压计
  AN.seated = (c, x, y, s = 1, o = {}) => L.with(c, () => {
    const p = P(), body = p.body || '#CFD8E6', bodyD = p.body_dark || '#AEBBD0', wood = p.wood || '#C9A77C', woodD = p.wood_dark || '#B08D62', cuff = p.cuff || '#7F93B2', cuffL = p.cuff_light || '#A9B8D0', arm = o.arm ?? 1;
    // 椅背（在身后）
    L.fillRR(c, -146, -64, 292, 360, 34, L.alpha(woodD, 0.5));
    // 另一侧的手臂（画面右）：自然下垂，手放在腿上，被桌子挡住
    L.line(c, [[158, -116], [188, 96], [150, 230]], 60, bodyD);
    // 躯干：肩宽 320，往下略收；脖子；头（不画五官）
    c.beginPath(); c.moveTo(-160, -100); c.bezierCurveTo(-160, -150, -112, -168, -60, -170); c.lineTo(60, -170); c.bezierCurveTo(112, -168, 160, -150, 160, -100); c.lineTo(140, 300); c.lineTo(-140, 300); c.closePath(); c.fillStyle = body; c.fill();
    L.fillRR(c, -34, -212, 68, 64, 20, bodyD); L.circle(c, 0, -284, 86, body);
    // 心脏：轻轻跳动
    heart(c, AN.HEART[0], AN.HEART[1], 0.62 * (1 + 0.05 * Math.sin((o.beat || 0) * 6.5)), p.heart || p.red, p.heart_dark || p.red_dark);
    // 桌子（在身前，挡住下半身）：一块前挡板 + 桌面
    L.fillRR(c, -350, AN.TABLE_Y + 18, 600, 290, 14, L.mix(wood, '#FFFFFF', 0.28)); L.fillRR(c, -380, AN.TABLE_Y, 660, 38, 12, woodD);
    // 血压计：白盒子、空白屏幕、两个按钮（不画读数）
    if (o.monitor !== false) { L.fillRR(c, 96, AN.TABLE_Y - 96, 138, 98, 18, '#FFFFFF'); L.fillRR(c, 110, AN.TABLE_Y - 84, 110, 50, 10, '#DCE3EC'); L.circle(c, 138, AN.TABLE_Y - 18, 8, p.red); L.circle(c, 166, AN.TABLE_Y - 18, 8, p.water_dark); }
    if (arm <= 0.01) return;
    c.save(); c.globalAlpha *= L.clamp(arm);
    // 量血压的手臂（画面左）：上臂从肩到肘，前臂平放在桌面上伸向血压计
    const hand = [-64, AN.TABLE_Y - 24];
    L.line(c, [AN.SHOULDER, AN.ELBOW], 66, bodyD); L.line(c, [AN.ELBOW, hand], 54, bodyD); L.circle(c, hand[0] + 6, hand[1], 30, bodyD);
    // 袖带：宽约 12 cm（93），下缘在肘窝上方约 2.5 cm（20）——从肩往下 0.515 到 0.914 这一段
    const a0 = along(0.515), a1 = along(0.914), ang = Math.atan2(a1[1] - a0[1], a1[0] - a0[0]), len = Math.hypot(a1[0] - a0[0], a1[1] - a0[1]);
    L.with(c, () => { L.fillRR(c, 0, -43, len, 86, 16, cuff); L.fillRR(c, len * 0.34, -43, 12, 86, 4, cuffL); L.fillRR(c, len * 0.62, -43, 12, 86, 4, cuffL); }, { x: a0[0], y: a0[1], r: ang });
    // 气管：从袖带下缘绕到桌上的血压计
    if (o.monitor !== false) L.bez(c, [a1[0] + 30, a1[1] - 6], [-60, AN.TABLE_Y - 120], [40, AN.TABLE_Y - 20], [98, AN.TABLE_Y - 50], 9, cuff);
    // 上臂中点：一个小白点（水平线从这里出发）
    L.circle(c, AN.MID[0], AN.MID[1], 11, '#FFFFFF'); L.circle(c, AN.MID[0], AN.MID[1], 6, p.water_dark);
    c.restore();
  }, { x, y, s });
})();
if (typeof module !== 'undefined') module.exports = AN; else window.AN = AN;
