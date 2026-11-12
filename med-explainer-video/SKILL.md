---
name: med-explainer-video
display_name: 医学科普动画短片
display_name_en: Medical Explainer Animation
description: 把一个医学科普选题做成 3 到 5 分钟的竖屏动画短片。流程是口径表与分镜、角色定妆（画风自选）、用户自己录配音、代码动画逐帧渲染、独立审核、出成片。Windows 和 macOS 通用，不需要 GPU 服务器。
description_zh: 把一个医学科普选题做成 3 到 5 分钟的竖屏动画短片。流程是口径表与分镜、角色定妆（画风自选）、用户自己录配音、代码动画逐帧渲染、独立审核、出成片。Windows 和 macOS 通用，不需要 GPU 服务器。
description_en: Turn a medical-education topic into a 3 to 5 minute vertical animated short. Claims table and storyboard, character sheets in an art style you choose, user-recorded voiceover, code-driven animation rendered frame by frame, independent review, final video. Works on Windows and macOS, no GPU server needed.
version: 1.0.0
author: （作者名）
examples_zh:
  - 帮我做一个讲老人在家怎么防跌倒的科普动画短片，给中老年人看
  - 把这份儿童发烧护理的科普稿改编成竖屏动画，我自己配音
  - 我录好音了，放在 audio/recordings 里，接着往下做
examples_en:
  - Make a short animated explainer about preventing falls at home for older adults
  - Turn this child fever care handout into a vertical animation; I will record the voiceover myself
  - My recordings are in audio/recordings, please continue
---

# 医学科普动画短片

把一个医学科普选题做成竖屏 1080×1920、3 到 5 分钟的动画短片：有剧情、有角色、口径严谨。画面是代码动画（Canvas 逐帧渲染），人物和道具用平台生图出的立体人偶静帧（画风由用户定，样例是黏土定格风），解剖示意由你（AI）用代码亲手画，配音由用户自己录，中文字幕和字卡由叠字层统一画。

下文 `$SKILL` 指本技能目录（这个 SKILL.md 所在的目录）。所有命令都用 `python "$SKILL/scripts/pipeline.py" …`，专题目录作为参数传进去。

## 先说清楚的边界

- **适用于任何医学科普选题**（内科、外科、儿科、口腔、护理、用药、急救、慢病管理…），不绑定专科。
- **医学内容由用户负责把关**：口径表（每条医学表述 + 出处）必须由用户（最好是执业医生）确认。你只能比原文写得更简略，不能更绝对；不确定的标出来问，不要编。
- **三个 HARD 停点必须停下等用户亲口确认**：S0 口径表 + 节拍表、S3 角色定稿与配音分工、S6a 动画预演。流水线读 `storyboard.status.{s0,s3,s6a}.confirmed`，没确认就拒绝往下跑。**绝不能替用户把 confirmed 改成 true**，只有用户在对话里明确说“确认”之后，才按用户原话写 `{"confirmed": true, "by": "用户", "date": "YYYY-MM-DD", "note": "原话"}`。
- **配音由用户录**。你负责出台词本、导入录音、核对回读结果。合成声只能当草稿（`voice --draft`，对节奏用），正式成片必须是真人录音，流水线会拦。
- **解剖结构不交给生图模型**：器官、管道、剖面由你在 `src/anat.js` / `src/scenes.js` 里用代码画，并逐项核对科学性（见 `references/anatomy.md`）。生图只用于人物、场景和道具图标。
- **模型能力**：写场景代码、画解剖、看图核对对模型要求高，建议用户选当前可用模型里最强、且能看图的那个；轻量模型容易写出跑不通或很空的画面。
- **画面里零文字**：所有中文由叠字层（字幕、字卡、片名、片尾）负责；生图提示词写明“无文字、无水印”。
- 不画生殖器等敏感画面；不出现商品名、医院名、联系方式；结尾不承诺疗效。

## 第一次用：装环境

```
python "$SKILL/scripts/pipeline.py" setup
```

会自动装 Python 包、Node 包（puppeteer-core），找 ffmpeg（没有就用 pip 包里自带的）、找本机 Chrome 或 Edge（都没有就下载一个无头浏览器）。国内网络会自动改用清华 PyPI、npmmirror、hf-mirror 镜像。最后打印每一项是否就绪；缺 Node.js 时请用户装 Node.js 18 或更新版本。语音识别模型（约 1.6 GB）在第一次导入录音时自动下载，想提前下好用 `setup --asr`。

## 先跑一遍样例（第一次用、或不确定画面怎么写时）

```
python "$SKILL/scripts/pipeline.py" new demo --example --dir <工作目录>
python "$SKILL/scripts/pipeline.py" timeline <工作目录>/demo --estimate
python "$SKILL/scripts/pipeline.py" animatic <工作目录>/demo
```

