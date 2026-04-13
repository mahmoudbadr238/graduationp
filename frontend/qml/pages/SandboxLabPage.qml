import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Window
import "../components"
import "../ui"

// ── Sandbox Lab — Interactive Monitoring Theater ──────────────────────────
// The theater panel fills the full viewport height.
// VM controls, results, logs, etc. scroll below it.
// ──────────────────────────────────────────────────────────────────────────
Item {
    id: root
    anchors.fill: parent

    // ── Safe accessors ────────────────────────────────────────────────────
    readonly property bool hasSandboxLab:  typeof SandboxLab !== "undefined" && SandboxLab !== null
    readonly property bool hasBackend:     typeof Backend !== "undefined" && Backend !== null
    readonly property bool hasPreview:     typeof SandboxPreview !== "undefined" && SandboxPreview !== null

    // ── SandboxLab properties ─────────────────────────────────────────────
    property bool   slBusy:       hasSandboxLab ? SandboxLab.busy           : false
    property bool   slAvailable:  hasSandboxLab ? SandboxLab.available      : false
    property bool   slGuestReady: hasSandboxLab ? SandboxLab.guestReady     : false
    property string slStatus:     hasSandboxLab ? SandboxLab.statusText     : "SandboxLab not registered"
    property int    slProgress:   hasSandboxLab ? SandboxLab.progressValue  : 0
    property string slStep:       hasSandboxLab ? SandboxLab.currentStep    : ""
    property string slVerdict:    hasSandboxLab ? SandboxLab.verdictSummary : ""
    property var    slResult:     hasSandboxLab ? SandboxLab.resultSummary  : ({})
    property string slLastError:  hasSandboxLab ? SandboxLab.lastError      : ""
    property var    slSteps:      hasSandboxLab ? SandboxLab.stepsModel     : []
    property string slLiveFrame:  hasSandboxLab ? SandboxLab.liveFrameSource : ""
    property bool   slInteractiveActive: hasSandboxLab ? SandboxLab.interactiveSessionActive : false
    property string slUiRunner:   hasSandboxLab ? SandboxLab.uiRunnerStatus : ""
    property var    slReplay:     hasSandboxLab ? SandboxLab.replayFramesModel : []
    property string slLastFolder: hasSandboxLab ? SandboxLab.lastRunFolder  : ""
    property string selectedSamplePath: ""
    property int monitorSeconds: 300
    property bool disableNetwork: false

    readonly property var slTelemetry: {
        if (!slResult || typeof slResult !== "object") return ({})
        return slResult.live_telemetry || ({})
    }

    function metricCount(resultObj, telemetryObj, key) {
        var fromTelemetry = telemetryObj ? telemetryObj[key] : undefined
        if (typeof fromTelemetry === "number") return fromTelemetry
        var fromResult = resultObj ? resultObj[key] : undefined
        if (Array.isArray(fromResult)) return fromResult.length
        if (typeof fromResult === "number") return fromResult
        return 0
    }

    function hasMeaningfulResult(resultObj) {
        if (!resultObj || typeof resultObj !== "object") return false
        var keys = Object.keys(resultObj)
        if (keys.length === 0) return false
        if (keys.length === 1 && keys[0] === "live_telemetry") return false
        return true
    }

    // ── VmwareEmbedder safe accessor ─────────────────────────────────────
    readonly property bool hasEmbedder: typeof VmwareEmbedder !== "undefined" && VmwareEmbedder !== null
    property bool vmEmbedded: hasEmbedder ? VmwareEmbedder.embedded : false

    Connections {
        target: root.hasEmbedder ? VmwareEmbedder : null
        enabled: target !== null
        function onEmbeddedChanged(val) { root.vmEmbedded = val }
    }

    // ── Live preview state ────────────────────────────────────────────────
    property int    pvFrame:   0
    property bool   pvLive:    false
    property string pvFileUrl: ""
    property real   pvLastMs:  0

    // ── Scan pipeline state ───────────────────────────────────────────────
    property bool   scanRunning: false
    property int    scanPct:     0
    property string scanStage:   ""

    // ── UI state ──────────────────────────────────────────────────────────
    property bool showLog:  false
    property bool showDiag: false
    property int  replayIdx: 0

    // ── Connections: SandboxLab ───────────────────────────────────────────
    Connections {
        target: hasSandboxLab ? SandboxLab : null
        enabled: target !== null
        function onStatus(msg)  { root.slStatus = msg }
        function onProgress(v)  { root.slProgress = v }
        function onStep(s)      { root.slStep = s }
        function onIsBusy(b)    { root.slBusy = b }
        function onLiveFramePath(p)        { root.slLiveFrame = p }
        function onVerdictSummaryChanged() { root.slVerdict = SandboxLab.verdictSummary }
        function onResultSummaryChanged()  { root.slResult  = SandboxLab.resultSummary }
        function onLastErrorChanged()      { root.slLastError = SandboxLab.lastError }
        function onStepsModelChanged()     { root.slSteps = SandboxLab.stepsModel }
        function onInteractiveSessionChanged() { root.slInteractiveActive = SandboxLab.interactiveSessionActive }
        function onUiRunnerStatusChanged(s) { root.slUiRunner = s }
        function onDiagnosticsFinished(checks) { diagModel.clear(); for (var i = 0; i < checks.length; i++) diagModel.append(checks[i]); root.showDiag = true }
        function onReplayFramesModelChanged() {
            root.slReplay = SandboxLab.replayFramesModel
            root.replayIdx = Math.max(0, root.slReplay.length - 1)
        }
    }

    // ── Connections: SandboxPreview image provider ────────────────────────
    Connections {
        target: hasPreview ? SandboxPreview : null
        enabled: target !== null
        function onFrameUpdated()   { root.pvFrame++; root.pvLive = true; root.pvLastMs = Date.now(); pvAgeTimer.restart() }
        function onPreviewStarted() { root.pvLive = true }
        function onPreviewStopped() { root.pvLive = false }
    }

    // ── Connections: Backend ──────────────────────────────────────────────
    Connections {
        target: hasBackend ? Backend : null
        enabled: target !== null
        function onScanCenterProgress(pct, stage) {
            root.scanPct = pct; root.scanStage = stage
            root.scanRunning = (pct > 0 && pct < 100)
        }
        function onScanCenterFinished(_r) { root.scanRunning = false }
        function onScanCenterFailed(_m)   { root.scanRunning = false }
        function onScanCenterPreviewUpdated(url) {
            if (url !== "") { root.pvFileUrl = url; root.pvLastMs = Date.now(); pvAgeTimer.restart() }
            else { root.pvFileUrl = ""; root.pvLastMs = 0; pvAgeTimer.stop() }
        }
        function onSandboxHandoffRequested(path) {
            if (path && path !== "") {
                root.selectedSamplePath = path
                root.slStatus = "Sample received from ScanCenter handoff."
            }
        }
        function onAgentStepAdded(stepJson) {
            try {
                var s = JSON.parse(stepJson)
                timelineModel.append({ ts: s.ts||"", stage: s.stage||"", title: s.title||"", result: s.result||"", status: s.status||"ok" })
            } catch(_e) {}
        }
        function onAgentStepsCleared() { timelineModel.clear() }
    }

    // ── Models & Timer ────────────────────────────────────────────────────
    ListModel { id: timelineModel }
    ListModel { id: diagModel }

    Timer {
        id: pvAgeTimer
        interval: 1000; repeat: true; running: false
        property int tick: 0
        onTriggered: tick++
    }

    FileDialog {
        id: interactiveFilePicker
        title: "Select sample for interactive analysis"
        fileMode: FileDialog.OpenFile
        onAccepted: {
            var s = selectedFile.toString()
                .replace(/^file:\/\/\//i, "")
                .replace(/\//g, "\\")
            root.selectedSamplePath = s
        }
    }

    // ══════════════════════════════════════════════════════════════════════
    //  FULL-HEIGHT LAYOUT
    //  Header + Status + Theater fill the viewport.
    //  Everything else scrolls below.
    // ══════════════════════════════════════════════════════════════════════

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        // ══════════════════════════════════════════════════════════
        // HEADER ROW (fixed)
        // ══════════════════════════════════════════════════════════
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // ← Back to File Scanner
            Rectangle {
                implicitWidth: backRow.implicitWidth + 20
                implicitHeight: 36; radius: 8
                color: backMa.containsMouse ? ThemeManager.elevated() : "transparent"
                border.color: ThemeManager.border(); border.width: 1

                Row {
                    id: backRow; anchors.centerIn: parent; spacing: 6
                    Text { text: "\u2190"; color: ThemeManager.primary; font.pixelSize: 16; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "Back to File Scanner"; color: ThemeManager.primary; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                }
                MouseArea {
                    id: backMa; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: window.loadRoute("scan-tool")
                }
                ToolTip.visible: backMa.containsMouse; ToolTip.delay: 400
                ToolTip.text: "Return to the File Scanner page"
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "\uD83D\uDDA5  Detonation Theater"
                    color: ThemeManager.foreground()
                    font.pixelSize: ThemeManager.fontSize_h2
                    font.weight: Font.Bold
                }
                Text {
                    text: "Live sandbox feed for analyst-driven interactive sessions."
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_small
                }
            }

            // VMware badge
            Rectangle {
                implicitWidth: vmBadgeRow.implicitWidth + 20
                implicitHeight: 30; radius: 15
                color: root.slAvailable ? "#16a34a22" : "#dc262622"
                border.color: root.slAvailable ? "#22c55e" : "#ef4444"; border.width: 1
                RowLayout {
                    id: vmBadgeRow; anchors.centerIn: parent; spacing: 6
                    Rectangle { width: 8; height: 8; radius: 4; color: root.slAvailable ? "#22c55e" : "#ef4444" }
                    Text { text: root.slAvailable ? "VMware Ready" : "VMware Unavailable"; color: root.slAvailable ? "#22c55e" : "#ef4444"; font.pixelSize: 12; font.weight: Font.Medium }
                }
            }

            // Guest Auth badge
            Rectangle {
                implicitWidth: guestBadgeRow.implicitWidth + 20
                implicitHeight: 30; radius: 15
                color: root.slGuestReady ? "#16a34a22" : "#ca8a0422"
                border.color: root.slGuestReady ? "#22c55e" : "#eab308"; border.width: 1
                RowLayout {
                    id: guestBadgeRow; anchors.centerIn: parent; spacing: 6
                    Rectangle { width: 8; height: 8; radius: 4; color: root.slGuestReady ? "#22c55e" : "#eab308" }
                    Text { text: root.slGuestReady ? "Guest Auth OK" : "Guest Auth Missing"; color: root.slGuestReady ? "#22c55e" : "#eab308"; font.pixelSize: 12; font.weight: Font.Medium }
                }
            }

            // Refresh
            Rectangle {
                implicitWidth: 36; implicitHeight: 36; radius: 8
                color: refreshMa.containsMouse ? ThemeManager.elevated() : "transparent"
                border.color: ThemeManager.border(); border.width: 1
                Text { anchors.centerIn: parent; text: "\u21BB"; color: ThemeManager.muted(); font.pixelSize: 18 }
                MouseArea {
                    id: refreshMa; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor; enabled: !root.slBusy
                    onClicked: if (root.hasSandboxLab) SandboxLab.refreshStatus()
                }
                ToolTip.visible: refreshMa.containsMouse; ToolTip.delay: 400
                ToolTip.text: "Re-check VMware availability"
            }
        }

        // ══════════════════════════════════════════════════════════
        // STATUS BAR (fixed, compact)
        // ══════════════════════════════════════════════════════════
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.scanRunning ? 48 : 38
            radius: 8; clip: true
            color: ThemeManager.surface()
            border.color: ThemeManager.border(); border.width: 1

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    Layout.leftMargin: 12; Layout.rightMargin: 12
                    spacing: 8

                    Rectangle {
                        width: 8; height: 8; radius: 4
                        Layout.alignment: Qt.AlignVCenter
                        visible: root.scanRunning || root.slBusy
                        color: root.scanRunning ? ThemeManager.primary : ThemeManager.warning
                        SequentialAnimation on opacity {
                            loops: Animation.Infinite; running: root.scanRunning || root.slBusy
                            NumberAnimation { to: 0.3; duration: 600 }
                            NumberAnimation { to: 1.0; duration: 600 }
                        }
                    }

                    Text {
                        text: root.scanRunning ? root.scanStage : root.slStatus
                        color: ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_small
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        visible: root.slStep !== "" && !root.scanRunning
                        text: root.slStep
                        color: ThemeManager.primary
                        font.pixelSize: ThemeManager.fontSize_small
                        font.weight: Font.Medium
                    }

                    Text {
                        visible: root.scanRunning
                        text: root.scanPct + "%"
                        color: ThemeManager.primary
                        font.pixelSize: ThemeManager.fontSize_small
                        font.weight: Font.Medium
                    }

                }

                ProgressBar {
                    id: progressBar
                    visible: root.scanRunning
                    Layout.fillWidth: true
                    Layout.leftMargin: 12; Layout.rightMargin: 12
                    Layout.preferredHeight: 6
                    value: root.scanPct / 100
                    background: Rectangle { implicitHeight: 6; radius: 3; color: ThemeManager.elevated() }
                    contentItem: Item {
                        implicitHeight: 6
                        Rectangle {
                            width: parent.width * root.scanPct / 100
                            height: parent.height; radius: 3; color: ThemeManager.primary
                            Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 92
            radius: 10
            color: ThemeManager.panel()
            border.color: ThemeManager.border()
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "Interactive Session"
                        color: ThemeManager.foreground()
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    Rectangle {
                        implicitWidth: modePill.implicitWidth + 12
                        implicitHeight: 20
                        radius: 10
                        color: root.slInteractiveActive ? "#16a34a22" : ThemeManager.elevated()
                        border.color: root.slInteractiveActive ? "#22c55e" : ThemeManager.border()
                        border.width: 1
                        Text {
                            id: modePill
                            anchors.centerIn: parent
                            text: root.slInteractiveActive ? "RUNNING" : "IDLE"
                            color: root.slInteractiveActive ? "#22c55e" : ThemeManager.muted()
                            font.pixelSize: 10
                            font.weight: Font.Bold
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: root.selectedSamplePath !== "" ? root.selectedSamplePath.split("\\").pop() : "No sample selected"
                        color: root.selectedSamplePath !== "" ? ThemeManager.foreground() : ThemeManager.muted()
                        font.pixelSize: 11
                        elide: Text.ElideLeft
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 300
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Button {
                        text: "Select Sample"
                        enabled: !root.slBusy
                        onClicked: interactiveFilePicker.open()
                    }

                    Label {
                        text: "Monitor (s)"
                        color: ThemeManager.muted()
                    }

                    SpinBox {
                        from: 30
                        to: 1800
                        stepSize: 15
                        value: root.monitorSeconds
                        enabled: !root.slBusy && !root.slInteractiveActive
                        onValueModified: root.monitorSeconds = value
                    }

                    CheckBox {
                        text: "Disable network"
                        checked: root.disableNetwork
                        enabled: !root.slBusy && !root.slInteractiveActive
                        onToggled: root.disableNetwork = checked
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "Start Analysis"
                        enabled: root.hasSandboxLab && !root.slBusy && !root.slInteractiveActive && root.selectedSamplePath !== ""
                        onClicked: SandboxLab.startInteractiveSession(root.selectedSamplePath, root.monitorSeconds, root.disableNetwork)
                    }

                    Button {
                        text: "Stop Analysis"
                        enabled: root.hasSandboxLab && !root.slBusy && root.slInteractiveActive
                        onClicked: SandboxLab.stopInteractiveSession()
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════════
        // THEATER PANEL — fills remaining vertical space
        // ══════════════════════════════════════════════════════════
        Rectangle {
            id: theaterPanel
            Layout.fillWidth: true
            Layout.fillHeight: true    // <— takes all remaining space

            radius: 12; clip: true
            color: ThemeManager.panel()
            border.color: root.pvLive ? ThemeManager.success : ThemeManager.border()
            border.width: root.pvLive ? 2 : 1
            Behavior on border.color { ColorAnimation { duration: 300 } }

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // ── Theater header bar ───────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 40
                    color: ThemeManager.elevated()
                    border.color: ThemeManager.border(); border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16; anchors.rightMargin: 16
                        spacing: 10

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: root.pvLive ? ThemeManager.success : ThemeManager.warning
                            SequentialAnimation on opacity {
                                loops: Animation.Infinite; running: root.pvLive
                                NumberAnimation { to: 0.2; duration: 600 }
                                NumberAnimation { to: 1.0; duration: 600 }
                            }
                        }

                        Text {
                            text: "\uD83D\uDDB5  Sandbox Live Preview"
                            color: ThemeManager.foreground()
                            font.pixelSize: 13; font.weight: Font.DemiBold
                        }

                        Item { Layout.fillWidth: true }

                        // VM control buttons — inline in header
                        Repeater {
                            model: [
                                { label: "\u26A1 Start",   action: "start",    needsAvail: true },
                                { label: "\u23F9 Stop",    action: "stop",     needsAvail: false },
                                { label: "\u21BB Revert",  action: "revert",   needsAvail: true },
                                { label: "\uD83D\uDD2C Diag", action: "diagnose", needsAvail: false }
                            ]

                            delegate: Rectangle {
                                implicitWidth: vmBtnTxt.implicitWidth + 16
                                implicitHeight: 28; radius: 6
                                color: vmBtnMa.containsMouse ? ThemeManager.surface() : "transparent"
                                border.color: ThemeManager.border(); border.width: 1
                                opacity: vmBtnMa.enabled ? 1.0 : 0.35

                                Text {
                                    id: vmBtnTxt; anchors.centerIn: parent
                                    text: modelData.label; color: ThemeManager.foreground()
                                    font.pixelSize: 11
                                }
                                MouseArea {
                                    id: vmBtnMa; anchors.fill: parent; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: !root.slBusy && (!modelData.needsAvail || root.slAvailable)
                                    onClicked: {
                                        if (!root.hasSandboxLab) return
                                        switch (modelData.action) {
                                            case "start":    SandboxLab.startVm(); break
                                            case "stop":     SandboxLab.stopVm(); break
                                            case "revert":   SandboxLab.resetToClean(); break
                                            case "diagnose": SandboxLab.runVmwareDiagnostics(); break
                                        }
                                    }
                                }
                                ToolTip.visible: vmBtnMa.containsMouse; ToolTip.delay: 400
                                ToolTip.text: {
                                    switch (modelData.action) {
                                        case "start":    return "Start the sandbox VM"
                                        case "stop":     return "Force stop the sandbox VM"
                                        case "revert":   return "Revert VM to clean snapshot"
                                        case "diagnose": return "Run VMware diagnostics"
                                        default: return ""
                                    }
                                }
                            }
                        }

                        // LIVE / age indicator
                        Text {
                            visible: root.pvLive || root.pvFileUrl !== ""
                            text: {
                                var _t = pvAgeTimer.tick
                                if (root.pvLive) return "LIVE"
                                var dt = root.pvLastMs > 0 ? Math.round((Date.now() - root.pvLastMs) / 1000) : 0
                                return dt + "s ago"
                            }
                            color: root.pvLive ? ThemeManager.success : ThemeManager.muted()
                            font.pixelSize: 10; font.bold: root.pvLive
                        }
                    }
                }

                // ── Full-width Live VM Preview / Embed Area ─────
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    // ── QWindow-based VM embedding via WindowContainer ──
                    WindowContainer {
                        id: vmContainer
                        window: root.hasEmbedder ? VmwareEmbedder.vmWindow : null
                        anchors.fill: parent
                        anchors.margins: 8
                        visible: root.vmEmbedded
                    }

                    // ── Screenshot-based fallback previews ───────
                    Image {
                        anchors.fill: parent; anchors.margins: 8
                        fillMode: Image.PreserveAspectFit
                        cache: false; asynchronous: true; mipmap: true; smooth: true
                        source: root.pvLive ? "image://sandboxpreview/frame?t=" + root.pvFrame : ""
                        visible: root.pvLive && !root.vmEmbedded
                    }
                    Image {
                        anchors.fill: parent; anchors.margins: 8
                        fillMode: Image.PreserveAspectFit
                        cache: false; asynchronous: true; mipmap: true; smooth: true
                        source: (!root.pvLive && root.pvFileUrl !== "") ? root.pvFileUrl : ""
                        visible: !root.pvLive && root.pvFileUrl !== "" && !root.vmEmbedded
                    }

                    // ── LIVE / EMBEDDED badge overlay ────────────
                    Rectangle {
                        anchors.left: parent.left; anchors.bottom: parent.bottom
                        anchors.leftMargin: 14; anchors.bottomMargin: 14
                        visible: root.vmEmbedded || root.pvLive || root.pvFileUrl !== ""
                        implicitWidth: liveBadgeRow.implicitWidth + 12
                        implicitHeight: 20; radius: 4
                        color: Qt.rgba(0, 0, 0, 0.62)
                        z: 10
                        Row {
                            id: liveBadgeRow; anchors.centerIn: parent; spacing: 6
                            Rectangle {
                                width: 6; height: 6; radius: 3; y: 5
                                color: root.vmEmbedded ? "#3b82f6" : root.pvLive ? "#22c55e" : ThemeManager.muted()
                                SequentialAnimation on opacity {
                                    running: root.vmEmbedded || root.pvLive; loops: Animation.Infinite
                                    NumberAnimation { to: 0.35; duration: 600 }
                                    NumberAnimation { to: 1.0;  duration: 600 }
                                }
                            }
                            Text {
                                text: {
                                    if (root.vmEmbedded) return "EMBEDDED"
                                    var _t = pvAgeTimer.tick
                                    if (root.pvLive) return "LIVE"
                                    var dt = root.pvLastMs > 0 ? Math.round((Date.now() - root.pvLastMs) / 1000) : 0
                                    return dt + "s ago"
                                }
                                color: "white"; font.pixelSize: 9; font.bold: root.vmEmbedded || root.pvLive
                            }
                        }
                    }

                    // ── "Finish Interactive Session" button overlay
                    Rectangle {
                        anchors.right: parent.right; anchors.bottom: parent.bottom
                        anchors.rightMargin: 14; anchors.bottomMargin: 14
                        visible: root.scanRunning
                        implicitWidth: finishBtnRow.implicitWidth + 24
                        implicitHeight: 40; radius: 8
                        color: finishBtnMa.containsMouse ? "#dc2626" : "#b91c1c"
                        border.color: "#ef4444"; border.width: 1
                        z: 10

                        Row {
                            id: finishBtnRow; anchors.centerIn: parent; spacing: 8
                            Text { text: "\u23F9"; color: "white"; font.pixelSize: 16; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: "Finish Interactive Session"
                                color: "white"; font.pixelSize: 13; font.weight: Font.Bold
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: finishBtnMa; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (typeof Backend !== "undefined" && Backend.finishInteractiveSession)
                                    Backend.finishInteractiveSession()
                            }
                        }
                    }

                    // ── Idle placeholder ─────────────────────────
                    Rectangle {
                        anchors.fill: parent; anchors.margins: 8
                        visible: !root.pvLive && root.pvFileUrl === "" && !root.vmEmbedded
                        color: ThemeManager.surface()
                        border.color: ThemeManager.border(); border.width: 1; radius: 6
                        ColumnLayout {
                            anchors.centerIn: parent; spacing: 8
                            Text {
                                text: root.scanRunning ? "\uD83D\uDDB5" : "\uD83D\uDD12"
                                font.pixelSize: 48; opacity: 0.3
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: root.scanRunning ? "Preview starting\u2026 (VM powering on)" : "Start an interactive session to begin monitoring."
                                color: ThemeManager.muted(); font.pixelSize: 13
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════════
        // SCROLLABLE LOWER SECTION — results, logs, etc.
        // ══════════════════════════════════════════════════════════
        ScrollView {
            id: lowerScroll
            Layout.fillWidth: true
            Layout.preferredHeight: lowerContent.implicitHeight > 0 ? Math.min(lowerContent.implicitHeight + 16, 500) : 0
            visible: lowerContent.implicitHeight > 0
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                id: lowerContent
                width: lowerScroll.availableWidth
                spacing: 12

                // ── Error banner ─────────────────────────────────
                Rectangle {
                    visible: root.slLastError !== ""
                    Layout.fillWidth: true
                    implicitHeight: errCol.implicitHeight + 20; radius: 8
                    color: "#dc262618"; border.color: "#dc2626"; border.width: 1
                    ColumnLayout {
                        id: errCol
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.top: parent.top; anchors.margins: 10; spacing: 4
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Text { text: "\u26A0  Error"; color: ThemeManager.danger; font.pixelSize: 13; font.weight: Font.DemiBold }
                            Item { Layout.fillWidth: true }
                            Text { text: "\u2715"; color: ThemeManager.muted(); font.pixelSize: 14; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.slLastError = "" } }
                        }
                        Text { text: root.slLastError; color: ThemeManager.danger; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    }
                }

                // ── Live frame viewer (standalone detonation) ────
                Rectangle {
                    visible: root.slLiveFrame !== "" && root.slBusy
                    Layout.fillWidth: true
                    implicitHeight: liveViewCol.implicitHeight + 28; radius: 12
                    color: ThemeManager.panel()
                    border.color: root.slInteractiveActive ? "#16a34a" : ThemeManager.border()
                    border.width: root.slInteractiveActive ? 2 : 1
                    Behavior on border.color { ColorAnimation { duration: 300 } }
                    ColumnLayout {
                        id: liveViewCol
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.top: parent.top; anchors.margins: 14; spacing: 8
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Text { text: "\uD83D\uDCF9  Live VM View"; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: Font.DemiBold }
                            Rectangle {
                                visible: root.slInteractiveActive
                                implicitWidth: autoRow.implicitWidth + 12; implicitHeight: 20; radius: 10
                                color: "#16a34a28"; border.color: "#16a34a"; border.width: 1
                                RowLayout {
                                    id: autoRow; anchors.centerIn: parent; spacing: 4
                                    Rectangle {
                                        width: 6; height: 6; radius: 3; color: "#22c55e"
                                        SequentialAnimation on opacity {
                                            loops: Animation.Infinite; running: root.slInteractiveActive
                                            NumberAnimation { to: 0.2; duration: 500 }
                                            NumberAnimation { to: 1.0; duration: 500 }
                                        }
                                    }
                                    Text { text: "Session active"; color: "#16a34a"; font.pixelSize: 10; font.weight: Font.Medium }
                                }
                            }
                            Item { Layout.fillWidth: true }
                            Text { visible: root.slReplay.length > 0; text: root.slReplay.length + " frame" + (root.slReplay.length !== 1 ? "s" : ""); color: ThemeManager.muted(); font.pixelSize: 10 }
                        }
                        Image {
                            source: root.pvLive ? "image://sandboxpreview/frame?t=" + root.pvFrame : (root.slLiveFrame !== "" ? ("file:///" + root.slLiveFrame) : "")
                            Layout.fillWidth: true; Layout.preferredHeight: 280
                            fillMode: Image.PreserveAspectFit; cache: false; mipmap: true; smooth: true
                        }
                    }
                }

                // ── Replay carousel ──────────────────────────────
                Rectangle {
                    visible: !root.slBusy && root.slReplay.length > 0
                    Layout.fillWidth: true
                    implicitHeight: replayCol.implicitHeight + 28; radius: 12
                    color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1
                    ColumnLayout {
                        id: replayCol
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.top: parent.top; anchors.margins: 14; spacing: 10
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Text { text: "\uD83C\uDFAC  Session Replay"; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: Font.DemiBold }
                            Text { text: root.slReplay.length + " frame" + (root.slReplay.length !== 1 ? "s" : ""); color: ThemeManager.muted(); font.pixelSize: 11 }
                            Item { Layout.fillWidth: true }
                            Rectangle {
                                implicitWidth: 28; implicitHeight: 28; radius: 6
                                color: prevMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                                border.color: ThemeManager.border(); border.width: 1; opacity: root.replayIdx > 0 ? 1 : 0.35
                                Text { anchors.centerIn: parent; text: "\u2039"; color: ThemeManager.foreground(); font.pixelSize: 16 }
                                MouseArea { id: prevMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (root.replayIdx > 0) root.replayIdx-- }
                            }
                            Text { text: (root.replayIdx + 1) + " / " + root.slReplay.length; color: ThemeManager.foreground(); font.pixelSize: 11; Layout.preferredWidth: 44; horizontalAlignment: Text.AlignHCenter }
                            Rectangle {
                                implicitWidth: 28; implicitHeight: 28; radius: 6
                                color: nextMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                                border.color: ThemeManager.border(); border.width: 1; opacity: root.replayIdx < root.slReplay.length - 1 ? 1 : 0.35
                                Text { anchors.centerIn: parent; text: "\u203A"; color: ThemeManager.foreground(); font.pixelSize: 16 }
                                MouseArea { id: nextMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (root.replayIdx < root.slReplay.length - 1) root.replayIdx++ }
                            }
                        }
                        Image { source: root.slReplay.length > 0 ? root.slReplay[root.replayIdx] : ""; Layout.fillWidth: true; Layout.preferredHeight: 300; fillMode: Image.PreserveAspectFit; cache: false; asynchronous: true; mipmap: true; smooth: true }
                        ScrollView {
                            Layout.fillWidth: true; implicitHeight: 64; clip: true
                            Row {
                                spacing: 6
                                Repeater {
                                    model: root.slReplay
                                    delegate: Rectangle {
                                        width: 90; height: 58; radius: 6
                                        border.color: index === root.replayIdx ? ThemeManager.accent : ThemeManager.border()
                                        border.width: index === root.replayIdx ? 2 : 1; color: ThemeManager.surface()
                                        Image { anchors.fill: parent; anchors.margins: 2; source: modelData; fillMode: Image.PreserveAspectCrop; cache: false; asynchronous: true; mipmap: true; smooth: true }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.replayIdx = index }
                                    }
                                }
                            }
                        }
                    }
                }

                // ── Verdict card ─────────────────────────────────
                Rectangle {
                    visible: (root.slVerdict !== "" || root.slInteractiveActive) && !root.slBusy
                    Layout.fillWidth: true
                    implicitHeight: verdictCol.implicitHeight + 28; radius: 12
                    color: { var v = (root.slVerdict || "").toLowerCase(); if (v.includes("clean") || v.includes("safe")) return "#16a34a18"; if (v.includes("malicious") || v.includes("threat")) return "#dc262618"; if (v.includes("suspicious")) return "#ca8a0418"; return ThemeManager.panel() }
                    border.color: { var v = (root.slVerdict || "").toLowerCase(); if (v.includes("clean") || v.includes("safe")) return "#16a34a"; if (v.includes("malicious") || v.includes("threat")) return "#dc2626"; if (v.includes("suspicious")) return "#ca8a04"; return ThemeManager.border() }
                    border.width: 1
                    ColumnLayout {
                        id: verdictCol
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 6
                        Text { text: "\uD83C\uDFC1  Sandbox Verdict"; color: ThemeManager.muted(); font.pixelSize: 12; font.weight: Font.Medium }
                        Text {
                            text: root.slInteractiveActive ? "Analysis in progress. Verdict is generated when Stop Analysis is pressed." : root.slVerdict
                            color: ThemeManager.foreground(); font.pixelSize: 16; font.weight: Font.Bold; wrapMode: Text.WordWrap; Layout.fillWidth: true
                        }
                    }
                }

                // ── Result metrics grid ──────────────────────────
                Rectangle {
                    visible: (root.slInteractiveActive || root.metricCount(root.slResult, root.slTelemetry, "new_processes") > 0 || root.metricCount(root.slResult, root.slTelemetry, "files_created") > 0 || root.metricCount(root.slResult, root.slTelemetry, "network_connections") > 0 || root.metricCount(root.slResult, root.slTelemetry, "registry_changes") > 0 || root.metricCount(root.slResult, root.slTelemetry, "alerts") > 0) && !root.slBusy
                    Layout.fillWidth: true
                    implicitHeight: metricsGrid.implicitHeight + 28; radius: 12
                    color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1
                    GridLayout {
                        id: metricsGrid
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                        anchors.margins: 14; columns: 5; rowSpacing: 12; columnSpacing: 12
                        Repeater {
                            model: [
                                { label: "Processes", key: "new_processes", icon: "\u2699" },
                                { label: "New Files", key: "files_created", icon: "\uD83D\uDCC4" },
                                { label: "Connections", key: "network_connections", icon: "\uD83C\uDF10" },
                                { label: "Registry", key: "registry_changes", icon: "\uD83D\uDD11" },
                                { label: "Alerts", key: "alerts", icon: "\u26A0" }
                            ]
                            delegate: Rectangle {
                                implicitWidth: (metricsGrid.width - metricsGrid.columnSpacing * 4) / 5
                                implicitHeight: 64; radius: 10; color: ThemeManager.surface(); border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    anchors.centerIn: parent; spacing: 2
                                    Text { text: modelData.icon; font.pixelSize: 20; Layout.alignment: Qt.AlignHCenter }
                                    Text {
                                        text: String(root.metricCount(root.slResult, root.slTelemetry, modelData.key))
                                        color: {
                                            var cnt = root.metricCount(root.slResult, root.slTelemetry, modelData.key)
                                            return (cnt > 0 && modelData.key === "alerts") ? ThemeManager.warning : ThemeManager.foreground()
                                        }
                                        font.pixelSize: 20; font.weight: Font.Bold; Layout.alignment: Qt.AlignHCenter
                                    }
                                    Text { text: modelData.label; color: ThemeManager.muted(); font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter }
                                }
                            }
                        }
                    }
                }

                // ── Result detail sections ───────────────────────
                Repeater {
                    model: [
                        { title: "\u2699  New Processes", key: "new_processes" },
                        { title: "\uD83D\uDCC4  File System Changes", key: "new_files" },
                        { title: "\uD83C\uDF10  Network Connections", key: "new_connections" },
                        { title: "\uD83D\uDD11  Registry Changes", key: "registry_changes" },
                        { title: "\u26A0  Alerts", key: "alerts" },
                        { title: "\u2715  Errors", key: "errors" }
                    ]
                    delegate: Rectangle {
                        property var items: ((root.slResult || {})[modelData.key]) || []
                        visible: items.length > 0 && !root.slBusy && root.hasMeaningfulResult(root.slResult)
                        Layout.fillWidth: true
                        implicitHeight: detCol.implicitHeight + 28; radius: 12
                        color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1
                        ColumnLayout {
                            id: detCol
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 6
                            Text { text: modelData.title; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: Font.DemiBold }
                            Repeater {
                                model: items
                                Text { text: "  \u2022 " + modelData; color: ThemeManager.muted(); font.pixelSize: 12; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                            }
                        }
                    }
                }

                // ── Execution log (collapsible) ──────────────────
                Rectangle {
                    visible: root.slSteps.length > 0
                    Layout.fillWidth: true
                    implicitHeight: logCol.implicitHeight + 28; radius: 12
                    color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1
                    ColumnLayout {
                        id: logCol
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 6
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Text { text: "\uD83D\uDCCB  Execution Log (" + root.slSteps.length + " events)"; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: Font.DemiBold }
                            Item { Layout.fillWidth: true }
                            Text { text: root.showLog ? "\u25B2 Hide" : "\u25BC Show"; color: ThemeManager.primary; font.pixelSize: 12; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showLog = !root.showLog } }
                        }
                        ColumnLayout {
                            visible: root.showLog; Layout.fillWidth: true; spacing: 3
                            Repeater {
                                model: root.slSteps
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 8
                                    Text { text: modelData.time || ""; color: ThemeManager.muted(); font.pixelSize: 10; font.family: "Consolas"; Layout.preferredWidth: 70 }
                                    Rectangle {
                                        implicitWidth: logStatusTxt.implicitWidth + 12; implicitHeight: 18; radius: 4
                                        color: { var s = (modelData.status || "").toLowerCase(); if (s === "ok") return "#16a34a22"; if (s === "error" || s === "fail") return "#dc262622"; if (s === "warn") return "#ca8a0422"; return ThemeManager.surface() }
                                        Text {
                                            id: logStatusTxt; anchors.centerIn: parent
                                            text: (modelData.status || "").toUpperCase()
                                            color: { var s = (modelData.status || "").toLowerCase(); if (s === "ok") return "#22c55e"; if (s === "error" || s === "fail") return "#ef4444"; if (s === "warn") return "#eab308"; return ThemeManager.muted() }
                                            font.pixelSize: 9; font.weight: Font.Bold
                                        }
                                    }
                                    Text { text: modelData.message || ""; color: ThemeManager.foreground(); font.pixelSize: 12; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                }
                            }
                        }
                    }
                }

                // ── Diagnostics results ──────────────────────────
                Rectangle {
                    visible: root.showDiag && diagModel.count > 0
                    Layout.fillWidth: true
                    implicitHeight: diagCol.implicitHeight + 28; radius: 12
                    color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1
                    ColumnLayout {
                        id: diagCol
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 10
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Text { text: "\uD83D\uDD2C  Diagnostics"; color: ThemeManager.foreground(); font.pixelSize: 14; font.weight: Font.DemiBold }
                            Item { Layout.fillWidth: true }
                            Text { text: "\u2715"; color: ThemeManager.muted(); font.pixelSize: 16; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showDiag = false } }
                        }
                        Repeater {
                            model: diagModel
                            delegate: Rectangle {
                                Layout.fillWidth: true; implicitHeight: diagItemCol.implicitHeight + 16; radius: 8
                                color: model.passed ? "#16a34a12" : "#dc262612"
                                border.color: model.passed ? "#16a34a" : "#dc2626"; border.width: 1
                                ColumnLayout {
                                    id: diagItemCol
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; spacing: 4
                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 8
                                        Text { text: model.passed ? "\u2713" : "\u2717"; color: model.passed ? "#22c55e" : "#ef4444"; font.pixelSize: 14; font.weight: Font.Bold }
                                        Text { text: model.check || ""; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                    }
                                    Text { text: model.message || ""; color: ThemeManager.muted(); font.pixelSize: 12; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; Layout.leftMargin: 22 }
                                    Text { visible: !model.passed && (model.fix || "") !== ""; text: "Fix: " + (model.fix || ""); color: "#f59e0b"; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.leftMargin: 22 }
                                }
                            }
                        }
                    }
                }

                // ── Last run folder link ─────────────────────────
                RowLayout {
                    visible: !root.slBusy && root.slLastFolder !== ""
                    Layout.fillWidth: true; spacing: 10
                    Text { text: "Last run folder:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                    Text {
                        text: root.slLastFolder; color: ThemeManager.primary; font.pixelSize: 12; font.underline: true
                        elide: Text.ElideLeft; Layout.fillWidth: true
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (root.hasSandboxLab) SandboxLab.openLastRunFolder() }
                    }
                }

                Item { height: 16 }
            }
        }
    }
}
