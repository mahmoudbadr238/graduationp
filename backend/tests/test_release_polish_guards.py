from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_shell_navigation_uses_vector_icons_with_route_labels() -> None:
    main_qml = _read("frontend/qml/main.qml")
    sidebar = _read("frontend/qml/components/SidebarItem.qml")
    icon_component = _read("frontend/qml/components/SidebarIcon.qml")
    qmldir = _read("frontend/qml/components/qmldir")

    for token in (
        'iconName: "home"',
        'iconName: "history"',
        'iconName: "snapshot"',
        'iconName: "monitor"',
        'iconName: "network"',
        'iconName: "scan"',
        'iconName: "file"',
        'iconName: "assistant"',
        'iconName: "sandbox"',
        'iconName: "settings"',
        'label: "Home"',
        'label: "History"',
        'label: "System Snapshot"',
        'label: "System Monitor"',
        'label: "Network Scan"',
        'label: "Scan Center"',
        'label: "File Function"',
        'label: "Security Assistant"',
        'label: "Sandbox"',
        'label: "Settings"',
        'text: "Navigation"',
        'text: "Tools"',
    ):
        assert token in main_qml

    for token in ('icon: "HM"', 'icon: "HI"', 'icon: "SC"', 'icon: "AI"', 'icon: "ST"'):
        assert token not in main_qml

    assert 'title: "Sentinel Endpoint Security"' in main_qml
    assert 'text: "Endpoint Security"' in main_qml
    assert 'text: "Ã°Å¸â€â€"' not in main_qml
    assert 'icon: "Ã°Å¸' not in main_qml
    assert 'icon: "Ã¢Å¡' not in main_qml
    assert 'property string iconName: "home"' in sidebar
    assert 'property bool expanded: true' in sidebar
    assert "SidebarIcon {" in sidebar
    assert "name: root.iconName" in sidebar
    assert "SidebarIcon 1.0 SidebarIcon.qml" in qmldir
    assert "HoverHandler {" in main_qml
    assert "property bool sidebarExpanded: false" in main_qml
    assert "readonly property int collapsedWidth: 74" in main_qml
    assert "readonly property int expandedWidth: 218" in main_qml
    assert "Layout.preferredWidth: sidebar.sidebarExpanded ? sidebar.expandedWidth : sidebar.collapsedWidth" in main_qml
    assert "collapseSidebarTimer.restart()" in main_qml
    assert 'expanded: sidebar.sidebarExpanded' in main_qml
    assert "anchors.left: iconContainer.right" in sidebar
    assert "opacity: expanded ? 1 : 0" in sidebar
    assert "clip: true" in sidebar
    assert "ToolTip {" in sidebar

    for token in (
        'case "home":',
        'case "history":',
        'case "snapshot":',
        'case "monitor":',
        'case "network":',
        'case "scan":',
        'case "file":',
        'case "assistant":',
        'case "sandbox":',
        'case "settings":',
    ):
        assert token in icon_component


def test_settings_page_is_local_first_and_capability_aware() -> None:
    settings = _read("frontend/qml/pages/SettingsPage.qml")

    assert 'text: "Background Telemetry:"' in settings
    assert 'text: "Crash and support diagnostics stay local in this release."' in settings
    assert "Sentinel does not automatically send error reports in this build." in settings
    assert 'text: "Send Error Reports:"' not in settings
    assert "Autostart is not configured for this platform in the current release" in settings


def test_user_facing_copy_drops_demo_and_gamer_language() -> None:
    gpu_monitor = _read("frontend/qml/pages/GPUMonitor.qml")
    file_function = _read("frontend/qml/pages/FileFunction.qml")

    assert "Real-time GPU telemetry, thermal data, and device health" in gpu_monitor
    assert "MSI Afterburner" not in gpu_monitor
    assert "bundled recovery sample data in this session" in file_function
    assert "Running in demo mode instead." not in file_function


def test_release_readme_matches_current_product_surface() -> None:
    readme = _read("README.md")

    assert "Sentinel is a sophisticated graduation/research project" in readme
    assert "MSI Afterburner" not in readme
    assert "Real-Time Protection (RTP)" in readme
    assert "Multi-Engine Scan Center" in readme


