// 样例专题《水喝少了，小心肾结石》的各场动画。照着这个文件写自己的片子：
//   每场一个函数 SC.<场景 id> = (c, A) => {…}：c 是画布，A 是本场的上下文。
//   A.t 场内秒；A.T 本场时长；A.cue('名字') storyboard 里声明的画面事件时刻；A.lab(k) 第 k 张字卡出现的时刻；A.ln(i) 第 i 句台词 {start, end}。
//   坐标：宽 1080，主舞台 y 236–1236（竖屏）。画面里不写字，中文都在 storyboard 的字幕和字卡里。
//   每一帧只由时间 A.t 决定：不要用 Math.random()（用 L.rand(seed)）、不要用 Date。
//   通用镜头函数见 references/api.md（SH.* 镜头、PR.* 道具、L.* 绘图与缓动）；解剖在 anat.js（AN.*）。
'use strict';
const SC = {};
(() => {
  const { W, P, paper, home, seg, full, SP, spX, IC, bang, tick, alarm, flags, paperFloor } = SH;

  // ================= s01 冷开场：满幅 3D 镜头 → 切到立绘 =================
  SC.s01 = (c, A) => {
    const t = A.t, pain = A.cue('pain');            // “腰”字出口的时刻
    // 镜头 1：办公室满幅图，整场缓慢推近 6%。新镜头盖上来之前一直画着（不要两个镜头同时半透明）
    if (t < pain + 0.35) full(c, A, 'fs_zhou_desk', { zoom: 1.3, ay: 0.7, ax: 0.55, push: 0.05 });   // 放大 1.3 倍、偏下裁切：裁掉原图顶上的空墙，头顶落在片名（开场 5 秒在 y 236–420）下面
    // 镜头 2：从 pain 起 0.3 秒淡入，自己铺满底色
    seg(c, t, pain, 1e9, () => {
      home(c, t);
      const jolt = L.jolt(t, pain + 0.1, 14);       // 出场时抖一下
      SP(c, A, 'sp_zhou_pain', spX(A, 'sp_zhou_pain', 520, 760) + jolt, 1190, 760, { pop: (t - pain) / 0.4 });
      const k = L.pop(t, pain + 0.25);               // 腰旁边弹出一个红色警示符号（图形，不是字）
      if (k > 0) L.with(c, () => bang(c, 0, 0, 54), { x: 730, y: 700, s: k * (1 + 0.06 * Math.sin(t * 9)) });
    });
  };

  // ================= s02 解剖：结石怎么形成、卡在哪 =================
  SC.s02 = (c, A) => {
    const t = A.t, p = P(), grow = A.cue('grow'), fall = A.cue('fall'), stuck = A.cue('stuck');
    paper(c, t);
    const X = 360, Y = 520, S = 1.2;                 // 肾中心与缩放：膀胱底在 y ≈ 1180，三张字卡的场主体底边别超过 1190
    const conc = L.seg(t, 0.6, grow);                // 尿越来越浓：颜色从浅黄到深黄
    const dil = L.easeInOut(L.seg(t, stuck + 0.2, stuck + 1.8));   // 卡住以后，上游慢慢扩张
    AN.tract(c, X, Y, S, { urine: L.mix(p.tube, p.urine_dark, conc * 0.8), dilate: dil });
    L.with(c, () => {                                 // 在肾的坐标系里画晶体和结石
      const g = L.seg(t, grow, grow + 2.4);           // 晶体小点从四周聚到下肾盏
      if (g > 0 && g < 1) { const R = L.rand(11); for (let k = 0; k < 14; k++) { const a = R() * 6.28, d = (26 + R() * 22) * (1 - L.easeIn(g)); L.circle(c, AN.CALYX[0] + Math.cos(a) * d, AN.CALYX[1] + Math.sin(a) * d, 2.5 + R() * 2, p.crystal); } }
      const u = L.seg(t, fall, stuck);                // 结石沿 肾盏 → 肾盂 → 输尿管上段 走
      const [sx, sy] = AN.stonePos(u);
      AN.stone(c, sx, sy, 15 * L.easeOut(L.seg(t, grow + 0.6, grow + 2.6)));
      if (t > stuck) { const q = (t - stuck) * 1.4 % 1; L.ring(c, AN.STUCK[0], AN.STUCK[1], 22 + 46 * q, 7, L.alpha(p.red, 0.8 * (1 - q))); }   // 卡住：红色脉动
    }, { x: X, y: Y, s: S });
    // 右侧：结石放大窗，让手机上也看得清
    const zk = L.pop(t, grow + 1.0);
    if (zk > 0) L.with(c, () => SH.inRing(c, 0, 0, 120, p.ink2, () => { c.fillStyle = L.mix(p.tube, p.urine_dark, 0.5); c.fillRect(-130, -130, 260, 260); AN.stone(c, 0, 0, 62 * L.easeOut(L.seg(t, grow + 0.6, grow + 2.6))); }), { x: 790, y: 440, s: zk });
  };

  // ================= s03 怎么办：多喝水，每天尿量 2 升以上 =================
  // 量杯：需要精确表达“到哪一格”的示意用代码画（刻度是短线，不写数字）
  const jug = (c, x, y, level, mark) => L.with(c, () => { const p = P(), w = 210, h = 340;
    L.fillRR(c, -w / 2 + 8, -h / 2 + 12, w, h, 26, 'rgba(59,47,74,0.10)'); L.fillRR(c, -w / 2, -h / 2, w, h, 26, '#FFFFFF');
    c.save(); L.rr(c, -w / 2 + 10, -h / 2 + 10, w - 20, h - 20, 18); c.clip(); c.fillStyle = L.alpha(p.urine, 0.9); c.fillRect(-w / 2, h / 2 - 10 - (h - 20) * level, w, (h - 20) * level + 10); c.restore();
    for (let k = 1; k <= 5; k++) { const yy = h / 2 - 10 - (h - 20) * k / 5.5, big = k === 4; L.line(c, [[-w / 2 + 14, yy], [-w / 2 + (big ? 96 : 56), yy]], big ? 9 : 6, big && mark > 0 ? p.green : p.ink2); }   // 每格半升，第 4 格 = 2 升
    if (mark > 0) L.with(c, () => { L.circle(c, 0, 0, 34, p.green); tick(c, 0, 2, 20, '#FFFFFF'); }, { x: w / 2 + 6, y: h / 2 - 10 - (h - 20) * 4 / 5.5, s: mark }); }, { x, y });
  SC.s03 = (c, A) => {
    const t = A.t, water = A.cue('water'), two = A.cue('two'), ok = A.cue('ok');
    home(c, t);
    IC(c, A, 'ic_bottle', 210, 760, 400, { pop: (t - water) / 0.45, shadow: true });
    const k = L.pop(t, water + 0.5);
    if (k > 0) L.with(c, () => jug(c, 0, 0, 4 / 5.5 * L.easeInOut(L.seg(t, water + 0.9, two + 0.4)), L.pop(t, two + 0.4)), { x: 500, y: 780, s: k });
    SP(c, A, 'sp_zhou_drink', spX(A, 'sp_zhou_drink', 800, 620), 1180, 620, { pop: (t - ok + 0.2) / 0.45 });
  };

  // ================= s04 危险信号：红色警报 + 警示牌，文字都在 alert 字卡里 =================
  SC.s04 = (c, A) => {
    const t = A.t, f1 = A.cue('f1'), f2 = A.cue('f2');
    paper(c, t);
    alarm(c, t, f1 - 0.3);
    flags(c, t, [f1, f2], 520);
    paperFloor(c, 1130);
    SP(c, A, 'sp_zhou_pain', spX(A, 'sp_zhou_pain', 540, 430), 1130, 430, { pop: t / 0.45 });
  };

  // ================= s99 片尾：口号等文字由叠字层画；人物脚底 ≤ 880 =================
  SC.s99 = (c, A) => { paper(c, A.t, 47); SP(c, A, 'sp_zhou_drink', 540, 880, 520, { pop: A.t / 0.45 }); };
})();
if (typeof module !== 'undefined') module.exports = SC; else window.SC = SC;
