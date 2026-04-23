import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../theme"
import "../ui"

// ─────────────────────────────────────────────────────────────────────────────
// ScanCenter  –  File Scan | URL Scan | History
// All colours via ThemeManager (light/dark aware).
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: root
    anchors.fill: parent
    readonly property var backend: (typeof Backend !== "undefined") ? Backend : null
    signal requestRoute(string route)
    readonly property var clamAvStatus: backend && backend.clamAvStatus ? backend.clamAvStatus : ({
        available: false,
        status: "unavailable",
        label: "Unavailable",
        detail: "Backend status unavailable"
    })

    // ── Segment: 0 = File Scan  1 = URL Scan  2 = History ─────────────────
    property int segment: 0

    // ── File-scan state ────────────────────────────────────────────────────
    property string filePath:    ""
    property string fileName:    "No file selected"
    property var    fileReport:  null
    property bool   fileScanning: false
    property int    filePct:     0
    property string fileStage:   ""
    property bool   optClamAV:   true
    property bool   optSandbox:  false
    property bool   optExec:     false
    property bool   optGuiAuto:  false   // deprecated: kept for payload compatibility
    property bool   optNet:      true
    property var    explainData: null

    // ── AI Security Analyst Summary (from Groq via orchestrator) ──
    property string aiBriefText: ""
    property string aiDetailedText: ""

    // ── URL-scan state ─────────────────────────────────────────────────────
    property string urlInput:         ""
    property var    urlResult:        null
    property bool   urlScanning:      false
    property int    urlPct:           0
    property string urlStage:         ""
    property bool   urlOptSandbox:    false
    property bool   urlOptBlockDl:    true
    property bool   urlOptBlockPvt:   true

    // ── Agent Timeline replay (report overview sub-tab) ──────────────────
    property bool replayActive:      false
    property int  replayCurrentStep: -1

    // ── Shared helpers ─────────────────────────────────────────────────────
    function riskColor(risk) {
        var r = (risk || "").toLowerCase()
        if (r === "critical" || r === "malicious")        return ThemeManager.danger
        if (r === "high"     || r === "likely_malicious") return "#f97316"
        if (r === "medium"   || r === "suspicious")       return ThemeManager.warning
        if (r === "low"      || r === "clean")            return ThemeManager.success
        return ThemeManager.muted()
    }
    function fmtSize(b) {
        if (!b || b === 0) return "0 B"
        if (b < 1024)    return b + " B"
        if (b < 1048576) return (b / 1024).toFixed(1) + " KB"
        return (b / 1048576).toFixed(2) + " MB"
    }
    function hasSandboxWarnPhase() {
        for (var i = 0; i < phaseModel.count; i++) {
            var row = phaseModel.get(i)
            if (row.phase === "sandbox" && row.status === "warn") return true
        }
        return false
    }

    Component.onCompleted: {
        if (backend && typeof backend.refreshIntegrationStatus === "function") {
            backend.refreshIntegrationStatus()
        }
    }
    function resetReportScrolls() {
        var views = [ovScroll, engScroll, behScroll, iocScroll, exScroll]
        for (var i = 0; i < views.length; i++) {
            var view = views[i]
            if (!view || !view.contentItem)
                continue
            view.contentItem.contentY = 0
            view.contentItem.contentX = 0
        }
    }

    // ── Backend connections ────────────────────────────────────────────────
    Connections {
        target: root.backend
        enabled: target !== null

        // File scan
        function onScanCenterProgress(pct, stage) {
            root.filePct = pct; root.fileStage = stage
        }
        function onScanCenterFinished(r) {
            root.fileReport = r; root.fileScanning = false
            fileSubBar.currentIndex = 0
            Qt.callLater(function() { root.resetReportScrolls() })
            Qt.callLater(function() {
                if (root.aiBriefText === "" && root.fileReport !== null) {
                    var v = (root.fileReport.verdict || {})
                    var fallback = "Scan complete — Risk: " + (v.risk || "Unknown")
                                 + " (Score " + (v.score || 0) + "/100). "
                                 + (v.label || "")
                    root.aiBriefText = fallback.trim()
                }
            })
        }
        function onScanCenterAiBrief(text) {
            root.aiBriefText = text || ""
        }
        function onScanCenterAiDetailed(text) {
            root.aiDetailedText = text || ""
        }
        function onScanCenterFailed(msg) {
            root.fileScanning = false
            errDlg.msg = msg; errDlg.open()
        }
        function onScanCenterHistoryLoaded(rows) {
            histModel.clear()
            for (var i = 0; i < rows.length; i++) histModel.append(rows[i])
        }
        function onScanCenterExplainFinished(ex) {
            explainBusy.running = false
            root.explainData = ex
            // Auto-switch to Explanation tab when AI auto-generates it
            if (root.fileReport !== null && fileSubBar.currentIndex === 0) {
                // Brief delay so user sees Overview first, then show explanation indicator
                // We add a subtle glow on the Explanation tab instead of auto-switching
            }
        }
        function onScanCenterExported(result) {
            if (result.ok) expOkLabel.text = "Exported → " + (result.report_path || "")
        }

        // Agent Timeline — one step per signal emission (cross-thread safe)
        function onAgentStepAdded(stepJson) {
            try {
                var step = JSON.parse(stepJson)
                agentTimelineListModel.append({
                    "ts":             step.ts             || "",
                    "stage":          step.stage          || "",
                    "title":          step.title          || "",
                    "result":         step.result         || "",
                    "status":         step.status         || "ok",
                    "artifact_paths": JSON.stringify(step.artifact_paths || [])
                })
            } catch (_e) {}
        }
        function onAgentStepsCleared() {
            agentTimelineListModel.clear()
            phaseModel.clear()
        }

        // Phase-card updates — emitted by backend for each pipeline phase
        function onScanCenterPhaseUpdate(phaseJson) {
            try {
                var p = JSON.parse(phaseJson)
                var found = false
                for (var i = 0; i < phaseModel.count; i++) {
                    if (phaseModel.get(i).phase === p.phase) {
                        phaseModel.set(i, {
                            phase:   p.phase,
                            status:  p.status,
                            summary: p.summary || "",
                            score:   p.score !== undefined ? p.score : -1
                        })
                        found = true
                        break
                    }
                }
                if (!found) {
                    phaseModel.append({
                        phase:   p.phase,
                        status:  p.status,
                        summary: p.summary || "",
                        score:   p.score !== undefined ? p.score : -1
                    })
                }
            } catch (_e) {}
        }

        // URL scan
        function onUrlScanStarted() {
            root.urlScanning = true; root.urlPct = 0; root.urlStage = "Starting…"
        }
        function onUrlScanProgress(stage, pct) {
            root.urlStage = stage; root.urlPct = pct
        }
        function onUrlScanFinished(r) {
            root.urlResult = r; root.urlScanning = false; root.urlPct = 100
        }
    }

    // ListModel for agent timeline (kept for phase-card lookups)
    ListModel { id: agentTimelineListModel }

    // ── Overlays / dialogs ─────────────────────────────────────────────────
    // Execute-mode confirmation dialog
    SentinelDialog {
        id: execConfirmDlg
        
        titleText: "Allow Sample Execution"
        iconText: "⚠"
        iconColor: ThemeManager.warning
        iconBgColor: Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.15)
        
        bodyText: "<b>This will run the sample inside an isolated VM.</b><br><br>Only proceed if you trust your sandbox environment and understand that the sample will execute with its normal code path."
        
        primaryButtonText: "Yes"
        secondaryButtonText: "No"
        primaryButtonColor: ThemeManager.warning
        
        onAccepted: {
            root.optExec = true
        }
        onRejected: {
            root.optExec = false
            root.optGuiAuto = false
        }
    }

    SentinelDialog {
        id: errDlg
        property string msg: ""
        
        titleText: "Scan Failed"
        iconText: "⚠"
        iconColor: ThemeManager.danger
        iconBgColor: Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.15)
        
        bodyText: errDlg.msg
        primaryButtonText: "OK"
        showSecondaryButton: false
    }

    FileDialog {
        id: filePicker
        title: "Select file to scan"
        fileMode: FileDialog.OpenFile
        onAccepted: {
            var s = selectedFile.toString()
            // Strip file:// prefix and decode URI-encoded characters
            if (root.backend && root.backend.isLinux) {
                // Linux: file:///home/… → /home/…
                s = s.replace(/^file:\/\//i, "")
                s = decodeURIComponent(s)
            } else {
                // Windows: file:///C:/… → C:\…
                s = s.replace(/^file:\/\/\//i, "")
                     .replace(/\//g, "\\")
            }
            root.filePath   = s
            root.fileName   = s.split(/[\\\/]/).pop()
            root.fileReport = null
            root.filePct    = 0
            root.explainData = null
            root.aiBriefText = ""
            root.aiDetailedText = ""
            fileSubBar.currentIndex = 0
            Qt.callLater(function() { root.resetReportScrolls() })
        }
    }

    ListModel { id: histModel }
    ListModel { id: phaseModel }   // Phase-card tracker: {phase, status, summary, score}

    // ══════════════════════════════════════════════════════════════════════
    //  Root column
    // ══════════════════════════════════════════════════════════════════════
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Top segment selector ──────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 44
            color: ThemeManager.panel()

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left; anchors.right: parent.right
                height: 1; color: ThemeManager.border()
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16; anchors.rightMargin: 16
                spacing: 0

                Repeater {
                    model: ["📄  File Scan", "🌐  URL Scan", "📋  History"]
                    Rectangle {
                        implicitWidth: 136; Layout.fillHeight: true
                        color: "transparent"
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left; anchors.right: parent.right
                            height: 2
                            color: root.segment === index ? ThemeManager.accent : "transparent"
                            Behavior on color { ColorAnimation { duration: 140 } }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            font.pixelSize: ThemeManager.fontSize_body
                            font.weight: root.segment === index ? (Font.SemiBold || 600) : (Font.Normal || 400)
                            color: root.segment === index
                                   ? ThemeManager.foreground()
                                   : ThemeManager.muted()
                            Behavior on color { ColorAnimation { duration: 140 } }
                        }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (index === 2) {
                                    root.requestRoute("history-scan")
                                    return
                                }
                                root.segment = index
                            }
                            Rectangle {
                                anchors.fill: parent
                                color: parent.containsMouse
                                       ? Qt.rgba(0.5, 0.5, 0.5, 0.06)
                                       : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
            }
        }

        // ── Main content StackLayout ──────────────────────────────────────
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.segment

            // ██████████████████████████████████████████████████████████████
            // [0]  FILE SCAN
            // ██████████████████████████████████████████████████████████████
            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // ── Control bar ───────────────────────────────────────
                    ColumnLayout {
                        id: ctrlBar
                        Layout.fillWidth: true
                        spacing: 0

                        // top padding
                        Item { Layout.fillWidth: true; height: 12 }

                        // ── Row 1: file picker ────────────────────────────
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.preferredHeight: 40
                            spacing: 8

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40
                                color: ThemeManager.surface()
                                radius: 8
                                border.color: fDrop.containsDrag ? ThemeManager.accent : ThemeManager.border()
                                border.width: fDrop.containsDrag ? 2 : 1
                                Behavior on border.color { ColorAnimation { duration: 140 } }

                                DropArea {
                                    id: fDrop
                                    anchors.fill: parent
                                    onDropped: {
                                        if (drop.urls.length > 0) {
                                            var s = drop.urls[0].toString()
                                            if (root.backend && root.backend.isLinux) {
                                                s = s.replace(/^file:\/\//i, "")
                                                s = decodeURIComponent(s)
                                            } else {
                                                s = s.replace(/^file:\/\/\//i, "")
                                                     .replace(/\//g, "\\")
                                            }
                                            root.filePath   = s
                                            root.fileName   = s.split(/[\\\/]/).pop()
                                            root.fileReport = null
                                            root.filePct    = 0
                                            root.explainData = null
                                            root.aiBriefText = ""
                                            root.aiDetailedText = ""
                                        }
                                    }
                                }
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10; anchors.rightMargin: 6
                                    spacing: 6
                                    Text { text: "📄"; font.pixelSize: 14 }
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.filePath !== ""
                                              ? root.filePath
                                              : "Drop a file here or click Choose…"
                                        color: root.filePath !== ""
                                               ? ThemeManager.foreground()
                                               : ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_body
                                        elide: Text.ElideMiddle
                                    }
                                }
                                MouseArea { anchors.fill: parent; onClicked: filePicker.open() }
                            }

                            Button {
                                text: "Choose…"; flat: true
                                Layout.preferredWidth: 90
                                Layout.preferredHeight: 40
                                onClicked: filePicker.open()
                                contentItem: Text {
                                    text: parent.text; color: ThemeManager.accent
                                    font.pixelSize: ThemeManager.fontSize_body
                                    wrapMode: Text.NoWrap
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    color: parent.parent.hovered ? ThemeManager.surface() : "transparent"
                                    radius: 8
                                }
                            }

                            Button {
                                id: fScanBtn
                                text: root.fileScanning ? "Scanning…" : "Scan"
                                enabled: root.filePath !== "" && !root.fileScanning
                                Layout.preferredWidth: 84
                                Layout.preferredHeight: 40
                                contentItem: Text {
                                    text: fScanBtn.text
                                    color: fScanBtn.enabled ? ThemeManager.selectionForeground : ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    font.weight: (Font.SemiBold || 600)
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    color: fScanBtn.enabled
                                           ? (fScanBtn.pressed ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent)
                                           : ThemeManager.surface()
                                    radius: 8
                                    Behavior on color { ColorAnimation { duration: 120 } }
                                }
                                onClicked: {
                                    root.fileScanning = true
                                    root.filePct = 0
                                    root.fileStage = "Preparing…"
                                    root.explainData = null
                                    root.aiBriefText = ""
                                    root.aiDetailedText = ""
                                    if (root.backend)
                                        root.backend.startScanCenter(root.filePath,
                                            JSON.stringify({
                                                use_sandbox:     root.optSandbox,
                                                allow_execution: root.optExec,
                                                disable_network: root.optNet,
                                                run_clamav:      root.optClamAV,
                                                use_visible_gui: false
                                            }))
                                }
                            }

                            Button {
                                visible: root.fileScanning
                                text: "✕"; flat: true
                                Layout.preferredWidth: 36
                                Layout.preferredHeight: 40
                                contentItem: Text {
                                    text: parent.text; color: ThemeManager.danger
                                    font.pixelSize: ThemeManager.fontSize_h4
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    color: parent.parent.hovered ? Qt.rgba(1, 0, 0, .1) : "transparent"
                                    radius: 8
                                }
                                onClicked: {
                                    if (root.backend) root.backend.cancelScanCenter()
                                    root.fileScanning = false
                                }
                            }
                        } // Row 1

                        // ── Row 2a: ClamAV + VMware Sandbox ──────────────
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.preferredHeight: 32
                            spacing: 24

                            CheckBox {
                                id: ckClamAV
                                property bool clamAvInstalled: root.clamAvStatus.available === true
                                implicitWidth: ckClamAVLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optClamAV && clamAvInstalled
                                enabled: clamAvInstalled && !root.fileScanning
                                opacity: (!clamAvInstalled || root.fileScanning) ? 0.45 : 1.0
                                onToggled: { if (!root.fileScanning && clamAvInstalled) root.optClamAV = checked }
                                indicator: Rectangle {
                                    width: 16; height: 16
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    radius: 3
                                    color: ckClamAV.checked ? ThemeManager.accent : ThemeManager.surface()
                                    border.color: ckClamAV.checked ? ThemeManager.accent : ThemeManager.border()
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"; color: "white"
                                        font.pixelSize: ThemeManager.fontSize_small
                                        visible: ckClamAV.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckClamAVLabel
                                    leftPadding: 24
                                    text: "ClamAV (" + (root.clamAvStatus.label || "Unavailable") + ")"
                                    color: ckClamAV.clamAvInstalled ? ThemeManager.foreground() : ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    verticalAlignment: Text.AlignVCenter
                                }
                                ToolTip.visible: clamAVHover.hovered
                                ToolTip.text: root.clamAvStatus.detail || "ClamAV status unavailable"
                                ToolTip.delay: 400
                                HoverHandler { id: clamAVHover }
                            }

                            CheckBox {
                                id: ckSandbox
                                implicitWidth: ckSandboxLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optSandbox
                                enabled: true
                                opacity: root.fileScanning ? 0.4 : 1.0
                                visible: root.backend ? !root.backend.isLinux : true
                                onToggled: {
                                    if (root.fileScanning) return
                                    root.optSandbox = checked
                                    if (checked) {
                                        // Sandbox option now points to interactive session workflow.
                                        root.optExec = true
                                        root.optGuiAuto = false
                                    } else {
                                        root.optExec = false
                                        root.optGuiAuto = false
                                    }
                                }
                                indicator: Rectangle {
                                    width: 16; height: 16
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    radius: 3
                                    color: ckSandbox.checked ? ThemeManager.accent : ThemeManager.surface()
                                    border.color: ckSandbox.checked ? ThemeManager.accent : ThemeManager.border()
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"; color: "white"
                                        font.pixelSize: ThemeManager.fontSize_small
                                        visible: ckSandbox.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckSandboxLabel
                                    leftPadding: 24
                                    text: "VMware Sandbox"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Item { Layout.fillWidth: true }
                        } // Row 2a

                        // ── Row 2b: Allow execution + Disable guest network (Windows only)
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.preferredHeight: (root.backend && root.backend.isLinux) ? 0 : 32
                            visible: root.backend ? !root.backend.isLinux : true
                            spacing: 24

                            CheckBox {
                                id: ckExec
                                implicitWidth: ckExecLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optExec
                                enabled: root.optSandbox && !root.fileScanning
                                opacity: (root.optSandbox && !root.fileScanning) ? 1.0 : 0.4
                                onToggled: {
                                    if (root.fileScanning) return
                                    if (checked) {
                                        execConfirmDlg.open()
                                    } else {
                                        root.optExec = false
                                    }
                                }
                                indicator: Rectangle {
                                    width: 16; height: 16
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    radius: 3
                                    color: ckExec.checked ? ThemeManager.accent : ThemeManager.surface()
                                    border.color: ckExec.checked ? ThemeManager.accent : ThemeManager.border()
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"; color: "white"
                                        font.pixelSize: ThemeManager.fontSize_small
                                        visible: ckExec.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckExecLabel
                                    leftPadding: 24
                                    text: "Allow execution"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            CheckBox {
                                id: ckNet
                                implicitWidth: ckNetLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optNet
                                enabled: root.optSandbox
                                opacity: (root.optSandbox && !root.fileScanning) ? 1.0 : 0.4
                                onToggled: { if (!root.fileScanning) root.optNet = checked }
                                indicator: Rectangle {
                                    width: 16; height: 16
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    radius: 3
                                    color: ckNet.checked ? ThemeManager.accent : ThemeManager.surface()
                                    border.color: ckNet.checked ? ThemeManager.accent : ThemeManager.border()
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"; color: "white"
                                        font.pixelSize: ThemeManager.fontSize_small
                                        visible: ckNet.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckNetLabel
                                    leftPadding: 24
                                    text: "Disable guest network"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Item { Layout.fillWidth: true }
                        } // Row 2b

                        // ── Row 2c: Interactive session guidance ──
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.preferredHeight: 0
                            visible: false
                            spacing: 24
                            clip: true
                            Behavior on Layout.preferredHeight { NumberAnimation { duration: 160 } }

                            CheckBox {
                                id: ckGuiAuto
                                implicitWidth: ckGuiAutoLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optGuiAuto
                                enabled: false
                                opacity: root.optSandbox ? 0.7 : 0.4
                                indicator: Rectangle {
                                    width: 16; height: 16
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    radius: 3
                                    color: ckGuiAuto.checked ? ThemeManager.accent : ThemeManager.surface()
                                    border.color: ckGuiAuto.checked ? ThemeManager.accent : ThemeManager.border()
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"; color: "white"
                                        font.pixelSize: ThemeManager.fontSize_small
                                        visible: ckGuiAuto.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckGuiAutoLabel
                                    leftPadding: 24
                                    text: "Auto detonation disabled. Use Sandbox Lab Interactive Session."
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Item { Layout.fillWidth: true }
                        } // Row 2c

                        // bottom padding + divider
                        Item { Layout.fillWidth: true; height: 8 }
                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: ThemeManager.border()
                        }
                    } // ColumnLayout ctrlBar

                    // ── Progress strip ────────────────────────────────────
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: root.fileScanning ? 32 : 0
                        visible: root.fileScanning
                        color: ThemeManager.surface(); clip: true
                        Behavior on implicitHeight { NumberAnimation { duration: 160 } }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16; anchors.rightMargin: 16
                            spacing: 10
                            Text {
                                text: root.fileStage; color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_small
                                Layout.preferredWidth: 180; elide: Text.ElideRight
                            }
                            ProgressBar { Layout.fillWidth: true; value: root.filePct / 100 }
                            Text {
                                text: root.filePct + "%"; color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_small
                                Layout.preferredWidth: 34
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }

                    // ── Phase Cards ───────────────────────────────────────
                    // 4 mini-cards showing live status of each pipeline phase
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: phaseModel.count > 0 ? (root.hasSandboxWarnPhase() ? 112 : phaseRow.implicitHeight + 20) : 0
                        visible: phaseModel.count > 0
                        color: ThemeManager.panel(); clip: true
                        Behavior on implicitHeight { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

                        RowLayout {
                            id: phaseRow
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 16; anchors.rightMargin: 16
                            spacing: 8

                            Repeater {
                                model: phaseModel
                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    visible: !(model.phase === "sandbox" && (root.backend ? root.backend.isLinux : false))
                                    implicitHeight: (model.phase === "sandbox" && model.status === "warn") ? 86 : 58
                                    radius: 8
                                    color: ThemeManager.surface()
                                    border.width: 1
                                    border.color: {
                                        if (model.status === "done") return ThemeManager.success
                                        if (model.status === "running") return ThemeManager.accent
                                        if (model.status === "error" || model.status === "warn") return ThemeManager.warning
                                        return ThemeManager.border()
                                    }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }

                                    ColumnLayout {
                                        anchors.fill: parent; anchors.margins: 8
                                        spacing: 4

                                        RowLayout {
                                            spacing: 6
                                            // Status icon
                                            Text {
                                                text: {
                                                    if (model.status === "done") return "✅"
                                                    if (model.status === "running") return "⏳"
                                                    if (model.status === "error") return "❌"
                                                    if (model.status === "warn") return "⚠️"
                                                    return "⏸"
                                                }
                                                font.pixelSize: ThemeManager.fontSize_body
                                            }
                                            // Phase name
                                            Text {
                                                text: {
                                                    var names = {
                                                        "static": "Static Analysis",
                                                        "iocs": "IOC Extraction",
                                                        "sandbox": "Sandbox",
                                                        "verdict": "Verdict"
                                                    }
                                                    return names[model.phase] || model.phase
                                                }
                                                color: ThemeManager.foreground()
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.weight: (Font.SemiBold || 600)
                                            }
                                            Item { Layout.fillWidth: true }
                                            // Spinner for running phase
                                            BusyIndicator {
                                                visible: model.status === "running"
                                                implicitWidth: 14; implicitHeight: 14
                                                running: visible
                                            }
                                        }
                                        // Summary text
                                        Text {
                                            text: model.summary || (model.status === "pending" ? "Waiting…" : "")
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_caption
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }

                                        RowLayout {
                                            visible: model.phase === "sandbox" && model.status === "warn"
                                            Layout.fillWidth: true
                                            spacing: 8

                                            Button {
                                                text: "Open Sandbox Lab"
                                                implicitHeight: 24
                                                onClicked: {
                                                    if (root.backend) {
                                                        root.backend.openSandboxLabForFile(root.filePath)
                                                    }
                                                }
                                            }

                                            Button {
                                                text: "Open File Folder"
                                                implicitHeight: 24
                                                onClicked: {
                                                    if (root.backend) {
                                                        root.backend.openFileParentFolder(root.filePath)
                                                    }
                                                }
                                            }

                                            Item { Layout.fillWidth: true }
                                        }
                                    }

                                    // Subtle glow / pulse for running state
                                    SequentialAnimation on opacity {
                                        loops: Animation.Infinite
                                        running: model.status === "running"
                                        NumberAnimation { to: 0.7; duration: 700 }
                                        NumberAnimation { to: 1.0; duration: 700 }
                                    }
                                }
                            }
                        }
                    }

                    // (Sandbox preview + timeline + frames playback moved to Sandbox Lab theater tab)

                    // ── Verdict bar ───────────────────────────────────────
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: root.fileReport !== null ? 44 : 0
                        visible: root.fileReport !== null
                        color: ThemeManager.panel(); clip: true
                        Behavior on implicitHeight { NumberAnimation { duration: 160 } }

                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left; anchors.right: parent.right
                            height: 2
                            color: root.fileReport
                                   ? root.riskColor(((root.fileReport.verdict) || {}).risk || "")
                                   : "transparent"
                        }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16; anchors.rightMargin: 16
                            spacing: 12
                            Rectangle {
                                visible: root.fileReport !== null
                                implicitWidth: fRiskLbl.implicitWidth + 18
                                implicitHeight: 24; radius: 12
                                color: root.fileReport
                                       ? root.riskColor(((root.fileReport.verdict) || {}).risk || "")
                                       : "transparent"
                                Text {
                                    id: fRiskLbl; anchors.centerIn: parent
                                    text: root.fileReport
                                          ? (((root.fileReport.verdict) || {}).risk || "").toUpperCase()
                                          : ""
                                    color: "#ffffff"
                                    font.pixelSize: 10; font.weight: (Font.Bold || 700)
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: root.fileReport
                                      ? (((root.fileReport.ai_explanation) || {}).one_line_summary
                                         || ((root.fileReport.verdict) || {}).label || "")
                                      : ""
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                elide: Text.ElideRight
                            }
                            Text {
                                visible: root.fileReport !== null
                                text: "Score: " + (((root.fileReport || {}).verdict || {}).score || 0) + " / 100"
                                color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_small
                            }
                            Text {
                                visible: root.fileReport !== null
                                text: "⏱ " + Math.round(((root.fileReport || {}).job || {}).duration_sec || 0) + "s"
                                color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_small
                            }
                        }
                    }

                    // ── Sub-tab bar ───────────────────────────────────────
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 38
                        color: ThemeManager.panel()
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left; anchors.right: parent.right
                            height: 1; color: ThemeManager.border()
                        }
                        TabBar {
                            id: fileSubBar
                            anchors.fill: parent
                            background: Rectangle { color: "transparent" }
                            Repeater {
                                model: ["Overview", "Engines", "Behavior", "IOCs", "Explanation", "\uD83D\uDCE1 Timeline"]
                                TabButton {
                                    text: modelData
                                    font.pixelSize: ThemeManager.fontSize_small
                                    implicitWidth: 102; implicitHeight: 38
                                    contentItem: Text {
                                        text: parent.text
                                        color: parent.checked ? ThemeManager.foreground() : ThemeManager.muted()
                                        font: parent.font
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                    }
                                    background: Rectangle {
                                        color: "transparent"
                                        Rectangle {
                                            anchors.bottom: parent.bottom
                                            anchors.left: parent.left; anchors.right: parent.right
                                            height: 2
                                            color: parent.parent.checked ? ThemeManager.accent : "transparent"
                                            Behavior on color { ColorAnimation { duration: 140 } }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ── Sub-tab StackLayout ───────────────────────────────
                    StackLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        currentIndex: fileSubBar.currentIndex

                        // ┄┄ Overview ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
                        ScrollView {
                            id: ovScroll; clip: true

                            ColumnLayout {
                                width: Math.min(860, ovScroll.availableWidth - 32)
                                x: Math.max(16, (ovScroll.availableWidth - width) / 2)
                                spacing: 12

                                Item { height: 10 }

                                // Empty state
                                Item {
                                    visible: root.fileReport === null && !root.fileScanning
                                    Layout.fillWidth: true; implicitHeight: 200
                                    ColumnLayout {
                                        anchors.centerIn: parent; spacing: 10
                                        Text { text: "🔍"; font.pixelSize: 48; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                                        Text { text: "No file scanned yet"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; Layout.alignment: Qt.AlignHCenter }
                                    }
                                }

                                // File info card
                                Rectangle {
                                    visible: root.fileReport !== null
                                    Layout.fillWidth: true
                                    implicitHeight: ovFiCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10
                                    border.color: ThemeManager.border(); border.width: 1

                                    ColumnLayout {
                                        id: ovFiCol
                                        anchors.left: parent.left; anchors.right: parent.right
                                        anchors.top: parent.top; anchors.margins: 14
                                        spacing: 10

                                        Text { text: "File Information"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }

                                        GridLayout {
                                            Layout.fillWidth: true
                                            columns: 2
                                            columnSpacing: 24; rowSpacing: 8

                                            Repeater {
                                                model: [
                                                    ["Name",      ((root.fileReport || {}).file || {}).name      || "—"],
                                                    ["Type",      ((root.fileReport || {}).file || {}).file_type || "—"],
                                                    ["Size",      root.fileReport ? root.fmtSize(((root.fileReport || {}).file || {}).size_bytes || 0) : "—"],
                                                    ["Signed",    ((root.fileReport || {}).file || {}).signed === true  ? "Yes ✓"
                                                                : ((root.fileReport || {}).file || {}).signed === false ? "No" : "Unknown"],
                                                    ["SHA-256",   ((root.fileReport || {}).file || {}).sha256    || "—"],
                                                    ["MD5",       ((root.fileReport || {}).file || {}).md5       || "—"],
                                                    ["Publisher", ((root.fileReport || {}).file || {}).publisher || "—"],
                                                ]
                                                ColumnLayout {
                                                    spacing: 2; Layout.fillWidth: true
                                                    Text { text: modelData[0]; color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.Medium || 500) }
                                                    Text { text: modelData[1]; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                                }
                                            }
                                        }
                                    }
                                }

                                // Findings card
                                Rectangle {
                                    visible: root.fileReport !== null
                                    Layout.fillWidth: true
                                    implicitHeight: ovFndCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10
                                    border.color: ThemeManager.border(); border.width: 1

                                    ColumnLayout {
                                        id: ovFndCol
                                        anchors.left: parent.left; anchors.right: parent.right
                                        anchors.top: parent.top; anchors.margins: 14
                                        spacing: 8

                                        Text { text: "Top Findings"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: {
                                                var v = ((root.fileReport || {}).verdict || {}).reasons || []
                                                return v.length > 0 ? v : ["No significant findings"]
                                            }
                                            RowLayout {
                                                spacing: 8; Layout.fillWidth: true
                                                Text { text: "•"; color: root.fileReport ? root.riskColor(((root.fileReport.verdict) || {}).risk || "") : ThemeManager.muted(); font.pixelSize: 16 }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

                                // ── Risk Score Gauge ──────────────────────────
                                Rectangle {
                                    visible: root.fileReport !== null
                                    Layout.fillWidth: true
                                    implicitHeight: 240
                                    color: ThemeManager.panel(); radius: 10
                                    border.color: ThemeManager.border(); border.width: 1

                                    property int scoreVal: {
                                        var r = root.fileReport
                                        if (!r || !r.verdict) return 0
                                        return r.verdict.score || 0
                                    }
                                    property string riskLabel: {
                                        var r = root.fileReport
                                        if (!r || !r.verdict) return "Unknown"
                                        return r.verdict.risk || "Unknown"
                                    }
                                    property real animatedScore: 0
                                    NumberAnimation on animatedScore {
                                        id: gaugeAnim
                                        from: 0; to: parent.scoreVal !== undefined ? parent.scoreVal : 0
                                        duration: 900
                                        easing.type: Easing.OutCubic
                                    }
                                    Component.onCompleted: gaugeAnim.start()
                                    onScoreValChanged: { gaugeAnim.from = 0; gaugeAnim.to = scoreVal; gaugeAnim.restart() }

                                    ColumnLayout {
                                        anchors.centerIn: parent
                                        spacing: 4

                                        // Canvas arc gauge
                                        Item {
                                            Layout.alignment: Qt.AlignHCenter
                                            implicitWidth: 160; implicitHeight: 110

                                            Canvas {
                                                id: gaugeCanvas
                                                anchors.fill: parent
                                                property real pct: parent.parent.parent.animatedScore / 100

                                                onPctChanged: requestPaint()
                                                onPaint: {
                                                    var ctx = getContext("2d")
                                                    ctx.reset()
                                                    var cx = width / 2
                                                    var cy = height - 10
                                                    var r  = Math.min(cx, cy) - 12
                                                    var startA = Math.PI    // 180° (left)
                                                    var endA   = 2 * Math.PI // 360° (right)

                                                    // Background track
                                                    ctx.beginPath()
                                                    ctx.arc(cx, cy, r, startA, endA)
                                                    ctx.lineWidth = 14
                                                    ctx.strokeStyle = ThemeManager.surface()
                                                    ctx.lineCap = "round"
                                                    ctx.stroke()

                                                    // Colored arc
                                                    var sweepAngle = startA + (endA - startA) * Math.min(1, Math.max(0, pct))
                                                    if (pct > 0) {
                                                        ctx.beginPath()
                                                        ctx.arc(cx, cy, r, startA, sweepAngle)
                                                        ctx.lineWidth = 14
                                                        ctx.lineCap = "round"
                                                        // Gradient from green → yellow → orange → red
                                                        var sc = parent.parent.parent.scoreVal
                                                        if (sc >= 70) ctx.strokeStyle = ThemeManager.danger
                                                        else if (sc >= 40) ctx.strokeStyle = "#f97316"
                                                        else if (sc >= 20) ctx.strokeStyle = ThemeManager.warning
                                                        else ctx.strokeStyle = ThemeManager.success
                                                        ctx.stroke()
                                                    }
                                                }
                                            }

                                            // Score number centered in the arc
                                            Text {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                anchors.bottom: parent.bottom
                                                anchors.bottomMargin: 14
                                                text: Math.round(parent.parent.parent.animatedScore)
                                                color: ThemeManager.foreground()
                                                font.pixelSize: 38
                                                font.weight: Font.Bold
                                            }
                                        }

                                        // "/ 100" subtitle
                                        Text {
                                            Layout.alignment: Qt.AlignHCenter
                                            text: "/ 100"
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                        }

                                        // Risk badge
                                        Rectangle {
                                            Layout.alignment: Qt.AlignHCenter
                                            implicitWidth: gaugeBadgeText.implicitWidth + 20
                                            implicitHeight: 26; radius: 13
                                            color: root.fileReport
                                                   ? root.riskColor(((root.fileReport.verdict) || {}).risk || "")
                                                   : "transparent"
                                            Text {
                                                id: gaugeBadgeText; anchors.centerIn: parent
                                                text: (((root.fileReport || {}).verdict || {}).risk || "").toUpperCase()
                                                color: "#ffffff"
                                                font.pixelSize: 11; font.weight: Font.Bold
                                            }
                                        }

                                        // Label underneath
                                        Text {
                                            Layout.alignment: Qt.AlignHCenter
                                            text: ((root.fileReport || {}).verdict || {}).label || ""
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                        }
                                    }
                                }

                                // ── AI Brief (1-sentence Groq summary + Show More) ─
                                Rectangle {
                                    visible: root.aiBriefText !== ""
                                    Layout.fillWidth: true
                                    implicitHeight: aiBriefCol.implicitHeight + 28
                                    radius: 12
                                    color: Qt.rgba(ThemeManager.accent.r || 0.2,
                                                   ThemeManager.accent.g || 0.5,
                                                   ThemeManager.accent.b || 1.0, 0.06)
                                    border.width: 1.5
                                    border.color: Qt.rgba(ThemeManager.accent.r || 0.2,
                                                          ThemeManager.accent.g || 0.5,
                                                          ThemeManager.accent.b || 1.0, 0.35)

                                    ColumnLayout {
                                        id: aiBriefCol
                                        anchors.left: parent.left; anchors.right: parent.right
                                        anchors.top: parent.top; anchors.margins: 14
                                        spacing: 8

                                        RowLayout {
                                            spacing: 8
                                            Text { text: "🛡️"; font.pixelSize: 18 }
                                            Text {
                                                text: "AI Security Analyst Summary"
                                                color: ThemeManager.foreground()
                                                font.pixelSize: ThemeManager.fontSize_body
                                                font.weight: (Font.Bold || 700)
                                            }
                                        }

                                        Rectangle {
                                            Layout.fillWidth: true
                                            implicitHeight: 1
                                            color: Qt.rgba(ThemeManager.accent.r || 0.2,
                                                           ThemeManager.accent.g || 0.5,
                                                           ThemeManager.accent.b || 1.0, 0.2)
                                        }

                                        Text {
                                            text: root.aiBriefText
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_body
                                            lineHeight: 1.5
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                        }

                                        Button {
                                            id: showMoreButton
                                            visible: root.aiDetailedText !== ""
                                            text: "Show More \u2192"
                                            flat: true
                                            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                                            leftPadding: 10
                                            rightPadding: 10
                                            topPadding: 6
                                            bottomPadding: 6
                                            implicitWidth: showMoreLabel.implicitWidth + leftPadding + rightPadding
                                            implicitHeight: showMoreLabel.implicitHeight + topPadding + bottomPadding
                                            contentItem: Text {
                                                id: showMoreLabel
                                                text: showMoreButton.text
                                                color: ThemeManager.accent
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.weight: (Font.SemiBold || 600)
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            background: Rectangle {
                                                color: showMoreButton.hovered ? ThemeManager.surface() : "transparent"
                                                radius: 6
                                            }
                                            onClicked: root.requestRoute("ai-report")
                                        }
                                    }
                                }
                                Item { height: 18 }


                                // Score Breakdown card
                                Rectangle {
                                    visible: root.fileReport !== null && typeof (((root.fileReport || {}).verdict || {}).breakdown) === "object"
                                    Layout.fillWidth: true
                                    implicitHeight: ovBdCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10
                                    border.color: ThemeManager.border(); border.width: 1

                                    ColumnLayout {
                                        id: ovBdCol
                                        anchors.left: parent.left; anchors.right: parent.right
                                        anchors.top: parent.top; anchors.margins: 14
                                        spacing: 10

                                        Text { text: "Score Breakdown"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }

                                        // Total score bar
                                        RowLayout {
                                            Layout.fillWidth: true; spacing: 10
                                            Text { text: "TOTAL"; color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.Bold || 700); Layout.preferredWidth: 120 }
                                            Rectangle {
                                                Layout.fillWidth: true; implicitHeight: 10; radius: 5
                                                color: ThemeManager.surface()
                                                Rectangle {
                                                    width: parent.width * Math.max(0, Math.min(1, (((root.fileReport || {}).verdict || {}).score || 0) / 100))
                                                    height: parent.height; radius: 5
                                                    color: root.riskColor(((root.fileReport || {}).verdict || {}).risk || "")
                                                    Behavior on width { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }
                                                }
                                            }
                                            Text { text: String((((root.fileReport || {}).verdict || {}).score || 0)) + "/100"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 48; horizontalAlignment: Text.AlignRight }
                                        }

                                        // Source rows
                                        Repeater {
                                            model: {
                                                var bd = (((root.fileReport || {}).verdict || {}).breakdown) || {}
                                                var order = ["clamav", "sandbox"]
                                                var nice  = { clamav: "ClamAV (Static)", sandbox: "Sandbox (Dynamic)" }
                                                var out = []
                                                for (var i = 0; i < order.length; i++) {
                                                    var k = order[i]
                                                    var src = bd[k] || {}
                                                    out.push({
                                                        name:  nice[k],
                                                        score: src.score !== undefined ? src.score : -1,
                                                        avail: src.available === true,
                                                        wt:    src.weight !== undefined ? Math.round(src.weight * 100) : 0
                                                    })
                                                }
                                                return out
                                            }
                                            RowLayout {
                                                Layout.fillWidth: true; spacing: 10
                                                Text {
                                                    text: modelData.name
                                                    color: modelData.avail ? ThemeManager.foreground() : ThemeManager.muted()
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    Layout.preferredWidth: 120
                                                }
                                                Rectangle {
                                                    Layout.fillWidth: true; implicitHeight: 6; radius: 3
                                                    color: ThemeManager.surface()
                                                    visible: modelData.avail
                                                    Rectangle {
                                                        width: parent.width * Math.max(0, Math.min(1, (modelData.score || 0) / 100))
                                                        height: parent.height; radius: 3
                                                        color: {
                                                            var s = modelData.score || 0
                                                            if (s >= 70) return ThemeManager.danger
                                                            if (s >= 40) return ThemeManager.warning
                                                            if (s >= 20) return "#f97316"
                                                            return ThemeManager.success
                                                        }
                                                        Behavior on width { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }
                                                    }
                                                }
                                                Text {
                                                    visible: !modelData.avail
                                                    text: "N/A"
                                                    color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_caption
                                                    Layout.fillWidth: true
                                                }
                                                Text {
                                                    text: modelData.avail ? (modelData.score + "/100") : ""
                                                    color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_caption
                                                    Layout.preferredWidth: 48; horizontalAlignment: Text.AlignRight
                                                }
                                                Text {
                                                    text: modelData.avail ? (modelData.wt + "%") : ""
                                                    color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_caption
                                                    Layout.preferredWidth: 34; horizontalAlignment: Text.AlignRight
                                                }
                                            }
                                        }
                                    }
                                }

                                Item { height: 24 }
                            }
                        }

                        ScrollView {
                            id: engScroll; clip: true

                            ColumnLayout {
                                width: Math.min(860, engScroll.availableWidth - 32)
                                x: Math.max(16, (engScroll.availableWidth - width) / 2)
                                spacing: 8

                                Item { height: 10 }

                                // Empty
                                Item {
                                    visible: root.fileReport === null
                                    Layout.fillWidth: true; implicitHeight: 160
                                    ColumnLayout { anchors.centerIn: parent; spacing: 8
                                        Text { text: "🛡️"; font.pixelSize: 44; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                                        Text { text: "No scan results"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; Layout.alignment: Qt.AlignHCenter }
                                    }
                                }

                                // Header row
                                Rectangle {
                                    visible: root.fileReport !== null
                                    Layout.fillWidth: true; implicitHeight: 30
                                    color: ThemeManager.surface(); radius: 6
                                    RowLayout {
                                        anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 0
                                        Text { text: "Engine";  color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 170 }
                                        Text { text: "Status";  color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 100 }
                                        Text { text: "Score";   color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 58 }
                                        Text { text: "Details"; color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.fillWidth: true }
                                        Text { text: "ms";      color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 52; horizontalAlignment: Text.AlignRight }
                                    }
                                }

                                // Engine rows
                                Repeater {
                                    model: root.fileReport ? (((root.fileReport.static) || {}).engines || []) : []
                                    Rectangle {
                                        Layout.fillWidth: true; implicitHeight: 40
                                        color: index % 2 === 0 ? "transparent" : ThemeManager.surface()
                                        radius: 6
                                        RowLayout {
                                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 0
                                            Text { text: modelData.name || ""; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; font.weight: (Font.Medium || 500); Layout.preferredWidth: 170; elide: Text.ElideRight }
                                            Item {
                                                Layout.preferredWidth: 100
                                                Rectangle {
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    implicitWidth: engStTxt.implicitWidth + 14; implicitHeight: 20; radius: 10
                                                    color: {
                                                        var s = (modelData.status || "").toLowerCase()
                                                        if (s === "detected") return Qt.rgba(ThemeManager.danger.r,  ThemeManager.danger.g,  ThemeManager.danger.b,  0.18)
                                                        if (s === "clean")    return Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.18)
                                                        return ThemeManager.surface()
                                                    }
                                                    Text {
                                                        id: engStTxt; anchors.centerIn: parent
                                                        text: (modelData.status || "").toUpperCase()
                                                        font.pixelSize: 9; font.weight: (Font.Bold || 700)
                                                        color: {
                                                            var s = (modelData.status || "").toLowerCase()
                                                            if (s === "detected") return ThemeManager.danger
                                                            if (s === "clean")    return ThemeManager.success
                                                            return ThemeManager.muted()
                                                        }
                                                    }
                                                }
                                            }
                                            Text { text: modelData.score !== undefined ? modelData.score.toFixed(0) : "—"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 58 }
                                            Text { text: modelData.details || "—"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; elide: Text.ElideRight; Layout.fillWidth: true }
                                            Text { text: modelData.time_ms !== undefined ? modelData.time_ms + "" : "—"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 52; horizontalAlignment: Text.AlignRight }
                                        }
                                    }
                                }

                                Item { height: 24 }
                            }
                        }

                        // ┄┄ Behavior ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
                        ScrollView {
                            id: behScroll; clip: true

                            ColumnLayout {
                                width: Math.min(860, behScroll.availableWidth - 32)
                                x: Math.max(16, (behScroll.availableWidth - width) / 2)
                                spacing: 12

                                Item { height: 10 }

                                // Empty / no sandbox
                                Item {
                                    visible: root.fileReport === null || !(((root.fileReport || {}).sandbox || {}).executed)
                                    Layout.fillWidth: true; implicitHeight: 200
                                    ColumnLayout {
                                        anchors.centerIn: parent; spacing: 8
                                        Text { text: "🖥"; font.pixelSize: 44; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                                        Text {
                                            text: root.fileReport === null ? "No scan results" : "Sandbox not executed"
                                            color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; Layout.alignment: Qt.AlignHCenter
                                        }
                                        Text {
                                            visible: root.fileReport !== null
                                            text: "Enable the VMware Sandbox option and re-scan to collect behavioral data."
                                            color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.alignment: Qt.AlignHCenter
                                        }
                                    }
                                }

                                // Processes
                                Rectangle {
                                    property var items: root.fileReport ? (((root.fileReport.sandbox) || {}).process_diff || []) : []
                                    visible: root.fileReport !== null && (((root.fileReport.sandbox) || {}).executed) && items.length > 0
                                    Layout.fillWidth: true
                                    implicitHeight: behProcCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout {
                                        id: behProcCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                                        spacing: 5
                                        Text { text: "⚙  New Processes"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: parent.parent.items
                                            RowLayout { spacing: 6; Layout.fillWidth: true
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

                                // File system changes
                                Rectangle {
                                    property var items: root.fileReport ? (((root.fileReport.sandbox) || {}).file_diff || []) : []
                                    visible: root.fileReport !== null && (((root.fileReport.sandbox) || {}).executed) && items.length > 0
                                    Layout.fillWidth: true
                                    implicitHeight: behFileCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout {
                                        id: behFileCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                                        spacing: 5
                                        Text { text: "📁  File System Changes"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: parent.parent.items
                                            Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                        }
                                    }
                                }

                                // Registry
                                Rectangle {
                                    property var items: root.fileReport ? (((root.fileReport.sandbox) || {}).registry_diff || []) : []
                                    visible: root.fileReport !== null && (((root.fileReport.sandbox) || {}).executed) && items.length > 0
                                    Layout.fillWidth: true
                                    implicitHeight: behRegCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout {
                                        id: behRegCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                                        spacing: 5
                                        Text { text: "🔑  Registry Changes"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: parent.parent.items
                                            Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                        }
                                    }
                                }

                                // Network
                                Rectangle {
                                    property var netItems: root.fileReport ? (((root.fileReport.sandbox) || {}).network_attempts || []) : []
                                    property var dnsItems: root.fileReport ? (((root.fileReport.sandbox) || {}).dns_queries      || []) : []
                                    visible: root.fileReport !== null && (((root.fileReport.sandbox) || {}).executed) && (netItems.length > 0 || dnsItems.length > 0)
                                    Layout.fillWidth: true
                                    implicitHeight: behNetCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout {
                                        id: behNetCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                                        spacing: 5
                                        Text { text: "🌐  Network Activity"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: parent.parent.netItems
                                            RowLayout { spacing: 6; Layout.fillWidth: true
                                                Text { text: "→"; color: ThemeManager.warning; font.pixelSize: 12 }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                            }
                                        }
                                        Repeater {
                                            model: parent.parent.dnsItems
                                            RowLayout { spacing: 6; Layout.fillWidth: true
                                                Text { text: "DNS"; color: ThemeManager.muted(); font.pixelSize: 9; font.weight: (Font.Bold || 700); Layout.preferredWidth: 28 }
                                                Text { text: modelData; color: ThemeManager.muted(); font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

                                // Highlights
                                Rectangle {
                                    property var items: root.fileReport ? (((root.fileReport.sandbox) || {}).highlights || []) : []
                                    visible: root.fileReport !== null && (((root.fileReport.sandbox) || {}).executed) && items.length > 0
                                    Layout.fillWidth: true
                                    implicitHeight: behHlCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout {
                                        id: behHlCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                                        spacing: 5
                                        Text { text: "⚠  Highlights"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: parent.parent.items
                                            RowLayout { spacing: 8; Layout.fillWidth: true
                                                Text { text: "⚠"; color: ThemeManager.warning; font.pixelSize: 13 }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

                                Item { height: 24 }
                            }
                        }

                        // ┄┄ IOCs ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
                        ScrollView {
                            id: iocScroll; clip: true

                            ColumnLayout {
                                width: Math.min(860, iocScroll.availableWidth - 32)
                                x: Math.max(16, (iocScroll.availableWidth - width) / 2)
                                spacing: 10

                                Item { height: 10 }

                                Item {
                                    visible: root.fileReport === null
                                    Layout.fillWidth: true; implicitHeight: 160
                                    ColumnLayout { anchors.centerIn: parent; spacing: 8
                                        Text { text: "🔒"; font.pixelSize: 44; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                                        Text { text: "No scan results"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; Layout.alignment: Qt.AlignHCenter }
                                    }
                                }

                                // URLs
                                Rectangle {
                                    property var items: root.fileReport ? ((root.fileReport.iocs || {}).urls || []) : []
                                    visible: items.length > 0
                                    Layout.fillWidth: true; implicitHeight: iocUrlCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout { id: iocUrlCol; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 4
                                        Text { text: "🌐  URLs (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater { model: parent.parent.items
                                            Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true } }
                                    }
                                }

                                // Domains
                                Rectangle {
                                    property var items: root.fileReport ? ((root.fileReport.iocs || {}).domains || []) : []
                                    visible: items.length > 0
                                    Layout.fillWidth: true; implicitHeight: iocDomCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout { id: iocDomCol; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 4
                                        Text { text: "🔗  Domains (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater { model: parent.parent.items
                                            Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true } }
                                    }
                                }

                                // IPs
                                Rectangle {
                                    property var items: root.fileReport ? ((root.fileReport.iocs || {}).ips || []) : []
                                    visible: items.length > 0
                                    Layout.fillWidth: true; implicitHeight: iocIpCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout { id: iocIpCol; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 4
                                        Text { text: "📡  IP Addresses (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater { model: parent.parent.items
                                            Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true } }
                                    }
                                }

                                // File paths
                                Rectangle {
                                    property var items: root.fileReport ? ((root.fileReport.iocs || {}).file_paths || []) : []
                                    visible: items.length > 0
                                    Layout.fillWidth: true; implicitHeight: iocFpCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout { id: iocFpCol; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 4
                                        Text { text: "📁  File Paths (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater { model: parent.parent.items
                                            Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true } }
                                    }
                                }

                                // Registry keys
                                Rectangle {
                                    property var items: root.fileReport ? ((root.fileReport.iocs || {}).registry_keys || []) : []
                                    visible: items.length > 0
                                    Layout.fillWidth: true; implicitHeight: iocRegCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout { id: iocRegCol; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 4
                                        Text { text: "🔑  Registry Keys (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater { model: parent.parent.items
                                            Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true } }
                                    }
                                }

                                // Hashes
                                Rectangle {
                                    property var items: root.fileReport ? ((root.fileReport.iocs || {}).hashes || []) : []
                                    visible: items.length > 0
                                    Layout.fillWidth: true; implicitHeight: iocHashCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout { id: iocHashCol; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 4
                                        Text { text: "🔢  Hashes (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater { model: parent.parent.items
                                            Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true } }
                                    }
                                }

                                // All-clear
                                Item {
                                    visible: root.fileReport !== null &&
                                             ((root.fileReport.iocs || {}).urls         || []).length === 0 &&
                                             ((root.fileReport.iocs || {}).domains      || []).length === 0 &&
                                             ((root.fileReport.iocs || {}).ips          || []).length === 0 &&
                                             ((root.fileReport.iocs || {}).file_paths   || []).length === 0 &&
                                             ((root.fileReport.iocs || {}).registry_keys|| []).length === 0 &&
                                             ((root.fileReport.iocs || {}).hashes       || []).length === 0
                                    Layout.fillWidth: true; implicitHeight: 120
                                    ColumnLayout { anchors.centerIn: parent; spacing: 8
                                        Text { text: "🔒"; font.pixelSize: 40; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                                        Text { text: "No IOCs found"; color: ThemeManager.success; font.pixelSize: ThemeManager.fontSize_body; Layout.alignment: Qt.AlignHCenter }
                                    }
                                }

                                Item { height: 24 }
                            }
                        }

                        // ┄┄ Explanation ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
                        ScrollView {
                            id: exScroll; clip: true

                            ColumnLayout {
                                width: Math.min(740, exScroll.availableWidth - 32)
                                x: Math.max(16, (exScroll.availableWidth - width) / 2)
                                spacing: 14

                                Item { height: 10 }

                                Item {
                                    visible: root.fileReport === null
                                    Layout.fillWidth: true; implicitHeight: 160
                                    ColumnLayout { anchors.centerIn: parent; spacing: 8
                                        Text { text: "🤖"; font.pixelSize: 44; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                                        Text { text: "No report loaded"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; Layout.alignment: Qt.AlignHCenter }
                                    }
                                }

                                Button {
                                    visible: root.fileReport !== null && root.explainData === null && !explainBusy.running
                                    Layout.alignment: Qt.AlignHCenter
                                    text: "✨  Get AI Explanation"
                                    implicitWidth: 218; implicitHeight: 44
                                    contentItem: Text {
                                        text: parent.text; color: ThemeManager.selectionForeground
                                        font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600)
                                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle {
                                        color: parent.parent.hovered ? Qt.darker(ThemeManager.accent, 1.08) : ThemeManager.accent
                                        radius: 8; Behavior on color { ColorAnimation { duration: 120 } }
                                    }
                                    onClicked: {
                                        if (root.fileReport && root.backend) {
                                            explainBusy.running = true
                                            root.backend.explainScanCenterReport(JSON.stringify(root.fileReport))
                                        }
                                    }
                                }

                                BusyIndicator {
                                    id: explainBusy; running: false; visible: running
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                Rectangle {
                                    visible: root.explainData !== null
                                    Layout.fillWidth: true; implicitHeight: exSumCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout {
                                        id: exSumCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                                        spacing: 8
                                        Text { text: "Summary"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Text { text: (root.explainData || {}).one_line_summary || ""; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.Medium || 500); wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    }
                                }

                                Rectangle {
                                    visible: root.explainData !== null && ((root.explainData || {}).top_reasons || []).length > 0
                                    Layout.fillWidth: true; implicitHeight: exReasCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout {
                                        id: exReasCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                                        spacing: 6
                                        Text { text: "Why This Risk Level?"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: (root.explainData || {}).top_reasons || []
                                            RowLayout { spacing: 8; Layout.fillWidth: true
                                                Text { text: "•"; color: ThemeManager.accent; font.pixelSize: 16 }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    visible: root.explainData !== null && ((root.explainData || {}).what_to_do || []).length > 0
                                    Layout.fillWidth: true; implicitHeight: exActCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout {
                                        id: exActCol
                                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                                        spacing: 6
                                        Text { text: "Recommended Actions"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: (root.explainData || {}).what_to_do || []
                                            RowLayout { spacing: 8; Layout.fillWidth: true
                                                Text { text: "→"; color: ThemeManager.success; font.pixelSize: 14; font.weight: (Font.Bold || 700) }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    visible: root.explainData !== null && (root.explainData || {}).false_positive_note !== ""
                                    Layout.fillWidth: true; implicitHeight: fpNoteTxt.implicitHeight + 24
                                    color: Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.08)
                                    radius: 10; border.width: 1
                                    border.color: Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.3)
                                    Text {
                                        id: fpNoteTxt
                                        anchors.fill: parent; anchors.margins: 12
                                        text: "ℹ  " + ((root.explainData || {}).false_positive_note || "")
                                        color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.WordWrap
                                    }
                                }

                                RowLayout {
                                    visible: root.fileReport !== null
                                    Layout.fillWidth: true; spacing: 12
                                    Button {
                                        text: "Export Report…"; flat: true
                                        contentItem: Text { text: parent.text; color: ThemeManager.accent; font.pixelSize: ThemeManager.fontSize_small; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                        background: Rectangle { color: parent.parent.hovered ? ThemeManager.surface() : "transparent"; radius: 8 }
                                        onClicked: {
                                            var jid = ((root.fileReport || {}).job || {}).job_id || ""
                                            if (jid && root.backend) root.backend.exportScanCenterReport(jid, "")
                                        }
                                    }
                                    Text { id: expOkLabel; text: ""; color: ThemeManager.success; font.pixelSize: ThemeManager.fontSize_small; elide: Text.ElideRight; Layout.fillWidth: true }
                                }

                                Item { height: 24 }
                            }
                        }

                        // ┄┄ Agent Timeline (tab 5) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                // Header row
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 10

                                    Text {
                                        text: "\uD83D\uDCE1  Agent Timeline"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_h3
                                        font.weight: (Font.SemiBold || 600)
                                    }
                                    Text {
                                        visible: agentTimelineListModel.count > 0
                                        text: agentTimelineListModel.count + " step" +
                                              (agentTimelineListModel.count !== 1 ? "s" : "")
                                        color: ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_small
                                        Layout.alignment: Qt.AlignVCenter
                                    }
                                    Item { Layout.fillWidth: true }

                                    // Replay button
                                    Rectangle {
                                        visible: agentTimelineListModel.count > 0 && !root.fileScanning
                                        implicitWidth: replayBtnTxt.implicitWidth + 22
                                        implicitHeight: 28; radius: 6
                                        color: root.replayActive
                                               ? ThemeManager.accent
                                               : (replayBtnMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface())
                                        border.color: ThemeManager.border(); border.width: 1
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Text {
                                            id: replayBtnTxt
                                            anchors.centerIn: parent
                                            text: root.replayActive ? "\u23F9  Stop" : "\u25B6  Replay"
                                            color: root.replayActive ? "#ffffff" : ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_small
                                        }
                                        MouseArea {
                                            id: replayBtnMa; anchors.fill: parent
                                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (root.replayActive) {
                                                    root.replayActive      = false
                                                    root.replayCurrentStep = -1
                                                } else {
                                                    root.replayCurrentStep = 0
                                                    root.replayActive      = true
                                                }
                                            }
                                        }
                                    }
                                } // header RowLayout

                                // Empty state
                                Item {
                                    visible: agentTimelineListModel.count === 0
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    ColumnLayout {
                                        anchors.centerIn: parent; spacing: 10
                                        Text {
                                            text: "\uD83D\uDCE1"
                                            font.pixelSize: 44; opacity: 0.35
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                        Text {
                                            text: root.fileScanning
                                                  ? "Steps will appear here as the scan runs\u2026"
                                                  : "Run a scan — the timeline fills in step-by-step."
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_body
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                    }
                                }

                                // Step list
                                ListView {
                                    id: timelineList
                                    visible: agentTimelineListModel.count > 0
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    model: agentTimelineListModel
                                    clip: true; spacing: 4
                                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                                    onCountChanged: {
                                        if (root.fileScanning)
                                            timelineList.positionViewAtEnd()
                                    }

                                    delegate: Rectangle {
                                        id: tlRow
                                        width: timelineList.width
                                        implicitHeight: tlInner.implicitHeight + 18
                                        radius: 8
                                        color: (root.replayCurrentStep === index)
                                               ? ThemeManager.elevated()
                                               : (tlMa.containsMouse ? ThemeManager.elevated()
                                                                      : ThemeManager.surface())
                                        border.color: (root.replayCurrentStep === index)
                                                      ? ThemeManager.accent : "transparent"
                                        border.width: 1
                                        Behavior on color { ColorAnimation { duration: 100 } }

                                        // Auto-scroll highlighted row into view during replay
                                        property bool highlighted: root.replayCurrentStep === index
                                        onHighlightedChanged: {
                                            if (highlighted)
                                                ListView.view.positionViewAtIndex(index, ListView.Contain)
                                        }

                                        RowLayout {
                                            id: tlInner
                                            anchors.left: parent.left; anchors.right: parent.right
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.leftMargin: 12; anchors.rightMargin: 12
                                            spacing: 10

                                            // Pulsing status dot
                                            Rectangle {
                                                width: 10; height: 10; radius: 5
                                                Layout.alignment: Qt.AlignVCenter
                                                color: {
                                                    var s = model.status || "ok"
                                                    if (s === "ok")      return ThemeManager.success
                                                    if (s === "running") return ThemeManager.warning
                                                    if (s === "warn")    return "#f97316"
                                                    if (s === "fail")    return ThemeManager.danger
                                                    return ThemeManager.muted()
                                                }
                                                SequentialAnimation on opacity {
                                                    loops: Animation.Infinite
                                                    running: (model.status || "") === "running" && root.fileScanning
                                                    NumberAnimation { to: 0.25; duration: 500 }
                                                    NumberAnimation { to: 1.0;  duration: 500 }
                                                }
                                            }

                                            // Timestamp
                                            Text {
                                                text: model.ts || ""
                                                color: ThemeManager.muted()
                                                font.pixelSize: 10; font.family: "Consolas"
                                                Layout.preferredWidth: 58
                                            }

                                            // Stage badge
                                            Rectangle {
                                                implicitWidth: tlStageTxt.implicitWidth + 12
                                                implicitHeight: 18; radius: 9
                                                color: ThemeManager.elevated()
                                                Layout.alignment: Qt.AlignVCenter
                                                Text {
                                                    id: tlStageTxt
                                                    anchors.centerIn: parent
                                                    text: (model.stage || "").toUpperCase()
                                                    color: ThemeManager.accent
                                                    font.pixelSize: 9; font.weight: (Font.Bold || 700)
                                                }
                                            }

                                            // Title + result
                                            ColumnLayout {
                                                Layout.fillWidth: true; spacing: 1
                                                Text {
                                                    text: model.title || ""
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    font.weight: (Font.Medium || 500)
                                                    elide: Text.ElideRight; Layout.fillWidth: true
                                                }
                                                Text {
                                                    visible: (model.result || "") !== ""
                                                    text: model.result || ""
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 10; font.family: "Consolas"
                                                    elide: Text.ElideRight; Layout.fillWidth: true
                                                }
                                            }
                                        } // tlInner

                                        MouseArea {
                                            id: tlMa; anchors.fill: parent
                                            hoverEnabled: true; propagateComposedEvents: true
                                            onClicked: function(mouse) { mouse.accepted = false }
                                        }
                                    } // delegate
                                } // ListView (timelineList)
                            } // ColumnLayout
                        } // Item (Timeline tab)

                    } // sub StackLayout
                } // file ColumnLayout
            } // file Item

            // ██████████████████████████████████████████████████████████████
            // [1]  URL SCAN
            // ██████████████████████████████████████████████████████████████
            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // ── URL control bar ───────────────────────────────────
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: uCtrlCol.implicitHeight + 24
                        color: ThemeManager.panel()
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left; anchors.right: parent.right
                            height: 1; color: ThemeManager.border()
                        }

                        ColumnLayout {
                            id: uCtrlCol
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 16
                            spacing: 10

                            RowLayout {
                                Layout.fillWidth: true; spacing: 8

                                // URL input field
                                Rectangle {
                                    Layout.fillWidth: true; implicitHeight: 40
                                    color: ThemeManager.surface(); radius: 8
                                    border.color: urlField.activeFocus ? ThemeManager.accent : ThemeManager.border()
                                    border.width: urlField.activeFocus ? 2 : 1
                                    Behavior on border.color { ColorAnimation { duration: 140 } }

                                    RowLayout {
                                        anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 6
                                        spacing: 6
                                        Text { text: "🌐"; font.pixelSize: 14 }
                                        Item {
                                            Layout.fillWidth: true
                                            implicitHeight: 40
                                            Text {
                                                visible: urlField.text === ""
                                                text: "Enter a URL — e.g. https://example.com"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_body
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            TextInput {
                                                id: urlField
                                                anchors.fill: parent
                                                anchors.topMargin: 1; anchors.bottomMargin: 1
                                                text: root.urlInput
                                                color: ThemeManager.foreground()
                                                font.pixelSize: ThemeManager.fontSize_body
                                                clip: true
                                                verticalAlignment: TextInput.AlignVCenter
                                                onTextChanged: root.urlInput = text
                                                Keys.onReturnPressed: {
                                                    if (text.trim() !== "" && !root.urlScanning)
                                                        uScanBtn.startScan()
                                                }
                                            }
                                        }
                                        Text {
                                            visible: urlField.text !== ""
                                            text: "✕"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small
                                            MouseArea {
                                                anchors.fill: parent
                                                onClicked: { urlField.text = ""; root.urlInput = "" }
                                            }
                                        }
                                    }
                                }

                                Button {
                                    id: uScanBtn
                                    text: root.urlScanning ? "Scanning…" : "Scan URL"
                                    enabled: root.urlInput.trim() !== "" && !root.urlScanning
                                    implicitWidth: 100; implicitHeight: 40

                                    function startScan() {
                                        if (!enabled) return
                                        root.urlResult = null; root.urlPct = 0; root.urlStage = "Starting…"
                                        if (root.backend) {
                                            if (root.urlOptSandbox)
                                                root.backend.scanUrlSandbox(root.urlInput.trim(),
                                                    root.urlOptBlockDl, root.urlOptBlockPvt, true, 30)
                                            else
                                                root.backend.scanUrlStatic(root.urlInput.trim(),
                                                    root.urlOptBlockPvt, true, 30)
                                        }
                                    }

                                    contentItem: Text {
                                        text: uScanBtn.text; color: uScanBtn.enabled ? ThemeManager.selectionForeground : ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600)
                                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle {
                                        color: uScanBtn.enabled
                                               ? (uScanBtn.pressed ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent)
                                               : ThemeManager.surface()
                                        radius: 8; Behavior on color { ColorAnimation { duration: 120 } }
                                    }
                                    onClicked: startScan()
                                }

                                Button {
                                    visible: root.urlScanning; text: "✕"; flat: true
                                    implicitWidth: 36; implicitHeight: 40
                                    contentItem: Text { text: parent.text; color: ThemeManager.danger; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    background: Rectangle { color: parent.parent.hovered ? Qt.rgba(1, 0, 0, .1) : "transparent"; radius: 8 }
                                    onClicked: { if (root.backend) root.backend.cancelUrlScan(); root.urlScanning = false }
                                }
                            }

                            // URL options — Flow wraps automatically on narrow windows
                            Flow {
                                Layout.fillWidth: true
                                spacing: 12

                                StyledCheckBox {
                                    id: ckUrlSb
                                    text: "Detonate in sandbox"
                                    checked: root.urlOptSandbox
                                    enabled: !root.urlScanning
                                    onToggled: root.urlOptSandbox = checked
                                }

                                StyledCheckBox {
                                    id: ckUrlBl
                                    text: "Block downloads"
                                    checked: root.urlOptBlockDl
                                    enabled: !root.urlScanning && root.urlOptSandbox
                                    opacity: enabled ? 1.0 : 0.4
                                    onToggled: root.urlOptBlockDl = checked
                                }

                                StyledCheckBox {
                                    id: ckUrlPv
                                    text: "Block private IPs"
                                    checked: root.urlOptBlockPvt
                                    enabled: !root.urlScanning
                                    onToggled: root.urlOptBlockPvt = checked
                                }
                            }
                        }
                    }

                    // ── URL progress ──────────────────────────────────────
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: root.urlScanning ? 32 : 0
                        visible: root.urlScanning; color: ThemeManager.surface(); clip: true
                        Behavior on implicitHeight { NumberAnimation { duration: 160 } }
                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16; spacing: 10
                            Text { text: root.urlStage; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 200; elide: Text.ElideRight }
                            ProgressBar { Layout.fillWidth: true; value: root.urlPct / 100 }
                            Text { text: root.urlPct + "%"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 34; horizontalAlignment: Text.AlignRight }
                        }
                    }

                    // ── URL verdict bar ───────────────────────────────────
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: root.urlResult !== null ? 44 : 0
                        visible: root.urlResult !== null; color: ThemeManager.panel(); clip: true
                        Behavior on implicitHeight { NumberAnimation { duration: 160 } }
                        Rectangle {
                            anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                            height: 2; color: root.urlResult ? root.riskColor((root.urlResult.verdict) || "") : "transparent"
                        }
                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16; spacing: 12
                            Rectangle {
                                visible: root.urlResult !== null
                                implicitWidth: urlVrdTxt.implicitWidth + 18; implicitHeight: 24; radius: 12
                                color: root.urlResult ? root.riskColor((root.urlResult.verdict) || "") : "transparent"
                                Text { id: urlVrdTxt; anchors.centerIn: parent; text: root.urlResult ? ((root.urlResult.verdict) || "unknown").toUpperCase().replace(/_/g, " ") : ""; color: "#ffffff"; font.pixelSize: 10; font.weight: (Font.Bold || 700) }
                            }
                            Text { Layout.fillWidth: true; text: root.urlResult ? ((root.urlResult.normalized_url) || "") : ""; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; wrapMode: Text.WrapAnywhere; elide: Text.ElideNone }
                            Text { visible: root.urlResult !== null; text: "Score: " + ((root.urlResult || {}).score || 0) + " / 100"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small }
                        }
                    }

                    // ── URL results scroll ────────────────────────────────
                    ScrollView {
                        id: urlScroll
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true

                        ColumnLayout {
                            width: Math.min(800, urlScroll.availableWidth - 32)
                            x: Math.max(16, (urlScroll.availableWidth - width) / 2)
                            spacing: 14

                            Item { height: 8 }

                            // ── Empty state ──────────────────────────────────
                            Item {
                                visible: root.urlResult === null && !root.urlScanning
                                Layout.fillWidth: true; implicitHeight: 200
                                ColumnLayout { anchors.centerIn: parent; spacing: 10
                                    Text { text: "🌐"; font.pixelSize: 48; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                                    Text { text: "Enter a URL above and click Scan URL"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; Layout.alignment: Qt.AlignHCenter }
                                    Text { text: "Multi-engine analysis: Heuristics + Content + Google Safe Browsing + optional Threat APIs"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.alignment: Qt.AlignHCenter }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  SCORE GAUGE + THREAT BADGES                │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null
                                Layout.fillWidth: true
                                implicitHeight: scoreGaugeRow.implicitHeight + 32
                                color: ThemeManager.panel(); radius: 12
                                border.color: root.urlResult ? root.riskColor((root.urlResult.verdict) || "") : ThemeManager.border()
                                border.width: 2
                                Behavior on border.color { ColorAnimation { duration: 300 } }

                                RowLayout {
                                    id: scoreGaugeRow
                                    anchors.fill: parent; anchors.margins: 16; spacing: 20

                                    // ── Circular score gauge ─────────────
                                    Item {
                                        implicitWidth: 110; implicitHeight: 110
                                        Layout.alignment: Qt.AlignVCenter

                                        // Background arc (grey)
                                        Canvas {
                                            id: gaugeArcBg
                                            anchors.fill: parent
                                            onPaint: {
                                                var ctx = getContext("2d")
                                                ctx.reset()
                                                var cx = width / 2, cy = height / 2, r = 44
                                                ctx.lineWidth = 8
                                                ctx.strokeStyle = ThemeManager.border()
                                                ctx.lineCap = "round"
                                                ctx.beginPath()
                                                ctx.arc(cx, cy, r, 0.75 * Math.PI, 2.25 * Math.PI)
                                                ctx.stroke()
                                            }
                                            Component.onCompleted: requestPaint()
                                            Connections { target: ThemeManager; function onThemeModeChanged() { gaugeArcBg.requestPaint() } }
                                        }

                                        // Foreground arc (colored)
                                        Canvas {
                                            id: gaugeArcFg
                                            anchors.fill: parent
                                            property int scoreVal: root.urlResult ? ((root.urlResult || {}).score || 0) : 0
                                            property color arcColor: root.urlResult ? root.riskColor((root.urlResult.verdict) || "") : ThemeManager.success
                                            onPaint: {
                                                var ctx = getContext("2d")
                                                ctx.reset()
                                                var cx = width / 2, cy = height / 2, r = 44
                                                var startAngle = 0.75 * Math.PI
                                                var endAngle = startAngle + (scoreVal / 100) * 1.5 * Math.PI
                                                ctx.lineWidth = 8
                                                ctx.strokeStyle = arcColor
                                                ctx.lineCap = "round"
                                                ctx.beginPath()
                                                ctx.arc(cx, cy, r, startAngle, endAngle)
                                                ctx.stroke()
                                            }
                                            onScoreValChanged: requestPaint()
                                            onArcColorChanged: requestPaint()
                                            Component.onCompleted: requestPaint()
                                        }

                                        // Score number
                                        Text {
                                            anchors.centerIn: parent; anchors.verticalCenterOffset: -6
                                            text: root.urlResult ? String((root.urlResult || {}).score || 0) : "0"
                                            color: root.urlResult ? root.riskColor((root.urlResult.verdict) || "") : ThemeManager.muted()
                                            font.pixelSize: 28; font.weight: (Font.Bold || 700)
                                        }

                                        // "/100" label
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            anchors.bottom: parent.bottom; anchors.bottomMargin: 16
                                            text: "/ 100"
                                            color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small
                                        }
                                    }

                                    // ── Verdict + threat info column ─────
                                    ColumnLayout {
                                        Layout.fillWidth: true; spacing: 8

                                        // Verdict badge
                                        Rectangle {
                                            implicitWidth: vrdLbl.implicitWidth + 24; implicitHeight: 28; radius: 14
                                            color: root.urlResult ? root.riskColor((root.urlResult.verdict) || "") : "transparent"
                                            Text {
                                                id: vrdLbl; anchors.centerIn: parent
                                                text: root.urlResult ? ((root.urlResult.verdict) || "unknown").toUpperCase().replace(/_/g, " ") : ""
                                                color: "#ffffff"; font.pixelSize: 12; font.weight: (Font.Bold || 700)
                                            }
                                        }

                                        // Threat type pills
                                        Flow {
                                            Layout.fillWidth: true; spacing: 6
                                            visible: root.urlResult !== null && ((root.urlResult || {}).threat_types || []).length > 0
                                            Repeater {
                                                model: (root.urlResult || {}).threat_types || []
                                                Rectangle {
                                                    implicitWidth: ttLbl.implicitWidth + 20; implicitHeight: 22; radius: 11
                                                    color: {
                                                        var t = (modelData || "").toLowerCase()
                                                        if (t === "phishing")   return Qt.rgba(0.9, 0.3, 0.2, 0.15)
                                                        if (t === "malware")    return Qt.rgba(0.8, 0.1, 0.1, 0.15)
                                                        if (t === "download risk") return Qt.rgba(0.9, 0.6, 0.1, 0.15)
                                                        return Qt.rgba(0.5, 0.5, 0.5, 0.1)
                                                    }
                                                    Text {
                                                        id: ttLbl; anchors.centerIn: parent
                                                        text: {
                                                            var t = (modelData || "").toLowerCase()
                                                            if (t === "phishing") return "🎣 Phishing"
                                                            if (t === "malware") return "🦠 Malware"
                                                            if (t === "suspicious structure") return "⚠️ Suspicious"
                                                            if (t === "redirect abuse") return "🔀 Redirect Abuse"
                                                            if (t === "download risk") return "⬇️ Download Risk"
                                                            return modelData || ""
                                                        }
                                                        color: ThemeManager.foreground(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600)
                                                    }
                                                }
                                            }
                                        }

                                        // Engine summary line
                                        Text {
                                            visible: root.urlResult !== null
                                            text: {
                                                var r = root.urlResult || {}
                                                var ec = r.engine_count || 0
                                                var ef = r.engines_flagged || 0
                                                var dur = r.scan_duration_sec || 0
                                                return ec + " engine" + (ec !== 1 ? "s" : "") +
                                                       " • " + ef + " flagged" +
                                                       " • " + dur.toFixed(1) + "s"
                                            }
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                        }

                                        // Normalized URL
                                        Text {
                                            visible: root.urlResult !== null
                                            text: root.urlResult ? ((root.urlResult.normalized_url) || "") : ""
                                            color: ThemeManager.foreground()
                                            font.pixelSize: 11; font.family: "Consolas"
                                            wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
                                        }
                                    }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  STRUCTURED EXPLANATION (What / Why / Do)   │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null && (root.urlResult || {}).explanation !== null && (root.urlResult || {}).explanation !== undefined
                                Layout.fillWidth: true; implicitHeight: explainCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1

                                ColumnLayout {
                                    id: explainCol
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 10

                                    Text { text: "🔍  Analysis"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }

                                    // What Is This?
                                    Rectangle {
                                        Layout.fillWidth: true; implicitHeight: whatCol.implicitHeight + 16
                                        color: ThemeManager.surface(); radius: 8
                                        ColumnLayout {
                                            id: whatCol
                                            anchors.left: parent.left; anchors.right: parent.right
                                            anchors.top: parent.top; anchors.margins: 8; spacing: 3
                                            Text { text: "📋  What Is This?"; color: ThemeManager.accent; font.pixelSize: 11; font.weight: (Font.SemiBold || 600) }
                                            Text {
                                                text: ((root.urlResult || {}).explanation || {}).what_it_is || "—"
                                                color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small
                                                wrapMode: Text.WordWrap; Layout.fillWidth: true
                                            }
                                        }
                                    }

                                    // Why Risky?
                                    Rectangle {
                                        Layout.fillWidth: true; implicitHeight: whyCol.implicitHeight + 16
                                        color: ThemeManager.surface(); radius: 8
                                        ColumnLayout {
                                            id: whyCol
                                            anchors.left: parent.left; anchors.right: parent.right
                                            anchors.top: parent.top; anchors.margins: 8; spacing: 3
                                            Text { text: "⚡  Why Risky?"; color: ThemeManager.warning; font.pixelSize: 11; font.weight: (Font.SemiBold || 600) }
                                            Text {
                                                text: ((root.urlResult || {}).explanation || {}).why_risky || "—"
                                                color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small
                                                wrapMode: Text.WordWrap; Layout.fillWidth: true
                                            }
                                        }
                                    }

                                    // What To Do
                                    Rectangle {
                                        Layout.fillWidth: true; implicitHeight: doCol.implicitHeight + 16
                                        color: ThemeManager.surface(); radius: 8
                                        ColumnLayout {
                                            id: doCol
                                            anchors.left: parent.left; anchors.right: parent.right
                                            anchors.top: parent.top; anchors.margins: 8; spacing: 3
                                            Text { text: "✅  What To Do"; color: ThemeManager.success; font.pixelSize: 11; font.weight: (Font.SemiBold || 600) }
                                            Text {
                                                text: ((root.urlResult || {}).explanation || {}).what_to_do || "—"
                                                color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small
                                                wrapMode: Text.WordWrap; Layout.fillWidth: true
                                            }
                                        }
                                    }

                                    // Confidence + technical
                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 12
                                        Text {
                                            text: "Confidence: " + (((root.urlResult || {}).explanation || {}).confidence || "—").toUpperCase()
                                            color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600)
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: ((root.urlResult || {}).explanation || {}).technical_summary || ""
                                            color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_caption
                                            wrapMode: Text.WrapAnywhere
                                        }
                                    }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  MULTI-ENGINE BREAKDOWN                     │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null && (root.urlResult || {}).engines !== null && (root.urlResult || {}).engines !== undefined
                                Layout.fillWidth: true; implicitHeight: engCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: engCol
                                    anchors.left: parent.left; anchors.right: parent.right
                                    anchors.top: parent.top; anchors.margins: 14; spacing: 8

                                    Text { text: "🔧  Engine Breakdown"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }

                                    Repeater {
                                        model: {
                                            var engines = (root.urlResult || {}).engines || {}
                                            var list = []
                                            for (var key in engines) {
                                                var e = engines[key]
                                                list.push({
                                                    name: e.engine_name || key,
                                                    available: e.available !== false,
                                                    flagged: e.flagged || false,
                                                    score: e.score || 0,
                                                    verdict: e.verdict || "unknown",
                                                    evidence_count: e.evidence_count || 0,
                                                    duration_ms: e.duration_ms || 0
                                                })
                                            }
                                            return list
                                        }
                                        Rectangle {
                                            Layout.fillWidth: true; implicitHeight: 44; radius: 8
                                            color: ThemeManager.surface()
                                            border.color: modelData.flagged ? root.riskColor(modelData.verdict) : ThemeManager.border()
                                            border.width: modelData.flagged ? 1.5 : 1
                                            Behavior on border.color { ColorAnimation { duration: 200 } }

                                            RowLayout {
                                                anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 10

                                                // Status icon
                                                Text {
                                                    text: {
                                                        if (!modelData.available) return "⏸"
                                                        if (modelData.flagged)    return "🚨"
                                                        return "✅"
                                                    }
                                                    font.pixelSize: ThemeManager.fontSize_body
                                                }

                                                // Engine name
                                                Text {
                                                    text: modelData.name || "Unknown"
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    font.weight: (Font.SemiBold || 600)
                                                    Layout.fillWidth: true
                                                }

                                                // Evidence count
                                                Text {
                                                    visible: modelData.evidence_count > 0
                                                    text: modelData.evidence_count + " finding" + (modelData.evidence_count !== 1 ? "s" : "")
                                                    color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_caption
                                                }

                                                // Score pill
                                                Rectangle {
                                                    implicitWidth: engScoreTxt.implicitWidth + 14; implicitHeight: 20; radius: 10
                                                    color: modelData.flagged
                                                           ? Qt.rgba(root.riskColor(modelData.verdict).r, root.riskColor(modelData.verdict).g, root.riskColor(modelData.verdict).b, 0.15)
                                                           : ThemeManager.elevated()
                                                    Text {
                                                        id: engScoreTxt; anchors.centerIn: parent
                                                        text: modelData.available ? String(modelData.score) : "N/A"
                                                        color: modelData.flagged ? root.riskColor(modelData.verdict) : ThemeManager.muted()
                                                        font.pixelSize: 10; font.weight: (Font.Bold || 700)
                                                    }
                                                }

                                                // Duration
                                                Text {
                                                    text: modelData.duration_ms + "ms"
                                                    color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_caption
                                                    Layout.preferredWidth: 42
                                                    horizontalAlignment: Text.AlignRight
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  URL DETAILS                                │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null
                                Layout.fillWidth: true; implicitHeight: urlMetaCol2.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlMetaCol2
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 8
                                    Text { text: "📄  URL Details"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                    GridLayout {
                                        Layout.fillWidth: true; columns: 2; columnSpacing: 24; rowSpacing: 6
                                        Repeater {
                                            model: [
                                                ["Original",     (root.urlResult || {}).url                 || "—"],
                                                ["Normalized",   (root.urlResult || {}).normalized_url      || "—"],
                                                ["Final URL",    (root.urlResult || {}).final_url           || "—"],
                                                ["HTTP Status",  (root.urlResult || {}).http_status ? String((root.urlResult || {}).http_status) : "—"],
                                                ["Content-Type", (root.urlResult || {}).http_content_type   || "—"],
                                                ["Redirects",    String((root.urlResult || {}).redirect_count || 0)],
                                            ]
                                            ColumnLayout { spacing: 1; Layout.fillWidth: true
                                                Text { text: modelData[0]; color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.Medium || 500) }
                                                Text { text: modelData[1]; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  FINDINGS / EVIDENCE                        │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null && ((root.urlResult || {}).evidence || []).length > 0
                                Layout.fillWidth: true; implicitHeight: urlEvCol2.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlEvCol2
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 8
                                    Text { text: "🔎  Findings (" + ((root.urlResult || {}).evidence_count || 0) + ")"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                    Repeater {
                                        model: (root.urlResult || {}).evidence || []
                                        Rectangle {
                                            Layout.fillWidth: true; implicitHeight: evInner2.implicitHeight + 16
                                            color: ThemeManager.surface(); radius: 8
                                            ColumnLayout {
                                                id: evInner2
                                                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; spacing: 3
                                                RowLayout { spacing: 8; Layout.fillWidth: true
                                                    Rectangle {
                                                        implicitWidth: sevLbl2.implicitWidth + 12; implicitHeight: 18; radius: 9
                                                        color: {
                                                            var s = (modelData.severity || "").toLowerCase()
                                                            if (s === "high" || s === "critical") return Qt.rgba(ThemeManager.danger.r,  ThemeManager.danger.g,  ThemeManager.danger.b,  0.2)
                                                            if (s === "medium")                   return Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.2)
                                                            return ThemeManager.surface()
                                                        }
                                                        Text {
                                                            id: sevLbl2; anchors.centerIn: parent
                                                            text: (modelData.severity || "info").toUpperCase()
                                                            font.pixelSize: 9; font.weight: (Font.Bold || 700)
                                                            color: {
                                                                var s = (modelData.severity || "").toLowerCase()
                                                                if (s === "high" || s === "critical") return ThemeManager.danger
                                                                if (s === "medium")                   return ThemeManager.warning
                                                                return ThemeManager.muted()
                                                            }
                                                        }
                                                    }
                                                    Text { text: modelData.title || ""; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; font.weight: (Font.Medium || 500); Layout.fillWidth: true; wrapMode: Text.WordWrap }
                                                }
                                                Text { visible: (modelData.detail || "") !== ""; text: modelData.detail || ""; color: ThemeManager.muted(); font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  REDIRECT CHAIN                             │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null && ((root.urlResult || {}).redirects || []).length > 0
                                Layout.fillWidth: true; implicitHeight: urlRedCol2.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlRedCol2
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 5
                                    Text { text: "🔀  Redirect Chain"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                    Repeater {
                                        model: (root.urlResult || {}).redirects || []
                                        RowLayout { spacing: 6; Layout.fillWidth: true
                                            Text { text: (index + 1) + "."; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 22 }
                                            Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                        }
                                    }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  SANDBOX RESULTS                            │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null && (root.urlResult || {}).has_sandbox
                                Layout.fillWidth: true; implicitHeight: urlSbCol2.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlSbCol2
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 6
                                    Text { text: "🖥  Sandbox Detonation"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                    Text {
                                        text: JSON.stringify((root.urlResult || {}).sandbox_result || {}, null, 2)
                                        color: ThemeManager.muted(); font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
                                    }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  IOCs                                       │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null && (root.urlResult || {}).has_iocs
                                Layout.fillWidth: true; implicitHeight: urlIocCol2.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlIocCol2
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 5
                                    Text { text: "🎯  Extracted IOCs"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }
                                    Repeater {
                                        model: {
                                            var res = []; var iocs = (root.urlResult || {}).iocs || {}
                                            for (var k in iocs) {
                                                var arr = iocs[k] || []
                                                for (var j = 0; j < arr.length; j++) res.push(k + ":  " + arr[j])
                                            }
                                            return res
                                        }
                                        Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                    }
                                }
                            }

                            // ┌─────────────────────────────────────────────┐
                            // │  SCORING BREAKDOWN                          │
                            // └─────────────────────────────────────────────┘
                            Rectangle {
                                visible: root.urlResult !== null && (root.urlResult || {}).scoring !== null && (root.urlResult || {}).scoring !== undefined
                                Layout.fillWidth: true; implicitHeight: scoreBreakCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: scoreBreakCol
                                    anchors.left: parent.left; anchors.right: parent.right
                                    anchors.top: parent.top; anchors.margins: 14; spacing: 6

                                    Text { text: "📊  Scoring Breakdown"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.weight: (Font.SemiBold || 600) }

                                    Repeater {
                                        model: {
                                            var bd = ((root.urlResult || {}).scoring || {}).breakdown || {}
                                            var list = []
                                            for (var k in bd) {
                                                list.push({ label: k.replace(/_/g, " "), pts: bd[k] })
                                            }
                                            // Sort by points descending
                                            list.sort(function(a, b) { return b.pts - a.pts })
                                            return list
                                        }
                                        RowLayout {
                                            Layout.fillWidth: true; spacing: 8
                                            // Bar
                                            Rectangle {
                                                Layout.fillWidth: true; implicitHeight: 18; radius: 4
                                                color: ThemeManager.surface()
                                                Rectangle {
                                                    anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                                                    width: Math.max(4, parent.width * Math.min(1, (modelData.pts || 0) / 35))
                                                    radius: 4
                                                    color: {
                                                        var p = modelData.pts || 0
                                                        if (p >= 25) return ThemeManager.danger
                                                        if (p >= 15) return ThemeManager.warning
                                                        return ThemeManager.accent
                                                    }
                                                }
                                                Text {
                                                    anchors.left: parent.left; anchors.leftMargin: 6
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    text: (modelData.label || "").charAt(0).toUpperCase() + (modelData.label || "").slice(1)
                                                    color: ThemeManager.foreground(); font.pixelSize: 10; font.weight: (Font.Medium || 500)
                                                }
                                            }
                                            // Points
                                            Text {
                                                text: "+" + (modelData.pts || 0)
                                                color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.Bold || 700)
                                                Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight
                                            }
                                        }
                                    }
                                }
                            }

                            Item { height: 24 }
                        }
                    }
                } // URL ColumnLayout
            } // URL Item

            // ██████████████████████████████████████████████████████████████
            // [2]  HISTORY
            // ██████████████████████████████████████████████████████████████
            Item {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true; spacing: 10
                        Text { text: "Scan History"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_h3; font.weight: (Font.SemiBold || 600) }
                        Text { visible: histModel.count > 0; text: histModel.count + " scan" + (histModel.count !== 1 ? "s" : ""); color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.alignment: Qt.AlignVCenter }
                        Item { Layout.fillWidth: true }
                        Button {
                            id: historyRefreshButton
                            text: "\u21BB Refresh"
                            flat: true
                            Layout.alignment: Qt.AlignVCenter
                            leftPadding: 10
                            rightPadding: 10
                            topPadding: 6
                            bottomPadding: 6
                            implicitWidth: historyRefreshLabel.implicitWidth + leftPadding + rightPadding
                            implicitHeight: historyRefreshLabel.implicitHeight + topPadding + bottomPadding
                            contentItem: Text {
                                id: historyRefreshLabel
                                text: historyRefreshButton.text
                                color: ThemeManager.accent
                                font.pixelSize: ThemeManager.fontSize_small
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                color: historyRefreshButton.hovered ? ThemeManager.surface() : "transparent"
                                radius: 8
                            }
                            onClicked: { histModel.clear(); if (root.backend) root.backend.loadScanCenterHistory(200) }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: 30
                        color: ThemeManager.surface(); radius: 6
                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 0
                            Text { text: "File";     color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.fillWidth: true }
                            Text { text: "Verdict";  color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 90 }
                            Text { text: "Mode";     color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 68 }
                            Text { text: "Score";    color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 52 }
                            Text { text: "Date";     color: ThemeManager.muted(); font.pixelSize: 10; font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 130 }
                        }
                    }

                    Item {
                        visible: histModel.count === 0
                        Layout.fillWidth: true; Layout.fillHeight: true
                        ColumnLayout { anchors.centerIn: parent; spacing: 8
                            Text { text: "📋"; font.pixelSize: 40; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                            Text { text: "No scan history"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; Layout.alignment: Qt.AlignHCenter }
                        }
                    }

                    ListView {
                        id: histList
                        Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; model: histModel; spacing: 2
                        ScrollBar.vertical: ScrollBar {}

                        delegate: Rectangle {
                            width: histList.width; implicitHeight: 44
                            color: hMouse.containsMouse ? ThemeManager.surface() : (index % 2 === 0 ? "transparent" : ThemeManager.elevated())
                            radius: 6
                            Behavior on color { ColorAnimation { duration: 100 } }

                            MouseArea {
                                id: hMouse; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (model.report_path && root.backend) {
                                        root.backend.openScanCenterReport(model.report_path)
                                        root.segment = 0
                                    }
                                }
                            }

                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 0
                                ColumnLayout { spacing: 1; Layout.fillWidth: true
                                    Text { text: model.file_name || "—"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; font.weight: (Font.Medium || 500); elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: (model.file_type || "") + (model.sha256 ? "  •  " + (model.sha256 || "").slice(0, 10) + "…" : ""); color: ThemeManager.muted(); font.pixelSize: 10; elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                                Rectangle {
                                    Layout.preferredWidth: 90; implicitHeight: 20; radius: 10
                                    color: root.riskColor(model.verdict_risk || ""); opacity: 0.85
                                    Text { anchors.centerIn: parent; text: (model.verdict_risk || "—").toUpperCase(); color: "#ffffff"; font.pixelSize: 9; font.weight: (Font.Bold || 700) }
                                }
                                Text { text: model.mode || "—"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 68 }
                                Text { text: String(model.score || "—"); color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 52 }
                                Text { text: model.created_at ? model.created_at.slice(0, 16).replace("T", " ") : "—"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 130 }
                            }
                        }
                    }
                }
            } // History Item

        } // main StackLayout
    } // root ColumnLayout
}
