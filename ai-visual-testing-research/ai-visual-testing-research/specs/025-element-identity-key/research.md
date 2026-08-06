# Research: 025-element-identity-key

**Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## R1. 元素检索主键形态

**Decision**: 使用结构化身份键  
`identity_key = "{schema_version}:g{G}|{normalized_visible_text}|{geom_cell}"`  
（例：`eid-v1:g16|小計|13,13`），在 `page_id` 作用域内检索；自然语言 `target_label`
仅作线索与审计。网格粒度 `G` MUST 编入键前缀，改 `G` 后旧键自动失配并可被 purge
识别。

**Rationale**: 实测 8 条 `element_memories` 的 `target_label` 混有短标签（`小計`、`金券`）
与长中文描述，且 Planner 措辞不稳定；精确字符串主键命中率趋近 0。澄清已锁定：文本
深度归一化 + 归一化网格几何 + 多候选不消歧。

**Alternatives considered**:

| 方案 | 否决原因 |
|------|----------|
| 继续 strip/lower 标签 | 已证实恒 0 命中 |
| 仅文本、几何只用于消歧 | 同文案多按钮无法区分（澄清倾向几何进键） |
| 嵌入向量语义匹配 | 新增模型/依赖，违反「无新模型调用」 |
| 容器相对坐标 | 黑盒无控件树 |

## R2. 几何网格参数

**Decision**: 默认 `identity_grid_size G = 16`（每轴 16 格）；中心  
`col = min(G-1, floor(cx / w * G))`，`row = min(G-1, floor(cy / h * G))`，  
`geom_cell = f"{col},{row}"`。**`cx`/`cy` 的来源 MUST 是被选中的可见文本 OCR 项的
bbox 中心**（写入侧与查询侧同源）；MUST NOT 用 `target_region` 中心算 `geom_cell`。
绝对像素 `target_region` 仍可存于 `ElementMemory.bbox` 供模板邻域。R5 表中
「bbox … 中心 (867,627)」类样例指的就是 **OCR 文字框** bbox 中心。

**Rationale**: 实测 UI 分辨率 1024×768；`小計` OCR bbox 约 54×30 px，中心约
(867, 627) → 归一化 ≈ (0.847, 0.816) → 16 格下约 cell `(13,13)`。格宽约 64×48 px，
大于典型按钮抖动、小于同屏两按钮间距（避免易误并）。可配置，语义固定为「同单元
相等」。

**Alternatives considered**: G=8（过粗，同文案双按钮易并）；G=32（过细，轻微布局抖动
易未命中）；绝对像素 ±N（跨配置难讲、与澄清 B 不一致）。

## R3. 可见文本抽取（线索 → 身份文本分量）

**Decision**:

**写入**（有 `target_region`）:

1. 取 `target_region` 中心**仅**作选 OCR 的参考点：在 `ocr_items` 中选中心距最近、且
   `normalize_visible_text(text)` 非空、非 `fingerprint.is_dynamic_token` 的项。
   **确定性 tie-break（MUST）**：中心距并列（欧氏距离平方相等）时，MUST 按
   `(normalize_visible_text(text), (x1,y1,x2,y2))` 的字典序取第一条；MUST NOT 依赖
   `ocr_items` 的输入顺序（Constitution 原则 I）。`target_region` 本身 MUST 另存为
   `ElementMemory.bbox` 供模板邻域校验。
2. 若选不出符合条件的 OCR 项 → 返回 `None`（身份不可建立），service MUST 跳过可检索
   写入（**无**「纯几何 / 空文本可检索身份」）。
3. 若选出 OCR 项：文本分量 = 其归一化文本；**`geom_cell` MUST 由该 OCR 项的 bbox
   中心**计算，MUST NOT 由 `target_region` 中心计算。写入侧与查询侧计算 `geom_cell`
   的锚点定义 MUST 同源（均为被选中 OCR 的 bbox 中心）。
4. 不把完整 Planner 长描述直接当可见文本，除非其归一化结果与某一 OCR 归一化结果
   **精确相等**。

**查询**（仅有 `target_label` + 当前 OCR）:

1. `L = normalize_visible_text(target_label)`；若 `L` 为空 → insufficient / 未命中。
2. 收集所有 `normalize_visible_text(ocr.text) == L` 的 OCR 项 → 各以其 **OCR bbox
   中心**算 `geom_cell` → 候选 identity 集合；
3. 若步骤 2 为空且 `L` 较长：收集「归一化 OCR 文本为 `L` 的**完整 token 子集**且在
   归一化后的 label 中作为**整词边界匹配**」的 OCR（实现：对每个 OCR 归一化串 `t`，
   若 `t` 非空且 (`t == L` 或 `L` 以非字母数字日文脚本边界包含 `t` 的唯一最长匹配)）—
   **仅当唯一一条 OCR 胜出**时采用；多条 → ambiguous / 未命中；
