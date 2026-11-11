# 版式 v2 与 layout.json

真源：各专题 `layout.json`（建专题时从 `$SKILL/scripts/layout.json` 复制）。`overlay.js`（叠字层）与 `engine.js`（舞台映射）只读它；**改版式只改这个文件，不改代码**。

## 竖屏 1080×1920 分区（自上而下）

| y | 区 | layout.json 字段 | 说明 |
|---|---|---|---|
| 0–120 | 平台顶栏留白 | `top_reserved` | 不放任何内容 |
| 120–230 | 进度条 + 章节名 | `header.*`（bar_y 140，chapter_y 192，chapter_size 56） | 章节名放大到 56 px（老年观众）；片名不再常驻 |
| 230–1300 | 主舞台 | `stage.top/bottom`；场景按 `design_top/design_bottom`（236–1236）设计；`stage.scale` 1.0（默认：原尺寸、底边对齐 1300，顶上 70 px 只铺背景、左右不溢出）或 `"fit"`（放大 1.07，左右各溢出 37 px） | 片名 72 px 只在正片前 `title.until_seconds`（5）秒出现在舞台内 y=300，然后上滑退场；`title.keepout_design_y` [236, 420]：s01 前 5 秒这一带设计坐标不放主体；AI 生成标识见下文「发布合规」（左上 x 48 / y 252，从第 0 帧起 3 s，字高 ≥ 54 px）；片名等标识退场后再入（title.min_seconds 3）|
| 1300–1452 | 字卡区 | `labels.*`（style pill：x 60，width 840 为上限，size 48，row_height 70，gap 14，dot 16，big_size 50，pad_l 30 / dot_gap 18 / pad_r 34，radius half，shadow {0.08, dy 5, blur 10}，alert_ring 3，secondary_weight 500，big_pad 40；max_on_screen 3；min_stay 2.5 / min_stay_alert 3.5） | 样式 A「贴纸胶囊」+ 防拥挤方案二（10-19，对比 `docs/layout_crowding_2026-10-19/`）：卡宽 = 文字宽 + 100 自适应、圆角 = 半高、白底软投影、色点（最新一张饱和、其余 0.6）、文字在第一个“（”/“：”处拆成主词 700 + 说明 500 ink2；alert 红点红字红描边；`big` 红底胶囊常驻第 0 格、不参与淘汰；弹入 0.4 s 胶囊从色点向右展开、文字后 0.25 s 淡入，淘汰整卡淡出上移 12 px。**同屏最多 3 张**（场景 `max_labels` 超过按 3 算）；`max_labels > 2` 自动用 `labels.compact`（40 px、行高 54、间距 12、色点 14）以底边为锚向上堆：3 张 = 186 px，顶到 1266，盖舞台底部 34 px → 该场人物脚底设计 y ≤ 1190。卡底 1452 到字幕可见顶约 1507：间距 54–55 px，扣投影约 45 px |
| 1552 中心 | 字幕 | `subtitle.*`（y 1552，size 74，center_x 480，max_width 840，max_chars 11） | 字顶约 1515，距字卡区底边 1480 留 35 px，字底约 1589 在 bottom_reserved 之上（10-18 用户反馈 1520 太靠上）；超宽缩字号并记 `subtitle_shrunk`；角色台词左侧名牌（颜色来自 storyboard.characters[who].color） |
| 1600–1920 | 底部留白 | `bottom_reserved` | 账号名/文案/底部 tab；`footer.waves` 只是背景装饰 |
| x ≥ 900（y 900–1600） | 右侧安全区 | `safe.*` | 字卡、字幕右缘不越过；片尾（`outro.safe`，10-24）也不越过 |

## 片尾守安全区、字幕句末让位（10-24，模板版式打开，旧专题 layout 不写这两个键就是旧画法、逐像素不变）

