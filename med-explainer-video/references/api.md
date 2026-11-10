# 场景代码速查（写 `src/scenes.js` 时看）

先看样例：`python $P new demo --example` 建一份 45 秒的样例专题，`src/scenes.js` 里四场戏分别示范了满幅 3D 镜头、立绘、解剖、道具图标、危险信号。**照着样例改，比从零写稳**。每写完一场就 `python $P frames <专题>` 看 `render/check_sheet.png`。

## 一场戏的骨架

```js
SC.s03 = (c, A) => {
  const t = A.t, ok = A.cue('ok');        // 时刻一律从 storyboard 的 cue / 字卡 / 台词取，不要写死秒数
  SH.home(c, t);                           // 1. 先铺满底色
  SH.IC(c, A, 'ic_bottle', 210, 760, 400, { pop: (t - A.cue('water')) / 0.45 });   // 2. 道具
  SH.SP(c, A, 'sp_zhou_drink', SH.spX(A, 'sp_zhou_drink', 800, 620), 1180, 620, { pop: (t - ok) / 0.45 });   // 3. 人物
};
```

规则：
- 坐标系宽 1080；主舞台 y 236–1236。同屏 3 张字卡的场，主体底边 y ≤ 1190。s01 开场 5 秒内 y 236–420 留给片名。立绘、图标右缘 x ≤ 885（`SH.spX` 自动收）。
- 画面里不写任何字（数字、字母也不行）；叹号、对勾、叉用 `SH.bang / tick / cross` 这些图形。
- 每帧只由 `A.t` 决定：随机数用 `const R = L.rand(seed); R()`，不用 `Math.random()`、`Date`。
- 颜色取 `SH.P()`（= storyboard `style.palette`），需要新颜色就加进 palette。
- 场内换镜头用 `SH.seg`：新镜头淡入盖在旧镜头上，旧镜头不要同时淡出（两边都半透明会透出底色发灰，QA 判失败）。

## A：本场上下文

| 写法 | 含义 |
|---|---|
| `A.t` / `A.T` | 场内秒 / 本场时长 |
| `A.cue('名字')` | storyboard `scenes[].cues` 里那个事件的场内时刻；没声明返回 1e9（= 永远不发生） |
| `A.lab(k)` | 第 k 张字卡出现的时刻 |
| `A.ln(i)` | 第 i 句台词 `{start, end}`；`SH.at(A, i, '词')` = 第 i 句里某个词出口的时刻 |
| `A.img(id)` | `storyboard.assets` 里登记的图；没登记返回 null |

常用时间写法：`L.seg(t, a, b)` 从 a 到 b 线性 0→1（夹在 0–1）；`L.pop(t, a)` 在 a 时刻弹入（带回弹）；`L.fin(t, a)` 淡入；`L.vis(t, a, b)` a 淡入、b 淡出；`{ pop: (t - a) / 0.45 }` 传给立绘 / 图标做弹入。

## SH：镜头函数（`src/shots.js`）

| 函数 | 作用 |
|---|---|
| `SH.full(c, A, id, {zoom, push, ax, ay, a})` | **满幅 3D 镜头**：带场景的竖版图铺满整个画面。`zoom` 放大（默认 1.04），`push` 整场缓慢推近幅度（0.05 左右），`ax / ay` 裁切锚点 0–1。人物的脸放画面中部，头顶别钻到章节名下面 |
| `SH.SP(c, A, id, x, 脚底y, 高, {pop, a, flip, bob, sway, shadow})` | **透明底立绘**。`flip` 水平翻转，`sway` 轻摆 |
| `SH.spX(A, id, x, 高)` | 把立绘中心 x 收进右安全线，配合 `SP` 用 |
| `SH.xf(c, A, idA, idB, k, x, 脚底y, 高)` | 两张立绘交叉淡化换姿势，`k` 0→1（0.3 秒内走完） |
| `SH.IC(c, A, id, x, y, 尺寸, {pop, a, r, flip, shadow, tint})` | **3D 道具图标**，(x, y) 是中心 |
| `SH.seg(c, t, a, b, fn)` | 场内镜头：a 起淡入并画到 b，`fn` 里自己铺满底色 |
| `SH.segX(c, t, a, b, fn)` | 同一底色上的内容叠化（淡入淡出） |
| `SH.paper / home / clinic / nightBg(c, t)` | 底色：米色纸 / 家里（带地面色带）/ 诊室 / 夜空 |
| `SH.bg(c, t, 色1, 色2, seed)`、`SH.band(c, y0, y1, 色)` | 自定底色、横向色带 |
| `SH.floor(c, y)`、`SH.paperFloor(c, y)` | 地板（夜景用）、一条浅色台面 |
| `SH.ring / inRing(c, x, y, r, 色, fn)` | 圆窗 / 放大镜：`inRing` 的 `fn` 里画的东西被裁在圆里 |
| `SH.drop(c, t, ta, x, y, fn)` | 在 ta 时刻从上方落下一个东西，`fn` 以 (0,0) 为中心画 |
| `SH.card(c, t, ta, x, y, w, h, 色, fn)` | 落下一张白卡片，顶上一条色带 |
| `SH.alarm(c, t, ta, tb)` | 整屏红色警报闪动（危险信号场） |
| `SH.flags(c, t, [时刻…], y)` | 一排警示牌依次落下（文字写在 alert 字卡里） |
| `SH.bang / cross / tick(c, x, y, r, 色)`、`SH.upArrow(c, x, y, s)` | 叹号 / 叉 / 对勾 / 上箭头（图形，不是字） |
| `SH.face(c, x, y, r, {mood, blink, blush})` | 给拟人器官、细菌、小球画一张小脸。mood：smile happy pain worried frown surprised whistle |

