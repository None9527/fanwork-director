# storyboard.json 规范

顶层结构：

```json
{
  "title": "片名",
  "slug": "work-dir-name",
  "source_library": "/abs/path/to/library",
  "aspect_ratio": "16:9",
  "total_duration_s": 32,
  "cast": ["黑熊精", "金池长老"],
  "scenes": [
    {
      "id": "S1",
      "name": "观音禅院·夜",
      "location_desc": "起火后的禅院后院，月光+余烬红光",
      "shots": ["01", "02", "03"]
    }
  ],
  "shots": [ <shot对象>, ... ]
}
```

## shot 对象字段

| 字段 | 类型 | 说明 |
|---|---|---|
| id | "01"… | 两位数序号，全片唯一 |
| scene | "S1" | 所属场景 |
| duration_s | 4–15 整数 | H3 硬约束；估算方法见下 |
| mode | I2VA / FL2VA / Ref2VA | 由 continuity-playbook 决策表得出，Phase 4 终定 |
| shot_size | 远/全/中/近/特 | 景别 |
| camera | string | 运镜：固定/推/拉/摇/移/跟/环绕 |
| frame | string | 画面内容：主体+动作+环境，一段可执行描述 |
| dialogue | [{who, line}] | 台词（中文原文保留）；H3 支持 11 语对白 |
| sound | string | 音效/环境声/音乐线索 |
| anchor_in | string | 承接上一镜的状态：角色位置/动作相位/光源/道具 |
| anchor_out | string | 预留给下一镜的衔接点 |
| first_frame | path 或 "PREV_LAST" | PREV_LAST = 上一镜末帧接力 |
| last_frame | path / null / "AUTO_EXTRACT" | FL2VA 时用 |
| char_refs | [images/ 相对路径] | 角色一致性参考图（Ref2VA 用，≤9 张） |
| prompt_file | prompts/shot_XX.md | Phase 4 产出 |
| clip_file | clips/shot_XX.mp4 | Phase 5 产出 |
| status | draft/keyframed/prompted/generated/accepted | 流水线状态机 |

## 时长估算规则

- 纯动作镜头：一个完整动作节拍 4–6s；移动/打斗 6–10s；环境建立镜头 6–8s。
- 台词镜头：中文约每秒 4 字 + 表演停顿 1–2s。例：20 字台词 ≈ 5+2 = 7s。
- 无台词但有复杂调度：宁长勿短，8–12s。
- 全片节奏：开场建立镜头可 8–10s；冲突段单镜缩到 4–6s 制造急促；结尾定格留 5–7s。
- 若总时长超 15s 需求 → 必然是多镜头拼接，这正是本流水线的存在意义；
  不要为塞进单镜而压缩叙事。

## anchor 写法示例

```
anchor_in: "黑熊精位于画面左1/3，面朝右，湿黑毛发带水光；背景余烬红光在角色右后方"
anchor_out: "黑熊精前爪抬起欲抓，画面将切至其爪部特写"
```

anchor 是给"下一镜的 frame/prompt"用的约束，不是给观众看的。同一场景内光源方向、
角色画面左右关系（轴线）不得翻转，除非剧情需要并在 ledger.md 注明越轴处理。
