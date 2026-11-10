---
name: med-explainer-video
display_name: 医学科普动画短片
display_name_en: Medical Explainer Animation
description: 把一个医学科普选题做成 3 到 5 分钟的竖屏动画短片。流程是口径表与分镜、3D 卡通角色定妆、用户自己录配音、代码动画逐帧渲染、独立审核、出成片。Windows 和 macOS 通用，不需要 GPU 服务器。
description_zh: 把一个医学科普选题做成 3 到 5 分钟的竖屏动画短片。流程是口径表与分镜、3D 卡通角色定妆、用户自己录配音、代码动画逐帧渲染、独立审核、出成片。Windows 和 macOS 通用，不需要 GPU 服务器。
description_en: Turn a medical-education topic into a 3 to 5 minute vertical animated short. Claims table and storyboard, 3D cartoon character sheets, user-recorded voiceover, code-driven animation rendered frame by frame, independent review, final video. Works on Windows and macOS, no GPU server needed.
version: 1.0.0
author: （作者名）
examples_zh:
  - 帮我做一个讲高血压在家怎么量的科普动画短片，给中老年人看
  - 把这份儿童发烧护理的科普稿改编成竖屏动画，我自己配音
  - 我录好音了，放在 audio/recordings 里，接着往下做
examples_en:
  - Make a short animated explainer about home blood pressure monitoring for older adults
  - Turn this child fever care handout into a vertical animation; I will record the voiceover myself
  - My recordings are in audio/recordings, please continue
---

# 医学科普动画短片

把一个医学科普选题做成竖屏 1080×1920、3 到 5 分钟的动画短片：有剧情、有角色、口径严谨。画面是代码动画（Canvas 逐帧渲染），人物和道具用平台生图出的 3D 卡通静帧，解剖示意由你（AI）用代码亲手画，配音由用户自己录，中文字幕和字卡由叠字层统一画。

下文 `$SKILL` 指本技能目录（这个 SKILL.md 所在的目录）。所有命令都用 `python "$SKILL/scripts/pipeline.py" …`，专题目录作为参数传进去。

## 先说清楚的边界

- **适用于任何医学科普选题**（内科、外科、儿科、口腔、护理、用药、急救、慢病管理…），不绑定专科。
- **医学内容由用户负责把关**：口径表（每条医学表述 + 出处）必须由用户（最好是执业医生）确认。你只能比原文写得更简略，不能更绝对；不确定的标出来问，不要编。
- **三个 HARD 停点必须停下等用户亲口确认**：S0 口径表 + 节拍表、S3 角色定稿与配音分工、S6a 动画预演。流水线读 `storyboard.status.{s0,s3,s6a}.confirmed`，没确认就拒绝往下跑。**绝不能替用户把 confirmed 改成 true**，只有用户在对话里明确说“确认”之后，才按用户原话写 `{"confirmed": true, "by": "用户", "date": "YYYY-MM-DD", "note": "原话"}`。
- **配音由用户录**，你不合成语音。你负责出台词本、导入录音、核对回读结果。
- **解剖结构不交给生图模型**：器官、管道、剖面由你在 `src/anat.js` / `src/scenes.js` 里用代码画，并逐项核对科学性（见 `references/anatomy.md`）。生图只用于 3D 人物、场景和道具图标。
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

得到一条 45 秒的无声预演 `render/demo_preview_v1.mp4`。样例的选题（肾结石）只是举例，写法适用于任何选题。样例的 `design/storyboard_demo.json`、`src/scenes.js`、`src/anat.js` 就是标准写法：满幅 3D 镜头、透明底立绘、道具图标、代码画的解剖、危险信号字卡各示范了一次。**写新片时照着样例改，不要从零发明写法**；函数用法查 `references/api.md`。

## 流程

