import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../ui"

Item {
    id: root
    objectName: "historyPageRoot"
    anchors.fill: parent

    readonly property var backend: (typeof Backend !== "undefined") ? Backend : null
    signal requestRoute(string route)

    property string requestedTab: "scan"
    property int currentTab: 0

    property var tabDefs: [
        { "key": "scan",       "label": "Scan History" },
        { "key": "incidents",  "label": "RTP / Incident History" },
        { "key": "quarantine", "label": "Quarantine History" },
        { "key": "url",        "label": "URL Scan History" }
    ]

    property var scanItems: []
    property var incidentItems: []
    property var quarantineItems: []
    property var urlItems: []
    property var pendingQuarantineItem: null
    property string pendingQuarantineAction: ""
    property var quarantineActionResult: null

    function applyRequestedTab() {
        for (var i = 0; i < tabDefs.length; i++) {
            if (tabDefs[i].key === requestedTab) {
                currentTab = i
                return
            }
        }
    }

    function refreshAll() {
        refreshScanHistory()
        refreshIncidentHistory()
        refreshQuarantineHistory()
        refreshUrlHistory()
    }

    function refreshCurrentTab() {
        switch (currentTab) {
        case 0:
            refreshScanHistory()
            break
        case 1:
            refreshIncidentHistory()
            break
        case 2:
            refreshQuarantineHistory()
            break
        case 3:
            refreshUrlHistory()
            break
        }
    }

    function refreshScanHistory() {
        scanItems = (backend && backend.getUnifiedScanHistory)
            ? backend.getUnifiedScanHistory(200)
            : []
    }

    function refreshIncidentHistory() {
        incidentItems = (backend && backend.getIncidentHistory)
            ? backend.getIncidentHistory(200)
            : []
    }

    function refreshQuarantineHistory() {
        quarantineItems = (backend && backend.getQuarantineHistory)
            ? backend.getQuarantineHistory()
            : []
    }

    function refreshUrlHistory() {
        urlItems = (backend && backend.getUrlScanHistory)
            ? backend.getUrlScanHistory(200)
            : []
    }

    function openQuarantineTab() {
        requestedTab = "quarantine"
        currentTab = 2
        refreshQuarantineHistory()
    }

    function queueQuarantineAction(action, item) {
        if (!item)
            return
        pendingQuarantineAction = action
        pendingQuarantineItem = item
        quarantineActionDialog.open()
    }

    function executePendingQuarantineAction() {
        if (!backend || !pendingQuarantineItem)
            return

        var performedAction = pendingQuarantineAction
        var affectedItem = pendingQuarantineItem
        var result = { "success": false, "message": "Backend unavailable." }
        if (pendingQuarantineAction === "restore" && backend.restoreQuarantineItem) {
            result = backend.restoreQuarantineItem(pendingQuarantineItem.id)
        } else if (pendingQuarantineAction === "delete" && backend.deleteQuarantineItem) {
            result = backend.deleteQuarantineItem(pendingQuarantineItem.id)
        }

        refreshQuarantineHistory()
        if (result && result.success)
            refreshIncidentHistory()

        quarantineActionResult = {
            "action": performedAction,
            "success": !!(result && result.success),
            "message": (result && result.message) ? result.message : "No result returned.",
            "original_name": (result && result.original_name) ? result.original_name : (affectedItem ? affectedItem.original_name : ""),
            "original_path": (result && result.original_path) ? result.original_path : (affectedItem ? affectedItem.original_path : ""),
            "restored_sha256": result ? result.restored_sha256 : "",
            "integrity_verified": result ? result.integrity_verified : undefined,
            "audit_retained": !!(result && result.audit_retained)
        }
        quarantineResultDialog.open()

        pendingQuarantineAction = ""
        pendingQuarantineItem = null
    }

    function formatTimestamp(value) {
        var text = String(value || "")
        if (!text)
            return ""
        return text.replace("T", " ").replace("Z", "").slice(0, 19)
    }

    function shortHash(value) {
        var text = String(value || "")
        if (text.length <= 16)
            return text
        return text.slice(0, 12) + "..."
    }

    function riskColor(risk) {
        var normalized = String(risk || "").toLowerCase()
        if (normalized === "critical" || normalized === "high" || normalized === "malicious")
            return ThemeManager.danger
        if (normalized === "medium" || normalized === "warning" || normalized === "suspicious")
            return ThemeManager.warning
        if (normalized === "low" || normalized === "clean" || normalized === "safe")
            return ThemeManager.success
        return ThemeManager.info
    }

    function statusColor(status) {
        var normalized = String(status || "").toLowerCase()
        if (normalized === "quarantined" || normalized === "blocked" || normalized === "deleted")
            return ThemeManager.danger
        if (normalized === "block failed" || normalized === "skipped")
            return ThemeManager.warning
        if (normalized === "restored" || normalized === "completed" || normalized === "allow")
            return ThemeManager.success
        if (normalized === "flagged" || normalized === "log_only" || normalized === "warning")
            return ThemeManager.warning
        return ThemeManager.info
    }

    function incidentOutcome(item) {
        if (!item)
            return "Recorded"
        // Use the backend-computed effective_outcome when present (added in list_incident_history).
        // This reflects the *actual* enforcement result, not the raw scanner verdict.
        if (item.effective_outcome)
            return item.effective_outcome
        // Legacy fallback for records that predate effective_outcome
        if (item.file_action_taken === "quarantined")
            return "Quarantined"
        if (item.action_taken === "terminated")
            return "Blocked"
        if (item.process_action === "log_only")
            return "Logged only"
        return "Recorded"
    }

    function quarantineSourceColor(sourceKey) {
        switch (String(sourceKey || "")) {
        case "rtp":
            return ThemeManager.info
        case "scan_center":
            return ThemeManager.accent
        case "manual":
            return ThemeManager.warning
        case "legacy":
            return ThemeManager.warning
        default:
            return ThemeManager.muted()
        }
    }

    function quarantineMetadataColor(qualityKey) {
        switch (String(qualityKey || "")) {
        case "complete":
            return ThemeManager.success
        case "partial":
            return ThemeManager.warning
        case "manual_record":
            return ThemeManager.info
        case "legacy_incomplete":
            return ThemeManager.warning
        default:
            return ThemeManager.muted()
        }
    }

    function _resultTitle(result) {
        if (!result) return "Action Result"
        if (result.action === "restore")
            return result.success ? "File Restored" : "Restore Failed"
        return result.success ? "File Deleted" : "Deletion Failed"
    }

    function _humanizeResultMessage(result) {
        if (!result) return ""
        if (result.success) {
            if (result.action === "restore")
                return "The file has been returned to its original location on disk."
            return "The file has been permanently removed from the vault."
        }
        var raw = String(result.message || "")
        var lower = raw.toLowerCase()
        if (lower.indexOf("permission") >= 0 || lower.indexOf("access is denied") >= 0 ||
            lower.indexOf("[errno 13]") >= 0 || lower.indexOf("permissionerror") >= 0) {
            return result.action === "restore"
                ? "Sentinel couldn't restore this file because Windows denied access to the destination folder."
                : "Sentinel couldn't complete this action because access was denied."
        }
        if (lower.indexOf("not found") >= 0 || lower.indexOf("no quarantine entry") >= 0)
            return "The vault entry was not found. It may have already been removed."
        if (lower.indexOf("already restored") >= 0)
            return "This file has already been restored to its original location."
        if (lower.indexOf("already") >= 0 && lower.indexOf("deleted") >= 0)
            return "This entry was already permanently deleted from the vault."
        return "Sentinel encountered an error and could not complete this action."
    }

    function _isPermissionError(result) {
        if (!result || result.success) return false
        var lower = String(result.message || "").toLowerCase()
        return lower.indexOf("permission") >= 0 || lower.indexOf("access is denied") >= 0 ||
               lower.indexOf("[errno 13]") >= 0 || lower.indexOf("permissionerror") >= 0
    }

    function openScanRecord(item) {
        if (!backend || !item || !item.report_path)
            return

        if (item.report_loader === "scancenter" && backend.openScanCenterReport) {
            backend.openScanCenterReport(item.report_path)
            requestRoute("scan-tool")
            return
        }

        if (backend.loadScanReport) {
            backend.loadScanReport(item.report_path)
            requestRoute("scan-tool")
        }
    }

    Component.onCompleted: {
        applyRequestedTab()
        refreshAll()
    }

    onRequestedTabChanged: applyRequestedTab()
    onCurrentTabChanged: refreshCurrentTab()

    Connections {
        target: root.backend
        enabled: target !== null

        function onScanFinished(scanType, _result) {
            if (scanType === "file")
                root.refreshScanHistory()
            else if (scanType === "url")
                root.refreshUrlHistory()
        }

        function onScanCenterFinished(_result) {
            root.refreshScanHistory()
        }
    }

    Connections {
        target: (typeof RTPBridge !== "undefined") ? RTPBridge : null
        enabled: target !== null

        function onThreatDetected(_message) {
            root.refreshIncidentHistory()
            root.refreshQuarantineHistory()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()
    }

    Dialog {
        id: quarantineActionDialog
        objectName: "quarantineActionDialog"
        parent: Overlay.overlay
        width: Math.min(560, parent ? parent.width - 48 : 560)
        implicitHeight: quarantineActionCard.implicitHeight
        height: implicitHeight
        x: parent ? Math.round((parent.width - width) / 2) : 0
        y: parent ? Math.round((parent.height - height) / 2) : 0
        margins: 24
        modal: true
        focus: true
        dim: true
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Item { }

        Overlay.modal: Rectangle {
            color: Qt.rgba(0, 0, 0, 0.6)
        }

        header: Item { visible: false; implicitHeight: 0 }

        contentItem: Rectangle {
            id: quarantineActionCard
            width: quarantineActionDialog.width
            implicitHeight: quarantineActionContent.implicitHeight + 48
            color: ThemeManager.elevated()
            radius: 14
            border.color: ThemeManager.border()
            border.width: 2

            ColumnLayout {
                id: quarantineActionContent
                anchors.fill: parent
                anchors.margins: 24
                spacing: 16

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle {
                        width: 40
                        height: 40
                        radius: 20
                        color: pendingQuarantineAction === "restore"
                               ? Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.15)
                               : Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.15)

                        Text {
                            anchors.centerIn: parent
                            text: "!"
                            font.pixelSize: 22
                            font.bold: true
                            color: pendingQuarantineAction === "restore" ? ThemeManager.warning : ThemeManager.danger
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: pendingQuarantineAction === "restore" ? "Restore Quarantined File" : "Delete Quarantined File"
                        color: ThemeManager.foreground()
                        font.pixelSize: ThemeManager.fontSize_h2
                        font.bold: true
                        wrapMode: Text.Wrap
                    }
                }

                Text {
                    text: pendingQuarantineAction === "restore"
                          ? "This will return the file to its original location on disk. Only continue if you trust this file."
                          : "This will permanently remove the file from Sentinel's vault. The audit record will remain in Quarantine History."
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_body
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    lineHeight: 1.4
                }

            ScrollView {
                id: quarantineActionScroll
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(280, quarantineActionBody.implicitHeight)
                clip: true
                ScrollBar.vertical: ScrollBar { }

                ColumnLayout {
                    id: quarantineActionBody
                    width: quarantineActionScroll.availableWidth
                    spacing: 16

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: pendingQuarantineItem
                                  ? (pendingQuarantineItem.original_name || "(unknown)")
                                  : ""
                            color: ThemeManager.foreground()
                            font.pixelSize: ThemeManager.fontSize_body
                            font.bold: true
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            text: pendingQuarantineItem
                                  ? ("Path: " + (pendingQuarantineItem.original_path || "(unknown path)"))
                                  : ""
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            visible: !!pendingQuarantineItem
                            text: pendingQuarantineItem
                                  ? ("Quarantined: " + root.formatTimestamp(pendingQuarantineItem.quarantined_at))
                                  : ""
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            visible: !!(pendingQuarantineItem && pendingQuarantineItem.metadata_quality_label)
                            text: pendingQuarantineItem
                                  ? ("Record quality: " + pendingQuarantineItem.metadata_quality_label)
                                  : ""
                            color: root.quarantineMetadataColor(
                                       pendingQuarantineItem ? pendingQuarantineItem.metadata_quality : ""
                                   )
                            font.pixelSize: ThemeManager.fontSize_small
                            font.bold: true
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    Rectangle {
                        visible: !!pendingQuarantineItem
                        Layout.fillWidth: true
                        height: 1
                        color: ThemeManager.border()
                        opacity: 0.5
                    }

                    ColumnLayout {
                        visible: !!pendingQuarantineItem
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: pendingQuarantineItem
                                  ? ("Source: " + (pendingQuarantineItem.source_label || "Not recorded"))
                                  : ""
                            color: ThemeManager.foreground()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            text: pendingQuarantineItem
                                  ? ("Score: " + (pendingQuarantineItem.decision_score_label || "Not recorded")
                                     + "  Verdict: " + (pendingQuarantineItem.decision_verdict_label || "Not recorded"))
                                  : ""
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            text: pendingQuarantineItem
                                  ? ("Decision: " + (pendingQuarantineItem.decision_action_label || "Not recorded")
                                     + "  File action: " + (pendingQuarantineItem.file_action_label || "Not recorded"))
                                  : ""
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            visible: !!(pendingQuarantineItem && pendingQuarantineItem.metadata_note)
                            text: pendingQuarantineItem ? pendingQuarantineItem.metadata_note : ""
                            color: root.quarantineMetadataColor(
                                       pendingQuarantineItem ? pendingQuarantineItem.metadata_quality : ""
                                   )
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            visible: !!(pendingQuarantineItem && pendingQuarantineItem.action_reason_label)
                            text: pendingQuarantineItem ? pendingQuarantineItem.action_reason_label : ""
                            color: ThemeManager.foreground()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }
            }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Item { Layout.fillWidth: true }

                    Button {
                        id: quarantineCancelButton
                        text: "Cancel"
                        flat: true
                        implicitWidth: 96
                        implicitHeight: 36
                        onClicked: quarantineActionDialog.reject()

                        contentItem: Text {
                            text: quarantineCancelButton.text
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_body
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        background: Rectangle {
                            implicitWidth: 96
                            implicitHeight: 36
                            radius: 8
                            color: quarantineCancelButton.hovered ? ThemeManager.surface() : "transparent"
                            border.color: ThemeManager.border()
                            border.width: 1
                        }
                    }

                    Button {
                        id: quarantineConfirmButton
                        text: pendingQuarantineAction === "restore" ? "Restore" : "Delete Permanently"
                        implicitWidth: pendingQuarantineAction === "restore" ? 96 : 170
                        implicitHeight: 36
                        onClicked: quarantineActionDialog.accept()

                        contentItem: Text {
                            text: quarantineConfirmButton.text
                            color: "white"
                            font.pixelSize: ThemeManager.fontSize_body
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        background: Rectangle {
                            implicitWidth: Math.max(96, quarantineConfirmButton.contentItem.implicitWidth + 24)
                            implicitHeight: 36
                            radius: 8
                            color: quarantineConfirmButton.hovered
                                   ? Qt.darker(
                                         pendingQuarantineAction === "restore" ? ThemeManager.success : ThemeManager.danger,
                                         1.15
                                     )
                                   : (pendingQuarantineAction === "restore" ? ThemeManager.success : ThemeManager.danger)
                        }
                    }
                }
            }
        }

        onAccepted: root.executePendingQuarantineAction()
    }

    SentinelDialog {
        id: quarantineResultDialog
        objectName: "quarantineResultDialog"
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        titleText: root._resultTitle(quarantineActionResult)

        iconText: quarantineActionResult && quarantineActionResult.success ? "✓" : "⚠"
        iconColor: quarantineActionResult && quarantineActionResult.success
                   ? ThemeManager.success : ThemeManager.warning
        iconBgColor: quarantineActionResult && quarantineActionResult.success
                     ? Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.15)
                     : Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.15)

        bodyText: root._humanizeResultMessage(quarantineActionResult)
        showSecondaryButton: false
        primaryButtonText: "OK"

        customContent: ColumnLayout {
            Layout.fillWidth: true
            spacing: 12

            // Suggestion box — only shown for permission-denied failures
            Rectangle {
                visible: root._isPermissionError(quarantineActionResult)
                Layout.fillWidth: true
                radius: 8
                color: Qt.rgba(ThemeManager.info.r, ThemeManager.info.g, ThemeManager.info.b, 0.10)
                border.color: Qt.rgba(ThemeManager.info.r, ThemeManager.info.g, ThemeManager.info.b, 0.25)
                border.width: 1
                implicitHeight: permHintLayout.implicitHeight + 20

                ColumnLayout {
                    id: permHintLayout
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 4

                    Text {
                        text: "Suggestion"
                        color: ThemeManager.info
                        font.pixelSize: 11
                        font.bold: true
                    }
                    Text {
                        text: quarantineActionResult && quarantineActionResult.action === "restore"
                              ? "Try running Sentinel with administrator privileges, or restore to a folder you have write access to."
                              : "Try running Sentinel with administrator privileges."
                        color: ThemeManager.foreground()
                        font.pixelSize: ThemeManager.fontSize_small
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        lineHeight: 1.4
                    }
                }
            }

            // Separator before file details
            Rectangle {
                visible: !!(quarantineActionResult && quarantineActionResult.original_name)
                Layout.fillWidth: true
                height: 1
                color: ThemeManager.border()
                opacity: 0.5
            }

            // File identity + outcome details
            ColumnLayout {
                visible: !!(quarantineActionResult && quarantineActionResult.original_name)
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: quarantineActionResult ? quarantineActionResult.original_name : ""
                    color: ThemeManager.foreground()
                    font.pixelSize: ThemeManager.fontSize_body
                    font.bold: true
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Text {
                    visible: !!(quarantineActionResult && quarantineActionResult.original_path)
                    text: quarantineActionResult ? quarantineActionResult.original_path : ""
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_small
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                // SHA-256 fingerprint (restore success only)
                Text {
                    visible: !!(quarantineActionResult && quarantineActionResult.success
                                && quarantineActionResult.action === "restore"
                                && quarantineActionResult.restored_sha256)
                    text: "SHA-256  " + (quarantineActionResult
                          ? root.shortHash(quarantineActionResult.restored_sha256) : "")
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_small
                    Layout.fillWidth: true
                }

                // Integrity check (restore success only)
                Text {
                    visible: !!(quarantineActionResult
                                && quarantineActionResult.success
                                && quarantineActionResult.integrity_verified !== undefined
                                && quarantineActionResult.integrity_verified !== null)
                    text: quarantineActionResult && quarantineActionResult.integrity_verified
                          ? "✓  Integrity verified — file matches original hash"
                          : "⚠  Integrity mismatch — hash differs from original"
                    color: quarantineActionResult && quarantineActionResult.integrity_verified
                           ? ThemeManager.success : ThemeManager.warning
                    font.pixelSize: ThemeManager.fontSize_small
                    font.bold: true
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                // Audit note (delete success only)
                Text {
                    visible: !!(quarantineActionResult && quarantineActionResult.success
                                && quarantineActionResult.action === "delete")
                    text: "The audit record remains available in Quarantine History."
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_small
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }

            // Technical details — failure only, subdued secondary section
            Rectangle {
                visible: !!(quarantineActionResult && !quarantineActionResult.success
                            && quarantineActionResult.message)
                Layout.fillWidth: true
                radius: 8
                color: ThemeManager.panel()
                border.color: ThemeManager.border()
                border.width: 1
                implicitHeight: techDetailsCol.implicitHeight + 20

                ColumnLayout {
                    id: techDetailsCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 4

                    Text {
                        text: "Technical details"
                        color: ThemeManager.muted()
                        font.pixelSize: 10
                        font.bold: true
                    }
                    Text {
                        text: quarantineActionResult ? quarantineActionResult.message : ""
                        color: ThemeManager.muted()
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        lineHeight: 1.3
                    }
                }
            }
        }

        onClosed: quarantineActionResult = null
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                text: "History"
                color: ThemeManager.foreground()
                font.pixelSize: 26
                font.bold: true
            }

            Text {
                text: "Unified audit trail for scans, incidents, quarantine records, and URL scan history."
                color: ThemeManager.muted()
                font.pixelSize: ThemeManager.fontSize_small
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 46
            radius: 10
            color: ThemeManager.panel()
            border.color: ThemeManager.border()
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.margins: 4
                spacing: 4

                Repeater {
                    model: root.tabDefs

                    delegate: Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 8
                        color: root.currentTab === index
                               ? ThemeManager.surface()
                               : "transparent"

                        border.width: root.currentTab === index ? 1 : 0
                        border.color: root.currentTab === index
                                      ? ThemeManager.border()
                                      : "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: modelData.label
                            color: root.currentTab === index
                                   ? ThemeManager.foreground()
                                   : ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            font.bold: root.currentTab === index
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            width: parent.width - 16
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.currentTab = index
                                root.requestedTab = modelData.key
                            }
                        }
                    }
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.currentTab

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "File Scan History"
                            color: ThemeManager.foreground()
                            font.pixelSize: 20
                            font.bold: true
                        }

                        Text {
                            text: root.scanItems.length + " entries"
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            text: "Refresh"
                            implicitWidth: 92
                            implicitHeight: 34
                            onClicked: root.refreshScanHistory()

                            background: Rectangle {
                                radius: 8
                                color: parent.hovered ? ThemeManager.surface() : ThemeManager.panel()
                                border.color: ThemeManager.border()
                                border.width: 1
                            }

                            contentItem: Text {
                                text: parent.text
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_small
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1

                        Item {
                            anchors.fill: parent
                            anchors.margins: 12

                            Text {
                                anchors.centerIn: parent
                                visible: root.scanItems.length === 0
                                text: "No scan history recorded yet."
                                color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_body
                            }

                            ListView {
                                anchors.fill: parent
                                visible: root.scanItems.length > 0
                                clip: true
                                spacing: 8
                                model: root.scanItems
                                ScrollBar.vertical: ScrollBar { }

                                delegate: Rectangle {
                                    width: ListView.view.width
                                    implicitHeight: scanRow.implicitHeight + 20
                                    radius: 10
                                    color: ThemeManager.elevated()
                                    border.color: ThemeManager.border()
                                    border.width: 1

                                    RowLayout {
                                        id: scanRow
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 12

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 4

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 8

                                                Text {
                                                    text: modelData.file_name
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: ThemeManager.fontSize_body
                                                    font.bold: true
                                                    elide: Text.ElideMiddle
                                                    Layout.fillWidth: true
                                                }

                                                Rectangle {
                                                    radius: 8
                                                    implicitHeight: 22
                                                    implicitWidth: sourceText.implicitWidth + 16
                                                    color: ThemeManager.surface()
                                                    border.color: ThemeManager.border()
                                                    border.width: 1

                                                    Text {
                                                        id: sourceText
                                                        anchors.centerIn: parent
                                                        text: modelData.source_label
                                                        color: ThemeManager.muted()
                                                        font.pixelSize: 10
                                                        font.bold: true
                                                    }
                                                }

                                                Rectangle {
                                                    radius: 8
                                                    implicitHeight: 22
                                                    implicitWidth: verdictText.implicitWidth + 16
                                                    color: Qt.rgba(
                                                        root.riskColor(modelData.verdict_risk).r,
                                                        root.riskColor(modelData.verdict_risk).g,
                                                        root.riskColor(modelData.verdict_risk).b,
                                                        0.16
                                                    )

                                                    Text {
                                                        id: verdictText
                                                        anchors.centerIn: parent
                                                        text: modelData.verdict_risk
                                                        color: root.riskColor(modelData.verdict_risk)
                                                        font.pixelSize: 10
                                                        font.bold: true
                                                    }
                                                }
                                            }

                                            Text {
                                                text: modelData.sha256
                                                      ? ("SHA256: " + root.shortHash(modelData.sha256))
                                                      : ("Mode: " + modelData.mode)
                                                color: ThemeManager.muted()
                                                font.pixelSize: 11
                                                elide: Text.ElideMiddle
                                                Layout.fillWidth: true
                                            }

                                            Text {
                                                text: (modelData.verdict_label || "")
                                                      + ((modelData.score !== null && modelData.score !== undefined)
                                                         ? ("  Score: " + modelData.score)
                                                         : "")
                                                      + (modelData.confidence ? ("  Confidence: " + modelData.confidence + "%") : "")
                                                visible: text.length > 0
                                                color: ThemeManager.muted()
                                                font.pixelSize: 11
                                                Layout.fillWidth: true
                                                elide: Text.ElideRight
                                            }
                                        }

                                        ColumnLayout {
                                            spacing: 8
                                            Layout.alignment: Qt.AlignTop

                                            Text {
                                                text: root.formatTimestamp(modelData.created_at)
                                                color: ThemeManager.muted()
                                                font.pixelSize: 11
                                                horizontalAlignment: Text.AlignRight
                                            }

                                            Button {
                                                text: modelData.report_path ? "Open Report" : "No Report"
                                                enabled: !!modelData.report_path
                                                implicitWidth: 100
                                                implicitHeight: 30
                                                onClicked: root.openScanRecord(modelData)

                                                background: Rectangle {
                                                    radius: 8
                                                    color: parent.enabled
                                                           ? (parent.hovered ? ThemeManager.surface() : ThemeManager.panel())
                                                           : ThemeManager.surface()
                                                    border.color: ThemeManager.border()
                                                    border.width: 1
                                                    opacity: parent.enabled ? 1 : 0.5
                                                }

                                                contentItem: Text {
                                                    text: parent.text
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: 11
                                                    horizontalAlignment: Text.AlignHCenter
                                                    verticalAlignment: Text.AlignVCenter
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "RTP / Incident History"
                            color: ThemeManager.foreground()
                            font.pixelSize: 20
                            font.bold: true
                        }

                        Text {
                            text: root.incidentItems.length + " incidents"
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            text: "Refresh"
                            implicitWidth: 92
                            implicitHeight: 34
                            onClicked: root.refreshIncidentHistory()

                            background: Rectangle {
                                radius: 8
                                color: parent.hovered ? ThemeManager.surface() : ThemeManager.panel()
                                border.color: ThemeManager.border()
                                border.width: 1
                            }

                            contentItem: Text {
                                text: parent.text
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_small
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1

                        Item {
                            anchors.fill: parent
                            anchors.margins: 12

                            Text {
                                anchors.centerIn: parent
                                visible: root.incidentItems.length === 0
                                text: "No RTP incidents recorded yet."
                                color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_body
                            }

                            ListView {
                                anchors.fill: parent
                                visible: root.incidentItems.length > 0
                                clip: true
                                spacing: 8
                                model: root.incidentItems
                                ScrollBar.vertical: ScrollBar { }

                                delegate: Rectangle {
                                    width: ListView.view.width
                                    implicitHeight: incidentRow.implicitHeight + 20
                                    radius: 10
                                    color: ThemeManager.elevated()
                                    border.color: ThemeManager.border()
                                    border.width: 1

                                    ColumnLayout {
                                        id: incidentRow
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 6

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8

                                            Text {
                                                text: modelData.process_name || "(unknown process)"
                                                color: ThemeManager.foreground()
                                                font.pixelSize: ThemeManager.fontSize_body
                                                font.bold: true
                                                elide: Text.ElideMiddle
                                                Layout.fillWidth: true
                                            }

                                            Rectangle {
                                                radius: 8
                                                implicitHeight: 22
                                                implicitWidth: outcomeText.implicitWidth + 16
                                                color: Qt.rgba(
                                                    root.statusColor(root.incidentOutcome(modelData)).r,
                                                    root.statusColor(root.incidentOutcome(modelData)).g,
                                                    root.statusColor(root.incidentOutcome(modelData)).b,
                                                    0.16
                                                )

                                                Text {
                                                    id: outcomeText
                                                    anchors.centerIn: parent
                                                    text: root.incidentOutcome(modelData)
                                                    color: root.statusColor(root.incidentOutcome(modelData))
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                }
                                            }

                                            Rectangle {
                                                radius: 8
                                                implicitHeight: 22
                                                implicitWidth: verdictBadgeText.implicitWidth + 16
                                                color: Qt.rgba(
                                                    root.riskColor(modelData.effective_verdict_label || modelData.decision_verdict).r,
                                                    root.riskColor(modelData.effective_verdict_label || modelData.decision_verdict).g,
                                                    root.riskColor(modelData.effective_verdict_label || modelData.decision_verdict).b,
                                                    0.16
                                                )

                                                Text {
                                                    id: verdictBadgeText
                                                    anchors.centerIn: parent
                                                    text: modelData.effective_verdict_label || modelData.decision_verdict || "Unknown"
                                                    color: root.riskColor(modelData.effective_verdict_label || modelData.decision_verdict)
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                }
                                            }
                                        }

                                        Text {
                                            text: modelData.executable_path
                                            color: ThemeManager.muted()
                                            font.pixelSize: 11
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            text: "Score " + (modelData.threat_score || 0)
                                                  + "  Raw verdict: " + (modelData.decision_verdict || "Unknown")
                                                  + "  Process: " + (modelData.process_action || "allow")
                                                  + "  File: " + (modelData.file_action || "allow")
                                                  + "  Result: " + (modelData.file_action_taken || modelData.action_taken || "recorded")
                                            color: ThemeManager.muted()
                                            font.pixelSize: 11
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            text: modelData.action_reason || "No enforcement reason recorded."
                                            color: ThemeManager.foreground()
                                            font.pixelSize: 12
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                        }

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 12

                                            Text {
                                                text: root.formatTimestamp(modelData.occurred_at)
                                                color: ThemeManager.muted()
                                                font.pixelSize: 11
                                            }

                                            Text {
                                                visible: !!modelData.publisher
                                                text: "Publisher: " + modelData.publisher
                                                color: ThemeManager.muted()
                                                font.pixelSize: 11
                                                Layout.fillWidth: true
                                                elide: Text.ElideRight
                                            }

                                            Button {
                                                visible: modelData.file_action_taken === "quarantined"
                                                         || modelData.file_action === "quarantine_file"
                                                text: "View Quarantine"
                                                implicitWidth: 114
                                                implicitHeight: 30
                                                onClicked: root.openQuarantineTab()

                                                background: Rectangle {
                                                    radius: 8
                                                    color: parent.hovered ? ThemeManager.surface() : ThemeManager.panel()
                                                    border.color: ThemeManager.border()
                                                    border.width: 1
                                                }

                                                contentItem: Text {
                                                    text: parent.text
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: 11
                                                    horizontalAlignment: Text.AlignHCenter
                                                    verticalAlignment: Text.AlignVCenter
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "Quarantine History"
                            color: ThemeManager.foreground()
                            font.pixelSize: 20
                            font.bold: true
                        }

                        Text {
                            text: root.quarantineItems.length + " entries"
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            text: "Refresh"
                            implicitWidth: 92
                            implicitHeight: 34
                            onClicked: root.refreshQuarantineHistory()

                            background: Rectangle {
                                radius: 8
                                color: parent.hovered ? ThemeManager.surface() : ThemeManager.panel()
                                border.color: ThemeManager.border()
                                border.width: 1
                            }

                            contentItem: Text {
                                text: parent.text
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_small
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1

                        Item {
                            anchors.fill: parent
                            anchors.margins: 12

                            Text {
                                anchors.centerIn: parent
                                visible: root.quarantineItems.length === 0
                                text: "No quarantine history recorded yet."
                                color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_body
                            }

                            ListView {
                                anchors.fill: parent
                                visible: root.quarantineItems.length > 0
                                clip: true
                                spacing: 8
                                model: root.quarantineItems
                                ScrollBar.vertical: ScrollBar { }

                                delegate: Rectangle {
                                    width: ListView.view.width
                                    implicitHeight: quarantineRow.implicitHeight + 20
                                    radius: 10
                                    color: ThemeManager.elevated()
                                    border.color: ThemeManager.border()
                                    border.width: 1

                                    ColumnLayout {
                                        id: quarantineRow
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 6

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8

                                            Text {
                                                text: modelData.original_name
                                                color: ThemeManager.foreground()
                                                font.pixelSize: ThemeManager.fontSize_body
                                                font.bold: true
                                                elide: Text.ElideMiddle
                                                Layout.fillWidth: true
                                            }

                                            Rectangle {
                                                radius: 8
                                                implicitHeight: 22
                                                implicitWidth: quarantineStatusText.implicitWidth + 16
                                                color: Qt.rgba(
                                                    root.statusColor(modelData.status).r,
                                                    root.statusColor(modelData.status).g,
                                                    root.statusColor(modelData.status).b,
                                                    0.16
                                                )

                                                Text {
                                                    id: quarantineStatusText
                                                    anchors.centerIn: parent
                                                    text: modelData.status || "unknown"
                                                    color: root.statusColor(modelData.status)
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                }
                                            }

                                            Rectangle {
                                                visible: !!modelData.source_label
                                                radius: 8
                                                implicitHeight: 22
                                                implicitWidth: quarantineSourceText.implicitWidth + 16
                                                color: Qt.rgba(
                                                    root.quarantineSourceColor(modelData.enforcement_source).r,
                                                    root.quarantineSourceColor(modelData.enforcement_source).g,
                                                    root.quarantineSourceColor(modelData.enforcement_source).b,
                                                    0.14
                                                )

                                                Text {
                                                    id: quarantineSourceText
                                                    anchors.centerIn: parent
                                                    text: modelData.source_label
                                                    color: root.quarantineSourceColor(modelData.enforcement_source)
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                }
                                            }

                                            Rectangle {
                                                visible: !!modelData.metadata_quality_label
                                                radius: 8
                                                implicitHeight: 22
                                                implicitWidth: quarantineQualityText.implicitWidth + 16
                                                color: Qt.rgba(
                                                    root.quarantineMetadataColor(modelData.metadata_quality).r,
                                                    root.quarantineMetadataColor(modelData.metadata_quality).g,
                                                    root.quarantineMetadataColor(modelData.metadata_quality).b,
                                                    0.12
                                                )

                                                Text {
                                                    id: quarantineQualityText
                                                    anchors.centerIn: parent
                                                    text: modelData.metadata_quality_label
                                                    color: root.quarantineMetadataColor(modelData.metadata_quality)
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                }
                                            }
                                        }

                                        Text {
                                            text: modelData.original_path
                                            color: ThemeManager.muted()
                                            font.pixelSize: 11
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            text: "SHA256: " + root.shortHash(modelData.sha256)
                                                  + "  Size: " + modelData.size_bytes + " bytes"
                                            color: ThemeManager.muted()
                                            font.pixelSize: 11
                                            Layout.fillWidth: true
                                        }

                                        Rectangle {
                                            visible: !!modelData.metadata_note || !!modelData.decision_metadata_note
                                            Layout.fillWidth: true
                                            radius: 8
                                            color: Qt.rgba(
                                                root.quarantineMetadataColor(modelData.metadata_quality).r,
                                                root.quarantineMetadataColor(modelData.metadata_quality).g,
                                                root.quarantineMetadataColor(modelData.metadata_quality).b,
                                                0.08
                                            )
                                            border.color: Qt.rgba(
                                                root.quarantineMetadataColor(modelData.metadata_quality).r,
                                                root.quarantineMetadataColor(modelData.metadata_quality).g,
                                                root.quarantineMetadataColor(modelData.metadata_quality).b,
                                                0.28
                                            )
                                            border.width: 1
                                            implicitHeight: quarantineContextDetails.implicitHeight + 22

                                            ColumnLayout {
                                                id: quarantineContextDetails
                                                anchors.fill: parent
                                                anchors.margins: 11
                                                spacing: 4

                                                Text {
                                                    text: modelData.metadata_quality === "legacy_incomplete"
                                                          ? "Legacy record context"
                                                          : modelData.metadata_quality === "manual_record"
                                                            ? "Manual action context"
                                                            : "Record context"
                                                    color: root.quarantineMetadataColor(modelData.metadata_quality)
                                                    font.pixelSize: 11
                                                    font.bold: true
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    visible: !!modelData.metadata_note
                                                    text: modelData.metadata_note
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: 11
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    visible: !!modelData.decision_metadata_note
                                                    text: modelData.decision_metadata_note
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 11
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }

                                        Rectangle {
                                            visible: !!modelData.path_trust_note
                                            Layout.fillWidth: true
                                            radius: 8
                                            color: Qt.rgba(
                                                ThemeManager.warning.r,
                                                ThemeManager.warning.g,
                                                ThemeManager.warning.b,
                                                0.08
                                            )
                                            border.color: Qt.rgba(
                                                ThemeManager.warning.r,
                                                ThemeManager.warning.g,
                                                ThemeManager.warning.b,
                                                0.28
                                            )
                                            border.width: 1
                                            implicitHeight: quarantineTrustDetails.implicitHeight + 22

                                            ColumnLayout {
                                                id: quarantineTrustDetails
                                                anchors.fill: parent
                                                anchors.margins: 11
                                                spacing: 4

                                                Text {
                                                    text: "Path trust warning"
                                                    color: ThemeManager.warning
                                                    font.pixelSize: 11
                                                    font.bold: true
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    text: modelData.path_trust_note
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: 11
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }

                                        Rectangle {
                                            Layout.fillWidth: true
                                            radius: 8
                                            color: ThemeManager.panel()
                                            border.color: ThemeManager.border()
                                            border.width: 1
                                            implicitHeight: quarantineIncidentDetails.implicitHeight + 22

                                            ColumnLayout {
                                                id: quarantineIncidentDetails
                                                anchors.fill: parent
                                                anchors.margins: 11
                                                spacing: 8

                                                Text {
                                                    text: "Incident details"
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: 11
                                                    font.bold: true
                                                    Layout.fillWidth: true
                                                }

                                                GridLayout {
                                                    Layout.fillWidth: true
                                                    columns: 2
                                                    rowSpacing: 6
                                                    columnSpacing: 12

                                                    Text {
                                                        text: "Source"
                                                        color: ThemeManager.muted()
                                                        font.pixelSize: 11
                                                    }

                                                    Text {
                                                        text: modelData.source_label || "Unknown source"
                                                        color: ThemeManager.foreground()
                                                        font.pixelSize: 11
                                                        wrapMode: Text.WordWrap
                                                        Layout.fillWidth: true
                                                    }

                                                    Text {
                                                        text: "Verdict"
                                                        color: ThemeManager.muted()
                                                        font.pixelSize: 11
                                                    }

                                                    Text {
                                                        text: modelData.decision_verdict_label
                                                        color: ThemeManager.foreground()
                                                        font.pixelSize: 11
                                                        wrapMode: Text.WordWrap
                                                        Layout.fillWidth: true
                                                    }

                                                    Text {
                                                        text: "Decision"
                                                        color: ThemeManager.muted()
                                                        font.pixelSize: 11
                                                    }

                                                    Text {
                                                        text: modelData.decision_action_label
                                                        color: ThemeManager.foreground()
                                                        font.pixelSize: 11
                                                        wrapMode: Text.WordWrap
                                                        Layout.fillWidth: true
                                                    }

                                                    Text {
                                                        text: "Score"
                                                        color: ThemeManager.muted()
                                                        font.pixelSize: 11
                                                    }

                                                    Text {
                                                        text: modelData.decision_score_label
                                                        color: ThemeManager.foreground()
                                                        font.pixelSize: 11
                                                        wrapMode: Text.WordWrap
                                                        Layout.fillWidth: true
                                                    }

                                                    Text {
                                                        text: "Final action"
                                                        color: ThemeManager.muted()
                                                        font.pixelSize: 11
                                                    }

                                                    Text {
                                                        text: modelData.final_action_label
                                                        color: ThemeManager.foreground()
                                                        font.pixelSize: 11
                                                        wrapMode: Text.WordWrap
                                                        Layout.fillWidth: true
                                                    }

                                                    Text {
                                                        text: "File action"
                                                        color: ThemeManager.muted()
                                                        font.pixelSize: 11
                                                    }

                                                    Text {
                                                        text: modelData.file_action_label
                                                        color: ThemeManager.foreground()
                                                        font.pixelSize: 11
                                                        wrapMode: Text.WordWrap
                                                        Layout.fillWidth: true
                                                    }
                                                }

                                                Text {
                                                    visible: !!modelData.file_action_note
                                                    text: modelData.file_action_note
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 11
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }

                                        Rectangle {
                                            visible: !!modelData.process_name
                                                     || !!modelData.publisher
                                                     || modelData.signature_valid === true
                                                     || modelData.signature_valid === false
                                            Layout.fillWidth: true
                                            radius: 8
                                            color: ThemeManager.panel()
                                            border.color: ThemeManager.border()
                                            border.width: 1
                                            implicitHeight: quarantineProcessDetails.implicitHeight + 22

                                            ColumnLayout {
                                                id: quarantineProcessDetails
                                                anchors.fill: parent
                                                anchors.margins: 11
                                                spacing: 4

                                                Text {
                                                    text: "Process and signer"
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: 11
                                                    font.bold: true
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    text: (modelData.process_name
                                                           ? ("Process: " + modelData.process_name
                                                              + (modelData.pid !== null && modelData.pid !== undefined
                                                                 ? (" (PID " + modelData.pid + ")")
                                                                 : ""))
                                                           : "Process: No process recorded")
                                                          + (modelData.publisher ? ("  Publisher: " + modelData.publisher) : "")
                                                          + (modelData.signature_valid === true
                                                             ? "  Signature: valid"
                                                             : modelData.signature_valid === false
                                                               ? "  Signature: invalid"
                                                               : "")
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 11
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 4

                                            Text {
                                                text: "Enforcement reason"
                                                color: ThemeManager.muted()
                                                font.pixelSize: 11
                                                font.bold: true
                                            }

                                            Text {
                                                text: modelData.action_reason_label
                                                color: ThemeManager.foreground()
                                                font.pixelSize: 12
                                                wrapMode: Text.WordWrap
                                                Layout.fillWidth: true
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 8

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 12

                                                Text {
                                                    text: "Quarantined: " + root.formatTimestamp(modelData.quarantined_at)
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 11
                                                }

                                                Text {
                                                    visible: !!modelData.restored_at
                                                    text: "Restored: " + root.formatTimestamp(modelData.restored_at)
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 11
                                                }

                                                Text {
                                                    visible: !!modelData.deleted_at
                                                    text: "Deleted: " + root.formatTimestamp(modelData.deleted_at)
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 11
                                                }

                                                Item { Layout.fillWidth: true }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 10

                                                Text {
                                                    visible: !modelData.can_restore && !modelData.can_delete
                                                    text: modelData.status === "restored"
                                                          ? "Vault payload already restored. This history entry remains for audit only."
                                                          : modelData.status === "deleted"
                                                            ? "Vault payload permanently removed. This history entry remains for audit only."
                                                            : "No quarantine action is available for this entry."
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 11
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }

                                                Item {
                                                    visible: modelData.can_restore || modelData.can_delete
                                                    Layout.fillWidth: true
                                                }

                                                Button {
                                                    visible: modelData.can_restore
                                                    enabled: modelData.can_restore
                                                    text: "Restore"
                                                    implicitWidth: 88
                                                    implicitHeight: 30
                                                    onClicked: root.queueQuarantineAction("restore", modelData)

                                                    background: Rectangle {
                                                        radius: 8
                                                        color: parent.hovered ? ThemeManager.surface() : ThemeManager.panel()
                                                        border.color: ThemeManager.border()
                                                        border.width: 1
                                                    }

                                                    contentItem: Text {
                                                        text: parent.text
                                                        color: ThemeManager.success
                                                        font.pixelSize: 11
                                                        font.bold: true
                                                        horizontalAlignment: Text.AlignHCenter
                                                        verticalAlignment: Text.AlignVCenter
                                                    }
                                                }

                                                Button {
                                                    visible: modelData.can_delete
                                                    enabled: modelData.can_delete
                                                    text: "Delete Permanently"
                                                    implicitWidth: 146
                                                    implicitHeight: 30
                                                    onClicked: root.queueQuarantineAction("delete", modelData)

                                                    background: Rectangle {
                                                        radius: 8
                                                        color: parent.hovered ? ThemeManager.surface() : ThemeManager.panel()
                                                        border.color: ThemeManager.border()
                                                        border.width: 1
                                                    }

                                                    contentItem: Text {
                                                        text: parent.text
                                                        color: ThemeManager.danger
                                                        font.pixelSize: 11
                                                        font.bold: true
                                                        horizontalAlignment: Text.AlignHCenter
                                                        verticalAlignment: Text.AlignVCenter
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "URL Scan History"
                            color: ThemeManager.foreground()
                            font.pixelSize: 20
                            font.bold: true
                        }

                        Text {
                            text: root.urlItems.length + " entries"
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            text: "Refresh"
                            implicitWidth: 92
                            implicitHeight: 34
                            onClicked: root.refreshUrlHistory()

                            background: Rectangle {
                                radius: 8
                                color: parent.hovered ? ThemeManager.surface() : ThemeManager.panel()
                                border.color: ThemeManager.border()
                                border.width: 1
                            }

                            contentItem: Text {
                                text: parent.text
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_small
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1

                        Item {
                            anchors.fill: parent
                            anchors.margins: 12

                            Text {
                                anchors.centerIn: parent
                                visible: root.urlItems.length === 0
                                text: "No URL scan history recorded yet."
                                color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_body
                            }

                            ListView {
                                anchors.fill: parent
                                visible: root.urlItems.length > 0
                                clip: true
                                spacing: 8
                                model: root.urlItems
                                ScrollBar.vertical: ScrollBar { }

                                delegate: Rectangle {
                                    width: ListView.view.width
                                    implicitHeight: urlRow.implicitHeight + 20
                                    radius: 10
                                    color: ThemeManager.elevated()
                                    border.color: ThemeManager.border()
                                    border.width: 1

                                    ColumnLayout {
                                        id: urlRow
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 6

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8

                                            Text {
                                                text: modelData.target || "(unknown URL)"
                                                color: ThemeManager.foreground()
                                                font.pixelSize: ThemeManager.fontSize_body
                                                font.bold: true
                                                elide: Text.ElideMiddle
                                                Layout.fillWidth: true
                                            }

                                            Rectangle {
                                                radius: 8
                                                implicitHeight: 22
                                                implicitWidth: urlVerdictText.implicitWidth + 16
                                                color: Qt.rgba(
                                                    root.riskColor(modelData.verdict).r,
                                                    root.riskColor(modelData.verdict).g,
                                                    root.riskColor(modelData.verdict).b,
                                                    0.16
                                                )

                                                Text {
                                                    id: urlVerdictText
                                                    anchors.centerIn: parent
                                                    text: modelData.verdict || "Unknown"
                                                    color: root.riskColor(modelData.verdict)
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                }
                                            }
                                        }

                                        Text {
                                            text: "Score " + (modelData.score || 0)
                                                  + "  Status: " + (modelData.status || "unknown")
                                                  + (modelData.has_sandbox ? "  Sandbox: yes" : "")
                                            color: ThemeManager.muted()
                                            font.pixelSize: 11
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            visible: (modelData.threat_types || []).length > 0
                                            text: "Threat types: " + (modelData.threat_types || []).join(", ")
                                            color: ThemeManager.foreground()
                                            font.pixelSize: 12
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            text: root.formatTimestamp(modelData.started_at || modelData.finished_at)
                                            color: ThemeManager.muted()
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
