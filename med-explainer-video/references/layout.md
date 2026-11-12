# 版式、主题色与 layout.json

真源：各专题的 `layout.json`（竖屏）和 `layout_land.json`（横屏），建专题时从 `$SKILL/scripts/` 复制。`overlay.js`（叠字层）与 `engine.js`（舞台映射、转场）只读它们；**改版式、改颜色只改这两个文件，不改代码**。

## 主题色

叠字层的颜色全部来自 `layout.json` 的 `theme`；画面层的底色来自 `storyboard.style.palette`。三套预设在 `$SKILL/scripts/themes.json`：

| 主题 | 样子 |
|---|---|
| `mint`（默认） | 冷白底、翠绿主色、深蓝字 |
| `indigo` | 淡紫灰底、靛蓝主色 |
| `amber` | 冷灰底、琥珀主色、炭黑字 |

```
python "$SKILL/scripts/pipeline.py" new <专题> --theme indigo        # 建专题时选
python "$SKILL/scripts/pipeline.py" theme <专题> amber               # 之后再换（已出的预演 / 成片要重跑）
```

想要自己的配色，直接改专题 `layout.json` 的 `theme`（横屏另改 `layout_land.json`）：

| 键 | 用在哪 |
|---|---|
| `accent` / `accent_dark` / `accent_soft` | 章节序号块、进度轨、字卡色条、片名横幅、转场色带、片尾口号、封面 |
| `ink` / `ink2` | 正文墨色（章节名、字卡、大字卡底）/ 次要文字 |
| `alert` / `alert_dark` / `alert_soft` | 危险信号卡 |
| `card` | 字卡底色 |
| `paper` | 顶部遮罩、页脚淡出、文献页底色，写成 `"r,g,b"` |
| `sub_bg` / `sub_text` | 字幕条底色（带透明度）/ 字幕字色 |
| `shadow` | 投影色，写成 `"r,g,b"` |

画面底色在 `storyboard.style.palette`：`paper` / `paper2`（纸面和花纹）、`home` / `home2` / `home_floor`（`SH.home`）、`clinic` / `clinic2` / `clinic_floor` / `clinic_line`（`SH.clinic`）、`stone`（`SH.paperFloor`）、`ink` / `ink2`。危险信号必须是红色系，别把 `alert` 改成别的颜色。

## 竖屏 1080×1920 分区（自上而下）

| y | 区 | layout.json 字段 | 说明 |
|---|---|---|---|
| 0–120 | 平台顶栏留白 | `top_reserved` | 不放任何内容 |
| 120–230 | 进度轨 + 章节名 | `header.*`（bar_y 140，bar_height 8，node 11，chapter_x 60，chapter_y 196，chapter_size 50） | 一条细轨道贯穿全片，每章起点一个节点；左对齐的“序号块 + 章节名”；片名不常驻 |
| 230–1300 | 主舞台 | `stage.top/bottom`；场景按 `design_top/design_bottom`（236–1236）设计；`stage.scale` 1.0（默认）或 `"fit"` | 片名横幅只在正片前 `title.until_seconds`（5）秒出现在 y=300，然后上滑退场；`title.keepout_design_y` [236, 420]：第一场前 5 秒这一带不放主体 |
| 1300–1452 | 字卡区 | `labels.*`（style tag：x 60，width 840 为上限，size 48，row_height 70，gap 14，bar 12，radius 16，big_size 50；max_on_screen 3；min_stay 2.5 / min_stay_alert 3.5） | 左对齐的标签卡：白底、左侧主题色条；`big` 深色底大字卡常驻第一格；`alert` 红底白字 + 叹号。同屏超过 `max_default`（2）张自动换紧凑尺寸（`compact`）。想居中加 `"align": "center", "center_x": 540` |
| 1552 中心 | 字幕条 | `subtitle.*`（y 1552，size 68，center_x 540，max_width 840，max_chars 11，bar_pad 32，bar_height 1.52，bar_radius 22，name_size 34） | 深色半透明圆角条 + 白字；超宽缩字号并记 `subtitle_shrunk`；角色台词的名牌搭在字幕条左上角（颜色取 `characters[who].color`） |
| 1600–1920 | 底部留白 | `bottom_reserved`、`footer`（style fade，from 1640） | 账号名、文案、底部按钮压在这里；页脚只是把画面向主题底色淡出 |
| x ≥ 900（y 900–1600） | 右侧安全区 | `safe.*` | 字卡、字幕条、片尾各行的右缘不越过 |

其他：