- `outro.safe: true`：片尾口号、免责声明、AI 说明、片尾短文献、署名都守右侧安全区和底部留白。口号单独居中在 540；下面那一块按最宽一行**整块共用一个中心**，右缘过 `safe.right_x` 900 才整块往左让（让到 `margin_x`，缺省 (1080 − max_width)/2 = 40），还放不下才缩字号——与字卡、字幕的“居中、只有右缘过 900 才往左让”同一规则（10-23 用户定）。这一块的字底不进 `bottom_reserved`（留 `bottom_pad` 12）：超了先整块上移（离口号至少 `gap` 36），还超就把文献与署名的字号和行距按比例收（≥ 0.75）。起因：nocturia 报告片尾口号 / 文献右端 960–1030 px；三集正式版实测口号右端 1031–1036 px、文献 1012–1019 px，foam 片尾署名最后一行到 y 1680。
  片尾底线可单独抬：`outro.bottom_y`（缺省 = `bottom_reserved` 上沿 1600）、`outro.top_min`（缺省 = `slogan_y`，即口号不动）。曾出现片尾文献“整块落在抖音底部文案区”——第三方估计文案区从 y 1260 起（底部 660 px），而模板 `bottom_reserved` 写的是 1600（字幕 1552、字卡区 1300–1452 也都在 1260 以下，用户 10-18 定过）。真机截图核出文案区上沿后：只想保片尾就写 `bottom_y`（抬到 1260 时整块会压到 s99 画面里的人物，要和片尾画面一起重排），要整体改就改 `bottom_reserved` 并重排字卡字幕。
- `subtitle.yield_next: true`：句末字幕块的停留按“下一句首块出现”截住（规则同句内换块：间隔 ≤ 0.6 s 一直亮到下一块，> 0.6 s 在末字后 `tail` 秒隐去）。旧画法里上一句的 `tail` 0.3 s 会压住下一句首块：同一人连说两句（句间 `gap_same` 0.12 s）时后句首块晚出 32–124 ms（nocturia 10 处、foam 旁白连句 53–125 ms）。
- 渲染期自检不论开关都记片尾的 `safe_right` 和 `safe_bottom`（字底进了底部留白带）；两者都是安全区类，`safe_area_verified` 为 false 时只警告（旧 layout 没写 `qa_gate.safe_bottom` 也按只警告）。安全区数值仍待真机截图核对（见下文）。

## 发布合规：AI 生成标识（GB 45438—2025，10-21）

`layout.ai_mark`：`text`“AI 生成内容”（含“AI”与“生成”两要素；投稿平台要求“人工智能生成合成”时只改这个字段）、`min_ratio` 0.05、`margin_px` 4、`from` 0、`show_seconds` 3.0、`fade_out` 0.5、`x` 48、`y` 252。`OV.aiMark`（移植自 bph）按实测字形高度（`actualBoundingBoxAscent + Descent`）迭代放大字号，直到 ≥ ceil(短边 × 5%) + 4 = 58 px（竖屏 1080）；从视频第 0 帧起盖在封面上、满不透明、不淡入，3 s 后 0.5 s 淡出（国标要求 ≥ 2 s，留余量）。位置避开平台 UI：第三方实测抖音竖屏顶栏约到 y 240、右侧图标列从 y 840 起、底部 660 px 文案区（未经本机真机核对，`safe_area_verified` 仍 false）。片名在标识退场前不入场。渲染期 `OV.lastAiMark` → `frames.js` 的 `overlay_check.json` / `render.js` 的 `overlay.json` `ai_mark`（字号、实测字高、要求字高、首帧、最后一帧完整显示、完整显示秒数）；`qa.py` 三条门：实测字高 ≥ 要求、首帧 = 0、完整显示 ≥ 2.0 s，任一不满足判失败。片尾 `outro.ai_note` 一行文字说明不变；专题封面代码不要再画自己的小标识（封面上由叠字层统一画）。

## 字卡停留（10-19 方案二）