| 阶段 | 命令（`P="$SKILL/scripts/pipeline.py"`） | 产物 | 停点 |
|---|---|---|---|
| 建专题 | `python $P new <project> --title "片名" --dir <工作目录>` | `<工作目录>/<project>/` | |
| S0 口径与分镜 | 你写 `design/storyboard_<project>.json` → `python $P s0 <专题>` | 修订稿 `design/<project>_修订稿_v<ver>.md` | **HARD S0** |
| S3 角色与配音分工 | 你用平台生图出定妆图 → `tools/cutout.py` 抠底登记 → `python $P s3 <专题>` | `assets/lib/characters/`、`scenes/`、`props/` | **HARD S3** |
| 配音 | `python $P voice <专题>` → 用户照 `audio/台词本.md` 录音放进 `audio/recordings/` → 再跑一次 | `audio/lines/*.wav` + `lines.json` | 缺录音停（退出码 6） |
| 动画 | 你写 `src/scenes.js`、`src/anat.js` → `python $P frames <专题>` 反复看 `render/check_sheet.png` | 抽帧联系表 | |
| 预演 + 渲染前审核 | `python $P run <专题> --until s6a` | `render/<project>_preview_vN.mp4` | 等审核（退出码 5）→ **HARD S6a** |
| 正式版 + QA | `python $P run <专题> --until qa` | `render/<project>_final.mp4` + `.qa.json` | QA 不过退出码 2 |
| 成片审核 + 交付 | `python $P run <专题> --until deliver` | `render/deliver_final.json` | 等审核（退出码 5） |
| 清理 | `python $P clean <专题>`，看过清单再 `--apply` | 旧版本移进回收站 | |

没录音也能先调画面：`python $P timeline <专题> --estimate` 按字数估时长，再 `frames` / `animatic`。`python $P status <专题>` 看各阶段状态。退出码：0 完成，2 失败，3 停在 HARD 点，5 等审核，6 等录音。

## 每一步怎么做

### 1. S0：口径表 + 分镜（storyboard 是唯一真源）

1. 先问清选题、目标观众、片长、想讲的重点，以及用户手头有没有要依据的资料（有就放进 `design/source/`）。
2. **按选题检索权威来源**（`references/sources.md`）：本技能不预设任何专科或指南，每个选题都用联网搜索现查当地的诊疗指南、专家共识、权威教材和官方科普，打开原文核对；没有联网能力就请用户提供资料。每条口径都要能指回来源原句，查不到来源的不进片。
3. 按 `references/story.md` 的七段骨架和角色三件套设计故事，写进 `design/storyboard_<project>.json`（字段说明见 `references/workflow.md` 的 S0 节和模板里的 `_comment`）：
   - `claims[]`：每条医学表述一个编号，口径 + 来源编号 + 来源原句（`quote`）；台词和字卡只能引用这里有的内容。`sources` 登记每个来源的名称、机构、年份、网址、检索日期。
   - `red_flags[]`：危险信号要齐全，每条都要上一张 alert 字卡。
   - `scenes[]`：每场 `beat` / `hook` / `visual` / `lines[]`（who、text、emo）/ `labels[]`（字卡锚到台词里的词，≤ 14 字）/ `cues{}` / `check_frames[]`。
   - 台词按每秒 4.5 字估时长；多音字在 `lines[].say` 里写同音字提示录音（字幕仍用原字）。
4. `python $P s0 <专题>` 生成修订稿，把口径表、危险信号、每场节拍交给用户逐条看。**停下等用户确认 S0。**

### 2. S3：3D 角色、场景、道具

按 `references/characters_3d.md`：

1. 每个角色先出一张**全身定妆图**（头顶到鞋底、纯色背景、无文字），用户选定后存 `assets/lib/characters/<who>/<who>_v1_c<n>.png`，登记 `characters[who].art3d`。之后每张姿势图都拿定妆图当参考，保证长相、衣服、鞋一致。
2. 反复出现的地点各出一张空场景图（无人物），登记 `places`。
3. 立绘和道具图标用**纯品红 #FF00FF 底**出图，再用 `python "$SKILL/scripts/tools/cutout.py" <图片> sp_<角色>_<动作>`（图标用 `ic_<物品>`）抠成透明底并登记进 `storyboard.assets`。
4. 和用户定每个角色由谁来配（`voices[who].actor`）和嗓音要求（`voices[who].desc`）。
5. `python $P s3 <专题>` 核对登记，**停下等用户确认 S3**。定稿图永不覆盖，要改就升版本（`_v2`）。

### 3. 配音：用户自己录

按 `references/voice_recording.md`：

