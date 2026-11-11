// 解剖图（专题自有）：模板里只放空壳。每个专题在这里写自己的解剖绘制（如 bph 的 AN.coronal / AN.sagittal、kidney_stone 的肾与输尿管），
// 参数驱动、画面零文字；解剖核对清单写在 storyboard.anatomy_checks，每张出图都要按原尺寸逐张核（见 references/anatomy.md）。
// 约定：AN.xxx(c, x, y, s, o)，(x,y) 为图中心，s=1 时约 600 px 高；颜色只取 L.P（storyboard.style.palette）。
'use strict';
const AN = {};
(() => {
  // 占位：一个示意用的“器官”轮廓，专题请删掉并写自己的
  AN.placeholder = (c, x, y, s = 1, o = {}) => L.with(c, () => { const P = L.P; L.ellipse(c, 0, 0, 220, 260, o.col || P.red || '#F0605D'); L.ellipse(c, -60, -70, 60, 40, 'rgba(255,255,255,0.35)'); }, { x, y, s });
})();
if (typeof module !== 'undefined') module.exports = AN; else window.AN = AN;
