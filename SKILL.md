---
name: fanwork-director
description: >
  题材二创视频导演流水线（自带《黑神话：悟空》影神图 203 角色库，支持替换为同结构的其他题材库）：
  把用户的故事梗概 + 题材资料库（角色卡片/图鉴）
  加工为成片——①按角色背景润色剧本 ②专业分镜拆解（镜头时长、衔接锚点）③角色参考图+分镜写 edit prompt
  生成视频关键帧参考图 ④按 MiniMax H3 官方 prompt-writing 规范逐镜头写视频提示词 ⑤调 H3 API 生成各镜头视频
  ⑥末帧接力保证故事连贯 ⑦ffmpeg 拼接成片。
  每当用户要基于游戏/影视/小说等既有题材做二创短片、改编视频、分镜脚本、"把这段故事做成视频"、
  提到影神图/角色图鉴+视频生成、或提到 H3/hailuo 视频工作流时，使用本技能。英文场景同理
  (fan-work / derivative video / storyboard pipeline / H3 video generation)。
---

# 题材二创导演流水线

六阶段、三道人工闸口。核心原则：**便宜的产物先审、贵的产物后生成**（文本→参考图→视频），
任何单镜头可独立重做而不推翻全片。

**项目结构**（自包含，可整体分发）：
```
fanwork-director/
├── SKILL.md
├── data/black-myth-wukong/   # 内置题材库：203 卡片+角色图+catalog.json
├── references/               # 分镜规范/连贯手册/edit prompt 指南/H3 官方 prompt 指南×2
├── scripts/                  # h3api.py / image_api.py / assemble.py
└── assets/                   # storyboard.template.json
```
产出目录 `works/<slug>/` 建在当前工作项目下，不写入技能目录。

## 0. 启动检查

1. **资料库**：本技能自带《黑神话：悟空》影神图库（203 角色，含图）：
   `<skill_base>/data/black-myth-wukong/`（catalog.json + cards/ + images/）。
   其他题材的库若同结构（catalog.json 含 Category/Chapter/Name/CardFile/ImageFile 字段）
   可直接替换 data/ 下内容；用户另给路径的库优先用用户的；无结构素材先问用户
   角色资料在哪，或降级为通用知识并明示。
2. **依赖**：Phase 5/6 需要 ffmpeg/ffprobe（`brew install ffmpeg`）。缺失时仍可跑
   Phase 1–4，末帧接力会退化为"每镜定制首帧"模式——提前告知用户这个质量差异。
3. **API 可用性**：
   - `MINIMAX_API_KEY` 环境变量 → H3 视频与图像 API 的默认后端。
   - 图像编辑后端可用 `FANWORK_IMAGE_PROVIDER` 覆盖（当前支持 `minimax`；未配置则为 `none` 占位）。
   - 无 key 时**照常跑 Phase 1–2**，Phase 3–5 全部用 `--dry-run` 产出待执行清单，不假装生成成功。
4. **工程目录**：`works/<slug>/` 下固定布局：
   ```
   works/<slug>/
   ├── story.md          # Phase1 剧本
   ├── cast.md           # Phase1 角色锁定表（外观/性格/动机/语言风格）
   ├── storyboard.json   # Phase2 分镜表
   ├── refs/shot_XX_first.png / shot_XX_last.png   # Phase3 关键帧
   ├── prompts/shot_XX.md # Phase4 H3 提示词全文
   ├── clips/shot_XX.mp4 # Phase5 成片镜头
   ├── ledger.md         # 衔接账本（场景状态/道具/光线/角色漂移记录）
   └── final.mp4         # Phase6
   ```
5. 向用户确认：片名 slug、目标总时长、画幅（默认 16:9）、风格基调。

## Phase 1 剧本润色 → 闸口1

- 读涉及角色的卡片（cards/）**并用视觉读角色图（images/）**产出 `cast.md`。
  注意：卡片可能只是导读 stub 不含细节，角色图可能是带文字的游戏 UI 截图——
  外观锁定串要从图里的角色形象（线描/立绘）+ 原作知识提取，性格/诗签可从 UI 截图内
  的故事文案提取。cast.md 每个角色给**中文锁定串（edit prompt 用）+ English lock
  （H3 prompt 用，官方指南要求正文英文）**双份，逐字复用于所有镜头——这是跨镜头一致性的锚。
- 把用户梗概扩成三幕微结构（起-压-转/合），台词精炼并贴合原作语感；标注每个情节点对应哪个场景。
- 尊重原作设定不 OOC；改动处向用户明示。
- **闸口1**：把 story.md + cast.md 呈现给用户，确认后才进 Phase 2。

## Phase 2 分镜拆解

按 `references/storyboard-spec.md` 的 schema 填 `storyboard.json`：