得到一条 45 秒的无声预演 `render/demo_preview_v1.mp4`（约 1 分钟）。样例的选题（在家量血压）和画风（黏土定格）只是举例，写法适用于任何选题。样例的 `design/storyboard_demo.json`、`src/scenes.js`、`src/anat.js` 就是标准写法：满幅镜头、透明底立绘、道具图标、分步卡、代码画的示意图、危险信号字卡各示范了一次。**写新片时照着样例改，不要从零发明写法**；函数用法查 `references/api.md`。

## 流程

| 阶段 | 命令（`P="$SKILL/scripts/pipeline.py"`） | 产物 | 停点 |
|---|---|---|---|
| 建专题 | `python $P new <project> --title "片名" --dir <工作目录> [--theme mint\|indigo\|amber]` | `<工作目录>/<project>/` | |
| S0 口径与分镜 | 你写 `design/storyboard_<project>.json` → `python $P check <专题>` → `python $P s0 <专题>` | 修订稿 `design/<project>_修订稿_v<ver>.md` / `.docx` | **HARD S0** |
| S3 角色与配音分工 | 你用平台生图出定妆图 → `tools/cutout.py` 抠底登记 → `python $P s3 <专题>` | `assets/lib/characters/`、`scenes/`、`props/` | **HARD S3** |
| 配音 | `python $P voice <专题>` → 用户照 `audio/台词本.docx` 录音放进 `audio/recordings/` → 再跑一次 | `audio/lines/*.wav` + `lines.json` | 缺录音停（退出码 6） |
| 动画 | 你写 `src/scenes.js`、`src/anat.js` → `python $P check <专题>` → `python $P frames <专题>` 反复看 `render/check_sheet.png` | 抽帧联系表 | |
| 预演 + 渲染前审核 | `python $P run <专题> --until s6a` | `render/<project>_preview_vN.mp4` | 等审核（退出码 5）→ **HARD S6a** |
| 正式版 + QA | `python $P run <专题> --until qa` | `render/<project>_final.mp4` + `.qa.json` | QA 不过退出码 2 |
| 成片审核 + 交付 | `python $P run <专题> --until deliver` | `render/deliver_final.json` | 等审核（退出码 5） |
| 清理 | `python $P clean <专题>`，看过清单再 `--apply` | 旧版本移进回收站 | |

配色有三套主题：`mint` 薄荷绿（默认）、`indigo` 靛蓝、`amber` 琥珀。建专题时问用户想要哪一套；之后想换跑 `python $P theme <专题> <主题名>`，想要自己的颜色就改专题 `layout.json` 的 `theme`（见 `references/layout.md`）。

没录音也能先调画面：`python $P timeline <专题> --estimate` 按字数估时长，再 `frames` / `animatic`。`python $P status <专题>` 看各阶段状态。退出码：0 完成，2 失败，3 停在 HARD 点，5 等审核，6 等录音，7 后台任务还在跑。

### 改完先 check

每次改完 `storyboard` 或 `src/scenes.js`，先跑 `python $P check <专题>`（1 秒出结果）。它会用人话指出：JSON 第几行写坏了、字卡锚的词不在那句台词里、角色没登记、图没登记、场景函数缺了、调用了不存在的函数（并给出相近的名字）、cue 没声明、画面里写了字。`✗` 是必须改的错误，`!` 是提醒（例如“这句台词讲到的内容画面上没有对应变化”“全片只用了一张立绘”），提醒也要逐条处理或向用户说明为什么不改。

### 长命令放后台

导入录音、预演、正式渲染都可能跑几分钟到几十分钟，超过你一次工具调用的时限就会被掐断。这类命令一律加 `--bg`：

```
python $P run <专题> --until s6a --bg      # 立刻返回，任务在后台跑
python $P wait <专题>                      # 等最多 90 秒，打印最近的进度；退出码 7 = 还在跑，接着再 wait
```

`wait` 返回别的退出码就是任务结束了，含义同上（0 完成、2 失败并带出错原因、3 / 5 / 6 停点）。同一个专题一次只跑一个后台任务。

## 每一步怎么做

### 1. S0：口径表 + 分镜（storyboard 是唯一真源）

