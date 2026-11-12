# 流水线细则

单一真源：专题的 `design/storyboard_<project>.json`；版式真源：专题的 `layout.json`；工具都在 `$SKILL/scripts/`，专题目录里只放数据、素材、场景代码和产物。

## 目录

| 类 | 在哪 | 谁改 |
|---|---|---|
| 工具（所有专题共用） | `$SKILL/scripts/pipeline.py`、`tools/*.py *.js`、`src/` 原件 | 不改 |
| 专题代码 | 专题 `src/scenes.js`（各场动画）、`src/anat.js`（解剖）、`src/cover.html`（可选封面）；`src/` 里其余文件是建专题时复制的引擎副本 | 你 |
| 专题数据 | `design/storyboard_<project>.json`、`layout.json`（版式和主题色，见 layout.md） | 你；HARD 点确认写进 `status` |
| 定稿素材（永不覆盖） | `assets/lib/characters/`、`assets/lib/scenes/`、`assets/lib/props/`、`assets/fonts/` | 改动升版本 |
| 录音 | `audio/recordings/`（用户放）→ `audio/lines/`（导入结果） | 用户 / 工具 |
| 产物 | `render/`（timeline.json、mix.wav、check/、预演、成片、qa.json、审核材料、pipeline.log、stage_status.json） | 工具 |

## S0 口径表 + 节拍表【HARD】

storyboard 主要字段（模板里每段都有 `_comment`）：

| 字段 | 内容 |
|---|---|
| `project` / `title` / `title_card` / `version` | 目录名、片名、片头大字、版本号（改稿升版本，修订稿文件名跟着变） |
| `claims[]` | `{id, text, src}`：每条医学表述的原文和出处 |
| `red_flags[]` / `red_flags_action` | 危险信号原文（每条要上一张 `alert: true` 字卡）、出现后怎么办 |
| `sources[]` / `references[]` | 参考来源；`references` 会出片尾文献页（横屏版） |
| `characters{}` | `{name, desc, color, art3d}`；`narrator` 是旁白 |
| `places{}` | 反复出现的地点：`{name, desc, art}` |
| `chapters[]` | `{id, node（顶部章节名）, scenes: [...]}` |
| `scenes[]` | `id, chapter, beat, hook, visual, claims, place, lines[], labels[], cues{}, check_frames[], lead, tail, max_labels` |
| `lines[]` | `{who, text, emo, say?, hold?, br?}`：`say` = 读音提示（同音字写法），`hold` = 句后多停几秒，`br` = 字幕断点 |
| `labels[]` | `{at: [句号, "锚词"], text, big?, alert?, rf?}`：字卡在第几句的哪个词出现；`big` 大字卡；`alert` 红色警示卡；`rf` 关联危险信号下标 |
| `cues{}` | `{名字: [句号, "锚词"]}`：画面事件锚点，场景代码用 `A.cue(名字)` |
| `check_frames[]` | `"cue:x+0.6"`、`"label:2+0.8"`、`"end-1.0"`：解剖场要声明，抽帧核对用 |
| `assets{}` | `{id: {src}}`：3D 立绘 `sp_*`、道具图标 `ic_*`（`tools/cutout.py` 自动登记） |
| `voices{}` / `tts{}` | 谁来配、嗓音要求（每个有台词的角色都要有一项；S3 之前 `actor` 可以先写“待定”）；回读提示词、关键词、门限、人耳确认名单（见 voice_recording.md） |
| `audio{}` | 配乐（bpm、小调段、安静段）与音效（见 sfx.md） |
| `outro{}` / `credits[]` / `disclaimer` / `cover{}` | 片尾口号、AI 说明、片尾短参考；署名；免责声明；封面 |
| `status{}` | 三个 HARD 点。只有用户在对话里确认后才写 `confirmed: true` |

检查清单：每条医学表述在口径表里有编号和出处；危险信号齐全且每条在某张字卡上；每场有 beat / hook / visual；字卡与 cue 锚到台词里的词；单张字卡 ≤ 14 字；同屏字卡 ≤ 3 张（`max_labels`）；普通卡停留 ≥ 2.5 s、危险信号卡 ≥ 3.5 s（timeline 自动算 `card_stays`，不够会延长场尾或报警）；声明 `max_labels: 3` 的场人物脚底 y ≤ 1190；s01 前 5 秒设计坐标 y 236–420 不放主体（片名会盖住）；解剖场至少 2–3 个 `check_frames`；估算片长按每秒 4.5 字。