- 每 shot 时长 4–15s（H3 硬约束），按动作节拍/台词长度估时；全片总时长=各 shot 之和。
- 每 shot 写明：景别、运镜、画面内容、台词、音效/音乐线索、**衔接锚点**（承接上一镜的什么视觉/动作状态）。
- 场景划分：同场景内镜头保持空间连续（轴线、光源方向、角色站位）。
- 节奏自检：开场 shot 宜 Establishing；对话正反打不超过 3 连；高潮段缩短单镜时长。
- 分镜表随闸口2一起送审（若用户赶时间可并闸）。

## Phase 3 关键帧参考图 → 闸口2

按 `references/image-edit-prompts.md` 为每个需要首帧的 shot 写 edit prompt：

- 每个场景的**首镜**：用角色参考图（images/）+ 分镜描述生成首帧关键图：
  `python3 scripts/image_api.py --prompt-file refs/shot_XX.prompt.txt --ref images/<角色图> --out refs/shot_XX_first.png`
- 后续镜头**不生成新首帧**——Phase 5 用上一镜末帧接力（见 continuity-playbook）。
- 只有当上一镜末帧构图与下一镜要求差距过大时，才为该镜额外生成定制首帧（并在 ledger.md 记录断点）。
- **闸口2**：storyboard.json + 全部关键帧图呈现给用户。参考图是最便宜的纠偏机会，务必在这里改够。

## Phase 4 H3 提示词

按 `references/continuity-playbook.md` 的模式决策表，为每 shot 选 I2VA / FL2VA / Ref2VA：

- 底图/底文本就绪后，**严格遵循官方指南**写提示词：base/keyframe 模式读
  `references/h3-base-guide.txt`；Ref2VA 模式读 `references/h3-ref-guide.txt`。
  （两份是 vendored 快照，发现与官方新行为不符时更新：
  `curl -sL https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/references/base-en.txt -o <skill>/references/h3-base-guide.txt`，ref-en.txt 同理。）
- 字段名、段落顺序、`<Picture N>` 标签、时间标注必须与指南一致；描述总时长严格等于 shot 规划时长。
- 说话人 ID（S1/S2）**只在单条 prompt 内部**保持连续；每个 shot 是独立 API 调用，
  跨 shot 不复用编号（本镜第一个开口者即 S1，无论他在别的镜头是几号）。
- API 参数规则（官方文档已实锤）：resolution ∈ 480P/768P/2K（默认不传即 768P 短边）；
  图生视频不传 ratio（由输入图自动判定），纯文本模式 ratio 必传且不能 adaptive；
  model ∈ MiniMax-H3 / MiniMax-H3-Max（Max 不支持 Ref2VA）。唯一待实测项：本地图片
  base64 直传是否被接受，被拒则走 /v1/files/upload 换链接。
- 台词保留中文原文；每段 prompt 存入 `prompts/shot_XX.md`，格式固定为：
  头部 `# shot_XX · 模式 · Ns` + `API 参数：...` 行 + 空行 + `---` 分隔行 + 提示词正文。
  调 API 时只取 `---` 之后的正文（`awk 'f{print} /^---$/{f=1}'`），duration 从 storyboard.json 读取。

## Phase 5 逐镜头生成（末帧接力）

按**场景为单位**的顺序执行（场景间可并行，场景内必须串行）：

1. 逐镜调用（脚本路径以本技能 base directory 为准，下同）：
   `python3 <skill>/scripts/h3api.py shot --storyboard works/<slug>/storyboard.json --shot 01`
   （自动解析 duration/mode/PREV_LAST/prompt 正文；`--dry-run` 输出完整请求 JSON 供人工核对）。
2. 下载至 `clips/shot_XX.mp4`，`assemble.py qc` 核对时长。
3. `python3 <skill>/scripts/assemble.py lastframe clips/shot_01.mp4 refs/shot_02_first.png`
   → 作为下一镜 first_frame（PREV_LAST 约定路径即此文件）。
4. 角色漂移或衔接失败：按 continuity-playbook 的纠偏流程处理（重生成→换末帧帧位→改 Ref2VA）。
5. 更新 ledger.md。

## Phase 6 组装 → 闸口3

- `python3 scripts/assemble.py concat storyboard.json final.mp4`（concat demuxer，统一帧率）。
- 快审清单：逐镜时长符合规划、末帧-首帧无跳变、角色外观无漂移、台词字幕时机。
- **闸口3**：把 final.mp4 + 分镜对照表交给用户；返工只重做指定 shot 再重新拼接。

## 成本与失败规则

- 一次只重生成**单个**失败 shot；连续两次失败则改该镜的 prompt/模式，而不是硬砸。
- 全部产物落盘、命令可复放；不删除旧版本（shot_XX.v2.mp4）。
- 任何 dry-run 产物标注"未实际生成"，绝不向用户谎报 API 已执行。
