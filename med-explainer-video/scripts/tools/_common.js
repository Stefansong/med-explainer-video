// 工具共用：项目根、画幅（ORIENT）、产物目录、storyboard 定位、layout 路径、Chrome 路径、player 页 URL。专题常量一律不写在这里，全从 storyboard / layout.json 读。
// 画幅：ORIENT=port（默认，竖屏，产物 render/）或 ORIENT=land（横屏投稿版，版式 layout_land.json，产物全部在 render/land/，竖屏产物不受影响）。
'use strict';
const fs = require('fs'); const path = require('path'); const { pathToFileURL } = require('url');
const ROOT = process.env.KEPU_PROJECT ? path.resolve(process.env.KEPU_PROJECT) : fs.existsSync(path.join(process.cwd(), 'design')) ? process.cwd() : path.resolve(__dirname, '..');   // 专题目录：$KEPU_PROJECT → 当前目录
// 浏览器：$CHROME_PATH（setup 写进 bin/env.json，pipeline 启动时带上）→ 常见安装位置（Chrome / Edge / Chromium）
const BROWSERS = process.platform === 'win32'
  ? [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean).flatMap((d) => [path.join(d, 'Google/Chrome/Application/chrome.exe'), path.join(d, 'Microsoft/Edge/Application/msedge.exe')])
  : process.platform === 'darwin'
    ? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/Applications/Chromium.app/Contents/MacOS/Chromium']
    : ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge'];
const CHROME = process.env.CHROME_PATH || BROWSERS.find((p) => { try { return fs.existsSync(p); } catch (_) { return false; } }) || BROWSERS[0];
const fileUrl = (p) => pathToFileURL(path.resolve(p)).href;
const ORIENT = ['land', 'landscape', 'h', '横屏'].includes((process.env.ORIENT || 'port').toLowerCase()) ? 'land' : 'port';
const LAND = ORIENT === 'land';
const renderRel = (name = '') => { const base = LAND ? 'render/land' : 'render'; return name ? `${base}/${name}` : base; };   // 相对项目根（工具都 chdir 到 ROOT）
const renderDir = (root = ROOT) => { const d = path.join(root, renderRel()); fs.mkdirSync(d, { recursive: true }); return d; };
// storyboard 定位：$STORYBOARD → design/storyboard.json → design/storyboard_<目录名>.json → design/storyboard_*.json 唯一一个（排除 archive）
const findStoryboard = (root = ROOT) => {
  if (process.env.STORYBOARD) return path.resolve(root, process.env.STORYBOARD);
  const d = path.join(root, 'design');
  for (const cand of ['storyboard.json', `storyboard_${path.basename(root)}.json`]) if (fs.existsSync(path.join(d, cand))) return path.join(d, cand);
  const all = fs.existsSync(d) ? fs.readdirSync(d).filter((f) => /^storyboard.*\.json$/.test(f) && !/archive|_v\d/.test(f)) : [];
  if (all.length === 1) return path.join(d, all[0]);
  throw new Error(all.length ? `design/ 里有多个 storyboard：${all.join(', ')}，请用 STORYBOARD=design/xxx.json 指定` : `找不到 storyboard（design/storyboard*.json）: ${root}`);
};
const loadSB = (root = ROOT) => JSON.parse(fs.readFileSync(findStoryboard(root), 'utf8'));
// 版式：$LAYOUT → 横屏 layout_land.json / 竖屏 layout.json（横屏缺文件直接报错，不回退竖屏版式）
const layoutPath = (root = ROOT) => {
  if (process.env.LAYOUT) return path.resolve(root, process.env.LAYOUT);
  const p = path.resolve(root, LAND ? 'layout_land.json' : 'layout.json');
  if (LAND && !fs.existsSync(p)) throw new Error(`横屏需要 ${path.basename(p)}（从 skill 的 scripts/ 复制后按需改数值）`);
  return p;
};
const loadLayout = (root = ROOT) => JSON.parse(fs.readFileSync(layoutPath(root), 'utf8'));
const loadTL = (root = ROOT) => JSON.parse(fs.readFileSync(path.join(renderDir(root), 'timeline.json'), 'utf8'));
// player.html 的 file:// URL，带 sb / layout / tl / orient 参数（相对 src/ 的路径），外加 STYLE / ART 环境变量
const playerUrl = (extra = {}, root = ROOT) => {
  const qs = new URLSearchParams(); const rel = (p) => path.relative(path.join(root, 'src'), p).split(path.sep).join('/');
  qs.set('sb', rel(findStoryboard(root))); qs.set('layout', rel(layoutPath(root))); qs.set('tl', rel(path.join(renderDir(root), 'timeline.json'))); qs.set('orient', ORIENT);
  if (process.env.STYLE) qs.set('style', process.env.STYLE); if (process.env.ART) qs.set('art', process.env.ART);
  for (const [k, v] of Object.entries(extra)) if (v != null) qs.set(k, v);
  return fileUrl(path.join(root, 'src/player.html')) + '?' + qs.toString();
};
// 把 "s03+4.5" / "s03@cue+0.5" / "12.3" 解析成绝对秒（在页面里也有同样的逻辑，这里给 node 侧用）
const parseT = (TL, s) => { let m = String(s).match(/^(s\d+)@(\w+)([+-][\d.]+)?$/); if (m) { const sc = TL.scenes.find((x) => x.id === m[1]); return sc.start + sc.cues[m[2]] + (+m[3] || 0); } if (String(s).includes('+')) { const [id, dt] = String(s).split('+'); return TL.scenes.find((x) => x.id === id).start + +dt; } return +s; };
const localIso = () => { const d = new Date(), z = (n) => String(n).padStart(2, '0'); return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`; };   // 与 Python 侧同用本地时间
const log = (line, root = ROOT) => { const f = path.join(renderDir(root), 'pipeline.log'); fs.appendFileSync(f, `${localIso()} ${line}\n`); };
module.exports = { ROOT, CHROME, fileUrl, ORIENT, LAND, renderRel, renderDir, findStoryboard, loadSB, layoutPath, loadLayout, loadTL, playerUrl, parseT, log };