`python $P check <专题>` 先把分镜的错误清零（JSON 写坏、字卡 / cue 的锚词不在那句台词里、角色或图没登记、危险信号没上卡…，每条都说怎么改）；`python $P s0 <专题>` 生成修订稿（md + docx）。用户看口径表、危险信号、每场节拍；通常 1–2 轮修订。估算片长超过 `target_seconds` 的 115% 会提醒，先删台词再往下走。

## S3 角色定稿 / 场景 / 配音分工【HARD】

见 characters_3d.md。`python $P s3 <专题>` 列出每个角色的定妆图、每个地点的场景图、`assets` 登记的文件是否都在、每个角色由谁来配。用户确认角色长相、场景、样帧风格、配音分工后写 `status.s3`。

## 配音

见 voice_recording.md。`voice` 阶段：出台词本（md + docx）→ 录音不齐就停（退出码 6）→ 齐了就导入。`voice --draft` 用合成声顶替还没录的句子，只够出预演：预演审核和正式渲染会等真人录音（退出码 6）。导入结果 `audio/lines/lines.json` 每句有 `passed`（回读核对）、`asr`（回读文字）、`cps`（字/秒）、`note`（问题说明）、`ct` / `ce`（逐字起止秒）。

## timeline / mix

- `timeline`：场景与台词的绝对时间、字幕分块（≤ 11 字一块，按标点和词边界切）、字幕块起点吸附波形开口点、字卡时刻、cue、`card_stays`。没录音时 `--estimate` 按字数估。
- `mix`：程序化配乐（电钢琴分解和弦，可指定小调段、安静段）+ 字卡出现的轻点声 + 转场气流声 + storyboard 声明的音效；人声闪避；整体 −16 LUFS。产物 `render/mix.wav` 和分轨 `stem_*.wav`。

## 动画与抽帧

- 场景函数 `SC.<id> = (c, A) => {…}` 在设计坐标里画（宽 1080，主舞台 y 236–1236），引擎整体映射到舞台。`A.t` 场内秒、`A.T` 场长、`A.ln(i)` 第 i 句 `{start, end}`、`A.cue(name)`、`A.lab(k)` 第 k 张字卡时刻、`A.img(id)` 素材。
- 通用镜头：`src/shots.js`（`SH.full` 满幅镜头、`SH.bg` 背景、`SH.floor`、`SH.home`、`SH.clinic` 场景底、`SH.SP` 立绘、`SH.spX` 立绘收进安全线、`SH.IC` 图标、`SH.xf` 两张立绘交叉淡化换姿势、`SH.steps` 分步演示、`SH.spot` 圈重点、`SH.arrow` 箭头、`SH.level` 等高线、`SH.zoomImg` 局部放大、`SH.drop` 掉落、`SH.card` 卡片；完整列表见 api.md）；道具 `src/props.js`（`PR.clock`、`PR.window` 等）；绘图工具 `src/lib.js`（`L.*` 缓动、形状）。
- 每帧是时间的纯函数：不用 `Math.random()`（用 `L.rand(seed)` 之类的确定性函数）、不用 `Date`。
- 写完一场先 `python $P check <专题>`（语法、函数名、图 id、cue、字卡下标；`frames` / `animatic` / `render` 开头也会自动跑）。
- `frames` 还会做空画面检查（`tools/emptyscan.py`）：某一场一半以上的抽帧舞台上只有底色就失败；确实要留白的场在 storyboard 里写 `"allow_empty": true`。
- `frames`：每句 35% / 85%、每张字卡出现后 0.8 s、每个 cue 后 0.5 s、场末各抽一帧 → `render/check_sheet.png`；声明了 `check_frames` 的场另出 `render/anat_sheet.png`。叠字层自检（字卡压字幕、越过安全区等）有硬错就失败，样本在 `render/check/overlay_check.json`。
- 细看（在专题目录里跑）：`node "$SKILL/scripts/tools/strip.js" player 3.0:3.5 render/strip.png --cols=8` 把 3.0–3.5 秒每一帧拼成一张条带图（时刻是全片的绝对秒）；`tools/crop.js player t0:t1 out.png --at=x,y,w,h` 只裁舞台上某一块。