def test_quickstart_and_release_checklist_match_polished_release_language() -> None:
    quickstart = _read("docs/QUICKSTART.md")
    checklist = _read("docs/releases/FINAL_RELEASE_CHECKLIST.md")

    assert "Start the Sentinel Desktop Application" in quickstart
    assert "glyph fallback issues" in checklist
    assert "Settings only exposes supported startup or tray controls" in checklist


# ── Dead-code removal guards ─────────────────────────────────────────────────

def test_dead_security_page_qml_is_removed() -> None:
    """SecurityPage.qml was confirmed dead (not in qmldir, zero imports).

    Deleting it removes the misleading duplicate and ensures SystemSnapshot.qml
    inline Security tab is the only authoritative implementation.
    """
    dead_path = REPO_ROOT / "frontend" / "qml" / "pages" / "snapshot" / "SecurityPage.qml"
    assert not dead_path.exists(), (
        "SecurityPage.qml was confirmed dead code and must not be re-created. "
        "The live Security tab lives inline in SystemSnapshot.qml (Tab 3)."
    )


def test_snapshot_subdir_has_no_extra_unregistered_qml() -> None:
    """No QML file in pages/snapshot/ should be registered in the pages qmldir.

    All remaining snapshot/ files are dead; none should be re-registered without
    also wiring them into SystemSnapshot.qml.
    """
    qmldir_text = _read("frontend/qml/pages/qmldir")
    snapshot_dir = REPO_ROOT / "frontend" / "qml" / "pages" / "snapshot"
    for qml_file in snapshot_dir.glob("*.qml"):
        assert qml_file.stem not in qmldir_text, (
            f"{qml_file.name} must not be registered in pages/qmldir without "
            "wiring it into the live SystemSnapshot.qml."
        )


# ── History / Events tab refresh guards ─────────────────────────────────────

def test_event_viewer_is_top_level_route_in_main_shell() -> None:
    """EventViewer must be a first-class top-level page in main.qml.

    It was promoted out of History (where it was buried as a sub-tab)
    and now lives as a direct page instance in the main shell with its
    own route, sidebar entry, title, and subtitle.
    """
    main_qml = _read("frontend/qml/main.qml")
    # Top-level page instance
    assert 'EventViewer {' in main_qml
    assert 'visible: currentRoute === "event-viewer"' in main_qml
    # Sidebar entry
    assert 'iconName: "events"' in main_qml
    assert 'label: "Event Viewer"' in main_qml
    assert 'isActive: currentRoute === "event-viewer"' in main_qml
    # Route title and subtitle
    assert 'case "event-viewer":' in main_qml
    assert "Event Viewer" in main_qml
    # Legacy aliases still route to the new top-level page
    assert 'routeId === "events" || routeId === "history-events"' in main_qml
    assert 'currentRoute = "event-viewer"' in main_qml
    # EventViewer must NOT be embedded in HistoryPage anymore
    history = _read("frontend/qml/pages/HistoryPage.qml")
    assert "EventViewer {" not in history


def test_history_refresh_tab_has_documented_case_3() -> None:
    """refreshCurrentTab() must have a documented case 3 to show the omission is intentional."""
    history = _read("frontend/qml/pages/HistoryPage.qml")
    assert "case 3:" in history, (
        "refreshCurrentTab() must include a case 3 branch (even as a no-op comment) "
        "so the absence of an explicit refresh call is clearly intentional."
    )


# ── Home page trust / protection state guards ────────────────────────────────

def test_home_page_surfaces_rtp_status() -> None:
    """Home page must show Real-Time Protection status drawn from RTPBridge.

    This ensures the landing page answers the primary protection question
    without requiring the user to navigate to System Monitor.
    """
    home = _read("frontend/qml/pages/HomePage.qml")
    assert 'label: "Real-Time Protection"' in home
    assert "rtpStatusLabel" in home
    assert "rtpGood" in home
    assert "syncRtpState" in home
    assert "RTPBridge" in home


def test_home_page_surfaces_activity_summary() -> None:
    """Home page must show recent scan + quarantine + incident counts.

    These fields must come from real backend calls, not hardcoded strings.
    """
    home = _read("frontend/qml/pages/HomePage.qml")
    assert "recentScanItem" in home
    assert "quarantineActiveCount" in home
    assert "incidentCount" in home
    assert "loadActivitySummary" in home
    assert "getUnifiedScanHistory" in home
    assert "getQuarantineHistory" in home
    assert "getIncidentHistory" in home
    # Must show quarantine review link when items exist
    assert "history-quarantine" in home
    assert "history-incidents" in home