4. **禁止**用编辑距离或业务同义词表；**禁止**在无 OCR 命中时猜测几何或写入空文本键。

**Rationale**: 澄清禁止子串作为**身份相等**；但 Planner 长描述必须能**抽取**到短可见
标签。整词/唯一最长 OCR 命中是可测、领域无关的折中。

**Alternatives considered**: 只用精确全串相等（长描述永远 0 命中）；任意子串（`小計`
误伤 `小計解除`）。

## R4. 日文 UI 文本归一化规则表

**Decision**: 纯函数 `normalize_visible_text(s: str) -> str`，步骤固定、无随机、无 I/O。
**无第三方库**（stdlib `unicodedata` + 显式半角片假名表）。

### 处理流水线（顺序固定）

| 步骤 | 操作 | 覆盖 |
|------|------|------|
| 0 | `None`/非 str → `""` | 空安全 |
| 1 | Unicode **NFKC**（`unicodedata.normalize("NFKC", s)`） | 全角英数→半角；半角片假名→全角片假名；兼容汉字；组合字符预合成 |
| 2 | 将半角浊点/半浊点若仍残留：与前一假名合并（NFKC 后通常已完成；单测锁定） | ﾞ ﾟ |
| 3 | **长音符号统一**：`ｰ` U+FF70、`─` 等在 NFKC 后与 `ー` U+30FC 对齐的，统一为 `ー`；ASCII 连字符 `-` **不**改为长音（避免破坏 `pre-paid` 等含 ASCII `-` 的标签） | 長音 |
| 4 | **大小写折叠**：`casefold()`（覆盖 ASCII/全角英文字母经 NFKC 后的形态） | 大小写 |
| 5 | **空白折叠**：`strip` + 任意 Unicode 空白连续 → 单空格 ` ` | 空白 |
| 6 | **清浊音**：不额外做「清音≡浊音」合并（会误并不同按钮）；仅接受 NFKC 预合成的标准清/浊字面值 | 濁点 |
| 7 | 输出精确字符串；比较用 `==` | — |

### 明确不做

| 不做 | 原因 |
|------|------|
| 清音↔浊音合并（は≡ば） | 不同控件误并 |
| 平假名≡片假名互转 | UI 标签语义可能不同；过度折叠 |
| 汉字异体字字典 | 业务/语言资源膨胀，VI 风险 |
| 同义改写 / 翻译 | 违反澄清与 VI |
| 子串/编辑距离相等 | 澄清 C 否定模糊相等 |

### 规则表示例（单测金样）

| 输入 | 期望输出 | 说明 |
|------|----------|------|
| `小計` | `小計` | 基准 |
| `  小計  ` | `小計` | 空白 |
| `レジ袋` | `レジ袋` | 片假名 |
| `ﾚｼﾞ袋`（半角片假名） | `レジ袋` | NFKC 半角→全角片假名 |
| `ＡＢＣ`（全角） | `abc` | NFKC + casefold |
| `Abc` | `abc` | casefold |
| `カード` | `カード` | 长音 `ー` 保留 |
| `ｶｰﾄﾞ` | `カード` | 半角片假名+半角长音 → 全角 |
| `ガ` vs `カ` + 组合浊点 | 均稳定为 `ガ`（若输入合法） | 濁点预合成 |
| `預/現計` | `預/現計` | 保留 `/` |
| `小計解除` | `小計解除` | **≠** `小計` |
| `1金券` | `1金券` | **≠** `金券` |
| `×` | `×` | 纯符号：合法非空文本分量 |
| `／`（全角斜杠） | `/`（经 NFKC） | 纯符号；几何仍可区分同屏多钮 |
| `--` | `--` | 纯 ASCII 标点：合法非空文本分量 |
| `pre-paid` | `pre-paid` | ASCII `-` 保留，不改为 `ー` |
| `""` / `"   "` | `""` | 空 → 身份不可建立（非可检索键） |

## R5. 真实 OCR / 记忆库正反例验证

数据来源：`vnc_agent/data/vnc_agent.db` 存量与页面指纹中的 `ocr_tokens`（运行写入，
非手工编造）。

### 正例（应解析为可稳定身份文本 / 应能跨措辞对齐）

| # | 来源 | 原始串 | 归一化后 | 几何线索（**OCR** bbox 中心 → 预期 cell@G=16, 1024×768） |
|---|------|--------|----------|--------------------------------------------------------|
| P1 | `element_memories.target_label` | `小計` | `小計` | bbox `[840,612,894,642]` 中心 (867,627) → ≈ (13,13) |
| P2 | 同页 `ocr_tokens` 含 | `小計` | `小計` | 与 P1 文本分量一致 → 查询 label=`小計` 可对齐 |
| P3 | `element_memories` | `レジ袋` | `レジ袋` | bbox `[298,661,376,695]` 中心 (337,678) → ≈ (5,14) |
| P4 | `element_memories` | `預/現計` | `預/現計` | bbox `[822,681,911,709]` |
| P5 | `element_memories` | `金券` | `金券` | 与 token `1金券` **区分**（反例 N2） |
| P6 | 页面 token | `オープン` | `オープン` | 片假名+长音 |

