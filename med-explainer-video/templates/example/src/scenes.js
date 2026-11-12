// 样例专题《在家量血压，这样才准》的各场动画。照着这个文件写自己的片子：
//   每场一个函数 SC.<场景 id> = (c, A) => {…}：c 是画布，A 是本场的上下文。
//   A.t 场内秒；A.T 本场时长；A.cue('名字') storyboard 里声明的画面事件时刻；A.lab(k) 第 k 张字卡出现的时刻；A.ln(i) 第 i 句台词 {start, end}。
//   坐标：宽 1080，主舞台 y 236–1236（竖屏）。画面里不写字，中文都在 storyboard 的字幕和字卡里。
//   每一帧只由时间 A.t 决定：不要用 Math.random()（用 L.rand(seed)）、不要用 Date。
//   通用镜头函数见 references/api.md（SH.* 镜头、PR.* 道具、L.* 绘图与缓动）；示意图 / 解剖图在 anat.js（AN.*）。
'use strict';
const SC = {};
(() => {
  const { W, P, paper, home, seg, full, SP, spX, IC, bang, tick, alarm, flags, paperFloor } = SH;

  // ================= s01 冷开场：满幅镜头 → 切到立绘 =================
  SC.s01 = (c, A) => {
    const t = A.t, shock = A.cue('shock');           // “高”字出口的时刻
    // 镜头 1：餐桌旁的满幅图，整场缓慢推近 5%。新镜头盖上来之前一直画着（不要两个镜头同时半透明）
    if (t < shock + 0.35) full(c, A, 'fs_lin_home', { zoom: 1.0, ay: 0, push: 0.03 });   // 不放大、顶端对齐：头顶正好在片名横幅（AI 标识退场后出现几秒，在 y 248–352）下面，袖带和血压计都在画面里（横屏只显示中间一段，也看得到）
    // 镜头 2：从 shock 起 0.3 秒淡入，自己铺满底色
    seg(c, t, shock, 1e9, () => {
      home(c, t);
      const jolt = L.jolt(t, shock + 0.1, 14);       // 出场时抖一下
      SP(c, A, 'sp_lin_worry', spX(A, 'sp_lin_worry', 500, 740) + jolt, 1190, 740, { pop: (t - shock) / 0.4 });
      const k = L.pop(t, shock + 0.25);              // 头旁边弹出一个红色警示符号（图形，不是字）
      if (k > 0) L.with(c, () => bang(c, 0, 0, 54), { x: 760, y: 560, s: k * (1 + 0.06 * Math.sin(t * 9)) });
    });
  };

  // ================= s02 怎么量：三步，一步一张卡（SH.steps） =================
  // 步骤卡上的小图：以 (0, 0) 为卡片中心，按 250 px 见方的卡片画，内容控制在 ±80 px 内
  const chairIcon = (c) => { const p = P();          // 椅子（靠背 + 座面 + 腿）和地上的两只脚：坐稳、双脚平放
    L.fillRR(c, -58, -80, 22, 124, 10, p.wood_dark); L.fillRR(c, -58, 22, 104, 22, 10, p.wood); L.fillRR(c, -54, 42, 16, 40, 6, p.wood_dark); L.fillRR(c, 26, 42, 16, 40, 6, p.wood_dark);
    L.fillRR(c, 4, 70, 36, 13, 6, p.ink2); L.fillRR(c, 48, 70, 36, 13, 6, p.ink2); };
  const cuffIcon = (c) => { const p = P();           // 上臂 + 袖带：袖带下缘和肘窝（横线）之间隔两横指（两道红色短线）
    L.fillRR(c, -30, -86, 60, 172, 28, p.skin); L.fillRR(c, -42, -66, 84, 80, 14, p.cuff); L.fillRR(c, -42, -44, 84, 10, 5, p.cuff_light);
    L.line(c, [[-20, 54], [20, 54]], 5, p.ink2); for (const y of [26, 40]) L.line(c, [[50, y], [74, y]], 7, p.red); };
  SC.s02 = (c, A) => {
    const t = A.t, rest = A.cue('rest'), sit = A.cue('sit'), cuff = A.cue('cuff');
    home(c, t);
    SH.steps(c, A, [                                  // 讲到哪一步，哪张卡弹出并高亮；讲过的打勾
      { at: rest, icon: (c2) => PR.clock(c2, 0, 0, 0.8, { h: 10, m: 10 }) },   // 代码画的道具
      { at: sit, icon: chairIcon },                                          // 自己画的小图
      { at: cuff, icon: cuffIcon },
    ], { y: 520 });
    IC(c, A, 'ic_bpmonitor', 300, 970, 440, { pop: t / 0.45, shadow: true });   // 3D 道具图标：开场第一秒就在
    SP(c, A, 'sp_lin_point', spX(A, 'sp_lin_point', 790, 540), 1190, 540, { pop: (t - 0.15) / 0.45 });
    SH.spot(c, 160, 978, 100, t, cuff + 0.3);          // 讲到袖带时圈出图标上的袖带：“看这里”
  };

  // ================= s03 关键一点：上臂和心脏一样高（代码画的示意图，AN.seated） =================
  SC.s03 = (c, A) => {
    const t = A.t, p = P(), heart = A.cue('heart'), level = A.cue('level'), ok = A.cue('ok');
    paper(c, t);
    const X = 450, Y = 660, S = 1.0;                  // 示意图的胸口位置和缩放：头顶 y ≈ 290，桌子底 y ≈ 1110；右下角留给立绘
    AN.seated(c, X, Y, S, { beat: t, arm: L.fin(t, 0.3, 0.5) });
    SH.spot(c, X + AN.HEART[0] * S, Y + AN.HEART[1] * S, 74, t, heart);           // 心脏：脉动圈
    const yl = Y + (AN.MID[1] + AN.HEART[1]) / 2 * S, k = L.easeInOut(L.seg(t, level, level + 0.7));
    SH.level(c, X + AN.MID[0] * S - 90, X + AN.HEART[0] * S + 110, yl, k);       // 水平线：从上臂中点长到心脏
    const kt = L.pop(t, level + 0.75);                // 对齐了：打勾
    if (kt > 0) L.with(c, () => { L.circle(c, 0, 0, 40, p.green); tick(c, 0, 2, 23, '#FFFFFF'); }, { x: X + AN.HEART[0] * S + 170, y: yl, s: kt });
    SP(c, A, 'sp_lin_point', spX(A, 'sp_lin_point', 850, 430), 1190, 430, { pop: (t - ok + 0.15) / 0.45 });
  };

  // ================= s04 危险信号：红色警报 + 警示牌，文字都在 alert 字卡里 =================
  SC.s04 = (c, A) => {
    const t = A.t, f1 = A.cue('f1'), f2 = A.cue('f2');
    paper(c, t);
    alarm(c, t, f1 - 0.3);
    flags(c, t, [f1, f2], 520);
    paperFloor(c, 1130);
    SP(c, A, 'sp_lin_worry', spX(A, 'sp_lin_worry', 540, 440), 1130, 440, { pop: t / 0.45 });
  };

  // ================= s99 片尾：口号等文字由叠字层画；人物脚底 ≤ 880 =================
  SC.s99 = (c, A) => { paper(c, A.t, 47); SP(c, A, 'sp_lin_point', 540, 880, 520, { pop: A.t / 0.45 }); };
})();
if (typeof module !== 'undefined') module.exports = SC; else window.SC = SC;