1. `python $P voice <专题>` 出 `audio/台词本.md`（按角色分组：文件名、台词、读音提示、语气、参考时长），把它交给用户。
2. 用户录好放进 `audio/recordings/`：一句一个文件（`s03_2.m4a`）、一个角色一整段（`narrator.m4a`，句间停 1.5 秒以上）、或一场一个文件都行。
3. 再跑 `python $P voice <专题>`：自动转码、降噪、切静音、统一响度，并用 whisper 回读逐句核对台词。对不上的句子会列出来，让用户听一下：没问题就写进 `storyboard.tts.ear_confirmed`，有问题就单句重录。
4. 你听不到声音：读音和语气的最终判断交给用户人耳。

### 4. 动画

1. 每场写 `src/scenes.js` 的 `SC.<场景id> = (c, A) => { … }`。先读 `references/api.md` 和样例的 `scenes.js`，用现成的镜头函数拼（`SH.full` 满幅镜头、`SH.SP` 立绘、`SH.IC` 图标、`SH.seg` 换镜、`SH.alarm` / `SH.flags` 危险信号、`PR.*` 道具），尽量不手写底层绘图。一次只写一场，写完就抽帧看，再写下一场。每帧只由时间决定（不用 `Math.random` 和 `Date`）。
2. 解剖示意写在 `src/anat.js`（`AN.*`），按 `references/anatomy.md` 先查权威参考图再画，逐项核对。
3. `python $P frames <专题>` 抽帧，**打开图片亲眼看** `render/check_sheet.png` 和 `render/anat_sheet.png`（原尺寸逐张核解剖）；叠字层自检有硬错会直接失败。如果你（当前模型）看不了图片，明确告诉用户，请用户看图反馈，不要假装看过。
4. 检查：画面零文字、道具跨镜头连续、字卡不压主体、人物不钻到顶部进度条下面、开场 2 秒内有东西动。

### 5. 预演、两道审核、S6a、正式版

1. `python $P run <专题> --until s6a`：出预演，然后打包审核材料，停在退出码 5。
2. **渲染前审核**：另开一个对话或子代理当独立审核员，把 `references/audit_pre_prompt.md` 原样交给它（替换 `{project}` `{n}`），材料起点是 `render/audit/pre_v<n>/index.md`。不要把你自己的判断带进去。审核员可以直接改非口径问题并重跑预演，口径问题只能提交给用户。报告 `design/audit_pre_v<n>.md` 写完后用 `audit.py stamp` 盖章。
3. 再跑 `run --until s6a`，审核门通过后，把预演 mp4、联系表、审核员交给用户的口径问题一起给用户看。**停下等用户确认 S6a。**
4. `python $P run <专题> --until qa`：60 fps + 4 子帧运动模糊的正式版，QA 门检查字幕逐字一致、逐句回读、字幕开口点对齐、响度、危险信号上屏、AI 标识、字体缺字等。
5. **成片审核**：`run --until deliver` 停在退出码 5，另开审核员用 `references/audit_post_prompt.md` 审成片，写 `render/audit_post_final.md` 并盖章；不过就修、重渲、换一个新审核员复审。
6. 交付后 `python $P clean <专题>` 列出旧版本，用户看过再 `--apply`（移进回收站，可还原）。`python $P export_subs <专题>` 可导出 srt 字幕。

## 规则

1. storyboard 是唯一真源：专题常量（角色名、口径、字卡、音效时刻、片尾文献）都写在 storyboard，不写进代码。版式只改专题的 `layout.json`。
2. 医学口径不为戏剧效果改动：`claims[]` 原意进画面或台词；危险信号必须齐全且全部上字卡（QA 门检查）。
3. 字幕时刻吸附波形开口点；whisper 的中文词级时间只作参考。
4. 审核看成片 mp4 抽出的帧，不只看开发渲染器；两道审核由独立审核员做，作者自己不审自己。
5. 定稿素材（定妆图、场景图、已批准的解剖画法）一经确认不覆盖，改动升版本。
6. 人物只用 3D（满幅静帧或透明底立绘），不和 2D 手绘小人混搭，不用画中画式贴图卡片。
7. 成片片头有“AI 生成内容”标识（叠字层自动画，符合 GB 45438—2025），片尾写明哪些素材由 AI 生成。
8. 成片审核通过才清理；清理只移进回收站，清空由用户自己决定。

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
| `references/layout.md` | 改版式（字号、位置、安全区）时 |
| `references/sfx.md` | 加音效时 |
| `references/review.md` | 审片方法（扫描工具、怎么取证） |
| `references/audit_pre_prompt.md` / `audit_post_prompt.md` | 交给独立审核员的提示词，原样使用 |
