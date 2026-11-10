// 各场动画（专题自有）。这是空白骨架：两场演示只用代码画的道具，不依赖任何图片素材，建好专题就能出画面。
// 完整的写法看样例专题（python pipeline.py new demo --example）的 src/scenes.js，函数速查见 references/api.md。
//   每场一个函数 SC.<场景 id> = (c, A) => {…}：A.t 场内秒；A.T 场长；A.cue('名字') 画面事件时刻；A.lab(k) 第 k 张字卡时刻；A.ln(i) 第 i 句台词 {start, end}。
//   坐标：宽 1080，主舞台 y 236–1236。画面里不写字；每一帧只由 A.t 决定（不用 Math.random / Date）。
//   人物只用 3D：满幅镜头 SH.full，或透明底立绘 SH.SP（tools/cutout.py 抠底并登记 storyboard.assets）；道具图标 SH.IC；解剖在 anat.js 用代码画。
'use strict';
const SC = {};
(() => {
  const { P, paper, alarm, flags, paperFloor } = SH;

  // s01 开场：家里 + 一只钟（钟面时间由代码画）；角色登场的时刻取 cue 'enter'
  SC.s01 = (c, A) => {
    const t = A.t;
    SH.home(c, t);
    PR.clock(c, 300, 520, 1.1, { h: 8, m: 30 + Math.floor(t / 4) });
    const k = L.pop(t, A.cue('enter')); if (k > 0) L.with(c, () => SH.bang(c, 0, 0, 60, P().yellow), { x: 700, y: 620, s: k });   // 占位：换成角色立绘 SH.SP(...)
  };

  // s02 危险信号：红色警报 + 警示牌（文字都在 alert 字卡里）
  SC.s02 = (c, A) => {
    const t = A.t;
    paper(c, t, 11);
    alarm(c, t, A.cue('f1') - 0.3);
    flags(c, t, ['f1', 'f2'].map((k) => A.cue(k)), 560);
    paperFloor(c, 1120);
  };

  // s99 片尾：文字由叠字层画，这里只铺背景（要放人物：脚底 y ≤ 880）
  SC.s99 = (c, A) => { paper(c, A.t, 47); };
})();
if (typeof module !== 'undefined') module.exports = SC; else window.SC = SC;
