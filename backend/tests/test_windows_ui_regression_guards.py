"""Regression guards for the Windows shared-control rendering fix."""

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_styled_controls_define_explicit_size() -> None:
    combo = _read("frontend/qml/components/StyledComboBox.qml")
    text_field = _read("frontend/qml/components/StyledTextField.qml")

    assert "implicitHeight: 36" in combo
    assert "contentItem: Text {" in combo
    assert "implicitHeight: 36" in text_field


def test_affected_pages_use_styled_controls() -> None:
    checks = {
        "frontend/qml/pages/SettingsPage.qml": ("StyledComboBox {", "StyledSwitch {", "StyledSpinBox {"),
        "frontend/qml/pages/FileFunction.qml": ("StyledComboBox {", "StyledSwitch {", "StyledCheckBox {", "StyledTextField {"),
        "frontend/qml/pages/NetworkScan.qml": ("StyledTextField {",),
        "frontend/qml/components/SecurityCard.qml": ("StyledSwitch {",),
        "frontend/qml/pages/ScanCenter.qml": ("StyledCheckBox {",),
        "frontend/qml/pages/SystemSnapshot.qml": ("StyledSwitch {",),
    }

    for relative_path, expected_tokens in checks.items():
        content = _read(relative_path)
        for token in expected_tokens:
            assert token in content, f"Missing {token!r} in {relative_path}"


def test_targeted_pages_do_not_fall_back_to_raw_controls() -> None:
    raw_control_patterns = {
        "frontend/qml/pages/SettingsPage.qml": (
            r"(?<![A-Za-z])ComboBox\s*\{",
            r"(?<![A-Za-z])Switch\s*\{",
            r"(?<![A-Za-z])SpinBox\s*\{",
        ),
        "frontend/qml/pages/FileFunction.qml": (
            r"(?<![A-Za-z])CheckBox\s*\{",
            r"(?<![A-Za-z])Switch\s*\{",
        ),
        "frontend/qml/pages/NetworkScan.qml": (r"(?<![A-Za-z])TextField\s*\{",),
        "frontend/qml/components/SecurityCard.qml": (r"(?<![A-Za-z])Switch\s*\{",),
    }

    for relative_path, patterns in raw_control_patterns.items():
        content = _read(relative_path)
        for pattern in patterns:
            assert re.search(pattern, content) is None, f"Unexpected raw control {pattern} in {relative_path}"


def test_system_snapshot_security_summary_uses_safe_text_headers() -> None:
    snapshot = _read("frontend/qml/pages/SystemSnapshot.qml")
    security_card = _read("frontend/qml/components/SecurityCard.qml")

    for bad_token in ("Ã°Å¸", "ÃƒÂ°", "Ã¯Â¸", "Ã¢â‚¬â€"):
        assert bad_token not in snapshot

    for unsupported in ("Segoe UI Emoji", "🛡️", "🔄", "💻", "🔒"):
        assert unsupported not in snapshot

    for expected_label in (
        'text: "Internet protection"',
        'text: "Updates"',
        'text: "Device protection"',
        'text: "Remote & apps"',
    ):
        assert expected_label in snapshot

    assert 'property string note: ""' in security_card
    assert "maximumLineCount: card.note.length > 0 ? 1 : 2" in security_card


def test_scan_center_show_more_and_refresh_hotfixes_are_pinned() -> None:
    scan_center = _read("frontend/qml/pages/ScanCenter.qml")
    main_qml = _read("frontend/qml/main.qml")

    assert 'signal requestRoute(string route)' in scan_center
    assert 'id: showMoreButton' in scan_center
    assert 'implicitWidth: showMoreLabel.implicitWidth + leftPadding + rightPadding' in scan_center
    assert 'onClicked: root.requestRoute("ai-report")' in scan_center
    assert 'typeof loadRoute === "function"' not in scan_center
    assert 'id: historyRefreshButton' in scan_center
    assert 'implicitWidth: historyRefreshLabel.implicitWidth + leftPadding + rightPadding' in scan_center
    assert 'historyRefreshButton.hovered' in scan_center
    assert 'onRequestRoute: route => loadRoute(route)' in main_qml


def test_sentinel_dialog_defines_explicit_popup_geometry() -> None:
    sentinel_dialog = _read("frontend/qml/components/SentinelDialog.qml")

    assert "parent: Overlay.overlay" in sentinel_dialog
    assert "implicitHeight:" in sentinel_dialog
    assert "height: implicitHeight" in sentinel_dialog
    assert "x: parent ? Math.round((parent.width - width) / 2) : 0" in sentinel_dialog
    assert "y: parent ? Math.round((parent.height - height) / 2) : 0" in sentinel_dialog


def test_sentinel_dialog_footer_uses_rectangle_not_button() -> None:
    """Guard against the Fusion-style height-collapse regression.

    In Qt Quick Controls 2 Fusion style, a Button whose implicitHeight is only
    set on background.implicitHeight (not on the Button itself) collapses to
    height 0 — QStyle metrics replace background.implicitHeight.  The footer
    must use Rectangle+MouseArea, which is immune to style-system interference,
    so it always renders a visible action button regardless of QML Controls style.
    """
    sentinel_dialog = _read("frontend/qml/components/SentinelDialog.qml")

    # Footer must declare explicit implicitHeight on the rectangles themselves
    assert "primaryActionRect" in sentinel_dialog
    assert "secondaryActionRect" in sentinel_dialog

    # Both action controls must have an explicit implicitHeight
    # (the guard is a substring check rather than exact line because spacing may vary)
    assert "implicitHeight: 36" in sentinel_dialog

    # MouseArea (not Button) must drive click handling to avoid QStyle interference
    assert "MouseArea" in sentinel_dialog
    assert "onClicked: sentinelDialogRoot.accept()" in sentinel_dialog
    assert "onClicked: sentinelDialogRoot.reject()" in sentinel_dialog

    # The footer must NOT use a bare Button for its primary action
    # (the confirm dialog in HistoryPage still uses Button and that's fine;
    # only the SentinelDialog reusable footer must be Button-free)
    footer_section = sentinel_dialog[sentinel_dialog.find("// 3. Footer"):]
    assert "Button {" not in footer_section, (
        "SentinelDialog footer must not use Button — it collapses in Fusion style. "
        "Use Rectangle+MouseArea instead."
    )