`timeline.py` 按叠字层同一套格位规则（big 常驻第 0 格、普通卡占其余格、满了挤掉最老的）算每张卡的在屏时长，写进 `timeline.json` 的 `card_stays`（场、文字、alert、停留秒、原因 squeezed / squeezed_by_big / replaced / scene_end）。规则：普通卡 ≥ `min_stay` 2.5 s，危险信号（alert）卡 ≥ `min_stay_alert` 3.5 s。**场景结束**导致不足的，自动把该场结尾延长到补足为止（无旁白、配乐继续，每场最多 `timing.max_extend` 2.0 s，超出只警告；mix.py / render.js 都读延长后的场景时长）；**被后来的卡挤走**导致不足的不自动改，timeline 打印警告并给建议（调 cue 错开、把该场 `max_labels` 提到 3、合并卡）。`qa.py`：alert 卡不足判失败，普通卡不足判警告，报张数与最短秒数。写卡规则见 WORKFLOW S0 检查清单。

## 2026-10-18 已按用户批准修订

晚间：字卡改为样式 A「贴纸胶囊」（见上表；compact 行高回到 60 / 间距 6，脚底规则改为 ≤ 1150；旧的 12 px 左竖条与固定卡宽参数已删）；字幕 y 1520 → 1552（用户反馈太靠上、离字卡太近）。

`big` 卡常驻；`stage.scale` 默认 1.0；角色台词的字幕块按名牌宽折算（timeline.py `maxc_for`）；片名 y 350→300 + `keepout_design_y`。卡宽 840 与 `safe.right_x` 900 暂不动，等真机截图。

## 待用户手机截图核安全区后再定的两处（字幕高度已定：1552）

1. 字卡宽上限：brief 写 880，但 60+880=940 越过 `safe.right_x=900`；草图上卡右缘恰在 900，模板取 **840**（贴纸胶囊卡宽自适应，840 只是上限）。要 880 就把 `labels.width` 改 880、`safe.right_x` 改 940。
2. 字幕横向：brief 写“居中 540、宽 ≤ 880”（右缘 980，进安全区 80 px）；模板为 **中心 480、宽 ≤ 840**（右缘 ≤ 900）。要改回只改 `subtitle.center_x`、`subtitle.max_width`（`max_chars` floor(840/74)=11 不变）。

## 安全区核对（`safe_area_verified: false`）

在抖音 / 视频号真机上截一张播放页（任何竖屏视频），量出：顶栏下缘 y、右侧图标列左缘 x 与上下 y、底部文案区上缘 y（按 1080×1920 换算），更新 `top_reserved`、`safe.right_x/y_from/y_to`、`bottom_reserved`，把 `safe_area_verified` 改 true。之前 `safe_right` 的越界计数在 QA 里只警告，之后按 0 计（`qa_gate.safe_right: "warn_until_verified"`）。

## 渲染期自检（`OV.CHECK`）

每帧叠字层自检，只计数不中断：`label_over_subtitle`（卡底边越过字幕字框顶边）、`label_slot_collision`（两张卡同一格位）、`label_below_band`（卡越出字卡区）、`subtitle_shrunk` / `label_shrunk`（缩了字号）、`safe_right`（右缘越过安全区；10-24 起片尾各行也查）、`safe_bottom`（10-24：片尾字底进了 `bottom_reserved`）。结果按 (scene, text) 去重：`items` 记每张卡/每块字幕的最小字号、帧数、首次时刻，`unique` 是张数，`counts` 是帧数。`frames.js` 写 `render/check/overlay_check.json`（逐场动画时先看），`render.js` 汇总写 `render/{project}_{tag}.overlay.json`，`qa.py` 按 `layout.qa_gate` 以张数判定，并在 qa.json 的 `overlay_detail` 里报“N 张缩了，最窄 X px”和最差 20 条。

## 字体

`fonts.files` 由 `player.html` 用 FontFace 注册（路径相对项目根）：字幕 黑体子集（思源黑体裁剪） Heavy 900、字卡 Bold 700、片名/大字卡 得意黑（老人看不清 → 粗黑体加大字号）。换字体改 `fonts.*.family/weight` 与 `files`。

