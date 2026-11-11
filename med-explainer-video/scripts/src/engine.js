// 渲染引擎（预览页 player.html 与各渲染工具共用）：给定时刻 T，从零画出整帧。
// ENGINE.create({ SB, TL, canvas, style, art, assetBase, strict }) → { renderAt(T, {overlay}), renderFrame(T, {sub, shutter, fps}), prepare(T, span) }
// 视频素材（storyboard 里 scene.media；片头 / 片尾素材在 SB.intro_media / SB.outro_media）按帧图片加载：逐帧渲染前先 await prepare(T)，场景里用 A.media(id) 取当前帧。
//   帧号：at=[cue, 偏移] 起播；dur 给定时只在窗口内有效（超出片长停在最后一帧）；loop='pingpong'|'loop'|[a,b]（帧号）或 loop_s=[a,b]（秒）；still=静帧；f0 / f0_s=从第几帧 / 几秒起播；tmap 分段对时。
// 皮克斯 3D 人物层（media 条目带 pix，本技能不带口型视频的生成流程，接口保留）：pixActive / drawPix 按 pix.layout（full / circle / card / ellipse）叠到场景上，
//   under=true 时经 L.bg → L.PIXBG 画在背景之上、前景之下；hide 让代码画的同一角色让位（L.HIDE，角色函数用 L.hide(who) 查：'skip' 不画 / 'faceless' 画无脸版）。
//   只有片段帧到位时代码角色才让位：缺帧自动回退代码版。运动模糊子帧取视频帧一律按主帧时刻（MDT），否则 25 fps 的片段相邻两帧叠成重影。
// 版式（舞台位置、片名、字卡、字幕）全部由 layout.json 决定（OV.LAYOUT，player.html 加载后 OV.setLayout）；本文件不写版式常量。
// 画幅：竖屏（layout.stage 只有 top/bottom）场景以舞台底边为锚缩放；横屏（layout.stage 给了 x/y/h 矩形）场景映射到左侧矩形、背景向右延伸（L.EXT），
//   右侧由叠字层放要点板；参考文献页 sref、封面 s00（项目 SC.cover / SC.cover_land，没有就用 cover_default.js 的 COVER）都在这里分发。
// 依赖全局 L / AN / PR / SC / OV / SK / COVER（由 lib.js、anat.js、props.js、scenes.js、overlay.js、sketch.js、cover_default.js 提供）。
'use strict';
const ENGINE = {};
(() => {
  ENGINE.create = ({ SB, TL, canvas, style = '', art = true, assetBase = '../', strict = false }) => {   // strict：素材缺失时 prepare 直接报错（正式渲染用），否则只警告并回退代码画法（预览用）
    const W = canvas.width, H = canvas.height, c = canvas.getContext('2d');
    const HAND = !!style; SK.mode = style || 'hand'; SK.amp = { hand: 1.6, paper: 0.8, clay: 0.9, chalk: 1.5, ink: 1.2, kz: 0 }[SK.mode] ?? 1.6;
    OV.dark = SK.mode === 'kz'; const ONTWOS = HAND && SK.mode !== 'kz';   // 手绘类风格：一拍二（15 张/秒）
    L.init(SB.style.palette); L.ART = !!art && typeof PUP !== 'undefined' && PUP.ready();   // 角色：S3 定稿矢量木偶（art=false 回到代码版）
    OV.setStoryboard(SB); if (OV.setTimeline) OV.setTimeline(TL);
    // ---------- 视频素材（帧序列）----------
    const sbScene = (id) => (id === 's99' ? { id: 's99', media: SB.outro_media || [] } : id === 's00' ? { id: 's00', media: SB.intro_media || [] } : SB.scenes.find((x) => x.id === id));   // 片头 s00 / 片尾 s99 由 timeline.py 生成，素材登记在 SB
    const MEDIA = {}; for (const s of [...SB.scenes, sbScene('s99'), sbScene('s00')]) for (const m of (s && s.media) || []) MEDIA[m.id] = { ...m, scene: s.id, imgs: new Map(), pend: new Map() };
    const mT0 = (m, sc) => { const k = m.at[0], ln = /^l(\d+)$/.exec(k); return (sc.cues && k in sc.cues ? sc.cues[k] : ln && sc.lines && sc.lines[+ln[1]] ? sc.lines[+ln[1]].start : 0) + (m.at[1] || 0); };   // at[0]：cue 名，或 l<i> = 第 i 句台词开口
    const tmapAt = (k, x) => { if (x <= k[0][0]) return k[0][1] + x - k[0][0]; for (let i = 1; i < k.length; i++) if (x <= k[i][0]) return k[i - 1][1] + (x - k[i - 1][0]) * (k[i][1] - k[i - 1][1]) / (k[i][0] - k[i - 1][0]); const z = k[k.length - 1]; return z[1] + x - z[0]; };
    const mLoop = (m) => (m.loop_s ? m.loop_s.map((s) => Math.round(s * m.fps)) : m.loop), mF0 = (m) => (m.f0_s != null ? Math.round(m.f0_s * m.fps) : (m.f0 || 0));   // 秒为单位的写法不受片段帧率（25 → 60 插帧）影响
    const mFrame = (m, sc, t) => { const loc = t - mT0(m, sc); if (loc < 0 || (m.dur != null && loc > m.dur)) return -1; if (m.still) return 0;
      let f = Math.floor((m.tmap ? tmapAt(m.tmap, loc) : loc) * m.fps + 1e-6) + mF0(m); const lp = mLoop(m);   // tmap：[[新片段时刻, 原片段时刻]…] 分段对时（台词改速后，片段里的事件仍对准原来那句话）
      if (lp === 'pingpong' && m.frames > 1) { const per = 2 * (m.frames - 1); f %= per; if (f >= m.frames) f = per - f; }
      else if (lp === 'loop') f %= m.frames;
      else if (Array.isArray(lp) && f > lp[1]) { const [a, b] = lp, per = 2 * (b - a), k = (f - b) % per; f = k <= b - a ? b - k : a + k - (b - a); }   // [a, b]：顺播到 b 后在 a..b 来回（说完话只循环闭嘴段）
      else if (f >= m.frames && m.dur != null) f = m.frames - 1;
      return f; };
    const mLoad = (m, f) => { if (m.imgs.has(f)) return Promise.resolve(); if (m.pend.has(f)) return m.pend.get(f);
      const img = new Image(); img.src = assetBase + m.src.replace('%04d', String(f).padStart(4, '0'));
      const pr = img.decode().then(() => { m.imgs.set(f, img); m.pend.delete(f); if (m.imgs.size > 240) { const k = m.imgs.keys().next().value; m.imgs.delete(k); } }).catch(() => { m.pend.delete(f); if (strict) throw new Error('media missing: ' + img.src); console.warn('media missing', img.src); });
      m.pend.set(f, pr); return pr; };
    let MDT = 0;   // 运动模糊子帧相对主帧的时间偏移：取视频帧一律按主帧时刻（InfiniteTalk 原片 25 fps）
    const mGet = (id, sc, t) => { const m = MEDIA[id]; if (!m) return null; let f = mFrame(m, sc, Math.max(0, Math.round((t - MDT) * 1e6) / 1e6)); if (f < 0) f = mFrame(m, sc, t); if (f < 0 || f >= m.frames) return null;
      if (m.imgs.has(f)) return m.imgs.get(f); for (let d = 1; d <= 6; d++) for (const g of [f - d, f + d]) if (m.imgs.has(g)) return m.imgs.get(g); return null; };   // 实时预览时允许借相邻帧
    const mHold = (m, sc) => { const f = mFrame(m, sc, mT0(m, sc)); return f >= 0 ? m.imgs.get(f) || null : null; };   // pix.holdIn：起播前的第 0 帧
    // 静态插图（storyboard.assets，如 Servier 医学插图）：第一次 prepare 时全部加载
    const IMGS = {}; let imgReady = null;
    const loadImgs = () => imgReady || (imgReady = Promise.all(Object.entries(SB.assets || {}).map(([id, a]) => { const im = new Image(); im.src = assetBase + a.src; return im.decode().then(() => { IMGS[id] = im; }).catch(() => { if (strict) throw new Error('asset missing: ' + im.src); console.warn('asset missing', im.src); }); })));
    const prepare = (T, span = 0) => { const jobs = [loadImgs()]; if (typeof IC !== 'undefined' && IC.load) jobs.push(IC.load(assetBase));   // 位图图标（props.js 先图标后代码）
      for (const sc of TL.scenes) { if (sc.end < T - span - 1 || sc.start > T + span + 1) continue; const ssb = sbScene(sc.id); for (const mm of (ssb && ssb.media) || []) { const m = MEDIA[mm.id];
        const need = new Set(); for (let tt = T - span; tt <= T + span + 1e-9; tt += Math.min(1 / m.fps, Math.max(span, 1e-3))) need.add(mFrame(m, sc, Math.max(0, tt - sc.start))); need.add(mFrame(m, sc, Math.max(0, T - sc.start)));   // 转场里下一场按 0 秒先画：预加载要夹到 0
        if (mm.pix && mm.pix.holdIn > 0) need.add(mFrame(m, sc, mT0(m, sc)));   // holdIn 的第 0 帧
        for (const f of need) if (f >= 0 && f < m.frames) jobs.push(mLoad(m, f)); } }
      return Promise.all(jobs); };
    const mkA = (sc, t) => ({ SB, TL, sc, t, tc: Math.max(0, Math.round((t - MDT) * 1e6) / 1e6), T: sc.end - sc.start,   // tc：主帧时刻，硬切判断用它，运动模糊子帧就不会跨切点把前后两个镜头叠在一帧里
      ln: (i) => sc.lines[i] || { start: 1e9, end: 1e9 }, lines: sc.lines, media: (id) => mGet(id, sc, t), img: (id) => IMGS[id] || null, fit: (cc, im, id, f) => fitImg(cc, im, id, f, 1, visRect(sc.id !== 's00')),
      cue: (n) => (sc.cues && n in sc.cues ? sc.cues[n] : 1e9),
      lab: (k) => (sc.labels && sc.labels[k] ? sc.labels[k].t : 1e9),
      say: (who) => { for (const l of sc.lines) if (l.who === who && t >= l.start && t <= l.end) return t; return 0; },
      // 口型：当前字的嘴型 + 配音音量决定张多大；不在说话时返回 null
      mouth: (who) => { for (const l of sc.lines) { if (l.who !== who || !l.mouth || t < l.start - 0.02 || t > l.end + 0.05) continue;
        const tau = t - l.start, M = l.mouth, n = l.ct.length; let k = -1; for (let i = 0; i < n; i++) if (M.vis[i] && l.ct[i] <= tau + 0.03) k = i; if (k < 0) return null;
        if (tau > M.ce[k] + 0.12) { let nx = -1; for (let i = k + 1; i < n; i++) if (M.vis[i]) { nx = i; break; } if (nx < 0 || l.ct[nx] - tau > 0.08) return { shape: 'M', open: 0 }; }
        const v = M.vis[k], d = Math.max(0.06, M.ce[k] - l.ct[k]); const j = Math.floor(tau / 0.025); const e = M.env; const open = Math.min(1, ((e[j - 1] || 0) + 2 * (e[j] || 0) + (e[j + 1] || 0)) / 4 * 1.25);
        if (v.endsWith('m') && tau - l.ct[k] < d * 0.35) return { shape: 'M', open: 0 };
        return { shape: v[0], open }; } return null; } });
    const mk = () => { const k = document.createElement('canvas'); k.width = W; k.height = H; return k; };
    const off = [mk(), mk()], acc = mk(), ac = acc.getContext('2d');
    const footer = (ctx, T, a = 1) => { const F = OV.LAYOUT.footer; if (!F || F.enabled === false || a <= 0.01) return; const [y1, y2] = F.waves || [1700, 1760]; ctx.save(); ctx.globalAlpha *= a;
      ctx.beginPath(); ctx.moveTo(0, H); for (let x = 0; x <= W; x += 20) ctx.lineTo(x, y1 + 14 * Math.sin(x / 90 + T * 1.6)); ctx.lineTo(W, H); ctx.closePath(); ctx.fillStyle = 'rgba(124,200,232,0.16)'; ctx.fill();
      ctx.beginPath(); ctx.moveTo(0, H); for (let x = 0; x <= W; x += 20) ctx.lineTo(x, y2 + 12 * Math.sin(x / 70 - T * 1.3)); ctx.lineTo(W, H); ctx.closePath(); ctx.fillStyle = 'rgba(124,200,232,0.14)'; ctx.fill(); ctx.restore(); };
    // 舞台映射：场景按 layout.stage.design_top–design_bottom 设计。
    //   竖屏：以舞台底边为锚放置；stage.scale = 1.0（默认，原尺寸、顶上多出的部分只铺背景）或 "fit"（整体缩放到 top–bottom）或任意倍数
    //   横屏（stage.x/y/h）：整块舞台缩放 k = h / 设计高 映射到 (x, y) 起的矩形（bph 横屏交付版：60,104,880 → k 0.88）
    const LANDM = () => OV.LAYOUT.stage && OV.LAYOUT.stage.x != null;
    const stageK = () => { const St = OV.LAYOUT.stage; if (LANDM()) return St.h / (St.design_bottom - St.design_top); const fit = (St.bottom - St.top) / (St.design_bottom - St.design_top); return St.scale == null || St.scale === 'fit' ? fit : +St.scale || 1; };
    ENGINE.stageK = stageK;
    ENGINE.ERRS = {}; ENGINE.err = (msg) => { ENGINE.ERRS[msg] = (ENGINE.ERRS[msg] || 0) + 1; if (ENGINE.ERRS[msg] === 1) console.error(msg); };   // 同一条错误每帧都会触发：只打印一次，次数记在 ENGINE.ERRS（frames.js / render.js 取走）
    const stageMap = (ctx) => { const St = OV.LAYOUT.stage, k = stageK(); if (LANDM()) { ctx.translate(St.x, St.y); ctx.scale(k, k); ctx.translate(0, -St.design_top); return; } ctx.translate(W / 2, St.bottom); ctx.scale(k, k); ctx.translate(-W / 2, -St.design_bottom); };
    ENGINE.stageToScreen = (x, y) => { const St = OV.LAYOUT.stage, k = stageK(); if (LANDM()) return [St.x + x * k, St.y + (y - St.design_top) * k]; return [W / 2 + (x - W / 2) * k, St.bottom + (y - St.design_bottom) * k]; };   // 给 crop.js --at 跟踪用（不含呼吸漂移）
    const DWH = () => [((OV.LAYOUT.stage && OV.LAYOUT.stage.design_width) || 1080), (OV.LAYOUT.stage ? (OV.LAYOUT.stage.design_bottom || 1236) + 684 : 1920)];   // 场景设计画幅（竖屏 1080×1920）
    // 画布在设计坐标里的可见矩形（整幅 pix 片段铺这个矩形）：竖屏 = 整个画布映射回舞台坐标（底边对齐、上方多出的部分）；横屏 = 舞台那一列、画布全高；封面 s00 不做舞台映射 = 画布本身
    const visRect = (mapped) => { if (!mapped || !OV.LAYOUT.stage) return { x0: 0, y0: 0, w: W, h: H }; const St = OV.LAYOUT.stage, k = stageK(), [DW] = DWH();
      if (LANDM()) return { x0: 0, y0: St.design_top - St.y / k, w: DW, h: H / k }; return { x0: (0 - W / 2) / k + DW / 2, y0: (0 - St.bottom) / k + St.design_bottom, w: W / k, h: H / k }; };
    // 封面：项目 scenes.js 的 SC.cover（竖屏）/ SC.cover_land（横屏）优先；没有就用模板默认 COVER.port / COVER.land（cover_default.js，文字来自 storyboard.cover）
    const coverFn = () => { const land = W > H, f = land ? (SC.cover_land || (typeof COVER !== 'undefined' && COVER.land)) : (SC.cover || (typeof COVER !== 'undefined' && COVER.port)); return f ? (cc, A) => f(cc, A.SB, { t: A.t, T: A.T, land }) : null; };
    ENGINE.coverFn = coverFn;
    // ---------- 皮克斯 3D 人物层（storyboard media 里带 pix 的条目）：按 pix.layout 叠到原场景上；hide 让代码画的同一角色让位 ----------
    // pix: { layout: full|circle|card|ellipse|none（none = 不自动画，场景代码用 A.media(id) 自己画，如替换某个贴图位置）, x, y, r | w, h, rr, focus:[u,v], zoom, ring, ringW, under, fade, fadeOut, pop, punch, fit:{s, top, nofill}, leader:[x,y], shadow }
    // 条目级：hide {who: 'skip'|'faceless'}、hidePre（起播前几秒先画无脸版）、hideRest（放完后本场剩余时间继续让位）
    const pixActive = (sc, t) => { const out = { over: [], under: [], hide: null };
      const ssb = sbScene(sc.id);
      const tm = Math.max(0, Math.round((t - MDT) * 1e6) / 1e6);   // 主帧时刻（同 mkA 的 tc）：片段出不出场按主帧判断，运动模糊子帧就不会在硬切处把前后两个镜头叠进同一帧（10-24 audit_post：foam_3d 成片 9 帧叠影）
      for (const mm of (ssb && ssb.media) || []) { if (!mm.pix || mm.pix.layout === 'none') continue; const m = MEDIA[mm.id], loc = tm - mT0(m, sc), dur = m.dur ?? m.frames / m.fps;
        if (mm.hideRest && mm.hide && loc > dur && m.imgs.size) { out.hide = { ...(out.hide || {}), ...mm.hide }; continue; }
        if (mm.hidePre && mm.hide && loc < 0 && loc > -mm.hidePre) { out.hide = { ...(out.hide || {}), ...Object.fromEntries(Object.keys(mm.hide).map((k) => [k, 'faceless'])) }; continue; }
        const hold = mm.pix.holdIn > 0 && loc < 0 && loc >= -mm.pix.holdIn;   // holdIn（秒）：起播前先停在第 0 帧。换场时下一场按 0 秒画，片段若场内 0.05 s 才起播，水浪里会先露底层代码画面再弹出 3D（10-25 psa_3d 成片审核 #2）
        if (!hold && (loc < 0 || loc > dur)) continue;
        const img = hold ? mHold(m, sc) : mGet(mm.id, sc, t); if (!img) continue; if (mm.hide) out.hide = { ...(out.hide || {}), ...mm.hide };   // 只有片段帧到位时代码角色才让位（缺帧就回退代码版）
        (mm.pix.under ? out.under : out.over).push({ m: mm, img, loc: hold ? 0 : loc, dur, t }); }
      return out; };
    const EDGE = {}; const edgeCv = document.createElement('canvas'); edgeCv.width = 24; edgeCv.height = 24;
    const edgeCol = (id, im) => { if (EDGE[id]) return EDGE[id]; const x = edgeCv.getContext('2d', { willReadFrequently: true }); x.drawImage(im, 0, 0, 24, 24); const d = x.getImageData(0, 0, 24, 24).data; let r = 0, g = 0, b = 0, n = 0;
      for (let yy = 0; yy < 24; yy++) for (let xx = 0; xx < 24; xx++) { if (xx > 1 && xx < 22 && yy > 1 && yy < 22) continue; const i = (yy * 24 + xx) * 4; r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
      return (EDGE[id] = `rgb(${Math.round(r / n)},${Math.round(g / n)},${Math.round(b / n)})`); };   // 画面四周一圈像素的平均色（每个片段算一次）
    const EXT = document.createElement('canvas'); EXT.width = 48; EXT.height = 2; const extX = EXT.getContext('2d');
    const fitImg = (c, im, id, fit, pk = 1, vis, land) => {   // fit {s, top}：整幅缩到 s 倍、顶边放在可见矩形的 top 处，露出的边用画面边缘取色补齐（脸避开字卡区）
      if (fit.ext) {   // fit {ext:true, top}：满幅——按宽铺满（不缩小、不留边框），整幅下移 top 让头顶避开顶部章节名；露出的顶条用画面最上沿一行拉伸 + 横向模糊补齐（同一面墙往上延伸），接缝 50 px 渐隐。10-23 用户：缩小留边像画中画
        const k = vis.w / im.width * pk, w = im.width * k, h = im.height * k, x0 = vis.x0 + (vis.w - w) / 2, y0 = vis.y0 + fit.top - (pk - 1) * h / 2;
        if (LANDM() && land && land.cover) {   // 横屏特写（media.pix.land = {cover: true, row0}）：片段按整幅宽铺满（放大成头肩特写），从片段第 row0 行起取景；手臂伸出竖幅边缘的镜头用它，不用底板（11-09 bph_3d s12 伸懒腰：底板接缝处手臂像消失进墙里）
          const ks = stageK(), WW = W / ks * 1.04 * pk, X0 = -OV.LAYOUT.stage.x / ks - (WW - W / ks) / 2, kk = WW / im.width; c.drawImage(im, X0, vis.y0 - (land.row0 ?? 300) * kk - (WW - W / ks * 1.04) * 0.3, im.width * kk, im.height * kk); return; }
        const pl = LANDM() && land && IMGS[land.img];   // 横屏底板（media.pix.land = {img, k, x0}）：竖幅片段第 1 帧经 GPT 向两侧补画成的静态横幅，先铺底板、再画片段，左右边缘 feather 设计单位渐隐进底板（11-08 bph_3d 投稿版：竖幅镜头在横屏像画中画）
        if (pl) { const s = k / land.k, px = x0 + land.x0 * k, py = y0 + (land.y0 || 0) * k, pw = pl.width * s, ph = pl.height * s, F = land.feather || 70;   // 底板也向上补画了 −y0 片段像素，顶条不用再拉伸
          c.drawImage(pl, px, py, pw, ph);
          if (py > vis.y0) { extX.clearRect(0, 0, 48, 2); extX.drawImage(pl, 0, 0, pl.width, Math.max(2, pl.height * 0.004), 0, 0, 48, 2); c.drawImage(EXT, 0, 0, 48, 1, px, vis.y0 - 60, pw, py - vis.y0 + 61); }
          c.drawImage(im, x0, y0, w, h);
          const n = 28, sw = F / n;   // 片段左、右、上边缘：底板分条盖回去，越靠外越不透明（底板中间就是片段第 1 帧，背景不动处看不出接缝）
          for (let i = 0; i < n; i++) { const a = 1 - (i + 0.5) / n, sx = (x0 + i * sw - px) / s, sx2 = (x0 + w - (i + 1) * sw - px) / s, sy = (y0 + i * sw - py) / s; c.save(); c.globalAlpha *= a;
            c.drawImage(pl, sx, sy, sw / s, (ph - (y0 + i * sw - py)) / s, x0 + i * sw, y0 + i * sw, sw + 0.5, ph - (y0 + i * sw - py)); c.drawImage(pl, sx2, sy, sw / s, (ph - (y0 + i * sw - py)) / s, x0 + w - (i + 1) * sw - 0.5, y0 + i * sw, sw + 0.5, ph - (y0 + i * sw - py));
            if (y0 > py) c.drawImage(pl, (x0 + (i + 1) * sw - px) / s, sy, (w - 2 * (i + 1) * sw) / s, sw / s, x0 + (i + 1) * sw, y0 + i * sw, w - 2 * (i + 1) * sw, sw + 0.5); c.restore(); }
          if (py > vis.y0) for (let i = 0; i < 5; i++) { c.save(); c.globalAlpha *= (5 - i) / 6; c.drawImage(EXT, 0, 0, 48, 1, px, py + i * 10, pw, 10); c.restore(); }
          return; }
        c.drawImage(im, x0, y0, w, h);
        if (y0 > vis.y0) { extX.clearRect(0, 0, 48, 2); extX.drawImage(im, 0, 0, im.width, Math.max(2, im.height * 0.004), 0, 0, 48, 2); c.drawImage(EXT, 0, 0, 48, 1, x0, vis.y0 - 60, w, y0 - vis.y0 + 61);
          for (let i = 0; i < 5; i++) { c.save(); c.globalAlpha *= (5 - i) / 6; c.drawImage(EXT, 0, 0, 48, 1, x0, y0 + i * 10, w, 10); c.restore(); } }
        return; }
      const k = Math.max(vis.w / im.width, vis.h / im.height) * fit.s * pk, w = im.width * k, h = im.height * k, x0 = vis.x0 + (vis.w - w) / 2, y0 = vis.y0 + fit.top - (pk - 1) * h / 2;
      const ec = edgeCol(id, im); if (!fit.nofill) { c.fillStyle = ec; c.fillRect(vis.x0 - 50, vis.y0 - 50, vis.w + 100, vis.h + 100); } c.drawImage(im, x0, y0, w, h);   // nofill：叠化到同机位的另一段时不再铺底色，否则半透明底色把画面洗灰
      const fe = (xa, ya, xb, yb, rx, ry, rw, rh) => { const g = c.createLinearGradient(xa, ya, xb, yb); g.addColorStop(0, ec); g.addColorStop(1, ec.replace('rgb(', 'rgba(').replace(')', ',0)')); c.fillStyle = g; c.fillRect(rx, ry, rw, rh); };
      const F = 70; fe(x0, 0, x0 + F, 0, x0, y0, F, h); fe(x0 + w, 0, x0 + w - F, 0, x0 + w - F, y0, F, h); fe(0, y0 + h, 0, y0 + h - F * 1.6, x0, y0 + h - F * 1.6, w, F * 1.6); fe(0, y0, 0, y0 + F, x0, y0, w, F); };
    const pixA = (q) => { const P = q.m.pix, fd = P.fade ?? 0.25, fo = P.fadeOut ?? fd; if (P.under && P.fade == null && P.fadeOut == null) return 1; return Math.min(fd > 0 ? L.clamp(q.loc / fd) : 1, fo > 0 ? L.clamp((q.dur - q.loc) / fo) : 1); };
    const drawPix = (c, q, vis) => { const P = q.m.pix, im = q.img, a = pixA(q);
      const s = P.pop ? L.backOut(L.clamp(q.loc / 0.4)) * (1 - L.easeIn(L.clamp((q.loc - q.dur + 0.4) / 0.4))) : 1;
      const breathe = q.m.still ? 1 + 0.008 * Math.sin(q.t * 2 * Math.PI / 3.2) : 1;
      const blit = (bw, bh) => { const z = (P.zoom || 1) * breathe, k = Math.max(bw / im.width, bh / im.height) * z, fu = (P.focus || [0.5, 0.5])[0], fv = (P.focus || [0.5, 0.5])[1];
        let dx = -fu * im.width * k, dy = -fv * im.height * k; dx = Math.min(-bw / 2, Math.max(bw / 2 - im.width * k, dx)); dy = Math.min(-bh / 2, Math.max(bh / 2 - im.height * k, dy)); c.drawImage(im, dx, dy, im.width * k, im.height * k); };
      c.save(); c.globalAlpha *= a;
      if (P.layout === 'full') {
        const pk = P.punch ? 1 + 0.07 * (1 - L.easeOut(L.clamp(q.loc / 0.35))) : 1;   // punch：硬切进来时从 1.07 倍推回 1，切点更利落
        if (P.fit) { fitImg(c, im, q.m.id, P.fit, pk, vis, P.land); c.restore(); return; }
        c.translate(vis.x0 + vis.w / 2, vis.y0 + vis.h / 2); c.scale(pk, pk); blit(vis.w, vis.h); c.restore(); return; }
      if (P.leader && s > 0.05) { const [lx, ly] = P.leader, ang = Math.atan2(ly - P.y, lx - P.x), rr = (P.r || Math.min(P.w, P.h) / 2) * s;   // 引线：从圈边指向场景里的对应物（如解剖图里的结石）
        L.line(c, [[P.x + Math.cos(ang) * rr, P.y + Math.sin(ang) * rr], [lx, ly]], 4, 'rgba(59,47,74,0.55)'); L.ring(c, lx, ly, 16, 4, 'rgba(59,47,74,0.55)'); }
      c.translate(P.x, P.y); c.scale(s, s);
      const path = () => { c.beginPath(); if (P.layout === 'circle') c.arc(0, 0, P.r, 0, Math.PI * 2); else if (P.layout === 'ellipse') c.ellipse(0, 0, P.w / 2, P.h / 2, 0, 0, Math.PI * 2); else L.rr(c, -P.w / 2, -P.h / 2, P.w, P.h, P.rr ?? 40); };
      const bw = P.layout === 'circle' ? 2 * P.r : P.w, bh = P.layout === 'circle' ? 2 * P.r : P.h;
      if (P.shadow !== false) { c.save(); c.translate(8, 12); path(); c.fillStyle = 'rgba(59,47,74,0.12)'; c.fill(); c.restore(); }
      c.save(); path(); c.clip(); blit(bw, bh); c.restore();
      if (P.ring !== null) { path(); c.lineWidth = P.ringW || 8; c.strokeStyle = P.ring || '#FFFFFF'; c.stroke(); }
      c.restore(); };
    const drawScene = (ctx, sc, t) => {
      if (HAND) { if (ONTWOS) { const Tq = Math.floor((sc.start + t) * 15 + 1e-6) / 15; t = Math.max(0, Tq - sc.start); } SK.on = true; SK.seed = SK.mode === 'paper' ? TL.scenes.indexOf(sc) * 7 : Math.floor((sc.start + t) * 15 + 1e-6) % 997; }
      ctx.save(); ctx.clearRect(0, 0, W, H);
      const TT = sc.start + t, ds = 1.012 + 0.008 * Math.sin(TT * 2 * Math.PI / 9), dx = 6 * Math.sin(TT * 2 * Math.PI / 13), dy = 6 * Math.sin(TT * 2 * Math.PI / 11);
      L.EXT = null; const mapped = sc.id !== 's00';
      ENGINE.drift = mapped && !LANDM() ? [ds, dx] : [1, 0];   // 本帧画面呼吸（竖屏），给 L.safeRight 扣掉；最坏情况 ds 1.02、|dx| 6 px
      if (mapped) {   // 封面（s00）按整幅画面设计：不呼吸、不做舞台映射，第一帧就是封面原样
        if (LANDM()) {   // 横屏：以舞台中心呼吸；背景向右延伸到整幅（设计坐标），右侧字卡浮在同一张背景上
          const S = OV.LAYOUT.stage, k = stageK(), DW = S.design_width || 1080, cx = S.x + DW / 2 * k, cy = S.y + S.h / 2;
          L.EXT = { x0: -S.x / k - 100, x1: (W - S.x) / k + 100 };
          ctx.translate(cx + dx, cy + dy); ctx.scale(ds, ds); ctx.translate(-cx, -cy);
        } else { ctx.translate(W / 2 + dx, H / 2 + dy); ctx.scale(ds, ds); ctx.translate(-W / 2, -H / 2); }
        stageMap(ctx);
      }
      const [DW, DH] = DWH();
      const fn = SC[sc.id] || (sc.id === 's99' ? SC.outro || ((cc, A) => L.bg(cc, DW, DH, L.P.paper, L.P.paper2, 47, A.t)) : null) || (sc.id === 's00' ? coverFn() : null) || (sc.id === 'sref' ? SC.refs_bg || ((cc, A) => L.bg(cc, DW, DH, L.P.paper, L.P.paper2, 53, A.t)) : null);
      const A_ = mkA(sc, t), PX = pixActive(sc, t), vis = visRect(mapped);
      L.HIDE = PX.hide; L.PIXBG = PX.under.length ? (cc) => { for (const q of PX.under) drawPix(cc, q, vis); } : null; L.NOFOOT = 0;
      try { if (fn) fn(ctx, A_); else { L.bg(ctx, DW, DH, L.P.paper, L.P.paper2, 3, TT); ENGINE.err(`场景 ${sc.id} 没有画面代码：src/scenes.js 里要写 SC.${sc.id} = (c, A) => {…}`); ctx.fillStyle = 'magenta'; ctx.fillRect(0, 0, 80, 80); }
        for (const q of PX.over) drawPix(ctx, q, vis); }
      catch (e) { const m = /(scenes|anat|shots|props|lib)\.js:(\d+)/.exec(e.stack || ''); ENGINE.err(`场景 ${sc.id} 运行出错：${e.message}${m ? `（src/${m[1]}.js 第 ${m[2]} 行）` : ''}`); ctx.fillStyle = 'magenta'; ctx.fillRect(0, 0, 80, 80); }
      const full = Math.max(L.NOFOOT || 0, ...PX.over.concat(PX.under).filter((q) => q.m.pix.layout === 'full').map(pixA));   // 整幅皮克斯画面上不叠底部水波（像一层雾）
      L.HIDE = null; L.PIXBG = null; L.NOFOOT = 0;
      ctx.restore(); footer(ctx, TT, 1 - full); SK.on = false; if (HAND) SK.finish(ctx, W, H); else L.grain(ctx, W, H);
    };
    const overlays = (ctx, sc, T) => {
      const t = T - sc.start; SK.on = HAND; SK.seed = Math.floor(T * 15) % 997;
      if (sc.id === 's00') { OV.aiMark(ctx, T, TL); SK.on = false; return; }   // 封面自带标题，不叠进度条/字卡/字幕；AI 标识从第 0 帧起盖在封面上（GB 45438）
      if (sc.id === 'sref') { OV.refs(ctx, SB, t); OV.aiMark(ctx, T, TL); SK.on = false; return; }   // 参考文献页：整屏文字，不叠导航/字卡/字幕
      OV.header(ctx, SB, TL, T); OV.title(ctx, SB, TL, T); OV.aiMark(ctx, T, TL);
      if (sc.id === 's99') OV.outro(ctx, SB, t); else { OV.labels(ctx, sc, t, T); OV.subtitle(ctx, sc, t, T); }
      SK.on = false;
    };
    const TD = 0.8; // 转场：一道水浪从底部涨上来
    const sceneAt = (T) => { const i = TL.scenes.findIndex((s) => T >= s.start && T < s.end); return i < 0 ? TL.scenes.length - 1 : i; };
    const renderAt = (T, opt = {}) => {
      T = Math.max(0, Math.min(TL.duration - 1e-3, T)); const ov = opt.overlay !== false;
      const idx = sceneAt(T), sc = TL.scenes[idx];
      let a = null, b = null;
      if (idx < TL.scenes.length - 1 && T > sc.end - TD / 2) { a = sc; b = TL.scenes[idx + 1]; }
      else if (idx > 0 && T < sc.start + TD / 2) { a = TL.scenes[idx - 1]; b = sc; }
      if (!a) { drawScene(c, sc, T - sc.start); if (ov) overlays(c, sc, T); return; }
      const B = a.end, p = L.easeInOut(L.clamp((T - (B - TD / 2)) / TD));
      drawScene(off[0].getContext('2d'), a, T - a.start); drawScene(off[1].getContext('2d'), b, Math.max(0, T - b.start));
      c.drawImage(off[0], 0, 0);
      const Y = H + 200 - p * (H + 400); const wave = (x, k) => Y + 40 * Math.sin(x / 110 + p * 9 + k) + 20 * Math.sin(x / 47 - p * 13);
      c.save(); c.beginPath(); c.moveTo(-10, H + 10); for (let x = -10; x <= W + 10; x += 15) c.lineTo(x, wave(x, 0)); c.lineTo(W + 10, H + 10); c.closePath(); c.clip(); c.drawImage(off[1], 0, 0); c.restore();
      for (const [dy, col, lw] of [[0, L.P.water_dark, 46], [-26, L.P.water, 18]]) { c.beginPath(); for (let x = -10; x <= W + 10; x += 15) c.lineTo(x, wave(x, 0) + dy); c.lineWidth = lw; c.strokeStyle = col; c.stroke(); }
      const R = L.rand(7); for (let k = 0; k < 18; k++) { const x = R() * W; L.circle(c, x, wave(x, 0) - 40 - R() * 80, (8 + R() * 14) * (0.6 + 0.4 * Math.sin(p * 20 + k)), 'rgba(255,255,255,0.85)'); }
      if (ov) overlays(c, T < B ? a : b, T);
    };
    // 运动模糊：快门时间内画 n 个子帧（只画场景），按 1/(i+1) 透明度逐个叠加 = 求平均；字幕字卡只在中心时刻画一次，保持清晰；视频片段按主帧时刻取帧（MDT）
    const renderFrame = (T, { sub = 1, shutter = 0.5, fps = 30 } = {}) => {
      if (sub <= 1) return renderAt(T);
      const span = shutter / fps; ac.clearRect(0, 0, W, H);
      for (let i = 0; i < sub; i++) { MDT = (i / (sub - 1) - 0.5) * span; renderAt(T + MDT, { overlay: false }); MDT = 0; ac.globalAlpha = 1 / (i + 1); ac.drawImage(canvas, 0, 0); }
      ac.globalAlpha = 1; c.clearRect(0, 0, W, H); c.drawImage(acc, 0, 0);
      T = Math.max(0, Math.min(TL.duration - 1e-3, T)); overlays(c, TL.scenes[sceneAt(T)], T);
    };
    return { renderAt, renderFrame, prepare };
  };
})();
if (typeof module !== 'undefined') module.exports = ENGINE; else window.ENGINE = ENGINE;
