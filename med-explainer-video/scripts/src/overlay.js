// 叠字层：顶部进度条 + 章节名（横屏：章节导航）、开场片名、要点字卡（竖屏贴纸胶囊 / 横屏要点板）、字幕（按字级时间戳分块）、片尾、参考文献页（sref）、AI 生成标识。画面层不含任何文字。
// 版式全部来自 layout.json / layout_land.json（OV.setLayout；画幅由 width/height 决定），专题常量（角色名牌、片尾文献、免责声明、章节、本场主题）全部来自 storyboard（OV.setStoryboard）。本文件不写任何专题数据。
// 横屏（layout_land.json）：header.style "nav" 章节导航、labels.style "board" 要点板、ai_mark.anchor "bottom_right"、refs 文献页、title.enabled false —— 移植自 bph/src/overlay.js（10-20 交付版），数值全在 layout_land.json。
// 渲染期自检（OV.CHECK）：字卡底边越过字幕顶边 / 两张卡同一格位 / 字卡越出字卡区 / 字幕或字卡缩字号 / 右缘越过安全区 —— 只计数不中断，render.js 收集后写进 qa.json。
'use strict';
const OV = {};
(() => {
  let W = 1080, HGT = 1920;   // 画幅（OV.setLayout 按 layout.width/height 更新；竖屏 1080×1920、横屏 1920×1080）
  // ---------- 版式默认值 = layout.json v2（真源是 layout.json；这里只是没加载到文件时的兜底，数值必须与 layout.json 一致） ----------
  OV.LAYOUT = {
    width: 1080, height: 1920, safe_area_verified: false,
    top_reserved: [0, 120],
    header: { band: [120, 230], bar_y: 140, bar_height: 14, bar_margin_x: 90, bar_gap: 12, chapter_y: 192, chapter_size: 56, chapter_chip: true, chapter_chip_height: 72 },
    title: { size: 72, y: 300, until_seconds: 5, min_seconds: 3.0, fade_in: 0.5, fade_out: 0.6, max_width: 980, keepout_design_y: [236, 420] },
    stage: { top: 230, bottom: 1300, design_top: 236, design_bottom: 1236, scale: 1.0 },
    ai_mark: { text: 'AI 生成内容', min_ratio: 0.05, margin_px: 4, from: 0, show_seconds: 3.0, fade_out: 0.5, x: 48, y: 252 },
    labels: { style: 'pill', band: [1300, 1452], x: 60, width: 840, max_default: 2, max_on_screen: 3, min_stay: 2.5, min_stay_alert: 3.5, size: 48, row_height: 70, gap: 14, big_size: 50, big_pad: 40, pad_l: 30, dot: 16, dot_gap: 18, pad_r: 34, radius: 'half', shadow: { alpha: 0.08, dy: 5, blur: 10 }, alert_ring: 3, secondary_weight: 500, dot_dim_alpha: 0.6, pop: { seconds: 0.4, text_fade: 0.25, leave_rise: 12 }, compact: { size: 40, row_height: 54, gap: 12, dot: 14, big_size: 46 }, newest_highlight_seconds: 2.2 },
    subtitle: { y: 1552, size: 74, center_x: 480, max_width: 840, max_chars: 11, name_size: 36, stroke: 0.24, lead: 0.06, tail: 0.3 },
    bottom_reserved: [1600, 1920],
    footer: { waves: [1700, 1760], enabled: true },
    safe: { right_x: 900, y_from: 900, y_to: 1600 },
    outro: { slogan_y: 1060, slogan_size: 56, block_y: 1200, disclaimer_size: 42, ai_note_size: 32, ref_size: 27, ref_line: 40, credit_size: 24, max_width: 1000 },
    fonts: { sub: { family: '"HeiTiSub"', weight: 900 }, label: { family: '"HeiTiSub"', weight: 700 }, title: { family: '"DeYiHei","HeiTiSub"', weight: 400 }, ref: { family: '"HeiTiSub"', weight: 400 } },   // 只用开源字体、不写系统回退（10-21 用户定）；缺字由 tools/check_fonts.py 在 QA 门报出
  };
  const merge = (a, b) => { for (const k in b) { if (k.startsWith('_')) continue; if (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k]) && a[k] && typeof a[k] === 'object' && !Array.isArray(a[k])) merge(a[k], b[k]); else a[k] = b[k]; } return a; };
  const fontsReady = () => { const F = OV.LAYOUT.fonts; F.label2 = { family: F.label.family, weight: (OV.LAYOUT.labels || {}).secondary_weight || 500 }; return F; };   // 字卡说明段：同字体、细一档
  OV.setLayout = (j) => { merge(OV.LAYOUT, j || {}); OV.FONTS = fontsReady(); W = OV.LAYOUT.width || 1080; HGT = OV.LAYOUT.height || 1920; OV._aiFont = null; refCache = null; };
  OV.TL = null; OV.refsPage = false;
  OV.setTimeline = (TL) => { OV.TL = TL; OV.refsPage = !!(TL && TL.scenes && TL.scenes.some((s) => s.id === 'sref')); refCache = null; };   // 章节名 / 参考文献页数 / 片尾是否重复短清单 要看 timeline
  OV.FONTS = fontsReady();
  OV.setFonts = (f) => { Object.assign(OV.FONTS, f); };
  const fnt = (size, role = 'sub') => { const f = OV.FONTS[role] || OV.FONTS.sub; return `${f.weight} ${size}px ${f.family}`; };
  OV.fnt = fnt;

  // ---------- 专题数据：全部来自 storyboard ----------
  // characters[who] = { name, color }：角色台词的名牌（旁白 narrator 不出名牌）。没写 color 的按顺序取默认色。
  const DEF_COLORS = ['#4F6C99', '#C9566F', '#9C5A35', '#2F8C83', '#D08A12', '#6B4A33', '#7A5BA8'];
  OV.CH = {}; OV.SB = null;
  OV.setStoryboard = (SB) => { OV.SB = SB; OV.CH = {}; let k = 0;
    for (const [who, ch] of Object.entries(SB.characters || {})) { if (who === 'narrator' || ch.no_badge) continue; OV.CH[who] = [ch.name || who, ch.color || DEF_COLORS[k++ % DEF_COLORS.length]]; } };

  // ---------- 渲染期自检 ----------
  // counts：帧计数；items[kind][scene|text]：去重后的每张卡/每块字幕（frames 帧数、min_size 最小字号、first_T 首次时刻）
  OV.CHECK = { counts: {}, items: {} };
  OV.resetCheck = () => { OV.CHECK = { counts: {}, items: {} }; };
  const flag = (kind, T, info) => { const C = OV.CHECK; C.counts[kind] = (C.counts[kind] || 0) + 1; const I = (C.items[kind] = C.items[kind] || {}); const key = `${info.scene}|${info.text || info.kind || ''}|${info.b || ''}`;
    const it = I[key] || (I[key] = { ...info, frames: 0, first_T: Math.round(T * 1000) / 1000 }); it.frames++; if (info.size != null) { it.min_size = Math.min(it.min_size ?? info.size, info.size); delete it.size; } };
  OV.flag = flag;
  const inSafeY = (y0, y1) => { const S = OV.LAYOUT.safe; return y1 >= S.y_from && y0 <= S.y_to; };

  const pop = (t, a, d = 0.42) => (t < a ? 0 : L.backOut(L.seg(t, a, a + d)));
  const txt = (c, s, x, y, size, col, stroke, font = 'sub', align = 'center', sw = 0.24) => {
    c.font = fnt(size, font); c.textAlign = align; c.textBaseline = 'middle';
    if (stroke) { c.lineJoin = 'round'; c.lineWidth = size * sw; c.strokeStyle = stroke; c.strokeText(s, x, y); }
    c.fillStyle = col; c.fillText(s, x, y);
  };
  OV.txt = txt; OV.F_SUB = 'sub'; OV.F_TITLE = 'title';
  OV.dark = false;   // 深色主题（Kurzgesagt 式）
  // 字体里没有“→”：按段排字，箭头用线条画（与文字同色）
  const AW = (size) => size * 1.05;
  const measureA = (c, s, size, font) => { c.font = fnt(size, font); const parts = s.split('→'); return parts.reduce((w, q) => w + c.measureText(q).width, 0) + (parts.length - 1) * AW(size); };
  OV.measureA = measureA;
  const fitSize = (c, s, size, font, maxW) => { const w = measureA(c, s, size, font); return w > maxW ? Math.floor(size * maxW / w) : size; };   // 太宽就缩字号（不截断）
  OV.fitSize = fitSize;
  const txtA = (c, s, x, y, size, col, font, align = 'left') => {
    const parts = s.split('→'); if (parts.length === 1) return txt(c, s, x, y, size, col, null, font, align);
    let cx = align === 'center' ? x - measureA(c, s, size, font) / 2 : x; c.font = fnt(size, font);
    parts.forEach((q, i) => { txt(c, q, cx, y, size, col, null, font, 'left'); cx += c.measureText(q).width;
      if (i < parts.length - 1) { const w = AW(size), m = size * 0.11; L.line(c, [[cx + w * 0.18, y + 1], [cx + w * 0.8, y + 1]], m, col); L.line(c, [[cx + w * 0.58, y - size * 0.2], [cx + w * 0.82, y + 1], [cx + w * 0.58, y + size * 0.22]], m, col); cx += w; } });
  };

  // ---------- 顶部：分段进度条 + 当前章节名（片名不常驻；0–120 留给平台顶栏） ----------
  // 横屏顶部章节导航（layout.header.style = "nav"，bph 10-20 D 改良要点板）：只列 storyboard.chapters[].nav !== false 的章；当前章蓝底白字 + 章内进度细线，讲过的蓝字，没讲到的灰字；封面过后逐个弹入（每颗间隔 pop_each 秒，轻微回弹）
  const navLock = (c, SB, TL, T) => {
    const P = L.P, Hd = OV.LAYOUT.header, chs = TL.chapters || [], n = chs.length; if (!n) return;
    let ci = chs.findIndex((ch) => T >= ch.start && T < ch.end); if (ci < 0) ci = n - 1;
    const meta = SB.chapters || [], sz = Hd.size || 30, h = Hd.height || 60, pad = Hd.pad ?? 52, T0 = (TL.cover || 0) + (Hd.pop_start ?? 0.25), each = Hd.pop_each ?? 0.12, dur = Hd.pop_seconds ?? 0.42;
    const vis = chs.map((ch, k) => ({ ch, k })).filter((o) => { const m = meta.find((q) => q.id === o.ch.id) || meta[o.k]; return !(m && m.nav === false); });
    let x = Hd.x ?? 60; const y = Hd.y ?? 62;
    vis.forEach((o, j) => {
      const name = o.ch.node, st = o.k < ci ? 'done' : o.k === ci ? 'cur' : 'todo';
      c.font = fnt(sz, 'label'); const w = c.measureText(name).width + pad;
      const pe = L.clamp((T - T0 - j * each) / dur); if (pe <= 0) return; const ps = L.lerp(0.6, 1, L.backOut(pe));
      c.save(); c.globalAlpha *= L.clamp(pe * 1.8); c.translate(x + w / 2, y); c.scale(ps, ps); c.translate(-(x + w / 2), -y);
      L.fillRR(c, x + 3, y - h / 2 + 5, w, h, h / 2, 'rgba(59,47,74,0.10)');
      if (st === 'cur') {
        L.fillRR(c, x, y - h / 2, w, h, h / 2, P.water_dark); txt(c, name, x + w / 2, y - 4, sz, '#FFFFFF', null, 'label');
        const f = L.clamp((T - o.ch.start) / (o.ch.end - o.ch.start)); L.fillRR(c, x + 24, y + h / 2 - 12, w - 48, 4, 2, 'rgba(255,255,255,0.28)'); L.fillRR(c, x + 24, y + h / 2 - 12, Math.max(4, (w - 48) * f), 4, 2, '#FFFFFF');
      } else {
        L.fillRR(c, x, y - h / 2, w, h, h / 2, 'rgba(255,255,255,0.90)');
        txt(c, name, x + w / 2, y + 1, sz, st === 'done' ? P.water_dark : 'rgba(80,70,92,0.55)', null, 'label');
      }
      c.restore(); x += w;
      if (j < vis.length - 1) { const ce = L.clamp((T - T0 - j * each - 0.2) / 0.25); if (ce > 0) L.fillRR(c, x + 8, y - 2, (Hd.connector ?? 24) * ce, 4, 2, o.k < ci ? P.water_dark : 'rgba(255,255,255,0.8)'); x += Hd.gap ?? 40; }
    });
  };
  OV.header = (c, SB, TL, T) => {
    const P = L.P, Lt = OV.LAYOUT, Hd = Lt.header; if (Hd && Hd.style === 'nav') return navLock(c, SB, TL, T);
    const a = L.fin(T, (TL.cover || 0) + 0.15, 0.6);   // 从正片开始（封面之后）淡入
    if (a <= 0) return;
    c.save(); c.globalAlpha *= a;
    const gh = Lt.stage.top + 10, gr = c.createLinearGradient(0, 0, 0, gh); const hb = OV.dark ? '12,14,38' : '255,244,226'; gr.addColorStop(0, `rgba(${hb},0.96)`); gr.addColorStop(0.8, `rgba(${hb},0.88)`); gr.addColorStop(1, `rgba(${hb},0)`); c.fillStyle = gr; c.fillRect(0, 0, W, gh);
    const chs = TL.chapters || [], n = chs.length; if (!n) { c.restore(); return; }
    let ci = chs.findIndex((ch) => T >= ch.start && T < ch.end); if (ci < 0) ci = n - 1;
    const x0 = Hd.bar_margin_x, x1 = W - Hd.bar_margin_x, gap = Hd.bar_gap, sw = (x1 - x0 - gap * (n - 1)) / n, by = Hd.bar_y, bh = Hd.bar_height;
    chs.forEach((ch, k) => { const x = x0 + k * (sw + gap), f = k < ci ? 1 : k > ci ? 0 : L.clamp((T - ch.start) / (ch.end - ch.start));
      L.fillRR(c, x, by - bh / 2, sw, bh, bh / 2, OV.dark ? 'rgba(255,255,255,0.18)' : 'rgba(110,97,120,0.16)'); if (f > 0) L.fillRR(c, x, by - bh / 2, Math.max(bh, sw * f), bh, bh / 2, k === ci ? P.water_dark : L.alpha(P.water_dark, 0.55)); });
    const cur = chs[ci].node, ca = L.fin(T, chs[ci].start + 0.1, 0.4), cs = Hd.chapter_size;
    c.save(); c.globalAlpha *= ca; c.font = fnt(cs, 'label'); const cw = c.measureText(cur).width + cs * 1.2, chh = Hd.chapter_chip_height;
    if (Hd.chapter_chip) L.fillRR(c, W / 2 - cw / 2, Hd.chapter_y - chh / 2, cw, chh, chh / 2, OV.dark ? 'rgba(255,255,255,0.14)' : '#FFFFFF');
    txt(c, cur, W / 2, Hd.chapter_y + 1, cs, OV.dark ? '#FFFFFF' : P.water_dark, Hd.chapter_chip ? null : (OV.dark ? 'rgba(10,12,40,0.9)' : '#FFFFFF'), 'label'); c.restore();
    c.restore();
  };

  // ---------- 片名：只在正片开场前 title.until_seconds 秒出现在舞台内，然后上滑退场 ----------
  OV.title = (c, SB, TL, T) => {
    const Lt = OV.LAYOUT, Tt = Lt.title; if (!Tt || Tt.enabled === false) return;   // 横屏：片名只在封面上，正片顶部是章节导航
    const AM = Lt.ai_mark, markEnd = AM && AM.text ? (AM.from || 0) + (AM.show_seconds || 0) : 0;
    const T0 = Math.max((TL.cover || 0) + 0.15, markEnd), T1 = Math.max((TL.cover || 0) + Tt.until_seconds, T0 + (Tt.min_seconds || 0)), main = SB.title_card && SB.title_card.main; if (!main) return;   // 片名等 AI 标识退场再入（两者都在左上/上方）
    const ain = L.fin(T, T0, Tt.fade_in), aout = 1 - L.seg(T, T1 - Tt.fade_out, T1), a = ain * aout; if (a <= 0.001) return;
    const P = L.P; c.save(); c.globalAlpha *= a;
    c.font = fnt(Tt.size, 'title'); const tsz = Math.min(Tt.size, Math.floor(Tt.size * Tt.max_width / c.measureText(main).width));
    txt(c, main, W / 2, Tt.y + (1 - ain) * 30 - (1 - aout) * 60, tsz, OV.dark ? '#FFFFFF' : P.ink, OV.dark ? 'rgba(10,12,40,0.9)' : '#FFFFFF', 'title', 'center', 0.22);
    c.restore();
  };

  // ---------- AI 生成标识（GB 45438—2025：起始画面显式标识，文字高 ≥ 画面最短边 5%，从第 0 帧起持续 ≥ 2 s；片尾另有 outro.ai_note）----------
  // 移植自 bph/src/overlay.js OV.aiMark：按实测字形高度迭代放大字号到 ≥ ceil(短边×min_ratio)+margin_px；第 0 帧满不透明、不淡入，show_seconds 后 fade_out 秒淡出。
  // 每帧写 OV.lastAiMark = { T, alpha, shown, size, ink, need, x, y, w, h }，frames.js / render.js 汇总进 overlay.json 的 ai_mark，qa.py 判定。
  OV.lastAiMark = null; OV._aiFont = null;
  OV.aiMark = (c, T, TL) => {
    const A = OV.LAYOUT.ai_mark; if (!A || !A.text) { OV.lastAiMark = null; return; }
    const Wc = c.canvas.width, Hc = c.canvas.height, short = Math.min(Wc, Hc), need = Math.ceil(short * (A.min_ratio ?? 0.05)) + (A.margin_px ?? 4);
    const t0 = A.from || 0, t1 = t0 + (A.show_seconds ?? 3), fo = A.fade_out ?? 0.5, alpha = T < t0 - 1e-6 || T >= t1 ? 0 : T <= t1 - fo ? 1 : 1 - L.seg(T, t1 - fo, t1);
    if (!OV._aiFont || OV._aiFont.text !== A.text || OV._aiFont.need !== need) {   // 字号只算一次（同文本、同要求）
      let size = Math.max(need, 60), ink = 0;
      for (let k = 0; k < 8; k++) { c.font = fnt(size, 'label'); const m = c.measureText(A.text); ink = m.actualBoundingBoxAscent + m.actualBoundingBoxDescent; if (ink >= need) break; size = Math.ceil(size * need / Math.max(1, ink)) + 1; }
      c.font = fnt(size, 'label'); OV._aiFont = { text: A.text, need, size, ink, tw: c.measureText(A.text).width };
    }
    const F = OV._aiFont, padX = F.size * 0.42, bh = F.size * 1.42, bw = F.tw + padX * 2;
    const BR = A.anchor === 'bottom_right', x = BR ? (A.right ?? Wc - 40) - bw : (A.x ?? 48), y = BR ? (A.bottom ?? Hc - 40) - bh : (A.y ?? 252);   // 竖屏左上（x,y）；横屏右下（right,bottom 锚）
    OV.lastAiMark = { T: Math.round(T * 1000) / 1000, alpha: Math.round(alpha * 1000) / 1000, shown: alpha >= 0.999, size: F.size, ink: Math.round(F.ink * 10) / 10, need, x, y, w: Math.round(bw), h: Math.round(bh) };
    if (alpha <= 0.001) return;
    c.save(); c.globalAlpha *= alpha;
    L.fillRR(c, x + 5, y + 7, bw, bh, bh * 0.28, 'rgba(0,0,0,0.16)'); L.fillRR(c, x, y, bw, bh, bh * 0.28, 'rgba(40,32,52,0.86)');
    txt(c, A.text, x + bw / 2, y + bh / 2 + F.size * 0.04, F.size, '#FFFFFF', null, 'label');
    c.restore();
  };
  OV.aiTag = OV.aiMark;   // 旧名兼容

  // ---------- 要点字卡「贴纸胶囊」：自适应宽、圆角 = 半高、软投影、色点；big = 红底大标题胶囊常驻第 0 格；alert = 红点 + 红字 + 红描边 ----------
  // 格位：固定槽位从上往下排（compact 以底边为锚向上堆）；最新一张色点饱和；超过上限时最老的淡出上移、其余上移一格；太长就缩字号，不截断（记 label_shrunk）。
  // 文字两档字重：第一个“（”或“：”之前是主词（700 墨色），之后是说明（secondary_weight，ink2）；big 不拆。
  const splitLabel = (s) => { const i = s.search(/[（：]/); return i > 0 ? [s.slice(0, i), s.slice(i)] : [s, '']; };
  // ---------- 横屏要点板（layout.labels.style = "board"，bph 10-20 用户选定的 D 改良要点板） ----------
  // 一块白板浮在右侧：板头 = 本场最近一张 big 卡（红底，术式名）或本场主题 scene.topic（蓝底；没写 topic 用章节名）；条目带色点，最新一条黄底高亮；
  // 同屏格数 maxN = (scene.max_labels || max_default) + extra_rows，超过时旧条整体上移、最老淡出（与竖屏同一套进出节奏；timeline 的 card_stays 用 big_takes_slot=False 算停留）
  const chapName = () => { const TL = OV.TL, T = OV._T || 0; if (!TL || !TL.chapters || !TL.chapters.length) return ''; const chs = TL.chapters; let ci = chs.findIndex((ch) => T >= ch.start && T < ch.end); if (ci < 0) ci = chs.length - 1; return chs[ci].node; };
  const topicOf = (sc) => { const s = OV.SB && OV.SB.scenes ? OV.SB.scenes.find((q) => q.id === sc.id) : null; return (s && s.topic) || chapName(); };
  const slotsOf = (items, maxN, t, POP) => {   // 超过上限时旧条整体上移、最老淡出，新条等旧条让位（enter_delay）后落在最终位置再淡入
    const D = POP.rotate_seconds ?? 0.3, dl = POP.enter_delay ?? 0.22, ps = POP.seconds ?? 0.4, hi = (OV.LAYOUT.labels || {}).newest_highlight_seconds ?? 2.4;
    const sh = Math.max(0, items.reduce((s, l) => s + L.easeInOut(L.clamp((t - l.t) / D)), 0) - maxN), out = [];
    items.forEach((l, k) => { const nAt = items.filter((m) => m.t <= l.t).length, enter = nAt > maxN && t - l.t < D, slot = enter ? k - (nAt - maxN) : k - sh;
      if (slot < -1 || slot > maxN - 1 + 1e-3) return; out.push({ l, k, slot, fade: slot < 0 ? 1 + slot : 1, p: L.clamp((t - l.t - (enter ? dl : 0)) / ps), newest: k === items.length - 1 && t - l.t < hi }); });
    return out;
  };
  const labelsBoard = (c, sc, t, Tabs) => {
    const P = L.P, Lt = OV.LAYOUT, Lb = Lt.labels, T = Tabs == null ? (sc.start || 0) + t : Tabs; OV._T = T;
    const maxN = (sc.max_labels || Lb.max_default || 3) + (Lb.extra_rows || 0), all = (sc.labels || []).filter((l) => t >= l.t).sort((a, b) => a.t - b.t); if (!all.length) return;
    const bigs = all.filter((l) => l.big), items = all.filter((l) => !l.big), lastBig = bigs[bigs.length - 1];
    const X = Lb.x, BW = Lb.width, HH = Lb.head_height || 82, ROW = Lb.row_height || 82, PAD = Lb.pad ?? 16, RAD = Lb.radius ?? 28, POP = Lb.pop || {}, SH = Lb.shadow || { alpha: 0.16, dx: 6, dy: 10 };
    const TOP = Lb.center_y != null ? Math.max(Lb.top_min ?? 150, Math.round(Lb.center_y - (HH + PAD * 2 + maxN * ROW) / 2)) : (Lb.top ?? 168);   // 按满格高度把板子居中到 center_y
    const nAnim = Math.min(maxN, items.reduce((s, l) => s + L.easeOut(L.clamp((t - l.t) / 0.35)), 0)), BH = HH + (items.length ? PAD * 2 + nAnim * ROW : 0);
    const ap = L.clamp((t - all[0].t) / (POP.board_seconds ?? 0.45)), s0 = L.lerp(0.94, 1, L.backOut(ap));
    const subTop = Lt.subtitle.y - Lt.subtitle.size * 0.5; if (ap > 0.05 && TOP + BH > subTop) flag('label_over_subtitle', T, { scene: sc.id, text: '要点板', bottom: Math.round(TOP + BH), subtitle_top: Math.round(subTop) });
    c.save(); c.globalAlpha *= L.clamp(ap * 1.6); c.translate(X + BW / 2, TOP); c.scale(s0, s0); c.translate(-(X + BW / 2), -TOP);
    L.fillRR(c, X + (SH.dx ?? 6), TOP + (SH.dy ?? 10), BW, BH, RAD, `rgba(59,47,74,${SH.alpha ?? 0.16})`); L.fillRR(c, X, TOP, BW, BH, RAD, OV.dark ? 'rgba(26,30,70,0.96)' : 'rgba(255,255,255,0.97)');
    c.save(); L.rr(c, X, TOP, BW, BH, RAD); c.clip();
    const hc = lastBig ? P.red : P.water_dark; c.fillStyle = hc; c.fillRect(X, TOP, BW, HH);
    const head = lastBig ? lastBig.text.replace(/·/g, '•') : (Lb.topic_head === false ? chapName() : topicOf(sc)), ha = lastBig ? L.fin(t, lastBig.t, 0.4) : 1, HX = Lb.head_x ?? 34, HS = Lb.head_size || 42;
    const hs = fitSize(c, head, HS, 'title', BW - 2 * HX); if (hs < HS) flag('label_shrunk', T, { scene: sc.id, text: head, size: hs, size0: HS });
    c.globalAlpha *= ha; txtA(c, head, X + HX, TOP + HH / 2 + 2, hs, '#FFFFFF', 'title', 'left'); c.globalAlpha /= Math.max(ha, 1e-3);
    const SZ = Lb.size || 40, TX = Lb.text_x ?? 68, TW = BW - TX - (Lb.text_pad_r ?? 32), hi = Lb.newest_highlight_seconds ?? 2.4;
    for (const o of slotsOf(items, maxN, t, POP)) {
      const l = o.l, y = TOP + HH + PAD + o.slot * ROW, e = L.easeOut(o.p); if (e <= 0) continue;
      c.save(); c.globalAlpha *= e * o.fade; c.translate((1 - e) * (POP.slide ?? 26), 0);
      if (o.newest) { const hl = 1 - L.seg(t, l.t + hi - 0.8, l.t + hi); L.fillRR(c, X + 14, y + 6, BW - 28, ROW - 12, 14, `rgba(255,232,150,${0.55 * hl})`); }
      if (o.slot > 0.05) { c.fillStyle = OV.dark ? 'rgba(255,255,255,0.10)' : 'rgba(59,47,74,0.08)'; c.fillRect(X + 30, y, BW - 60, 2); }
      L.circle(c, X + (Lb.dot_x ?? 44), y + ROW / 2, Lb.dot ?? 9, l.alert ? P.red : P.water_dark);
      const sz = fitSize(c, l.text, SZ, 'label', TW); if (sz < SZ && e * o.fade > 0.05) flag('label_shrunk', T, { scene: sc.id, text: l.text, size: sz, size0: SZ });
      txtA(c, l.text, X + TX, y + ROW / 2 + 2, sz, OV.dark ? '#FFFFFF' : (l.alert ? P.red_dark : P.ink), 'label', 'left');
      c.restore();
    }
    c.restore(); c.restore();
  };
  OV.labels = (c, sc, t, Tabs) => {
    if ((OV.LAYOUT.labels || {}).style === 'board') return labelsBoard(c, sc, t, Tabs);
    const P = L.P, Lt = OV.LAYOUT, Lb = Lt.labels, maxN = Math.min(sc.max_labels || Lb.max_default, Lb.max_on_screen || Infinity), X0 = Lb.x, MAXW = Lb.width, T = Tabs == null ? (sc.start || 0) + t : Tabs;   // 同屏上限 max_on_screen（方案二：3）
    const all = (sc.labels || []).filter((l) => t >= l.t).sort((a, b) => a.t - b.t); if (!all.length) return;
    const compact = maxN > Lb.max_default, Cp = Lb.compact, H = compact ? Cp.row_height : Lb.row_height, GAP = compact ? Cp.gap : Lb.gap, sizeN = compact ? Cp.size : Lb.size, DOT = compact ? (Cp.dot || Lb.dot) : Lb.dot, bigSize = compact ? (Cp.big_size || Lb.big_size) : Lb.big_size;
    const GAPe = compact || maxN < 2 ? GAP : Math.min(GAP, (Lb.band[1] - Lb.band[0] - maxN * H) / (maxN - 1));   // 普通模式：行距最多压到让 maxN 行正好填满字卡区（方案二 1300–1452 放 2×70 时行距 14→12）
    const colTop = compact ? Lb.band[1] - maxN * (H + GAP) + GAP : Lb.band[0];   // compact：以底边为锚向上堆，永远不越过 band[1]
    const subTop = Lt.subtitle.y - Lt.subtitle.size * 0.5;   // 字幕字框顶边（em box；描边再往上几像素不算）
    const D = 0.3, ease = (x) => L.easeInOut(L.clamp(x)), POP = Lb.pop || { seconds: 0.4, text_fade: 0.25, leave_rise: 12 }, R = Lb.radius === 'half' || Lb.radius == null ? H / 2 : +Lb.radius, SH = Lb.shadow || { alpha: 0.14, dy: 10, blur: 18 };
    const bigs = all.filter((l) => l.big), big = bigs.length ? bigs[bigs.length - 1] : null, prevBig = bigs.length > 1 ? bigs[bigs.length - 2] : null;
    const baseF = big ? ease((t - big.t) / D) : 0, cap = maxN - (big ? 1 : 0);   // big 占第 0 格：普通卡从第 1 格起（下推进度 baseF），可用格数 cap
    const norm = all.filter((l) => !l.big);
    // 普通卡轮换：超出上限时每进来一张，旧卡整栏上移一格（0.3 s）、最老的淡出；新卡等旧卡让出位置（0.22 s 后）再弹入。
    // big 进场：有空位时普通卡整栏随 baseF 下移一格；栏已满时上移（淘汰最老）与下移抵消——幸存的卡原地不动，被挤掉的那张在原位淡出上移、big 等它让开（0.22 s）再弹入。
    const sumE = norm.reduce((s, l) => s + ease((t - l.t) / D), 0), shPre = Math.max(0, sumE - maxN), shPost = Math.max(0, sumE - cap), sh = shPre + (shPost - shPre) * baseF;
    const bigDelay = big && (norm.filter((l) => l.t <= big.t).length >= maxN || prevBig) ? 0.22 : 0;
    const used = new Map();
    const dark = OV.dark, inkMain = dark ? '#FFFFFF' : P.ink, inkSec = dark ? 'rgba(255,255,255,0.75)' : P.ink2, cardFill = dark ? 'rgba(22,26,64,0.92)' : '#FFFFFF';
    // 一张卡：row 是它的格位（可为分数，淘汰中为负），q 是弹入进度（0..1 含过冲），fade 是淘汰淡出，newest 决定色点饱和
    const draw = (l, row, q, fade, newest, leaveP) => {
      const [main, sec] = l.big ? [l.text.replace(/·/g, '•'), ''] : splitLabel(l.text);
      const size0 = l.big ? bigSize : sizeN, fontM = l.big ? 'title' : 'label', pads = l.big ? 2 * Lb.big_pad : Lb.pad_l + DOT + Lb.dot_gap + Lb.pad_r;
      const mw = (sz) => measureA(c, main, sz, fontM) + (sec ? measureA(c, sec, sz, 'label2') : 0);
      const m0 = mw(size0), size = m0 + pads > MAXW ? Math.floor(size0 * (MAXW - pads) / m0) : size0, w = Math.min(MAXW, mw(size) + pads);
      const X = Lb.align === 'center' ? Math.max(X0, Math.min(Lb.center_x ?? (Lt.width || 1080) / 2, ((Lt.safe || {}).right_x ?? 1e9) - w / 2) - w / 2) : X0;   // align=center：每张卡按自身宽度居中，右缘过 safe.right_x 才往左让（10-23 用户：字卡字幕偏左）
      const yRow = Math.min(colTop + Math.max(row, 0) * (H + (compact ? GAP : GAPe)), Lb.band[1] - H) - POP.leave_rise * (leaveP || 0), p = L.clamp(q);   // 任何一张卡的底边都不越过字卡区底边
      // 自检（可见度 = 弹入 × 淡出）
      const alpha = L.clamp(q * 1.4) * fade;
      if (size < size0 && alpha > 0.05) flag('label_shrunk', T, { scene: sc.id, text: l.text, size, size0 });
      const rs = Math.round(row); if (Math.abs(row - rs) < 0.02 && alpha > 0.5 && !(leaveP > 0)) { if (used.has(rs)) flag('label_slot_collision', T, { scene: sc.id, slot: rs, a: used.get(rs), b: l.text, text: used.get(rs) }); else used.set(rs, l.text); }
      if (alpha > 0.05) { if (yRow + H > Lb.band[1] + 0.5) flag('label_below_band', T, { scene: sc.id, text: l.text, bottom: Math.round(yRow + H), band: Lb.band[1] });
        if (yRow + H > subTop) flag('label_over_subtitle', T, { scene: sc.id, text: l.text, bottom: Math.round(yRow + H), subtitle_top: Math.round(subTop) });
        if (X + w > Lt.safe.right_x && inSafeY(yRow, yRow + H)) flag('safe_right', T, { scene: sc.id, kind: 'label', right: X + w, text: l.text }); }
      if (alpha <= 0.001) return;
      // 弹入：胶囊从色点（直径 DOT 的圆）展开到全宽全高（以色点为锚向右长），文字在后 text_fade 秒淡入
      const cx = X + (l.big ? Lb.big_pad : Lb.pad_l), e = L.backOut(p), x0 = L.lerp(cx - DOT / 2, X, e), x1 = L.lerp(cx + DOT / 2, X + w, e), hh = L.lerp(DOT, H, e), yy = yRow + (H - hh) / 2, rr = Math.min(R, hh / 2);
      const tA = L.clamp((q * POP.seconds - (POP.seconds - POP.text_fade)) / POP.text_fade);   // q 按 seconds 归一：最后 text_fade 秒文字淡入
      c.save(); c.globalAlpha *= fade;
      c.save(); c.shadowColor = `rgba(59,47,74,${SH.alpha})`; c.shadowBlur = SH.blur * 2; c.shadowOffsetY = SH.dy;   // Canvas 的 shadowBlur ≈ 2σ，PIL GaussianBlur(r) 的 σ = r
      L.fillRR(c, x0, yy, x1 - x0, hh, rr, l.big ? P.red : cardFill); c.restore();
      if (l.alert && Lb.alert_ring) { const k = Lb.alert_ring / 2; L.rr(c, x0 + k, yy + k, x1 - x0 - 2 * k, hh - 2 * k, Math.max(0, rr - k)); c.lineWidth = Lb.alert_ring; c.strokeStyle = P.red; c.stroke(); }   // 描边画在卡内侧（与 PIL outline 一致）
      if (!l.big) { const dc = l.alert ? P.red : newest ? P.water_dark : L.alpha(P.water_dark, Lb.dot_dim_alpha ?? 0.6); L.circle(c, cx, yRow + H / 2, DOT / 2, dc); }
      if (tA > 0) { c.globalAlpha *= tA; const ty = yRow + H / 2 + (l.big ? 0 : 1);
        if (l.big) txtA(c, main, X + Lb.big_pad, ty, size, '#FFFFFF', 'title', 'left');
        else { const tx = cx + DOT / 2 + Lb.dot_gap, colM = l.alert ? P.red_dark : inkMain, colS = l.alert ? P.red_dark : inkSec;
          txtA(c, main, tx, ty, size, colM, 'label', 'left'); if (sec) txtA(c, sec, tx + measureA(c, main, size, 'label'), ty, size, colS, 'label2', 'left'); } }
      c.restore();
    };
    const popQ = (l, delay) => (t - l.t - delay) / POP.seconds;
    if (prevBig && baseF < 1) draw(prevBig, 0, 1, 1 - baseF, false, baseF);   // 前一张 big 原地淡出上移（新 big 延迟弹入）
    norm.forEach((l, k) => {   // 先画普通卡，big 最后画在最上层（被挤走的卡从它底下淡出）
      const nAt = norm.filter((m) => m.t <= l.t).length, enter = nAt > cap && t - l.t < D, slotN = enter ? k - (nAt - cap) : k - sh, slot = slotN + baseF;
      if (slotN < -1 || slot > maxN - 1 + 1e-3) return;
      const leaving = slotN < 0, fade = leaving ? 1 + slotN : 1, homeRow = leaving ? (big && baseF >= 1 - 1e-6 ? 1 : 0) : slot;   // 淘汰：留在原格位、淡出并上移 leave_rise
      draw(l, homeRow, popQ(l, enter ? 0.22 : 0), fade, k === norm.length - 1 && t - l.t < Lb.newest_highlight_seconds, leaving ? -slotN : 0);
    });
    if (big) draw(big, 0, popQ(big, bigDelay), 1, t - big.t < Lb.newest_highlight_seconds, 0);
  };

  // ---------- 字幕：块在首字开口前 lead 秒出现，到下一块开口时切换；停顿 >0.6 s 则在末字后 tail 秒隐去。角色台词：名牌放在同一行左侧 ----------
  OV.subtitle = (c, sc, t, Tabs) => {
    const P = L.P, Lt = OV.LAYOUT, Sb = Lt.subtitle, T = Tabs == null ? (sc.start || 0) + t : Tabs;
    for (let li = 0; li < sc.lines.length; li++) {
      const ln = sc.lines[li], cs = ln.chunks || []; if (!cs.length) continue;
      // subtitle.yield_next（10-24 起模板版式打开；不写 = 旧画法）：句末块的停留按“下一句首块出现”截住，规则同句内换块——上一句的 tail 0.3 s 不再压住下一句首块
      // （同一人连说两句句间只停 gap_same 0.12 s，后句首块晚出 32–124 ms：nocturia 10 处、foam 旁白连句 53–125 ms）
      const nl = Sb.yield_next ? sc.lines.slice(li + 1).find((x) => (x.chunks || []).length) : null, nextA = nl ? nl.start + nl.chunks[0].start - Sb.lead : Infinity;
      const endL = ln.start + cs[cs.length - 1].end, lastHold = nextA === Infinity ? endL + Sb.tail : Math.min(nextA, endL + (nextA - endL > 0.6 ? Sb.tail : 1e9));
      if (t < ln.start + cs[0].start - Sb.lead || (nextA === Infinity ? t > lastHold : t >= lastHold)) continue;
      let cur = null;
      for (let k = 0; k < cs.length; k++) {
        const a = ln.start + cs[k].start - Sb.lead, nxt = k + 1 < cs.length ? ln.start + cs[k + 1].start - Sb.lead : nextA;
        const hold = Math.min(nxt, ln.start + cs[k].end + (nxt - (ln.start + cs[k].end) > 0.6 ? Sb.tail : 1e9));
        if (t >= a && t < hold) cur = cs[k];
      }
      if (!cur) return;
      const s = cur.text.replace(/[。]$/, ''), who = OV.CH[ln.who], S0 = Sb.size, y = Sb.y, NS = Sb.name_size, CX = Sb.center_x;
      c.font = fnt(NS); const bw = who ? c.measureText(who[0]).width + 34 : 0, bg = who ? 18 : 0;
      c.font = fnt(S0); const tw0 = c.measureText(s).width, size = Math.min(S0, Math.floor(S0 * (Sb.max_width - bw - bg) / tw0)); c.font = fnt(size); const tw = c.measureText(s).width;
      const tot = bw + bg + tw, x0 = Math.min(CX - tot / 2, ((Lt.safe || {}).right_x ?? 1e9) - tot), right = x0 + tot;   // 居中；右缘过 safe.right_x 才往左让
      // ---- 自检 ----
      if (size < S0) flag('subtitle_shrunk', T, { scene: sc.id, text: s, size, size0: S0 });
      if (right > Lt.safe.right_x && inSafeY(y - S0 / 2, y + S0 / 2)) flag('safe_right', T, { scene: sc.id, kind: 'subtitle', right: Math.round(right), text: s });
      if (who) { L.fillRR(c, x0, y - NS * 0.72, bw, NS * 1.44, NS * 0.72, who[1]); txt(c, who[0], x0 + bw / 2, y + 1, NS, '#FFFFFF', null); txt(c, s, x0 + bw + bg, y, size, '#FFFFFF', who[1], 'sub', 'left', Sb.stroke); }
      else txt(c, s, x0 + tw / 2, y, size, '#FFFFFF', P.ink, 'sub', 'center', Sb.stroke);
      return;
    }
  };

  // ---------- 片尾：口号 + 免责声明 + AI 说明 + 参考文献 + 署名，全部来自 storyboard（outro.slogan / disclaimer / outro.ai_note / outro.references / credits） ----------
  // 署名条目可写 {text, orient: 'port'|'land'}：只在该画幅显示（例：投稿版画面不许出现作者信息，署名只留竖屏）
  OV.credits = (SB) => (SB.credits || []).filter((cr) => !(cr && typeof cr === 'object' && cr.orient) || cr.orient === (OV.LAYOUT && OV.LAYOUT.orient === 'land' ? 'land' : 'port'));
  // 横屏：center_x 在右半幅、fit 让免责声明/AI 说明按 max_width 缩字号、credit_line 行距；有参考文献页（sref）时片尾不再重复 outro.references 短清单
  OV.outro = (c, SB, t) => {
    const P = L.P, O = OV.LAYOUT.outro, a = L.fin(t, 0.2, 0.6), ink = OV.dark ? '#FFFFFF' : P.ink, ink2 = OV.dark ? 'rgba(255,255,255,0.75)' : P.ink2, ou = SB.outro || {};
    const CX = O.center_x ?? W / 2, fit = (s, size, font) => (O.fit ? fitSize(c, s, size, font, O.max_width) : size);
    // 自检（10-24）：片尾每行右缘在 safe.y_from–y_to 段内越过 safe.right_x 记 safe_right、字底进 bottom_reserved 记 safe_bottom（nocturia 报告口号 / 文献右端到 960–1030 px，foam 署名进了底部留白带）。只量不画，旧版式画面逐位不变
    const Lt = OV.LAYOUT, RX = (Lt.safe || {}).right_x ?? 1e9, BOT = (Lt.bottom_reserved || [HGT])[0], s99 = OV.TL && (OV.TL.scenes || []).find((s) => s.id === 's99'), T = (s99 ? s99.start : 0) + t;
    const meas = (s, size, role, stroke) => { c.save(); c.font = fnt(size, role); const w = c.measureText(s).width + (stroke ? size * 0.24 : 0); c.restore(); return w; };
    const chk = (s, x, y, size, role, stroke) => { const w = meas(s, size, role, stroke);
      if (x + w / 2 > RX + 0.5 && inSafeY(y - size / 2, y + size / 2)) flag('safe_right', T, { scene: 's99', kind: 'outro', right: Math.round(x + w / 2), text: s });
      if (y + size * 0.6 > BOT) flag('safe_bottom', T, { scene: 's99', kind: 'outro', bottom: Math.round(y + size * 0.6), text: s }); };
    if (O.safe) return outroSafe(c, SB, t, { O, a, ink, ink2, ou, CX, RX, BOT, meas, chk });
    if (ou.slogan) L.with(c, () => { c.font = fnt(O.slogan_size, 'title'); const sz = Math.min(O.slogan_size, Math.floor(O.slogan_size * O.max_width / c.measureText(ou.slogan).width)); txt(c, ou.slogan, 0, 0, sz, ink, OV.dark ? 'rgba(10,12,40,0.9)' : '#FFFFFF', 'title'); chk(ou.slogan, CX, O.slogan_y, sz, 'title', true); }, { x: CX, y: O.slogan_y, a });
    const b = L.fin(t, 0.7, 0.6);
    L.with(c, () => {
      let yy = 0;
      if (SB.disclaimer) { const sz = fit(SB.disclaimer, O.disclaimer_size, 'label'); txt(c, SB.disclaimer, 0, yy, sz, ink, null, 'label'); chk(SB.disclaimer, CX, O.block_y + yy, sz, 'label'); yy += O.disclaimer_size * 1.3; }
      if (ou.ai_note) { const sz = fit(ou.ai_note, O.ai_note_size, 'label'); txt(c, ou.ai_note, 0, yy, sz, ink2, null, 'label'); chk(ou.ai_note, CX, O.block_y + yy, sz, 'label'); yy += O.ai_note_size * 1.9; }
      const refs = OV.refsPage ? [] : (ou.references || []);
      refs.forEach((r) => { c.font = fnt(O.ref_size, 'ref'); const sz = Math.min(O.ref_size, Math.floor(O.ref_size * O.max_width / c.measureText(r).width)); txt(c, r, 0, yy, sz, ink2, null, 'ref'); chk(r, CX, O.block_y + yy, sz, 'ref'); yy += O.ref_line; });
      yy += OV.credits(SB).length ? (O.credit_gap || 0) : 0;   // 署名上方空隙（layout outro.credit_gap；10-24：作者行贴着文献像第 6 条文献）
      OV.credits(SB).forEach((cr) => { const s = typeof cr === 'string' ? cr : cr.text; c.font = fnt(O.credit_size, 'ref'); const sz = Math.min(O.credit_size, Math.floor(O.credit_size * O.max_width / c.measureText(s).width)); txt(c, s, 0, yy, sz, ink2, null, 'ref'); chk(s, CX, O.block_y + yy, sz, 'ref'); yy += O.credit_line || O.credit_size * 1.6; });
    }, { x: CX, y: O.block_y, a: b });
  };
  // layout.outro.safe = true（10-24 起模板竖屏版式打开；旧专题 layout 没写这个键就走上面的旧画法）：
  //   居中在 center_x，在 safe.y_from–y_to 段内右缘过 safe.right_x 才往左让、让到 margin_x（缺省 (画宽 − max_width)/2）还放不下才缩字号——与字卡 / 字幕同一规则（10-23 用户定“居中、只有右缘过 900 的才往左让”）；
  //   口号单独算；下面那一块（免责声明 / AI 说明 / 文献 / 署名）按最宽一行整块共用一个中心（逐行各让各的会参差不齐）；
  //   这一块的字底不进 bottom_reserved：超了先整块上移（不压口号，留 gap），还超就把文献与署名的字号、行距一起按比例收（最小 0.75），仍超照画并记 safe_bottom
  const outroSafe = (c, SB, t, { O, a, ink, ink2, ou, CX, RX, BOT, meas, chk }) => {
    const LM = O.margin_x ?? Math.max(0, (W - O.max_width) / 2);
    const fitW = (s, size, role, y, stroke) => {   // → { size, w, inS }：段内宽度上限 min(max_width, right_x − LM)，段外 max_width
      const inS = inSafeY(y - size / 2, y + size / 2), lim = Math.min(O.max_width, inS ? RX - LM : W - 2 * LM); let w = meas(s, size, role, stroke);
      if (w > lim) { size = Math.floor(size * lim / w); w = meas(s, size, role, stroke); }
      return { size, w, inS };
    };
    const center = (w, inS) => (inS ? Math.max(LM + w / 2, Math.min(CX, RX - w / 2)) : CX);
    const items = [];
    if (SB.disclaimer) items.push({ s: SB.disclaimer, size: O.disclaimer_size, role: 'label', col: ink, step: O.disclaimer_size * 1.3 });
    if (ou.ai_note) items.push({ s: ou.ai_note, size: O.ai_note_size, role: 'label', col: ink2, step: O.ai_note_size * 1.9 });
    (OV.refsPage ? [] : (ou.references || [])).forEach((r) => items.push({ s: r, size: O.ref_size, role: 'ref', col: ink2, step: O.ref_line, k: true }));
    OV.credits(SB).forEach((cr, i) => items.push({ s: typeof cr === 'string' ? cr : cr.text, size: O.credit_size, role: 'ref', col: ink2, step: O.credit_line || O.credit_size * 1.6, k: true, pre: i === 0 ? (O.credit_gap || 0) : 0 }));
    const lay = (y0, kk) => { let y = y0; return items.map((it) => { y += (it.pre || 0) * (it.k ? kk : 1); const r = { ...it, y, size: it.k ? Math.round(it.size * kk) : it.size }; y += it.step * (it.k ? kk : 1); return r; }); };
    // 底线：outro.bottom_y（缺省 = bottom_reserved 上沿 1600）。真机核对后若抖音底部文案区更高（第三方估计底部 660 px，即 y 1260 起），只把片尾抬上去：写 bottom_y，必要时再写 top_min 让口号一起上移
    const bottom = (ls) => (ls.length ? ls[ls.length - 1].y + ls[ls.length - 1].size * 0.6 : 0), lim = (O.bottom_y ?? BOT) - (O.bottom_pad ?? 12);
    let y0 = O.block_y, kk = 1, ls = lay(y0, kk), sy = O.slogan_y;
    if (bottom(ls) > lim) {
      const top = ou.slogan ? sy + O.slogan_size * 0.75 + (O.gap ?? 36) : 0; y0 = Math.max(Math.min(y0, top), y0 - (bottom(ls) - lim)); ls = lay(y0, kk);
      const lift = Math.min(Math.max(0, bottom(ls) - lim), Math.max(0, sy - (O.top_min ?? sy)));   // 口号和这一块一起上移（top_min 缺省 = slogan_y，即不上移）
      if (lift > 0) { sy -= lift; y0 -= lift; ls = lay(y0, kk); }
      while (bottom(ls) > lim && kk > 0.75) { kk -= 0.01; ls = lay(y0, kk); }
    }
    if (ou.slogan) { const f = fitW(ou.slogan, O.slogan_size, 'title', sy, true), x = center(f.w, f.inS); L.with(c, () => txt(c, ou.slogan, 0, 0, f.size, ink, OV.dark ? 'rgba(10,12,40,0.9)' : '#FFFFFF', 'title'), { x, y: sy, a }); chk(ou.slogan, x, sy, f.size, 'title', true); }
    const b = L.fin(t, 0.7, 0.6), fs = ls.map((it) => fitW(it.s, it.size, it.role, it.y)), inS = fs.some((f) => f.inS), xb = center(Math.max(0, ...fs.map((f) => f.w)), inS);
    ls.forEach((it, i) => { L.with(c, () => txt(c, it.s, 0, 0, fs[i].size, it.col, null, it.role), { x: xb, y: it.y, a: b }); chk(it.s, xb, it.y, fs[i].size, it.role); });
  };

  // ---------- 参考文献页（sref 场）：GB/T 7714 顺序编码制，按影片首次出现顺序；页数/每页秒数来自 timeline.refs（storyboard.references_pages / references_page_seconds，没写就按条数自动分页）----------
  // 按实测字宽折行（西文按词、中文按字），悬挂缩进；字号从 refs.size_max 往下试，直到能装进页数；装不下记 overflow（qa 不通过）。版式数值全在 layout.refs。
  const wrapRef = (c, s, maxW) => {
    const toks = s.match(/[A-Za-z0-9À-ɏ\-–—.,:;()\[\]\/'’&%+@#*_=]+|\s+|./gu) || []; const lines = []; let cur = '';
    for (const tk of toks) { const nx = cur + tk; if (c.measureText(nx).width <= maxW || !cur.trim()) { cur = nx; continue; } lines.push(cur.trimEnd()); cur = tk.trimStart(); }
    if (cur.trim()) lines.push(cur.trimEnd()); return lines;
  };
  let refCache = null; OV.refInfo = null;
  const refLayout = (c, SB) => {
    const Rf = OV.LAYOUT.refs || {}, refs = SB.references || [], TLr = (OV.TL && OV.TL.refs) || {}, N = TLr.pages || SB.references_pages || Math.max(1, Math.ceil(refs.length / (Rf.per_page_default || 10)));
    const key = `${W}x${HGT}|${N}|${refs.length}`; if (refCache && refCache.key === key) return refCache;
    const x0 = Rf.x ?? 80, width = Rf.width ?? (W - 160), top = Rf.top ?? 160, avail = HGT - top - (Rf.bottom_margin ?? 50);
    const paginate = (size) => {
      c.font = fnt(size, 'ref'); const lh = Math.round(size * (Rf.line_height ?? 1.34)), gap = Math.round(size * (Rf.gap ?? 0.34)), items = [];
      for (let i = 0; i < refs.length; i++) { const tag = `[${i + 1}] `, ind = c.measureText('[00] ').width, ls = wrapRef(c, refs[i], width - ind); items.push({ tag, ind, lines: ls, h: ls.length * lh + gap }); }
      const pages = [[]]; let hcur = 0;
      for (const it of items) { if (hcur + it.h > avail && pages[pages.length - 1].length) { pages.push([]); hcur = 0; } pages[pages.length - 1].push(it); hcur += it.h; }
      return { size, lh, pages };
    };
    let got = null;
    for (let size = Rf.size_max ?? 34; size >= (Rf.size_min ?? 15); size--) { const r = paginate(size); if (r.pages.length <= N) { got = r; break; } }
    const overflow = !got; if (!got) got = paginate(Rf.size_min ?? 15);
    refCache = { key, size: got.size, lh: got.lh, x0, top, pages: got.pages, overflow };
    OV.refInfo = { count: refs.length, size: got.size, pages: got.pages.map((q) => q.length), pages_planned: N, overflow };
    return refCache;
  };
  OV.refs = (c, SB, t) => {
    const P = L.P, Rf = OV.LAYOUT.refs || {}, Lo = refLayout(c, SB), TLr = (OV.TL && OV.TL.refs) || {}, sec = TLr.page_seconds || SB.references_page_seconds || Rf.page_seconds_default || 5, np = Lo.pages.length; if (!np) return;
    const pg = Math.min(np - 1, Math.floor(t / sec)), a = L.fin(t, 0, Rf.fade_in ?? 0.5), pa = pg > 0 ? L.fin(t, pg * sec, Rf.page_fade ?? 0.35) : 1;
    c.save(); c.globalAlpha *= a; c.fillStyle = OV.dark ? '#14183A' : (Rf.bg || '#FFF8EE'); c.fillRect(0, 0, W, HGT);
    txt(c, `参考文献（${pg + 1}/${np}）`, Rf.title_x ?? 90, Rf.title_y ?? 96, Rf.title_size ?? 46, OV.dark ? '#FFFFFF' : P.ink, null, 'title', 'left');
    c.globalAlpha *= pa; let y = Lo.top; c.font = fnt(Lo.size, 'ref'); c.textBaseline = 'top'; c.textAlign = 'left'; c.fillStyle = OV.dark ? 'rgba(255,255,255,0.9)' : P.ink;
    for (const it of Lo.pages[pg]) { c.fillText(it.tag, Lo.x0, y); it.lines.forEach((ln, i) => c.fillText(ln, Lo.x0 + it.ind, y + i * Lo.lh)); y += it.h; }
    c.restore();
  };
})();
if (typeof module !== 'undefined') module.exports = OV; else window.OV = OV;
