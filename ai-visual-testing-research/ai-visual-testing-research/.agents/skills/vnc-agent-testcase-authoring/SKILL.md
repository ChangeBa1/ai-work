---
name: vnc-agent-testcase-authoring
description: >
  Author and revise vnc-agent YAML testcases under vnc_agent/testcases/ for POS and other
  VNC black-box GUI flows. Use whenever the user asks to write, fix, update, or review a
  vnc-agent testcase (.yaml), POS checkout/payment scenario, visual_question / text_appears
  assertions, intent wording, action_tags, or mixed payment (金券/現金) steps — even if they
  only say "写个 case" or "改断言" without naming this skill. Prefer this skill over ad-hoc
  YAML when lessons from pos-buy-bag-checkout and pos-buy-bag-mixed-kinken-cash apply.
---

# vnc-agent 测试用例编写规范

编写或修改 `vnc_agent/testcases/*.yaml` 时遵循本 skill。目标：让 Planner/Grounder/Verifier
在真实 POS 画面上稳定通过，避免已踩过的 OCR、断言覆盖、多动作步骤、输入方式等坑。

参考样例（成功路径）：

- `vnc_agent/testcases/pos-buy-bag-checkout.yaml`
- `vnc_agent/testcases/pos-buy-bag-mixed-kinken-cash.yaml`

写完后务必：

```bash
cd vnc_agent
uv run vnc-agent run testcases/<file>.yaml --dry-run --config config
```

---

## 1. 结构骨架

每个 case 保持与现网一致的字段：

| 字段 | 用途 |
|---|---|
| `id` / `name` / `mode: explicit` / `target_id` / `timeout_seconds` | 元数据 |
| `precondition.facts[]` | 开跑前事实（如购物车为空） |
| `action_tags[]` | 声明式动作审计（不写死业务到 core） |
| `steps[]` | 每步一个主目标动作 + 业务断言 |

步骤推荐字段：

```yaml
- id: stable-kebab-id
  name: 中文短名
  intent: >-
    明确、可执行的单一主动作（见第 3 节）
  max_retries: 2
  verification_mode: business
  expected:
    operator: all
    conditions: [...]
```

业务内容（商品名、金额、按钮文案）只写在 testcase YAML 里，不要暗示改 core。

---

## 2. 断言：确定性 OCR 会覆盖视觉结果

引擎规则（FR-010）：`operator: all` 时，若同时有 `text_appears` 与 `visual_question`，
**确定性条件失败会覆盖视觉 passed**（`deterministic_overrides_visual`）。

因此：

1. **不要**用 RapidOCR 经常读错的字做 `text_appears` 硬门槛。
2. 业务语义优先交给 **收紧的 `visual_question`**。
3. `text_appears` 只选 OCR **稳定出现**、且空机不会误中的串。

### 2.1 禁止或慎用的 needles

| 问题类型 | 坏例子 | 原因 | 更好做法 |
|---|---|---|---|
| 空机假阳性 | `"1"` `"5"` `"袋"` | 小键盘数字、レジ袋按钮本身就有 | 用入车后才有的 chrome + visual |
| 日文 UI / CN OCR | `"単価"` | RapidOCR 常读成 `单`/`单！`，丢「価」 | 用 `点数`、`内税` + visual 确认数量金额 |
| 千分位格式 | 只认 `"10,000"` | OCR 常出 `10.000` | 引擎已做金额 digit-key 归一；case 可写逗号形式，仍建议 visual 复述金额 |
| 找零写死算错 | 金券 4 却写找零 `9,997` | 10,000−应付才是找零 | 先定支付拆分，再算 預り/お釣り |

### 2.2 推荐组合（购物袋入车后）

```yaml
conditions:
  - type: text_appears
    value: "点数"    # 表头/明细 chrome，空机通常没有
  - type: text_appears
    value: "内税"    # 常以 内税10% 出现
  - type: visual_question
    value: >-
      …明确要求：レジ袋 1 点、数量 1 個、金额 5；
      仅当全部明确时 passed；0 個/无法确认则不要 passed。
```

### 2.3 visual_question 写法

- 写清 **看哪里**（左合計 / 右上金额框 / 入金对话框 / 明细表）。
- 写清 **passed 条件** 与 **不要 passed 的条件**（否定句很重要）。
- 金额、数量用数字写死，并与 intent 一致。
- 明确 **不要**看找零机模拟器、不要用小键盘高亮代替金额框。

### 2.4 现金入金对话框

```yaml
- type: text_appears
  value: "10,000"   # 引擎可匹配 OCR 的 10.000
- type: text_appears
  value: "9,999"    # 必须与「剩余应付」一致：お釣り = 預り − 剩余
- type: visual_question
  value: >-
    預り金 10,000、お釣り <正确找零>、確定可点；
    仅三项都成立才 passed。
```

先确认支付拆分，再写找零：

```text
合计 S − 金券 V = 剩余 R
自动入金 預り P（常为 10000）→ お釣り = P − R
```

---

## 3. 步骤切分：一步一个主动作

Planner **每轮通常只产出一个** `SemanticAction`。把「点 2 再点金券」写在同一步里会导致：

- 只完成半步就进入 verify → 失败；
- 或重试时重复错误动作。

**把复合流程拆开**，例如混合支付：

1. `enter-kinken-amount` — 只输入金额  
2. `apply-kinken` — 只点「金券」  
3. `start-cash-for-remainder` — 只点「預/現計」并等对话框  
4. `finalize-mixed-payment` — 只点对话框「確定」  

`finalize` 与 `start-cash` 不要合并：验证失败会停在当前步，**永远不会点確定**。