## PR：代码画的道具（`src/props.js`）

统一写法 `PR.xxx(c, x, y, s, o)`：(x, y) 中心，`s = 1` 时约 200 px 见方。先用这些，不够再出 3D 图标。

- 家里：`clock`（`{h, m}` 指针时间）`window` `bed` `blanket` `toilet` `door` `calendar` `tree` `bench` `bag`
- 吃喝：`glass`（`{level}` 水位）`coffee` `tea` `beer` `glassClink` `orange` `steam`
- 医疗：`pillBox` `blister` `thermo` `urineCup` `tube` `glove` `clipboard` `usMachine` `uroflow` `glucometer` `microscope` `jar` `scalpel` `ambulance` `anesthesia`
- 示意：`drop` `stone` `germ` `heart` `stairs` `timerRing` `alert` `wind` `zzz`
- 符号：`check` `bang` `cross` `qmark`
- `PR.card(c, x, y, w, h, 色, 圆角)`：白卡片底

不要用 `PR.doctor`、`PR.oldman`、`PR.kidney`、`PR.bladder`：人物只用 3D 图，解剖要按 anatomy.md 在 `anat.js` 里认真画。参数细节直接读 `props.js` 里那一行。

## L：绘图与缓动（`src/lib.js`）

| 类 | 函数 |
|---|---|
| 缓动 | `L.clamp(x)` `L.lerp(a, b, k)` `L.seg(t, a, b)` `L.easeIn / easeOut / easeInOut(k)` `L.backOut(k)`（回弹）|
| 动势 | `L.wob(t, 频率, 幅度)` 正弦摆动；`L.jolt(t, t0, 幅度)` 在 t0 抖一下后衰减；`L.squash(t, t0)` 落地压扁回弹（当缩放用）|
| 随机 | `const R = L.rand(seed)`，每次 `R()` 给 0–1，同一个 seed 永远同一串 |
| 颜色 | `L.mix(色1, 色2, k)` 混色（#RRGGBB）；`L.alpha(色, a)` 加透明度 |
| 形状 | `L.circle(c, x, y, r, 色)` `L.ellipse(c, x, y, rx, ry, 色, 旋转)` `L.fillRR(c, x, y, w, h, 圆角, 色)` `L.ring(c, x, y, r, 线宽, 色)` `L.line(c, [[x, y]…], 线宽, 色)` `L.poly(c, [[x, y]…], 色)` `L.bez(c, p0, p1, p2, p3, 线宽, 色)` `L.star(…)` |
| 变换 | `L.with(c, () => {…}, {x, y, s, r, a})`：在平移 / 缩放 / 旋转 / 透明度下画一组东西，里面以 (0, 0) 为中心 |
| 点缀 | `L.sweat` 汗滴、`L.sparkle` 闪光、`L.anger` 生气符号、`L.shadow` 地面影子 |
| 人体轮廓 | `L.ghostBody(c, x, y, s)`：无脸半透明人体轮廓，“身体里画器官”时垫在解剖图下面 |

## 常见做法

- **东西依次出现**：每个东西一个 cue，`pop: (t - A.cue('x')) / 0.45`。
- **强调**：`L.with(c, fn, { s: 1 + 0.06 * Math.sin(t * 9) })` 轻微脉动；红色扩散圈 `L.ring(c, x, y, 22 + 46 * q, 7, L.alpha(红, 1 - q))`，`q = (t - t0) * 1.4 % 1`。
- **放大看细节**：`SH.inRing` 开一个圆窗，把同一个东西按大尺寸再画一遍（手机上小结构看不清）。
- **要精确表达程度的示意**（量杯到哪一格、颜色深浅对照、多少的对比）用代码画，不用图标。
- **人物换表情**：出两张立绘，`SH.xf` 交叉淡化；位置、脚底、高度保持一致。
- **画面空**：主体宽度至少占舞台的一半；人物立绘高度 600–760，图标 300–420。

## 解剖 `src/anat.js`

约定 `AN.xxx(c, x, y, s, o)`，参数驱动（比如 `dilate` 扩张程度、`urine` 尿色），关键点坐标导出成常量（样例里的 `AN.STUCK`、`AN.CALYX`、`AN.stonePos(u)`），场景代码在同一坐标系里叠加结石、箭头、脉动圈：`L.with(c, () => {…}, {x, y, s})`。画法和核对清单见 anatomy.md。