1. 先问清选题、目标观众、片长、想讲的重点，以及用户手头有没有要依据的资料（有就放进 `design/source/`）。
2. **按选题检索权威来源**（`references/sources.md`）：本技能不预设任何专科或指南，每个选题都用联网搜索现查当地的诊疗指南、专家共识、权威教材和官方科普，打开原文核对；没有联网能力就请用户提供资料。每条口径都要能指回来源原句，查不到来源的不进片。
3. 按 `references/story.md` 的七段骨架和角色三件套设计故事，写进 `design/storyboard_<project>.json`（字段说明见 `references/workflow.md` 的 S0 节和模板里的 `_comment`）：
   - `claims[]`：每条医学表述一个编号，口径 + 来源编号 + 来源原句（`quote`）；台词和字卡只能引用这里有的内容。`sources` 登记每个来源的名称、机构、年份、网址、检索日期。
   - `red_flags[]`：危险信号要齐全，每条都要上一张 alert 字卡。
   - `scenes[]`：每场 `beat` / `hook` / `visual` / `lines[]`（who、text、emo）/ `labels[]`（字卡锚到台词里的词，≤ 14 字）/ `cues{}` / `check_frames[]`。
   - 台词按每秒 4.5 字估时长；多音字在 `lines[].say` 里写同音字提示录音（字幕仍用原字）。
4. 删掉模板里用不上的占位角色、占位场景和占位口径，跑 `python $P check <专题>` 把错误清零。
5. `python $P s0 <专题>` 生成修订稿（md + Word），把口径表、危险信号、每场节拍交给用户逐条看。**停下等用户确认 S0。**

### 2. S3：画风、角色、场景、道具

按 `references/characters_3d.md`：

0. 先和用户定**画风**，写进 storyboard 的 `style.art`（`references/characters_3d.md` 第 0 节有三种现成写法）；之后每张图的提示词都以它开头。
1. 每个角色先出一张**全身定妆图**（头顶到鞋底、纯色背景、无文字），用户选定后存 `assets/lib/characters/<who>/<who>_v1_c<n>.png`，登记 `characters[who].art3d`。之后每张姿势图都拿定妆图当参考，保证长相、衣服、鞋一致。
2. 反复出现的地点各出一张空场景图（无人物），登记 `places`。
3. 立绘和道具图标用**纯品红 #FF00FF 底**出图，再用 `python "$SKILL/scripts/tools/cutout.py" <图片> sp_<角色>_<动作>`（图标用 `ic_<物品>`）抠成透明底并登记进 `storyboard.assets`。
4. 和用户定每个角色由谁来配（`voices[who].actor`）和嗓音要求（`voices[who].desc`）。
5. `python $P s3 <专题>` 核对登记，**停下等用户确认 S3**。定稿图永不覆盖，要改就升版本（`_v2`）。

### 3. 配音：用户自己录

按 `references/voice_recording.md`：

1. `python $P voice <专题>` 出 `audio/台词本.md` 和 `台词本.docx`（按角色分组：文件名、台词、读音提示、语气、参考时长），把 Word 版交给用户。
2. 用户录好放进 `audio/recordings/`：一句一个文件（`s03_2.m4a`）、一个角色一整段（`narrator.m4a`，句间停 1.5 秒以上）、或一场一个文件都行。
3. 再跑 `python $P voice <专题>`：自动转码、降噪、切静音、统一响度，并用 whisper 回读逐句核对台词。对不上的句子会列出来，让用户听一下：没问题就写进 `storyboard.tts.ear_confirmed`，有问题就单句重录。
4. 你听不到声音：读音和语气的最终判断交给用户人耳。
5. 用户想在录音前先看带声音的预演：先问用户是否同意把台词文本发给微软的在线朗读服务，同意再跑 `python $P voice <专题> --draft`（要联网、要 `pip install edge-tts`）。草稿声只用来对节奏，预演审核、S6a 确认和正式版都要等真人录音导入之后，流水线会拦（退出码 6）。

### 4. 动画

1. 新专题的 `src/scenes.js` 是一份占位骨架（只有两个示范场），**整份换成你自己的场景**，别在它上面打补丁。每场写 `SC.<场景id> = (c, A) => { … }`。先读 `references/api.md` 和样例的 `scenes.js`，用现成的镜头函数拼（`SH.full` 满幅镜头、`SH.SP` 立绘、`SH.IC` 图标、`SH.seg` 换镜、`SH.steps` 分步演示、`SH.spot` 圈出重点、`SH.arrow` 箭头、`SH.level` 等高线、`SH.zoomImg` 局部放大、`SH.alarm` / `SH.flags` 危险信号、`PR.*` 道具），尽量不手写底层绘图。一次只写一场，写完就 `check`、抽帧看，再写下一场。每帧只由时间决定（不用 `Math.random` 和 `Date`）。
   - **每条要点都要有对应的画面**：台词讲到一个动作、一个部位、一个数字，画面上就要有东西在那一刻出现或变化（在 storyboard 给那句话声明 `cues`，场景代码里用 `A.cue('名字')` 触发）。只放一张人物立绘加字卡，等于没有演示。
   - **每场换姿势或换道具**：同一张立绘不要从头用到尾；按内容出不同动作的立绘（示范、指、皱眉、点头）。
   - **开场第一秒就有主体**：第一场不要让所有东西都等某个 cue 才出现。