---

## 4. 金额输入：本 POS 用小键盘数字键（慎用 type_text / 禁用 Escape）

在 **本项目目标 POS** 支付画面输入金额时（live 证据）：

- **优先** click 画面数字小键盘上的目标数字键（如 `"4"`），并写清邻接：上 7 / 右 5 / 下 1 / 左近「クリア」。
- 成功判据看 **支付区青色大号金额显示框**（在 金券/電子マネー **下方**、小键盘 **上方**），不要看小键盘键帽本身、不要看合計 5。
- **`type_text` 在本 POS 上经常不产生 `amount_type` 命中**（焦点不可靠）；不要把 case 成败绑死在 type_text。
- **禁止 `press_key` Escape**：会弹出「現在の操作を行うには、一度、操作を確定またはキャンセルしてください」，挡住「金券」→ grounder `TARGET_NOT_FOUND`。
- 金额框已空时 **不要先点「クリア」**（无意义且易误点到 4/7 邻域）；planner 示例里的 Escape 清输入在此 POS 有害。
- 若已出现上述遮挡提示：先 click 粉色「戻る」，再重试业务步；可用 `pos-recover-idle.yaml` 清半截交易。

`action_tags` 示例（与小键盘策略一致）：

```yaml
- tag: amount_type
  matcher:
    action_type: click
    target_text_contains: "4"
```

---

## 5. intent 写法

好的 intent：

- **一个主目标**（点哪个控件 / type 什么）。
- **空间/邻接线索**（仅当必须 click 时）：相对位置、邻近文案。
- **明确禁止项**：不要点模拟器、不要点ビール券、不要点閉じる。
- **成功判据提示**（与 expected 对齐）：右上角应显示 4；对话框应出现 確定。

避免：

- 一步里串多个独立 UI 动作且无拆分；
- 只写业务愿望不写控件名；
- 与 expected 金额/数量矛盾。

---

## 6. precondition 与环境

- 购物车类流程：precondition 用 visual 确认合計 **0 個**。
- Live 重跑前保证 POS 不在半截支付对话框/非空购物车，否则 precondition 或第一步会假失败。
- `timeout_seconds`：含自动入金与多步支付时给足（如 300–360）。

---

## 7. action_tags

- 只声明 case 关心的审计标签；matcher 用稳定子串（`袋`、`小計`、`金券`、`預/現計`、`確定`）。
- tag 名业务可读即可；core 不解释业务含义。
- 拆步后核对 tag 是否仍覆盖关键 click/type（便于报告里的 `declared_tag_counts`）。

---

## 8. 从失败报告反推修改（排障清单）

读 `artifacts/runs/<run_id>/report.json` 或 HTML 时按序查：

1. **卡在哪一步**？后续步是否未执行？  
2. **`deterministic_overrides_visual`**？→ 哪个 `text_appears` failed，OCR 实际读成什么？  
3. **`action_effect=no_effect`**？→ 点错/没点上，改 intent 或改 type_text。  
4. **多动作半完成**？→ 拆步。  
5. **金额/找零不一致**？→ 按 S/V/R/P 重算断言。  
6. **Vision answer 非法**？→ 引擎应已把 `not_passed` 等归一；若仍崩，查 provider 归一与 prompt。  
7. **仅 visual passed、det failed**？→ 放宽或替换 det needles，保留 visual 业务语义。

对失败帧可本地 OCR 探针（在 `vnc_agent/`）：

```bash
uv run python -c "from vnc_agent.perception.ocr.engine import run_ocr; print([i.text for i in run_ocr(r'artifacts/runs/.../safe_evidence.png')])"
```

---

## 9. 自检清单（提交 case 前）

- [ ] dry-run exit 0  
- [ ] 每步一个主动作；支付确认与启动现金分离  
- [ ] 无裸 `"1"`/`"5"`/`"袋"` 作为唯一入车证据  
- [ ] 无依赖 `"単価"` 的硬断言  
- [ ] 金额输入用 type_text；visual 盯右上角金额框  
- [ ] 找零 = 預り − 剩余应付，与金券金额一致  
- [ ] visual_question 含「仅当…passed」与「若…不要 passed」  
- [ ] intent 与 expected 数字一致  
- [ ] precondition 覆盖脏环境（空车等）  
- [ ] action_tags 覆盖本 case 关键动作  

---

## 10. 最小模板（新 POS 支付 case）

```yaml
id: pos-<flow>-001
name: <中文名>
mode: explicit
target_id: win10-test-01
timeout_seconds: 360

precondition:
  facts:
    - key: cart_item_count
      spec:
        operator: all
        conditions:
          - type: visual_question
            value: >-
              画面左侧「合計」绿色数量是否为 0 個？
              仅明确为 0 時 passed。

action_tags:
  - tag: add_to_bag
    matcher: { action_type: click, target_text_contains: "袋" }
  # …按流程追加

steps:
  - id: add-item
    name: 加入商品
    intent: 点击「…」…
    max_retries: 2
    verification_mode: business
    expected:
      operator: all
      conditions:
        - type: text_appears
          value: "点数"
        - type: text_appears
          value: "内税"
        - type: visual_question
          value: >-
            …数量与金额…仅当明确成立时 passed…

  - id: calc-subtotal
    name: 小计
    intent: 点击「小計」…
    max_retries: 2
    verification_mode: business
    expected:
      operator: all
      conditions:
        - type: text_appears
          value: "不足"

  # 金额：单独一步 type_text
  # 支付方式：单独一步 click
  # 现金启动 / 对话框确认：两步拆开
```

按第 9 节清单自检后再交给 live run。