- `outro.safe: true`：片尾口号、免责声明、AI 说明、短文献、署名都守右侧安全区和底部留白；放不下先整块上移，再按比例缩文献和署名的字号。
- `subtitle.yield_next: true`：句末字幕块到下一句首块出现时让位，不压住下一句。
- 转场（场与场之间）：一道和背景光带同角度的斜向色带从左扫到右，0.7 秒，颜色取 `theme.accent`。

## AI 生成标识（GB 45438—2025）

`layout.ai_mark`：`text`“AI 生成内容”（要含“AI”与“生成”；平台要求别的写法时只改这个字段）、`min_ratio` 0.05、`margin_px` 4、`from` 0、`show_seconds` 3.0、`fade_out` 0.5、`x` 48、`y` 252。叠字层按实测字形高度把字号放大到 ≥ 画面短边 5% + 4 px，从第 0 帧起满不透明显示，3 秒后淡出；白底、墨色描边。成片 QA 检查它的字高、起始时刻、持续时间。片尾另有一行 `outro.ai_note`。

## 字卡停留

`timeline.py` 按叠字层同一套格位规则算每张卡的在屏时长，写进 `timeline.json` 的 `card_stays`。普通卡 ≥ `min_stay` 2.5 s，危险信号卡 ≥ `min_stay_alert` 3.5 s。场景结束导致不足的自动延长场尾；被后面的卡挤掉导致不足的会报警：把卡挪早、合并、或提高 `scenes[].max_labels`。

## 安全区核对（`safe_area_verified: false`）

安全区数值是按平台界面估的。在抖音 / 视频号真机上截一张播放页，量出顶栏下缘 y、右侧图标列左缘 x 与上下 y、底部文案区上缘 y（按 1080×1920 换算），更新 `top_reserved`、`safe.right_x / y_from / y_to`、`bottom_reserved`，再把 `safe_area_verified` 改成 true。改之前越界只警告，改之后按 0 容忍。

## 渲染期自检（`OV.CHECK`）

每帧叠字层自检，只计数不中断：`label_over_subtitle`（字卡底边越过字幕条顶边）、`label_slot_collision`（两张卡同一格位）、`label_below_band`（字卡越出字卡区）、`subtitle_shrunk` / `label_shrunk`（缩了字号）、`safe_right`（右缘越过安全区）、`safe_bottom`（片尾字底进了底部留白）。阈值在 `qa_gate`：数字 = 超过即 QA 不通过，null = 只记录。`frames` 阶段就会报，不用等成片。

## 字体

全片只用思源黑体子集（可变字重，`assets/fonts/HanSansSC-Subset-VF.otf`，SIL OFL）：字幕 900、字卡 700、片名 / 章节名 / 大字卡 900、文献 / 署名 400。`fonts.files` 由 `player.html` 注册，路径相对专题根目录。

换字体：把字体文件放进专题 `assets/fonts/`，在 `fonts.files` 登记，再改各角色的 `family`。只用可商用的开源字体，不写系统字体回退。字体里没有的字浏览器会悄悄回退系统字体，所以 `tools/check_fonts.py` 逐字核对，缺字在 QA 门报出（`qa_gate.font_fallback`）；子集缺字时按 `assets/fonts/SOURCES.md` 换完整字体。

## 横屏版 `layout_land.json`

画幅 1920×1080；`--orient land` 时自动选它，产物全在 `render/land/`。

- `stage {x 60, y 104, h 880}`：场景仍按竖屏舞台设计，引擎把它映射到左侧矩形（缩到 0.88），背景向右铺满整幅。
- `header {style "nav", radius 14}`：顶部章节导航（当前章主题色底白字、带章内进度线），`chapters[].nav: false` 的章不列。`title.enabled false`：片名只在封面上。
- `labels {style "board", x 1110, width 760, radius 18, center_y 544, max_default 3, extra_rows 2}`：右侧要点板。板头 = 本场主题 `scenes[].topic`（墨色底 + 主题色底线；没写用章节名）或本场最近一张 `big` 卡（主题深色底，危险信号红底）；条目前一个小方块，最新一条高亮。
- `subtitle {y 1022, size 60, center_x 960, max_width 1500, max_chars 13}`；`footer {from 960}`；`safe.right_x 1920`（网页播放器没有侧栏）。
- `ai_mark {text "人工智能生成合成", anchor "bottom_right"}`：右下角；封面 `cover.hold_land` 默认 3 秒，保证标识完整显示。
- `outro {center_x 1510, …}`：片尾文字在右半幅；有参考文献页时片尾不重复 `outro.references`。
- `refs {…}`：参考文献页（`storyboard.references` 非空时自动追加在片尾之后），字号从大往小试到能装进页数，装不下 QA 失败。
