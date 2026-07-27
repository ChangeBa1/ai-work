# Quickstart: OCR 漏读弱否定证据仲裁

```bash
cd vnc_agent
uv sync --extra dev
```

## 场景 1：弱否定被高置信视觉覆盖（US1，新行为）

```bash
uv run pytest tests/fixtures/test_business_resolver.py -k "weak_ocr_miss" -v
```

预期：`text_appears` 未命中（OCR 漏读形态，如 `10,000` vs `10.000`）+ `visual_question`
passed（confidence ≥ 0.8）+ `action_effect=expected_effect` → 最终 `passed`，reason 含
`weak_ocr_miss_overridden_by_visual`，`failed_conditions` 保留未命中条目。

## 场景 2：强否定/低置信/非预期效果维持 002 规则（US2/US3）

```bash
uv run pytest tests/fixtures/test_business_resolver.py -k "strong_negative or old_rule or deterministic_overrides" -v
uv run pytest tests/unit/test_verification_compound.py -v
```

## 场景 3：保底回归（scenario 11/12/13 + uncertain 传播）

```bash
uv run pytest tests/e2e/test_scenario_11_error_popup_not_passed.py \
             tests/e2e/test_scenario_12_legacy_weak_assertion.py \
             tests/e2e/test_scenario_13_pos_bag_regression.py \
             tests/e2e/test_uncertain_propagation.py -q
```

## 全量

```bash
uv run pytest tests/unit tests/fixtures -q   # 基线（改动前）：686 passed
uv run pytest tests/e2e -q
```

## 配置

`config/agent.yaml`:

```yaml
verification:
  visual_override_confidence_threshold: 0.8   # [0,1]；调高收紧仲裁，1.0 近似禁用
```

注意：运行时装配层（runtime/）在本 feature 冻结，yaml 自定义值的调用点接线为后续
一行级任务（plan.md Complexity Tracking）；默认部署（0.8）行为双端一致。