**只用开源字体，不回退系统字体：逐字核对缺字，缺字在 QA 门报出。** `layout.json` 四个角色现在只写 `"HeiTiSub"` / `"DeYiHei","HeiTiSub"`（`ref` 由苹方首选改为黑体子集（思源黑体裁剪） Regular，片尾文献/署名字形随之变成黑体子集（思源黑体裁剪）；其余画面逐像素不变）。浏览器遇到字体里没有的字仍会回退系统字体（声明不声明 `sans-serif` 都一样），所以防线是 `tools/check_fonts.py`：把所有上屏文字（章节、片名、字卡、字幕块、名牌、片尾、文献、署名、封面、AI 标识）按角色逐字查 `fonts.files` 各字体的 cmap，缺字列出字、U+ 码、角色、该用的字体文件和出现位置；箭头“→”是线条画的不查，其它符号照查；`fonts.*` 里声明了不在 `files` 里的字体族也算系统回退。`qa.py` 竖屏横屏都按 `qa_gate.font_fallback`（0）判：缺字、系统回退声明、渲染页字体未全部 loaded 任一即不通过。

## 横屏版 `layout_land.json`

画幅 1920×1080；`ORIENT=land` 时 `tools/_common` 自动选它，产物全在 `render/land/`。改版式只改这里：
- `stage {x 60, y 104, h 880, design_top 236, design_bottom 1236, design_width 1080}`：场景仍按竖屏舞台设计，engine 映射到左侧矩形（k = 0.88），以舞台中心呼吸；`L.EXT = {x0, x1}` 让 `L.bg` 和场景自定义背景（`L.XR()`）向右铺满整幅。
- `header {style "nav", x 60, y 62, size 30, height 60, pad 52, gap 40, connector 24, pop_start 0.25, pop_each 0.12, pop_seconds 0.42}`：章节导航代替常驻片名（`title.enabled false`），`chapters[].nav: false` 的章不列；封面过后逐个弹入。
- `ai_mark {text "人工智能生成合成", anchor "bottom_right", right 1880, bottom 1040, min_ratio 0.05, margin_px 4, from 0, show_seconds 3.0, fade_out 0.5}`：右下角，字高 ≥ 58 px（1080×5% + 4），第 0 帧起；封面 `cover.hold_land` 3.0 s 保证完整显示 ≥ 2 s。
- `labels {style "board", x 1110, width 760, head_height 82, row_height 82, pad 16, radius 28, center_y 544, top_min 150, max_default 3, extra_rows 2, max_on_screen null, head_size 42, size 40, dot 9, dot_x 44, text_x 68, text_pad_r 32, newest_highlight_seconds 2.4, pop {board_seconds 0.45, seconds 0.4, enter_delay 0.22, rotate_seconds 0.3, slide 26}, shadow {alpha 0.16, dx 6, dy 10}}`：D 改良要点板，板头 = 本场 `topic`（蓝）或最近 big 卡（红），条目超过格数最老的淡出上移；`label_shrunk`（条目/板头缩字号）、`label_over_subtitle`（板底越过字幕顶）照常自检。
- `subtitle {y 1022, size 64, center_x 960, max_width 1500, max_chars 13, name_size 34}`；`footer.waves [980, 1040]`；`safe.right_x 1920`（网页播放器无侧栏）。
- `outro {center_x 1510, slogan_y 300, slogan_size 54, block_y 400, max_width 720, fit true, credit_line 50}`：片尾文字在右半幅；有 sref 文献页时片尾不重复 `outro.references`。
- `refs {x 80, width 1760, top 160, bottom_margin 50, title 90/96/46 px, size_max 34 → size_min 15, line_height 1.34, gap 0.34, bg #FFF8EE, per_page_default 10, page_seconds_default 5.0}`：参考文献页，字号从大往小试到能装进 `references_pages` 页；装不下记 overflow（qa 失败）。
- `fonts.*.family` 只写黑体子集（思源黑体裁剪）/得意黑（只用开源字体、不回退系统字体）；`qa_gate.font_fallback 0`。
- `submit {target_mb 46, max_mb 50, fps 30, sub 4, min_width 1280, min_height 720, ai_mark_min_seconds 2.0}`。