2. 解剖示意写在 `src/anat.js`（`AN.*`），按 `references/anatomy.md` 先查权威参考图再画，逐项核对。
3. `python $P frames <专题>` 抽帧，**打开图片亲眼看** `render/check_sheet.png` 和 `render/anat_sheet.png`（原尺寸逐张核解剖）；叠字层自检有硬错、画面代码运行出错、或某一场抽出来基本是空画面，都会直接失败并说明是哪一场、为什么。如果你（当前模型）看不了图片，明确告诉用户，请用户看图反馈，不要假装看过。
4. 检查：画面零文字、道具跨镜头连续、字卡不压主体、人物不钻到顶部进度条下面、开场 2 秒内有东西动。

### 5. 预演、两道审核、S6a、正式版

1. `python $P run <专题> --until s6a --bg`：出预演，然后打包审核材料，停在退出码 5。
2. **渲染前审核**：另开一个对话或子代理当独立审核员，把 `references/audit_pre_prompt.md` 原样交给它（替换 `{project}` `{n}`），材料起点是 `render/audit/pre_v<n>/index.md`。不要把你自己的判断带进去。审核员可以直接改非口径问题并重跑预演，口径问题只能提交给用户。报告 `design/audit_pre_v<n>.md` 写完后用 `audit.py stamp` 盖章。
3. 再跑 `run --until s6a`，审核门通过后，把预演 mp4、联系表、审核员交给用户的口径问题一起给用户看。**停下等用户确认 S6a。**
4. `python $P run <专题> --until qa --bg`：出正式版。默认标准画质（30 fps + 2 子帧运动模糊）；用户要更顺滑的画面再加 `--quality high`（60 fps + 4 子帧，耗时约 1.6 倍）。渲染耗时和电脑核数有关：15 核笔记本上大约和片长一样长，核少的电脑会慢几倍，所以一律放后台跑。QA 门检查字幕逐字一致、逐句回读、字幕开口点对齐、响度、危险信号上屏、AI 标识、字体缺字等。
5. **成片审核**：`run --until deliver` 停在退出码 5，另开审核员用 `references/audit_post_prompt.md` 审成片，写 `render/audit_post_final.md` 并盖章；不过就修、重渲、换一个新审核员复审。
6. 交付后 `python $P clean <专题>` 列出旧版本，用户看过再 `--apply`（移进回收站，可还原）。`python $P export_subs <专题>` 可导出 srt 字幕。

## 规则

1. storyboard 是唯一真源：专题常量（角色名、口径、字卡、音效时刻、片尾文献）都写在 storyboard，不写进代码。版式只改专题的 `layout.json`。
2. 医学口径不为戏剧效果改动：`claims[]` 原意进画面或台词；危险信号必须齐全且全部上字卡（QA 门检查）。
3. 字幕时刻吸附波形开口点；whisper 的中文词级时间只作参考。
4. 审核看成片 mp4 抽出的帧，不只看开发渲染器；两道审核由独立审核员做，作者自己不审自己。
5. 定稿素材（定妆图、场景图、已批准的解剖画法）一经确认不覆盖，改动升版本。
6. 全片一种画风：人物只以满幅静帧或透明底立绘出现，所有生成的图用同一段画风描述；不把生成的人物和代码画的小人混搭，不用画中画式贴图卡片。
7. 成片片头有“AI 生成内容”标识（叠字层自动画，符合 GB 45438—2025），片尾写明哪些素材由 AI 生成。
8. 成片审核通过才清理；清理只移进回收站，清空由用户自己决定。
9. 报错先读报错：流水线的错误信息会说哪个文件第几行、为什么、怎么改。照着改，不要绕过检查，也不要删掉报错的那一场了事。

## 参考文件

| 文件 | 什么时候读 |
|---|---|
| `references/workflow.md` | 各阶段的输入、产物、检查清单、storyboard 字段 |
| `references/sources.md` | 写 S0 前：按选题检索权威来源、核对原文、登记出处 |
| `references/story.md` | 写 S0 前：故事骨架、角色三件套、写卡规则 |
| `references/api.md` | 写场景代码前：骨架、A 上下文、SH / PR / L 函数速查、常见做法 |
| `templates/example/` | 样例专题的原件（`new --example` 会复制它） |
| `references/characters_3d.md` | S3 出图前：定妆图、场景图、姿势图提示词，抠底与登记 |
| `references/voice_recording.md` | 出台词本、导入录音、看回读结果时 |
| `references/anatomy.md` | 画解剖前 |
| `references/layout.md` | 换主题色、改版式（字号、位置、安全区）时 |
| `references/sfx.md` | 加音效时 |
| `references/review.md` | 审片方法（扫描工具、怎么取证） |
| `references/audit_pre_prompt.md` / `audit_post_prompt.md` | 交给独立审核员的提示词，原样使用 |
