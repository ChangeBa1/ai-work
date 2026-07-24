"""Regression coverage for VNCToolDriver._sync_text (feature 006).

The fake client below is deliberately shaped like vncdotool's real VNCDoToolClient
surface: it implements and records keyPress(key) calls, and does NOT define type or
paste, so any accidental call to either reproduces the original AttributeError from
run 18ba967a-822c-4860-a90d-d8e849205a75.
"""

from __future__ import annotations

import pytest

from vnc_agent.drivers.vncdotool_driver import VNCToolDriver


class FakeKeyPressClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def keyPress(self, key: str) -> None:
        self.calls.append(key)


def _build_driver_with_fake_client() -> tuple[VNCToolDriver, FakeKeyPressClient]:
    driver = VNCToolDriver("test-host")
    fake_client = FakeKeyPressClient()
    driver._client = fake_client
    driver._connected = True
    return driver, fake_client


def test_types_pure_digit_string_sends_ordered_keypresses() -> None:
    driver, fake_client = _build_driver_with_fake_client()

    driver._sync_text("45127366")

    assert fake_client.calls == ["4", "5", "1", "2", "7", "3", "6", "6"]


def test_types_mixed_ascii_letters_digits_punctuation_in_order() -> None:
    driver, fake_client = _build_driver_with_fake_client()

    driver._sync_text("Ab12-_.@")

    assert fake_client.calls == ["A", "b", "1", "2", "-", "_", ".", "@"]


def test_newline_maps_to_enter_keypress() -> None:
    driver, fake_client = _build_driver_with_fake_client()

    driver._sync_text("a\nb")

    assert fake_client.calls == ["a", "enter", "b"]


def test_tab_maps_to_tab_keypress() -> None:
    driver, fake_client = _build_driver_with_fake_client()

    driver._sync_text("a\tb")

    assert fake_client.calls == ["a", "tab", "b"]


def test_consecutive_and_trailing_newline_tab_trigger_each_occurrence() -> None:
    driver, fake_client = _build_driver_with_fake_client()

    driver._sync_text("\n\n\t\t")

    assert fake_client.calls == ["enter", "enter", "tab", "tab"]


def test_empty_string_sends_no_keypress_calls() -> None:
    driver, fake_client = _build_driver_with_fake_client()

    driver._sync_text("")

    assert fake_client.calls == []


class FailAfterNKeyPressClient(FakeKeyPressClient):
    def __init__(self, fail_at_call_number: int) -> None:
        super().__init__()
        self._fail_at_call_number = fail_at_call_number

    def keyPress(self, key: str) -> None:
        if len(self.calls) + 1 == self._fail_at_call_number:
            raise RuntimeError("simulated driver failure")
        super().keyPress(key)


def test_mid_send_exception_stops_immediately_and_propagates() -> None:
    driver = VNCToolDriver("test-host")
    fake_client = FailAfterNKeyPressClient(fail_at_call_number=3)
    driver._client = fake_client
    driver._connected = True

    with pytest.raises(RuntimeError, match="simulated driver failure"):
        driver._sync_text("abcdef")

    assert fake_client.calls == ["a", "b"]


def test_generic_text_input_in_unrelated_synthetic_context() -> None:
    """Second, unrelated scenario for FR-016/SC-006 (Clarification Session 2026-07-24, Q2):
    an unrelated generic value, on a freshly constructed driver/fake-client pair, exercised
    through the identical unmodified _sync_text code path used by the barcode-accident tests
    above — no branching on which text/context is passed."""
    driver, fake_client = _build_driver_with_fake_client()

    driver._sync_text("user.name-01@test")

    assert fake_client.calls == list("user.name-01@test")
