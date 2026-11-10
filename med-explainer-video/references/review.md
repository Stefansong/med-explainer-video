# 审片方法

审核员（AI）听不到声音：音频类结论靠 whisper 回读、声学测量和图（波形、语谱、响度），**判不了的列给用户人耳确认**，不要猜。画面类结论一律从成片 mp4 抽帧取证，不看开发渲染器。下面的命令都在专题目录下执行，`T="$SKILL/scripts/tools"`。

## 1. 画面

| 看什么 | 怎么取 | 判据 |
|---|---|---|
| 全片节奏、空档、遮挡 | 审核材料包里每 2 s 一帧；场景交界前后 0.4 s 每 0.1 s 一帧（`ffmpeg -ss 秒 -i 成片 -frames:v 1 x.png`） | 没有空帧、闪帧 |
| 突变 | `python $T/scan.py jumps <mp4>` | 每个峰值都能说出是哪个有意的切换；说不出的逐帧看 |
| 换镜透底变灰 | QA 自动跑（qa.json `stage_dips`），或 `python $T/dipscan.py <mp4>` | 场内换镜时新旧镜头同时半透明、透出底色 = 失败，修法：新镜头盖在不透明的旧镜头上只淡入。有意的暗场（关灯、闭眼）写进 `storyboard.qa.dips_ok` 并写 why |
| 字卡字幕位置 | `python $T/scan.py edges <mp4>` | 右缘 ≤ 900（`safe.right_x`）；中心约 540 |
| 顶部遮挡 | `python $T/scan.py top <mp4>` | 人物头顶、主体不钻到进度条 / 章节名下面 |
| 改时长后的对位 | `python $T/scan.py warp <旧mp4> <旧timeline> <新mp4>` | 差异中位数约 3；大于 18 的连续段逐个看 |
| 3D 立绘 | 关键帧原尺寸 | 长相、衣服、鞋与定妆图一致；边缘没有残留底色；不压道具、不越右安全线 |
| 解剖 | `render/anat_sheet.png` 原尺寸 | 按 storyboard `anatomy_checks` 逐条（见 anatomy.md） |

## 2. 配音

1. `audio/lines/lines.json`：`passed: false` 且不在 `tts.ear_confirmed` 里的句子必须查；看 `asr`（回读文字）和 `note`。
2. 单句回读：`python $T/asr.py audio/lines/<id>.wav`（提示词只写领域，不写目标词）。
3. 多音字：whisper 对“长 cháng / zhǎng”这类两种读音都写原字，回读查不出；台词本里标了读音的字，交给用户听。
4. 判不了（证据矛盾、声音特殊）→ 列给用户人耳确认，听过没问题写进 `storyboard.tts.ear_confirmed`。

## 3. 音频其余项

- 响度 / 真峰值：`ffmpeg -i 成片 -af ebur128=peak=true -f null -`（−16 ± 1.5 LUFS，真峰值 ≤ −1 dBTP）。
- 语速：旁白约每秒 4.5 字，不要快。
- 音效：看 `render/sfx_events.json` 的时刻与分轨 `render/stem_sfx.wav` 的波形，确认音效对准画面动作；听感交用户。
- 配乐压人声、句间杂音（“嗒”“呲”）：看语谱，判不了交用户。

## 4. 两轮审核

- 第一轮：独立审核员出问题表（必改 / 建议）→ 作者逐条修 → 重渲。
- 第二轮：**另起一个新的审核员**复审，只看改过的项 + 全片回归（不和第一轮同一个审核员，避免“自己改的自己验”）。
- 两轮都要写明证据（时刻、帧、测量值），不写“看起来没问题”。
