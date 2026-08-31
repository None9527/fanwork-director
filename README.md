# fanwork-director · 题材二创视频导演流水线

一个自包含的 Agent Skill 项目：**内置《黑神话：悟空》影神图 203 角色资料库** +
**六阶段视频二创流水线**（剧本润色 → 分镜拆解 → 关键帧生成 → H3 提示词 → 逐镜视频生成 → 拼接成片），
以 MiniMax H3 为视频后端，用"末帧接力 + 角色参考图锚定"的混合模式保证跨镜头故事连贯。

English: A self-contained agent skill that turns a rough story idea into a finished short video
against an IP reference library (Black Myth: Wukong bundled). Six phases, three human gates,
MiniMax H3 backend, mixed-mode continuity (last-frame handoff + character-reference anchoring).

## 目录结构

```
fanwork-director/
├── SKILL.md                        # 流水线编排：六阶段 + 三道人工闸口
├── data/black-myth-wukong/         # 内置题材库（406 文件）
│   ├── catalog.json                #   203 条目：Category/Chapter/Name/来源页/文件映射
│   ├── cards/                      #   203 张故事卡（Markdown，含导读与来源链接）
│   └── images/                     #   203 张角色图（游戏内影神图/游记页）
├── references/
│   ├── storyboard-spec.md          # 分镜表 schema + 镜头时长估算规则
│   ├── continuity-playbook.md      # 混合连贯模式：模式决策表/末帧接力/角色漂移三级纠偏
│   ├── image-edit-prompts.md       # 关键帧 edit prompt 四段结构
│   ├── h3-base-guide.txt           # MiniMax H3 官方 prompt 指南（T2VA/I2VA/FL2VA/L2VA）
│   └── h3-ref-guide.txt            # MiniMax H3 官方 prompt 指南（Ref2VA 六段式）
├── scripts/
│   ├── h3api.py                    # H3 视频 API 客户端（create/wait/run/shot，支持 --dry-run）
│   ├── image_api.py                # 图像编辑适配器（minimax 后端 / none 占位）
│   └── assemble.py                 # 末帧抽取 / 时长质检 / ffmpeg 拼接
└── assets/storyboard.template.json # 分镜表模板
```

## 安装

解压到以下任一目录（`<name>` 即技能发现名）：

```
~/.agents/skills/fanwork-director/          # 用户级，所有项目可用
<project>/.agents/skills/fanwork-director/  # 项目级
```

运行依赖：

```bash
brew install ffmpeg                 # Phase 5/6 末帧接力与拼接需要
export MINIMAX_API_KEY="***"      # platform.minimax.io（CN: platform.minimaxi.com）
```

无 key 时流水线仍可跑到 Phase 4，Phase 3/5 以 `--dry-run` 输出完整 API 请求清单，
产物如实标注"未实际生成"。

## 六阶段流水线

| 阶段 | 产物 | 说明 |
|---|---|---|
| 1 剧本润色 | `story.md` + `cast.md` | 读角色卡与图，提取外观中英双锁定串 |
| 2 分镜拆解 | `storyboard.json` | 每镜 4–15s（H3 约束），含衔接锚点与模式规划 |
| 3 关键帧生成 | `refs/shot_XX_first.png` | 角色参考图 + edit prompt → 图像 API |
| 4 H3 提示词 | `prompts/shot_XX.md` | 严格遵循官方指南结构（含 `<d>[语言]台词</d>`） |
| 5 逐镜生成 | `clips/shot_XX.mp4` | 场景内串行：上一镜末帧 → 下一镜首帧（接力） |
| 6 组装 | `final.mp4` | ffmpeg 统一重编码拼接 + 时长质检 |

**三道人工闸口**：① 剧本+角色表确认 → ② 分镜+关键帧确认（最便宜的纠偏点）→ ③ 成片确认。
核心原则：便宜的产物先审、贵的产物后生成；单镜可独立重做不推翻全片。

## 连贯性设计（本流水线的灵魂）

- **视觉连贯**：场景首镜用定制关键帧（I2VA），后续镜头用上一镜末帧接力（I2VA/FL2VA）。
- **角色连贯**：`cast.md` 外观锁定串逐字复用于每个镜头；漂移时三级纠偏
  （重roll → 换末帧帧位 → Ref2VA 挂角色参考图拉回）。
- **状态账本**：`ledger.md` 记录每镜的角色位置/光源/轴线，写下一镜提示词前必读。

## H3 API 速查（文档实测核对）

- 创建 `POST /v2/video_generation`：`content[]` 含 text + 图（role: first_frame / last_frame /
  reference_image）；duration 4–15s；resolution ∈ {480P, 768P, 2K}；
  图生视频不传 ratio（由输入图判定），纯文本必传。
- 查询 `GET /v2/query/video_generation/{task_id}`：status ∈ {Preparing, Queueing, Processing, Success, Fail}
- 下载 `GET /v1/files/retrieve_content?file_id=`
- 模型：`MiniMax-H3`（全模式）/ `MiniMax-H3-Max`（快速变体，不支持 Ref2VA）

## 使用示例

> 用黑神话影神图库里的黑熊精和金池长老，做个 30 秒短片。梗概：观音禅院的火烧完后，
> 黑熊精重返废墟寻找袈裟残片，撞见已化为白骨僧的金池长老。

技能被触发后按六阶段推进，在闸口处停下等你确认。

## 换题材

把 `data/black-myth-wukong/` 替换为同结构的资料库（`catalog.json` 含
Category/Chapter/Name/CardFile/ImageFile 字段 + `cards/` + `images/`）即可，
流水线逻辑零改动；也可在对话中直接指定外部库路径。

## 数据与版权

- 内置资料库整理自游民星空《黑神话：悟空》图鉴页面（203 条目，含来源 URL 可溯源）。
- 角色图像与文本权利归游戏科学及相关负责人所有；本库仅供个人学习、检索与非商业参考。
- 二创成片发布前请自行确认平台对 IP 衍生内容的政策。

## 未验证项（诚实清单）

- 本地图片 base64 直传是否被 API 接受（被拒则走 `/v1/files/upload`，脚本已留提示）
- 实际生成质量与角色一致性保持效果（需真实 key 跑最短镜头验证）
- `assemble.py` 需 ffmpeg 环境实测