## animatic（预演）

`render.js` 低帧率无运动模糊并行渲染 → `render/<project>_preview_vN.mp4` + 每 2 s 一张的联系表 `_sheet.png` + 预演 QA（不拦流程，但 failures 要处理）。

## audit_pre（渲染前审核）→ S6a【HARD】

`audit.py pack pre` 打包：预演每 2 s 一帧缩图、封面 / 每场开头 / 每张字卡 / 每个 cue 的原尺寸关键帧、storyboard / timeline / layout / src 快照、`index.md`。门：最新 `design/audit_pre_v<n>.md` 的 `result: pass` 且 storyboard / timeline / src 哈希与当前一致。审核员（另开对话或子代理）按 audit_pre_prompt.md 审，非口径问题可以直接改并重跑预演，口径问题交用户。写完报告在专题目录下执行 `python "$SKILL/scripts/tools/audit.py" stamp design/audit_pre_v<n>.md` 盖章。

S6a 后又改了任何东西（storyboard、timeline、画面代码、版式），`render` 门会拦下并自动出差异稿 `design/audit_diff_v<n>.md`：让审核员只复审差异，写 `audit_pre_v<n+1>.md`，不用重新确认 S6a。只作记录的字段（`status`、`tts.ear_confirmed` 等）改了不触发复审。

## render / qa

- `render`：默认标准画质 30 fps + 2 子帧运动模糊；`--quality high`（或 storyboard 写 `"quality": "high"`）60 fps + 4 子帧。字幕字卡不模糊，BT.709 电视范围；有 `cover` 时成片第一帧即封面，另出 `render/<project>_cover_9x16.png`。
- QA 门（`render/<project>_final.qa.json`，任一项不过退出码 2）：字幕与台词逐字一致；逐句回读拼音相似度 ≥ 0.97（`qa.asr_min` 可调）；字幕开口点 ≤ 100 ms 的块 ≥ 95%；响度 −16 ± 1.5 LUFS；分辨率 / 时长 / 像素格式；危险信号逐卡上屏；字卡停留；舞台换镜暗谷；AI 标识（字高 ≥ 短边 5%、从第 0 帧起 ≥ 2 s）；字体缺字。

## audit_post（成片审核）→ deliver → clean

- `audit.py pack post`：成片每 2 s 一帧、片头片尾原尺寸、音频统计与 6 段回放片段。审核员按 audit_post_prompt.md 审，只写报告不改源文件；写完盖章 `audit.py stamp render/audit_post_final.md`。不过就修、重渲、换新审核员复审。
- `deliver`：成片审核 pass 且成片哈希一致、QA pass → `render/deliver_final.json`（文件、大小、sha1）。
- `clean`：每类生成物（旧预演、渲染分段缓存、开发抽帧、旧审核材料、带版本号的旧文稿）只留最新 2 版，其余先归拢到 `<工作目录>/清理_<专题>_<时刻>/` 再整个移进回收站；清单 `render/cleanup_<时刻>.json`。定稿素材、录音、storyboard、代码、交付清单里的文件永远不动。

## 横屏版（可选）

`--orient land`：1920×1080，版式 `layout_land.json`（动画在左、右侧要点板、片尾文献页），产物全在 `render/land/`，竖屏不受影响。阶段相同，`run <专题> --orient land --until deliver`。

## 发布

标题 ≤ 30 字备 3 个、简介、话题、封面（9:16，横屏 16:9）；发布时勾选平台的“AI 生成”声明；简介不写商品名、医院名；最好用医生或机构认证账号发。

## 后台运行

`voice`（导入）、`animatic`、`render`、`run` 都可能超过一次工具调用的时限。加 `--bg` 放后台，立刻返回；`python $P wait <专题> [--timeout=90]` 等并打印最近进度，退出码 7 = 还在跑（继续 `wait`），其余退出码就是任务自己的结果。进度和日志在 `render/bg_job.log`，状态在 `render/bg_job.json`；同一专题同时只允许一个后台任务。
