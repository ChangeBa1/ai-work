# Contract: 声明式测试用例 Schema

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

对应 spec 用户故事一（FR-001~004）。测试用例以 YAML 编写，加载时按下列 JSON Schema 校验；
校验失败 MUST 在运行开始前拒绝（退出码 `2`，见 `cli-contract.md`）。

## JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "TestCase",
  "type": "object",
  "required": ["id", "name", "target_id", "mode", "steps"],
  "properties": {
    "id": { "type": "string", "minLength": 1 },
    "name": { "type": "string", "minLength": 1 },
    "target_id": { "type": "string", "minLength": 1 },
    "mode": { "type": "string", "enum": ["explicit"] },
    "timeout_seconds": { "type": "integer", "minimum": 1, "default": 600 },
    "steps": {
      "type": "array",
      "minItems": 1,
      "items": { "$ref": "#/$defs/TestStep" }
    }
  },
  "$defs": {
    "TestStep": {
      "type": "object",
      "required": ["id", "name", "intent", "expected"],
      "properties": {
        "id": { "type": "string", "minLength": 1 },
        "name": { "type": "string", "minLength": 1 },
        "intent": { "type": "string", "minLength": 1 },
        "timeout_seconds": { "type": "integer", "minimum": 1 },
        "max_retries": { "type": "integer", "minimum": 0 },
        "expected": { "$ref": "#/$defs/VerificationSpec" }
      }
    },
    "VerificationSpec": {
      "type": "object",
      "required": ["operator", "conditions"],
      "properties": {
        "operator": { "type": "string", "enum": ["all", "any"] },
        "timeout_seconds": { "type": "integer", "minimum": 1 },
        "conditions": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/VerificationCondition" }
        }
      }
    },
    "VerificationCondition": {
      "type": "object",
      "required": ["type"],
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "text_appears", "text_disappears",
            "template_appears", "template_disappears",
            "region_changed", "screen_changed", "visual_question"
          ]
        },
        "value": { "type": "string" },
        "region": {
          "type": "array",
          "items": { "type": "integer" },
          "minItems": 4,
          "maxItems": 4
        }
      }
    }
  }
}
```

## 示例

```yaml
id: app-login-001
name: 正确账号登录
mode: explicit
target_id: win10-test-01
timeout_seconds: 180

steps:
  - id: open-app
    name: 打开应用
    intent: 打开 ExampleApp
    expected:
      operator: all
      conditions:
        - type: text_appears
          value: "运行"

  - id: submit-login
    name: 提交登录
    intent: 点击登录按钮
    max_retries: 2
    expected:
      operator: all
      timeout_seconds: 30
      conditions:
        - type: text_appears
          value: "欢迎"
        - type: text_disappears
          value: "密码"
```

## 契约保证

- 敏感值（如密码）MUST 通过 `text_value_ref: secrets.xxx` 形式的引用传入，MUST NOT 出现
  在测试用例正文的明文字段中（FR-047 的用例侧对应要求）。
- 加载器 MUST 拒绝 `mode` 为 `explicit` 之外的取值（本切片不支持目标驱动型用例，FR-004）。
- 加载器对每个校验失败字段 MUST 输出 `字段路径 + 失败原因`，而不是单一笼统错误。
