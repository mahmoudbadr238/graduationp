"""Static guards for the unified History shell integration."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_main_shell_mounts_history_page_and_routes_events_to_viewer() -> None:
    """History page mounts correctly; legacy event aliases go to Event Viewer."""
    main_qml = _read("frontend/qml/main.qml")

    assert 'property string historyRequestedTab: "scan"' in main_qml
    # Legacy aliases "events" and "history-events" must route to event-viewer, not history
    assert 'routeId === "events" || routeId === "history-events"' in main_qml
    assert 'currentRoute = "event-viewer"' in main_qml
    assert 'routeId === "history-scan"' in main_qml
    assert 'label: "History"' in main_qml
    assert 'HistoryPage {' in main_qml
    assert 'visible: currentRoute === "history"' in main_qml
    assert 'requestedTab: historyRequestedTab' in main_qml


def test_event_viewer_sidebar_icon_is_registered() -> None:
    """SidebarIcon must include the SVG case for the 'events' icon name."""
    icon_qml = _read("frontend/qml/components/SidebarIcon.qml")
    assert 'case "events":' in icon_qml
    assert "<path d='m9 15 2 2 4-4'/>" in icon_qml


def test_history_has_exactly_four_tabs() -> None:
    """History must have exactly 4 tabs after Event Viewer was promoted."""
    history_page = _read("frontend/qml/pages/HistoryPage.qml")
    # Count tab key declarations — each tab has one key entry in tabDefs
    assert history_page.count('"key":') == 4
    # Verify exact tabs present
    for key in ('"scan"', '"incidents"', '"quarantine"', '"url"'):
        assert key in history_page
    # Events key must be absent
    assert '"events"' not in history_page


def test_history_refresh_handles_four_tabs() -> None:
    """refreshCurrentTab must handle tabs 0-3 (URL moved from index 4 to 3)."""
    history_page = _read("frontend/qml/pages/HistoryPage.qml")
    assert "case 0:" in history_page
    assert "case 1:" in history_page
    assert "case 2:" in history_page
    assert "case 3:" in history_page
    # case 4 no longer needed
    assert "case 4:" not in history_page


def test_incident_history_qml_uses_effective_fields() -> None:
    """incidentOutcome must prefer effective_outcome; verdict badge must use effective_verdict_label."""
    history_page = _read("frontend/qml/pages/HistoryPage.qml")

    # incidentOutcome must use effective_outcome when present
    assert "item.effective_outcome" in history_page
    # Verdict badge must use effective_verdict_label with fallback to decision_verdict
    assert "modelData.effective_verdict_label || modelData.decision_verdict" in history_page
    # Legacy fallback in incidentOutcome must NOT fire for guardrail cases
    # (process_action === "kill_process" alone must not say Blocked — it was wrong)
    assert 'item.action_taken === "terminated"' in history_page
    assert 'item.process_action === "kill_process"' not in history_page  # removed incorrect guard
    # Raw verdict shown in secondary detail line for audit (not as primary badge)
    assert '"Raw verdict: " + (modelData.decision_verdict' in history_page or \
           "Raw verdict: " in history_page
    # Status color handles new outcome labels without throwing
    assert '"block failed"' in history_page or '"Block failed"' in history_page or \
           "block failed" in history_page


def test_history_page_declares_all_required_tabs() -> None:
    """History must contain only its four audit-record tabs.

    Event Viewer was promoted to a top-level route and is no longer
    embedded in History.  "Security / System Events" must not appear.
    """
    history_page = _read("frontend/qml/pages/HistoryPage.qml")
    qmldir = _read("frontend/qml/pages/qmldir")

    for tab_label in (
        "Scan History",
        "RTP / Incident History",
        "Quarantine History",
        "URL Scan History",
    ):
        assert tab_label in history_page

    # Events tab was removed from History — guard against re-introduction
    assert "Security / System Events" not in history_page

    for backend_token in (
        "getUnifiedScanHistory",
        "getIncidentHistory",
        "getQuarantineHistory",
        "getUrlScanHistory",
        "restoreQuarantineItem",
        "deleteQuarantineItem",
    ):
        assert backend_token in history_page

    assert "HistoryPage 1.0 HistoryPage.qml" in qmldir
    assert 'root.requestRoute("history-scan")' in _read("frontend/qml/pages/ScanCenter.qml")
    assert 'text: "Restore"' in history_page
    assert 'text: "Delete Permanently"' in history_page
    assert 'text: "View Quarantine"' in history_page
    assert 'id: quarantineActionDialog' in history_page
    assert 'id: quarantineResultDialog' in history_page
    assert 'closePolicy: Popup.CloseOnEscape' in history_page
    assert 'Popup.CloseOnPressOutside' in history_page
    assert "onClosed: quarantineActionResult = null" in history_page
    assert 'text: "Cancel"' in history_page
    assert '("Quarantined: " + root.formatTimestamp(pendingQuarantineItem.quarantined_at))' in history_page
    assert '("Source: " + (pendingQuarantineItem.source_label || "Not recorded"))' in history_page
    assert '("Score: " + (pendingQuarantineItem.decision_score_label || "Not recorded")' in history_page
    assert '("Decision: " + (pendingQuarantineItem.decision_action_label || "Not recorded")' in history_page
    assert "standardButtons: Dialog.Ok | Dialog.Cancel" not in history_page

    # Result dialog — polished copy helpers must be present
    assert '_resultTitle' in history_page
    assert '_humanizeResultMessage' in history_page
    assert '_isPermissionError' in history_page
    # Titles cover all four outcome states
    assert '"File Restored"' in history_page
    assert '"Restore Failed"' in history_page
    assert '"File Deleted"' in history_page
    assert '"Deletion Failed"' in history_page
    # Human-readable failure messages replace raw exception text
    assert 'Windows denied access to the destination folder' in history_page
    assert 'administrator privileges' in history_page
    assert 'Sentinel encountered an error' in history_page
    # Suggestion box wired to permission-error helper
    assert 'root._isPermissionError' in history_page
    # Technical details section is present but secondary
    assert 'Technical details' in history_page
    # Result dialog uses helpers, not raw message or old hard-coded title
    assert 'root._resultTitle(quarantineActionResult)' in history_page
    assert 'root._humanizeResultMessage(quarantineActionResult)' in history_page
    assert '"Quarantine Action Result"' not in history_page
    assert '"Restore Complete"' not in history_page
    assert '"Deletion Complete"' not in history_page

    assert 'decision_score_label' in history_page
    assert 'decision_metadata_note' in history_page
    assert 'file_action_note' in history_page
    assert 'metadata_quality_label' in history_page
    assert 'path_trust_note' in history_page
    assert 'text: "Incident details"' in history_page
    assert 'text: "Enforcement reason"' in history_page
