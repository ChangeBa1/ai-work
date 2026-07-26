"""zh-CN resource registry + locale-aware display values
(report-contract.md "Locale configuration", "Resource registry contract").

Jinja templates only consume `display()`/`localize_error()` output — no
enum/error translation branches live in the template itself. An
unregistered locale fails immediately (`UnknownLocaleError`), never a
silent fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from vnc_agent.config import KNOWN_LOCALES


class UnknownLocaleError(ValueError):
    """A locale outside `config.KNOWN_LOCALES` was requested."""


@dataclass(frozen=True)
class DisplayValue:
    machine_value: str
    display_value: str
    css_class: str
    data_marker: str


_ZH_CN: dict[str, str] = {
    # Page-level labels
    "report.title": "测试运行报告",
    "report.case": "测试用例",
    "report.run_id": "运行编号",
    "report.status": "状态",
    "report.started_at": "开始时间",
    "report.ended_at": "结束时间",
    "report.step": "步骤",
    "report.iteration": "迭代",
    "report.evidence": "证据",
    "report.evidence_before": "操作前证据",
    "report.evidence_after": "操作后证据",
    "report.precondition": "前置条件",
    "report.human_confirmed_facts": "人工确认事实",
    "report.action_audit": "动作审计",
    "report.declared_tag_counts": "声明标签计数",
    "report.performance_summary": "性能摘要",
    "report.stage_measurements": "阶段测量",
    "report.frames": "逻辑帧轨迹",
    "report.recovery": "恢复",
    "report.recovery_attempts": "恢复尝试",
    "report.failure_reason": "失败原因",
    "report.action_effect": "动作效果",
    "report.verification_result": "验证结果",
    "report.grounding_candidates": "定位候选",
    "report.executable_action": "可执行动作",
    "report.semantic_action": "语义动作",
    "report.wait_result": "等待结果",
    "report.coordinate_space_audit": "坐标空间审计",
    "report.canonical_action_identity": "规范动作身份",
    "report.none": "无",
    "report.unavailable": "不可用",
    "report.evidence_error": "证据异常",
    "report.unknown_error": "未知错误",
    "report.model_call_audits": "模型调用审计",

    # TestRun / step status
    "status.passed": "通过",
    "status.failed": "失败",
    "status.cancelled": "已取消",
    "status.running": "运行中",
    "status.created": "已创建",
    "status.pending": "待处理",

    # Precondition
    "precondition.not_required": "无需前置条件",
    "precondition.passed": "前置条件通过",
    "precondition.failed": "前置条件失败",

    # Verification status
    "verification.passed": "通过",
    "verification.failed": "失败",
    "verification.uncertain": "不确定",

    # Verification label
    "verification_label.weak_assertion_warning": "弱断言警告",
    "verification_label.effect_only_pass": "仅动作效果通过",
    "verification_label.trusted_pass": "可信通过",

    # ActionEffect status
    "action_effect.no_effect": "无效果",
    "action_effect.expected_effect": "符合预期效果",
    "action_effect.unexpected_effect": "非预期效果",
    "action_effect.effect_uncertain": "效果不确定",

    # Wait end reason
    "wait.stable": "画面已稳定",
    "wait.expected_condition": "满足预期条件",
    "wait.timeout": "等待超时",
    "wait.vnc_error": "VNC 连接异常",
    "wait.cancelled": "已取消",

    # Stage measurement status
    "stage_status.completed": "已完成",
    "stage_status.failed": "失败",
    "stage_status.cancelled": "已取消",
    "stage_status.unavailable": "不可用",

    # Stage names
    "stage_name.capture": "截图采集",
    "stage_name.pixel_hash": "像素哈希",
    "stage_name.persistence": "持久化",
    "stage_name.OCR": "文字识别",
    "stage_name.template": "模板匹配",
    "stage_name.vision": "视觉理解",
    "stage_name.planner": "规划",
    "stage_name.grounder": "定位",
    "stage_name.verification": "验证",
    "stage_name.report_build": "报告构建",
    "stage_name.report_output": "报告输出",

    # Condition types
    "condition.text_appears": "文本出现",
    "condition.text_disappears": "文本消失",
    "condition.template_appears": "模板出现",
    "condition.template_disappears": "模板消失",
    "condition.region_changed": "区域变化",
    "condition.screen_changed": "画面变化",
    "condition.visual_question": "视觉提问",

    # Evidence errors
    "evidence_error.missing": "证据文件缺失",
    "evidence_error.out_of_bounds": "证据路径越界",
    "evidence_error.truncated": "证据文件被截断",
    "evidence_error.corrupted": "证据文件已损坏",
    "evidence_error.byte_size_mismatch": "证据文件大小不匹配",
    "evidence_error.hash_mismatch": "证据文件哈希不匹配",
    "evidence_error.undecodable": "证据文件无法解码",
    "evidence_error.mask_mismatch": "证据遮罩身份不匹配",
    "evidence_error.wrong_purpose": "证据用途不是安全证据",
    "evidence_error.private": "证据为私有图片，禁止展示",
    "evidence_error.orphan_bundle": "证据所在制品包未被引用",
    "evidence_error.not_found": "未找到对应逻辑帧",

    # Model roles
    "model_role.vision": "视觉模型",
    "model_role.planner": "规划模型",
    "model_role.grounder": "定位模型",
    "model_role.verification": "验证模型",

    # Performance summary fields
    "performance.total_capture_count": "总采集次数",
    "performance.unique_frame_count": "唯一帧数",
    "performance.duplicate_frame_count": "重复帧数",
    "performance.dedup_ratio": "去重比例",
    "performance.physical_image_count": "物理图片数",
    "performance.avoided_write_count": "避免写入次数",
    "performance.avoided_write_bytes": "避免写入字节数",
    "performance.cache_hits": "缓存命中",
    "performance.analysis_invocations": "分析调用次数",
    "performance.model_calls": "模型调用次数",
    "performance.actual_model_call_count": "实际模型调用次数",
    "performance.memory_hit_count": "记忆命中次数",
    "performance.replay_locate_methods": "回放定位方式统计",
    "performance.replay_patch_count": "回放候选补丁数",
    "performance.skipped_model_call_count": "跳过模型调用次数",
    "performance.completeness": "数据完整性",
    "performance.consistency_errors": "一致性错误",

    "completeness.complete": "完整",
    "completeness.partial": "部分",
}

_REGISTRY: dict[str, dict[str, str]] = {"zh-CN": _ZH_CN}

assert set(_REGISTRY) == set(KNOWN_LOCALES), (
    "localization bundle registry must match config.KNOWN_LOCALES"
)

_KNOWN_ERROR_CODES: dict[str, str] = {
    "decode_error": "截图解码失败",
    "mask_encode_error": "遮罩编码失败",
    "persistence_error": "证据持久化失败",
    "logical_commit_error": "逻辑记录提交失败",
    "vnc_connect_failed": "VNC 连接失败",
    "vnc_disconnected": "VNC 连接中断",
    "black_screen": "黑屏",
    "page_not_stable": "画面未稳定",
    "target_not_found": "未找到目标元素",
    "grounding_low_confidence": "定位置信度过低",
    "action_no_effect": "操作无效果",
    "focus_error": "焦点错误",
    "input_method_error": "输入法错误",
    "unexpected_dialog": "出现意外对话框",
    "verification_failed": "验证失败",
    "timeout": "超时",
}


def registered_locales() -> frozenset[str]:
    return frozenset(_REGISTRY)


def _bundle(locale: str) -> dict[str, str]:
    if locale not in _REGISTRY:
        raise UnknownLocaleError(f"unregistered locale {locale!r}; known: {sorted(_REGISTRY)}")
    return _REGISTRY[locale]


def resource_text(locale: str, key: str) -> str:
    bundle = _bundle(locale)
    if key not in bundle:
        raise KeyError(f"resource key {key!r} missing from locale {locale!r} bundle")
    return bundle[key]


def display(locale: str, category: str, machine_value: str) -> DisplayValue:
    text = resource_text(locale, f"{category}.{machine_value}")
    return DisplayValue(
        machine_value=machine_value,
        display_value=text,
        css_class=f"{category}-{machine_value}".replace("_", "-"),
        data_marker=machine_value,
    )


def localize_error(locale: str, code: str | None, detail: str | None) -> str:
    """已知 code：显示中文说明并保留原始 code/detail；未知 code：通用中文说明，
    同样完整保留原始 code/detail，不猜测含义（report-contract.md "Error
    localization")."""
    _bundle(locale)  # raises UnknownLocaleError early
    message = _KNOWN_ERROR_CODES.get(code or "", resource_text(locale, "report.unknown_error"))
    bits = [f"code={code if code else 'null'}"]
    if detail:
        bits.append(f"detail={detail}")
    return f"{message}（{', '.join(bits)}）"
