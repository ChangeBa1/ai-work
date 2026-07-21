# Contract: 测试用例 Schema 增量（`verification_mode`）

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

对应 FR-007~012/FR-025~027。本契约是对 001
[`test-case-schema.md`](../../001-vnc-core-execution-loop/contracts/test-case-schema.md)
的增量修改，只描述新增/变化的部分；未提及的字段与规则保持 001 原样不变。

## JSON Schema 增量

在 001 `TestStep` 定义中新增一个可选属性：

```json
{
  "$defs": {
    "TestStep": {
      "properties": {
        "verification_mode": {
          "type": "string",
          "enum": ["business", "effect_only"],
          "description": "省略即默认按正式业务模式处理，但加载时不做业务断言强制校验（向后兼容）；显式声明 business 时加载器立即校验至少一个业务结果断言存在。"
        }
      }
    }
  }
}
```

## 加载时校验流程（`load_test_case`）

```text
for each step in steps:
  business_assertion_present = any(
      c.type not in {"screen_changed", "region_changed"}
      for c in step.expected.conditions
  )
  if step.verification_mode == "business" and not business_assertion_present:
      REJECT: "steps[{id}].expected.conditions: business 模式下必须至少包含一个业务结果
               断言（text_appears/text_disappears/template_appears/template_disappears/
               region_changed 与其它业务断言组合/结构化状态/visual_question 之一），
               当前仅含 screen_changed/region_changed（FR-008）"
  # verification_mode == "effect_only" 或省略（None）时不因此拒绝加载
```

## 示例

### 新建正式业务步骤（推荐写法，显式声明，加载时即获得校验反馈）

```yaml
- id: add-shopping-bag
  name: 加入购物袋商品
  intent: 点击"レジ袋"（购物袋）按钮，将一个购物袋商品加入购物车
  verification_mode: business
  max_retries: 2
  expected:
    operator: all
    conditions:
      - type: screen_changed
        value: ""
      - type: text_appears
        value: "1点"   # 业务结果断言：购物袋件数文字
```

### effect-only 步骤（显式声明，只关心画面是否响应）

```yaml
- id: probe-hover-feedback
  name: 探测按钮悬停反馈
  intent: 移动鼠标到"レジ袋"按钮上，确认按钮存在悬停视觉反馈
  verification_mode: effect_only
  expected:
    operator: all
    conditions:
      - type: screen_changed
        value: ""
```

### 旧用例（省略字段，继续可加载，运行时按弱断言处理）

```yaml
- id: add-shopping-bag
  name: 加入购物袋商品
  intent: 点击"レジ袋"（购物袋）按钮，将一个购物袋商品加入购物车
  max_retries: 2
  expected:
    operator: all
    conditions:
      - type: screen_changed
        value: ""
  # 未声明 verification_mode → 加载器接受；
  # 运行时该步骤的 StepVerificationResult 封顶为 uncertain，并附带弱断言警告（FR-026）
```

## 契约保证

- 加载器 MUST 对每个校验失败的步骤输出 `字段路径 + 失败原因`（沿用 001 既有错误格式），
  不得笼统报错。
- `verification_mode` 省略与显式设为 `"business"` 在**加载时**行为不同（前者宽松、后者
  严格），但在**运行时**对最终 StepVerificationResult 的封顶规则完全一致——只要缺少业务
  断言，无论是否显式声明 `business`，运行时都 MUST 产生弱断言警告并封顶为 `uncertain`
  （FR-026 不因 `verification_mode` 的显隐而豁免）。
- 本契约 MUST NOT 影响 001 中除 `TestStep.verification_mode` 之外的任何 Schema 字段或
  校验规则。