**换措辞查询（逻辑正例）**：写入身份文本=`小計`、cell=(13,13)；查询
`target_label="屏幕右下角的小計按钮"` 时，若当前帧 OCR 唯一抽出 `小計` 且其中心
cell 同为 (13,13)（或仅唯一 `小計` OCR），则 identity 一致 → 允许进入模板校验。

### 反例（不得相等 / 不得直点）

| # | A | B | 原因 |
|---|---|---|------|
| N1 | `小計` | `小計解除` | 归一化后仍不同；禁止子串相等 |
| N2 | `金券` | `1金券`（ocr_tokens） | 完整串不同 |
| N3 | 长描述 A：`标题以 scanner 开头的窗口缩略图内部的浅色预览区域…` | 长描述 B：`标题为 'scanners..' 的窗口缩略图预览区域…` | 旧主键互不相等；新方案若 OCR 无稳定短标签且几何不同 cell → 不同身份或不可检索 |
| N4 | 同文案两按钮、两 cell | 查询无几何且 OCR 命中两条 `小計` | 候选 ≥2 → `identity_ambiguous`，未命中 |
| N5 | 仅身份命中、模板分 < 0.85 | — | 强制模板失败 → 不直点（非误命中） |

### 存量 8 行 `target_label` 一览（作废对象）

```
レジ袋
小計
4
金券
預/現計
確定
标题以 scanner 开头的窗口缩略图内部的浅色预览区域，位于标题文字下方约30像素处
标题为 'scanners..' 的窗口缩略图预览区域（包含密集黑色条码/文本列表）
```

结论：短标签可经新身份重建；两条中文长描述在无稳定 OCR 短标签时 MUST 身份不可
建立（跳过可检索写入 / 查询未命中）——符合「宁可不命中」，且避免空文本记录污染
SC-001 分母。

## R6. 存量与迁移

**Decision**: 元素表 8 行整表 DELETE + 模板文件隔离/删除；页面表 5 行保留；迁移前
JSONL/旁路表备份以支持回滚（plan §6）。

**Rationale**: 澄清 Q4；旧键无法可靠推导 `eid-v1`。

**Alternatives considered**: 惰性迁移、双写 — 已否决。

## R7. 模板门禁与误命中

**Decision**: 身份唯一后仍强制 `match_element_template`；误命中 = 直点后 verify
`failed|uncertain`；验收比 ≤10%。

**Rationale**: 澄清 Q5；对齐 Constitution III (c) 与 IV。

## R8. 主循环与 API

**Decision**: 保持 `lookup(screen, target_label)` / `record_success(...)` 签名；身份
解析封装在 `PageElementMemory` 内。`agent_runtime` 默认零控制流变更。

**Rationale**: 用户约束；降低回归面。

## R9. 复用边界

**Decision**:

| 模块 | 动作 |
|------|------|
| `memory/fingerprint.py` | **只读复用** `build_page_fingerprint` / `page_similarity` / `is_dynamic_token` |
| `memory/retrieval.py` | **只读复用** `find_best_page` / `match_element_template` / `expand_bbox` |
| `memory/identity.py` | **新建** 归一化与身份解析纯函数 |
| `memory/service.py` | **改** 写/查主键逻辑 |
| `storage/*` | **改** 列与查询 |

**MUST NOT**: 复制模板匹配实现、复制 pHash、在 runtime 内嵌归一化。

## R10. 依赖

**Decision**: 无新第三方包。

**Rationale**: NFKC 与映射表足够覆盖澄清要求的全半角/假名/长音；避免 pykakasi 等
引入语义转换与 VI 风险。

## R11. 验收度量门禁（与 Spec SC / plan §8 / tasks T034 一致）

**Decision**:

| SC | 规则 |
|----|------|
| SC-001 | 同 manifest：`hits>0` 且 `hit_rate≥0.30` |
| SC-002 | `SC002_MIN_HITS=20`；三态 inconclusive / pass / fail |
| SC-003 | `SC003_MIN_SAMPLES=20`；三态 inconclusive / pass / fail（p95≤50ms） |
| SC-004/005/006 | 开关 e2e、复用无分叉、双场景契约 |

**Rationale**: analyze 已消除 SC-003 样本量仅写在 tasks 的漂移；与 SC-002 对称。

**Alternatives considered**: 二态硬判（小样本不稳）— 否决。

---

## NEEDS CLARIFICATION

无（澄清会话 5 题已关闭；后续修订已锁定 OCR 锚点、键含 G、tie-break、SC 三态、
`identity_lookup_error` 计数）。
