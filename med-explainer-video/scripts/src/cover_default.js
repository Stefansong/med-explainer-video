// 模板默认封面（项目 scenes.js 没有 SC.cover / SC.cover_land 时由 engine / cover.html 调用）。文字全部来自 storyboard.cover：title_lines（两行片名）、hook（痛点句，红胶囊）、tagline（小字）。
//   COVER.port(c, SB, o)：竖屏 1080×1920。片名从 y 480 起（左上 48–430×252–340 留给 AI 标识 layout.ai_mark，别画东西进去）。
//   COVER.land(c, SB, o)：横屏 1920×1080，文字在左半幅（cx 560）；带 bph 交付版的退场动画：最后 0.9 s 片名逐字上浮淡出、痛点胶囊收拢、小字淡出，再接水浪转场。
//   o.t / o.T（场内秒 / 场长）由 engine 传入；不传 = 静态封面图（cover.html）。
// 项目要加画面（人物、道具、钟表…）：在 scenes.js 定义 SC.cover_art(c, SB, o)，这里在画文字之前调用；o.land 区分画幅（横屏画在右半幅 x ≥ 1100、右下角 1880−240×1040−100 留给 AI 标识；竖屏画在 y ≥ 900）。
// AI 标识不在这里画：叠字层 OV.aiMark 从第 0 帧起按 layout.ai_mark 叠在封面上（竖屏左上、横屏右下）；封面图（cover.html）同样叠上，保证封面图 = 视频第一帧。
'use strict';
const COVER = {};
(() => {
  const P = () => L.P;
  const art = (c, SB, o) => { if (typeof SC !== 'undefined' && SC.cover_art) { c.save(); try { SC.cover_art(c, SB, o); } catch (e) { console.error('cover_art', e.message); } c.restore(); } };
  const lineFit = (c, s, size, maxW) => { c.font = OV.fnt(size, 'title'); return Math.min(size, Math.floor(size * maxW / Math.max(1, c.measureText(s).width))); };
  const hook = (c, s, cx, cy, size, h) => { c.font = OV.fnt(size, 'sub'); const hw = c.measureText(s).width + 80; L.fillRR(c, cx - hw / 2 + 6, cy - h / 2 + 8, hw, h, h / 2, 'rgba(59,47,74,0.15)'); L.fillRR(c, cx - hw / 2, cy - h / 2, hw, h, h / 2, P().red); OV.txt(c, s, cx, cy + 1, size, '#FFFFFF', null, 'sub'); };
  const titles = (SB) => { const cv = SB.cover || {}; return (cv.title_lines && cv.title_lines.length ? cv.title_lines : [(SB.title_card && SB.title_card.main) || SB.title || '']).slice(0, 2); };
  COVER.port = (c, SB, o = {}) => {
    const p = P(), cv = SB.cover || {}, W = 1080, H = 1920;
    L.EXT = null; L.bg(c, W, H, p.paper, p.paper2, 5, 0); art(c, SB, { ...o, land: false, W, H });
    titles(SB).forEach((s, i) => OV.txt(c, s, W / 2, 480 + i * 150, lineFit(c, s, 124, 980), p.ink, '#FFFFFF', 'title', 'center', 0.2));
    if (cv.hook) hook(c, cv.hook, W / 2, 785, 50, 84);
    if (cv.tagline && !o.markBottom) OV.txt(c, cv.tagline, W / 2, 1625, 46, p.ink2, null, 'label');
  };
  COVER.land = (c, SB, o = {}) => {
    const p = P(), cv = SB.cover || {}, W = 1920, H = 1080;
    L.EXT = null; L.bg(c, W, H, p.paper, p.paper2, 5, 0); art(c, SB, { ...o, land: true, W, H });
    const anim = o.t !== undefined && o.T !== undefined, S0 = anim ? o.T - 0.9 : 1e9, tt = anim ? o.t : 0, pr = (t0, d) => L.clamp((tt - t0) / d);
    const cx = 560, line = (s, y, size, t0) => {   // 退场：逐字上浮 64 px、缩小 18%、交替微转、淡出；先描边后填字，免得后一个字的白边压住前一个字
      const sz = lineFit(c, s, size, 900);
      if (tt < t0) return OV.txt(c, s, cx, y, sz, p.ink, '#FFFFFF', 'title', 'center', 0.2);
      c.font = OV.fnt(sz, 'title'); c.textAlign = 'center'; c.textBaseline = 'middle'; c.lineJoin = 'round'; c.lineWidth = sz * 0.2; c.strokeStyle = '#FFFFFF'; c.fillStyle = p.ink;
      const ch = [...s], x0 = cx - c.measureText(s).width / 2;
      const st = ch.map((q, k) => { const w = c.measureText(q).width, x = x0 + c.measureText(ch.slice(0, k).join('')).width + w / 2, e = L.easeIn(pr(t0 + k * 0.035, 0.42)); return { q, x, e, r: (k % 2 ? 1 : -1) * 0.14 * e }; });
      for (const pass of ['stroke', 'fill']) for (const o2 of st) { if (o2.e >= 1) continue; c.save(); c.globalAlpha *= 1 - o2.e; c.translate(o2.x, y - 64 * o2.e); c.rotate(o2.r); c.scale(1 - 0.18 * o2.e, 1 - 0.18 * o2.e); if (pass === 'stroke') c.strokeText(o2.q, 0, 0); else c.fillText(o2.q, 0, 0); c.restore(); }
    };
    titles(SB).forEach((s, i) => line(s, 270 + i * 150, 118, S0 + i * 0.12));
    if (cv.hook) { const e = L.easeIn(pr(S0 + 0.24, 0.34)); if (e < 1) { c.save(); c.globalAlpha *= 1 - e; c.translate(cx, 561 - 24 * e); c.scale(1 - 0.3 * e, 1 - 0.3 * e); c.translate(-cx, -561); hook(c, cv.hook, cx, 561, 48, 82); c.restore(); } }
    if (cv.tagline) { const e = L.easeIn(pr(S0 + 0.06, 0.36)); if (e < 1) { c.save(); c.globalAlpha *= 1 - e; OV.txt(c, cv.tagline, cx, 690 - 26 * e, 44, p.ink2, null, 'label'); c.restore(); } }
  };
})();
if (typeof module !== 'undefined') module.exports = COVER; else window.COVER = COVER;
