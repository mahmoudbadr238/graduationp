import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../theme"

// ── VMware Sandbox Lab — Detonation Theater ───────────────────────────────
// Read-only view automatically activated by the File Scan pipeline during
// Phase 4 (sandbox detonation).  Shows the live SandboxPreviewStream feed
// and the Agent Timeline.  No manual detonation controls — the scan is
// driven entirely from the File Scan tab.
// ─────────────────────────────────────────────────────────────────────────
ScrollView {
    id: root
    clip: true

    // ── SandboxLab controller state ──────────────────────────────────────────
    property bool   _busy:      (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.busy       : false
    property bool   _available: (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.available  : false
    property bool   _guestOk:   (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.guestReady : false
    property string _status:    (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.statusText : "SandboxLab not registered"
    property int    _progress:  (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.progressValue : 0
    property string _step:      (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.currentStep  : ""
    property string _verdict:   (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.verdictSummary : ""
    property var    _result:    (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.resultSummary  : ({})
    property string _liveFrame: (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.liveFrameSource    : ""
    property string _lastError: (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.lastError          : ""
    property var    _steps:     (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.stepsModel          : []
    property bool   _automationVisible: (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.automationVisible : false
    property string _uiRunnerStatus:    (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.uiRunnerStatus    : ""
    property var    _replayFrames:      (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.replayFramesModel  : []
    property int    _replayIndex:  0
    property var    _diagChecks:   []

    // ── Live preview state ──────────────────────────────────────────────────
    property int    _pvFrame:   0      // cache-bust counter for image://sandboxpreview/
    property bool   _pvLive:    false  // true while image provider is streaming
    property string _pvFileUrl: ""     // file:/// URL fallback from scanCenterPreviewUpdated
    property real   _pvLastMs:  0      // timestamp of last frame

    // ── ScanCenter pipeline state (forwarded from File Scan) ────────────────
    property bool   _scanRunning: false
    property int    _scanPct:     0
    property string _scanStage:   ""

    // ── UI state ────────────────────────────────────────────────────────────
    property bool showLog:  false
    property bool showDiag: false

    // ── Connections to SandboxLabController ───────────────────────────────────
    Connections {
        target: (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab : null
        enabled: target !== null

        function onStatus(msg) { root._status = msg }
        function onProgress(v) { root._progress = v }
        function onStep(s)     { root._step = s }
        function onIsBusy(b)   { root._busy = b }
        function onLiveFramePath(p) { root._liveFrame = p }
        function onVerdictSummaryChanged() { root._verdict = SandboxLab.verdictSummary }
        function onResultSummaryChanged()  { root._result  = SandboxLab.resultSummary }
        function onLastErrorChanged()      { root._lastError = SandboxLab.lastError }
        function onStepsModelChanged()     { root._steps = SandboxLab.stepsModel }
        function onDiagnosticsFinished(checks) { root._diagChecks = checks; root.showDiag = true }
        function onAutomationVisibleChanged()  { root._automationVisible = SandboxLab.automationVisible }
        function onUiRunnerStatusChanged(s)    { root._uiRunnerStatus = s }
        function onReplayFramesModelChanged()  {
            root._replayFrames = SandboxLab.replayFramesModel
            root._replayIndex  = Math.max(0, SandboxLab.replayFramesModel.length - 1)
        }
    }

    // ── SandboxPreview image provider connections (live video feed) ───────────
    Connections {
        target: (typeof SandboxPreview !== "undefined" && SandboxPreview !== null)
                ? SandboxPreview : null
        enabled: target !== null
        function onFrameUpdated()   { root._pvFrame++; root._pvLive = true; root._pvLastMs = Date.now(); if (!pvAgeTimer.running) pvAgeTimer.restart() }
        function onPreviewStarted() { root._pvLive = true }
        function onPreviewStopped() { root._pvLive = false }
    }

    // ── Backend connections (File Scan pipeline feeds this theater) ───────────
    Connections {
        target: (typeof Backend !== "undefined") ? Backend : null
        enabled: target !== null

        function onScanCenterProgress(pct, stage) {
            root._scanPct = pct; root._scanStage = stage; root._scanRunning = (pct > 0 && pct < 100)
        }
        function onScanCenterFinished(_r) { root._scanRunning = false }
        function onScanCenterFailed(_msg) { root._scanRunning = false }

        function onScanCenterPreviewUpdated(url) {
            if (url !== "") {
                root._pvFileUrl = url
                root._pvLastMs  = Date.now()
                pvAgeTimer.restart()
            } else {
                root._pvFileUrl = ""
                root._pvLastMs  = 0
                pvAgeTimer.stop()
            }
        }

        function onAgentStepAdded(stepJson) {
            try {
                var step = JSON.parse(stepJson)
                agentTimelineModel.append({
                    "ts":     step.ts     || "",
                    "stage":  step.stage  || "",
                    "title":  step.title  || "",
                    "result": step.result || "",
                    "status": step.status || "ok"
                })
            } catch (_e) {}
        }
        function onAgentStepsCleared() { agentTimelineModel.clear() }
    }

    // Models
    ListModel { id: agentTimelineModel }

    // Timer — drives the "N s ago" label in the LIVE badge
    Timer {
        id: pvAgeTimer
        interval: 1000; repeat: true; running: false
        property int tick: 0
        onTriggered: tick++
    }

    // ── Page content ──────────────────────────────────────────────────────────
    ColumnLayout {
        width: Math.min(1200, root.availableWidth - 48)
        x: Math.max(24, (root.availableWidth - width) / 2)
        spacing: 0

        Item { height: 24 }

        // ── Page header ───────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                spacing: 4; Layout.fillWidth: true
                Text {
                    text: "\uD83D\uDDA5  Detonation Theater"
                    color: ThemeManager.foreground()
                    font.pixelSize: (ThemeManager.fontSize_h2() || 24)
                    font.weight: (Font.Bold || 700)
                }
                Text {
                    text: "Live sandbox feed \u2014 automatically activated during Phase 4 of a File Scan."
                    color: ThemeManager.muted()
                    font.pixelSize: (ThemeManager.fontSize_small() || 12)
                }
            }

            // Availability badge
            Rectangle {
                implicitWidth: badgeRow.implicitWidth + 20
                implicitHeight: 32; radius: 16
                color: root._available ? "#16a34a22" : "#dc262622"
                border.color: root._available ? "#16a34a" : "#dc2626"; border.width: 1
                RowLayout {
                    id: badgeRow; anchors.centerIn: parent; spacing: 6
                    Rectangle { width: 8; height: 8; radius: 4; color: root._available ? "#22c55e" : "#ef4444" }
                    Text {
                        text: root._available ? "VMware Ready" : "VMware Unavailable"
                        color: root._available ? "#22c55e" : "#ef4444"
                        font.pixelSize: 12; font.weight: (Font.Medium || 500)
                    }
                }
            }

            // Guest credentials badge
            Rectangle {
                implicitWidth: guestRow.implicitWidth + 20
                implicitHeight: 32; radius: 16
                color: root._guestOk ? "#16a34a22" : "#ca8a0422"
                border.color: root._guestOk ? "#16a34a" : "#ca8a04"; border.width: 1
                RowLayout {
                    id: guestRow; anchors.centerIn: parent; spacing: 6
                    Rectangle { width: 8; height: 8; radius: 4; color: root._guestOk ? "#22c55e" : "#eab308" }
                    Text {
                        text: root._guestOk ? "Guest Auth OK" : "Guest Auth Missing"
                        color: root._guestOk ? "#22c55e" : "#eab308"
                        font.pixelSize: 12; font.weight: (Font.Medium || 500)
                    }
                }
            }

            Button {
                enabled: !root._busy
                text: "\u21BA"; implicitWidth: 36; implicitHeight: 36
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.refreshStatus()
                background: Rectangle { color: parent.pressed ? ThemeManager.elevated() : (parent.hovered ? ThemeManager.surface() : "transparent"); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.muted(); font.pixelSize: 18; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Re-check VMware availability"
            }
        }

        // Status bar
        Rectangle {
            Layout.fillWidth: true; Layout.topMargin: 12
            implicitHeight: 38; radius: 8
            color: ThemeManager.surface(); border.color: ThemeManager.border(); border.width: 1
            RowLayout {
                anchors.fill: parent; anchors.margins: 10; spacing: 8
                Text { text: "\uD83D\uDD35"; font.pixelSize: 11; visible: root._scanRunning || root._busy }
                Text {
                    text: root._scanRunning ? root._scanStage : root._status
                    color: ThemeManager.muted(); font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true
                }
                Text {
                    visible: root._scanRunning
                    text: root._scanPct + "%"
                    color: ThemeManager.primary; font.pixelSize: 11; font.weight: (Font.Medium || 500)
                }
                Text {
                    visible: root._step !== "" && !root._scanRunning
                    text: root._step
                    color: ThemeManager.primary; font.pixelSize: 11; font.weight: (Font.Medium || 500)
                    elide: Text.ElideRight; Layout.preferredWidth: 200; horizontalAlignment: Text.AlignRight
                }
            }
        }

        Item { height: 12 }

        // ── VM Controls bar (manual VM management only) ───────────────────────
        RowLayout {
            Layout.fillWidth: true; spacing: 10

            Item { Layout.fillWidth: true }

            Button {
                text: "\u26A1 Start VM"; implicitHeight: 38; enabled: !root._busy && root._available
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.startVm()
                background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Start the sandbox VM"
            }
            Button {
                text: "\u2B1B Stop VM"; implicitHeight: 38; enabled: !root._busy
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.stopVm()
                background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Force stop the sandbox VM"
            }
            Button {
                text: "\u21BA Revert"; implicitHeight: 38; enabled: !root._busy && root._available
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.resetToClean()
                background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Revert VM to clean snapshot"
            }
            Button {
                text: "\uD83D\uDD2C Diagnose"; implicitHeight: 38; enabled: !root._busy
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.runVmwareDiagnostics()
                background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Run VMware prerequisite checks"
            }
        }

        Item { height: 16 }

        // ── Error banner ─────────────────────────────────────────────────────
        Rectangle {
            visible: root._lastError !== ""
            Layout.fillWidth: true; Layout.bottomMargin: 12
            implicitHeight: errCol.implicitHeight + 20; radius: 8
            color: "#dc262218"; border.color: "#dc2626"; border.width: 1
            ColumnLayout {
                id: errCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                spacing: 4
                RowLayout {
                    spacing: 8; Layout.fillWidth: true
                    Text { text: "\u26A0  Error"; color: "#ef4444"; font.pixelSize: 13; font.weight: (Font.SemiBold || 600) }
                    Item { Layout.fillWidth: true }
                    Text { text: "\u2715"; color: ThemeManager.muted(); font.pixelSize: 14; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root._lastError = "" } }
                }
                Text { text: root._lastError; color: "#fca5a5"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            }
        }

        // ── Progress bar (from File Scan pipeline) ───────────────────────────
        Rectangle {
            visible: root._scanRunning
            Layout.fillWidth: true; Layout.bottomMargin: 12
            implicitHeight: 32; radius: 8; clip: true
            color: ThemeManager.surface()
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16; spacing: 10
                Text { text: root._scanStage; color: ThemeManager.muted(); font.pixelSize: 12; Layout.preferredWidth: 200; elide: Text.ElideRight }
                ProgressBar { Layout.fillWidth: true; value: root._scanPct / 100 }
                Text { text: root._scanPct + "%"; color: ThemeManager.muted(); font.pixelSize: 12; Layout.preferredWidth: 34; horizontalAlignment: Text.AlignRight }
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // ── LIVE SPLIT PANEL: VM Preview (left) + Agent Timeline (right) ─────
        // ══════════════════════════════════════════════════════════════════════
        Rectangle {
            id: theaterPanel
            Layout.fillWidth: true
            Layout.bottomMargin: 16

            property bool hasContent: root._pvLive || root._pvFileUrl !== "" || agentTimelineModel.count > 0 || root._scanRunning
            implicitHeight: hasContent ? 520 : 180
            Behavior on implicitHeight { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
            radius: 12; clip: true
            color: ThemeManager.panel()
            border.color: root._pvLive ? ThemeManager.success : ThemeManager.border()
            border.width: root._pvLive ? 2 : 1
            Behavior on border.color { ColorAnimation { duration: 300 } }

            ColumnLayout {
                anchors.fill: parent; spacing: 0

                // ─ Header bar ────────────────────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 40
                    color: ThemeManager.elevated()
                    border.color: ThemeManager.border(); border.width: 1
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16; spacing: 10

                        // LIVE dot
                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: root._pvLive ? ThemeManager.success : ThemeManager.warning
                            SequentialAnimation on opacity {
                                loops: Animation.Infinite; running: root._pvLive
                                NumberAnimation { to: 0.2; duration: 600 }
                                NumberAnimation { to: 1.0; duration: 600 }
                            }
                        }
                        Text {
                            text: "\uD83D\uDDB5  Sandbox Live Preview"
                            color: ThemeManager.foreground()
                            font.pixelSize: 13; font.weight: (Font.DemiBold || 600)
                        }

                        Rectangle { width: 1; height: 18; color: ThemeManager.border() }

                        Text {
                            text: "\uD83D\uDCE1  Agent Timeline"
                            color: ThemeManager.foreground()
                            font.pixelSize: 13; font.weight: (Font.DemiBold || 600)
                        }
                        Text {
                            visible: agentTimelineModel.count > 0
                            text: agentTimelineModel.count + " step" + (agentTimelineModel.count !== 1 ? "s" : "")
                            color: ThemeManager.muted(); font.pixelSize: 11
                        }

                        Item { Layout.fillWidth: true }

                        // Last updated
                        Text {
                            visible: root._pvLive || root._pvFileUrl !== ""
                            text: {
                                var _ignored = pvAgeTimer.tick
                                if (root._pvLive) return "LIVE"
                                var dt = root._pvLastMs > 0 ? Math.round((Date.now() - root._pvLastMs) / 1000) : 0
                                return dt + "s ago"
                            }
                            color: root._pvLive ? ThemeManager.success : ThemeManager.muted()
                            font.pixelSize: 10; font.bold: root._pvLive
                        }
                    }
                }

                // ─ LEFT = VM screenshot | RIGHT = Agent Timeline ─────────────
                RowLayout {
                    Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0

                    // LEFT: Live VM preview
                    Item {
                        Layout.preferredWidth: Math.round(parent.width * 0.70)
                        Layout.fillHeight: true

                        Image {
                            id: pvImgLiveLab
                            anchors.fill: parent; anchors.margins: 12
                            fillMode: Image.PreserveAspectFit; cache: false; asynchronous: true
                            mipmap: true; smooth: true; antialiasing: true
                            source: root._pvLive ? "image://sandboxpreview/frame?t=" + root._pvFrame : ""
                            visible: root._pvLive
                        }
                        Image {
                            id: pvImgFallback
                            anchors.fill: parent; anchors.margins: 12
                            fillMode: Image.PreserveAspectFit; cache: false; asynchronous: true
                            mipmap: true; smooth: true; antialiasing: true
                            source: (!root._pvLive && root._pvFileUrl !== "") ? root._pvFileUrl : ""
                            visible: !root._pvLive && root._pvFileUrl !== ""
                        }

                        // LIVE badge overlay
                        Rectangle {
                            anchors.left: parent.left; anchors.bottom: parent.bottom
                            anchors.leftMargin: 16; anchors.bottomMargin: 16
                            visible: root._pvLive || root._pvFileUrl !== ""
                            implicitWidth: liveBadgeRow.implicitWidth + 12; implicitHeight: 20; radius: 4
                            color: Qt.rgba(0, 0, 0, 0.62)
                            Row {
                                id: liveBadgeRow; anchors.centerIn: parent; spacing: 6
                                Rectangle {
                                    width: 6; height: 6; radius: 3; y: 5
                                    color: root._pvLive ? "#22c55e" : ThemeManager.muted()
                                    SequentialAnimation on opacity {
                                        running: root._pvLive; loops: Animation.Infinite
                                        NumberAnimation { to: 0.35; duration: 600 }
                                        NumberAnimation { to: 1.0;  duration: 600 }
                                    }
                                }
                                Text {
                                    text: {
                                        var _ignored = pvAgeTimer.tick
                                        if (root._pvLive) return "LIVE"
                                        var dt = root._pvLastMs > 0 ? Math.round((Date.now() - root._pvLastMs) / 1000) : 0
                                        return dt + "s ago"
                                    }
                                    color: "white"; font.pixelSize: 9; font.bold: root._pvLive
                                }
                            }
                        }

                        // Idle placeholder
                        Rectangle {
                            anchors.fill: parent; anchors.margins: 12
                            visible: !root._pvLive && root._pvFileUrl === ""
                            color: ThemeManager.surface(); border.color: ThemeManager.border(); border.width: 1; radius: 6
                            ColumnLayout {
                                anchors.centerIn: parent; spacing: 8
                                Text { text: root._scanRunning ? "\uD83D\uDDB5" : "\uD83D\uDD12"; font.pixelSize: 36; opacity: 0.3; Layout.alignment: Qt.AlignHCenter }
                                Text {
                                    text: root._scanRunning ? "Preview starting\u2026 (VM powering on)" : "Waiting for Phase 4 to start\u2026"
                                    color: ThemeManager.muted(); font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                    }

                    Rectangle { width: 1; Layout.fillHeight: true; color: ThemeManager.border() }

                    // RIGHT: Agent Timeline
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0

                        // Empty state
                        Item {
                            visible: agentTimelineModel.count === 0
                            Layout.fillWidth: true; Layout.fillHeight: true
                            ColumnLayout {
                                anchors.centerIn: parent; spacing: 8
                                Text { text: "\uD83D\uDCE1"; font.pixelSize: 32; opacity: 0.25; Layout.alignment: Qt.AlignHCenter }
                                Text {
                                    text: root._scanRunning ? "Steps streaming\u2026" : "Agent timeline will appear here during Phase 4."
                                    color: ThemeManager.muted(); font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }

                        ListView {
                            id: tlList
                            visible: agentTimelineModel.count > 0
                            Layout.fillWidth: true; Layout.fillHeight: true
                            model: agentTimelineModel; clip: true; spacing: 2
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            onCountChanged: if (root._scanRunning) tlList.positionViewAtEnd()

                            delegate: Rectangle {
                                width: tlList.width
                                implicitHeight: tlRow.implicitHeight + 14; radius: 5
                                color: index % 2 === 0 ? "transparent" : ThemeManager.elevated()

                                RowLayout {
                                    id: tlRow
                                    anchors.left: parent.left; anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 8

                                    Rectangle {
                                        width: 8; height: 8; radius: 4; Layout.alignment: Qt.AlignVCenter
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
                                            running: (model.status || "") === "running" && root._scanRunning
                                            NumberAnimation { to: 0.25; duration: 500 }
                                            NumberAnimation { to: 1.0;  duration: 500 }
                                        }
                                    }
                                    Text { text: model.ts || ""; color: ThemeManager.muted(); font.pixelSize: 10; font.family: "Consolas"; Layout.preferredWidth: 54 }
                                    Rectangle {
                                        implicitWidth: stageTxt.implicitWidth + 10; implicitHeight: 15; radius: 7
                                        color: ThemeManager.elevated()
                                        Text { id: stageTxt; anchors.centerIn: parent; text: (model.stage || "").toUpperCase(); color: ThemeManager.accent; font.pixelSize: 8; font.weight: (Font.Bold || 700) }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true; spacing: 1
                                        Text { text: model.title || ""; color: ThemeManager.foreground(); font.pixelSize: 12; font.weight: (Font.Medium || 500); elide: Text.ElideRight; Layout.fillWidth: true }
                                        Text { visible: (model.result || "") !== ""; text: model.result || ""; color: ThemeManager.muted(); font.pixelSize: 10; font.family: "Consolas"; elide: Text.ElideRight; Layout.fillWidth: true }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        } // theaterPanel

        // ── Live frame viewer (SandboxLab standalone) ─────────────────────────
        Rectangle {
            visible: root._liveFrame !== "" && root._busy
            Layout.fillWidth: true; Layout.bottomMargin: 16
            implicitHeight: liveViewerCol.implicitHeight + 28; radius: 12
            color: ThemeManager.panel()
            border.color: root._automationVisible ? "#16a34a" : ThemeManager.border()
            border.width: root._automationVisible ? 2 : 1
            Behavior on border.color { ColorAnimation { duration: 300 } }

            ColumnLayout {
                id: liveViewerCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14; spacing: 8

                RowLayout {
                    Layout.fillWidth: true; spacing: 8
                    Text { text: "\uD83D\uDCF9  Live VM View"; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600) }

                    Rectangle {
                        visible: root._automationVisible
                        implicitWidth: autoVisBadgeRow.implicitWidth + 12; implicitHeight: 20; radius: 10
                        color: "#16a34a28"; border.color: "#16a34a"; border.width: 1
                        RowLayout {
                            id: autoVisBadgeRow; anchors.centerIn: parent; spacing: 4
                            Rectangle {
                                width: 6; height: 6; radius: 3; color: "#22c55e"
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite; running: root._automationVisible
                                    NumberAnimation { to: 0.2; duration: 500 }
                                    NumberAnimation { to: 1.0; duration: 500 }
                                }
                            }
                            Text { text: "Automation visible"; color: "#16a34a"; font.pixelSize: 10; font.weight: (Font.Medium || 500) }
                        }
                    }

                    Item { Layout.fillWidth: true }
                    Text { visible: root._replayFrames.length > 0; text: root._replayFrames.length + " frame" + (root._replayFrames.length !== 1 ? "s" : ""); color: ThemeManager.muted(); font.pixelSize: 10 }
                }

                Image {
                    source: root._pvLive ? "image://sandboxpreview/frame?t=" + root._pvFrame : (root._liveFrame !== "" ? ("file:///" + root._liveFrame) : "")
                    Layout.fillWidth: true; Layout.preferredHeight: 280
                    fillMode: Image.PreserveAspectFit; cache: false
                    mipmap: true; smooth: true; antialiasing: true
                }
            }
        }

        // ── Automation Replay Carousel ────────────────────────────────────────
        Rectangle {
            id: replayCard
            visible: !root._busy && root._replayFrames.length > 0
            Layout.fillWidth: true; Layout.bottomMargin: 16
            implicitHeight: replayCardCol.implicitHeight + 28; radius: 12
            color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1

            ColumnLayout {
                id: replayCardCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14; spacing: 10

                RowLayout {
                    Layout.fillWidth: true; spacing: 8
                    Text { text: "\uD83C\uDFAC  Automation Replay"; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600) }
                    Text { text: root._replayFrames.length + " frame" + (root._replayFrames.length !== 1 ? "s" : ""); color: ThemeManager.muted(); font.pixelSize: 11 }
                    Item { Layout.fillWidth: true }

                    Rectangle {
                        implicitWidth: 28; implicitHeight: 28; radius: 6
                        color: prevMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                        border.color: ThemeManager.border(); border.width: 1
                        enabled: root._replayIndex > 0; opacity: root._replayIndex > 0 ? 1 : 0.35
                        Text { anchors.centerIn: parent; text: "\u2039"; color: ThemeManager.foreground(); font.pixelSize: 16 }
                        MouseArea { id: prevMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (root._replayIndex > 0) root._replayIndex-- }
                    }
                    Text { text: (root._replayIndex + 1) + " / " + root._replayFrames.length; color: ThemeManager.foreground(); font.pixelSize: 11; Layout.preferredWidth: 44; horizontalAlignment: Text.AlignHCenter }
                    Rectangle {
                        implicitWidth: 28; implicitHeight: 28; radius: 6
                        color: nextMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                        border.color: ThemeManager.border(); border.width: 1
                        enabled: root._replayIndex < root._replayFrames.length - 1; opacity: root._replayIndex < root._replayFrames.length - 1 ? 1 : 0.35
                        Text { anchors.centerIn: parent; text: "\u203A"; color: ThemeManager.foreground(); font.pixelSize: 16 }
                        MouseArea { id: nextMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (root._replayIndex < root._replayFrames.length - 1) root._replayIndex++ }
                    }
                }

                Image {
                    source: root._replayFrames.length > 0 ? root._replayFrames[root._replayIndex] : ""
                    Layout.fillWidth: true; Layout.preferredHeight: 300
                    fillMode: Image.PreserveAspectFit; cache: false; asynchronous: true
                    mipmap: true; smooth: true; antialiasing: true
                }

                ScrollView {
                    Layout.fillWidth: true; implicitHeight: 64; clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AsNeeded; ScrollBar.vertical.policy: ScrollBar.AlwaysOff
                    Row {
                        spacing: 6
                        Repeater {
                            model: root._replayFrames
                            delegate: Rectangle {
                                width: 90; height: 58; radius: 6
                                border.color: index === root._replayIndex ? "#7c3aed" : ThemeManager.border()
                                border.width: index === root._replayIndex ? 2 : 1
                                color: ThemeManager.surface()
                                Image { anchors.fill: parent; anchors.margins: 2; source: modelData; fillMode: Image.PreserveAspectCrop; cache: false; asynchronous: true; mipmap: true; smooth: true; antialiasing: true }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root._replayIndex = index }
                            }
                        }
                    }
                }
            }
        }

        // ── Verdict card ──────────────────────────────────────────────────────
        Rectangle {
            visible: root._verdict !== "" && !root._busy
            Layout.fillWidth: true; Layout.bottomMargin: 16
            implicitHeight: verdictContent.implicitHeight + 28; radius: 12
            color: {
                var v = (root._verdict || "").toLowerCase()
                if (v.includes("clean") || v.includes("safe")) return "#16a34a18"
                if (v.includes("malicious") || v.includes("threat")) return "#dc262618"
                if (v.includes("suspicious")) return "#ca8a0418"
                return ThemeManager.panel()
            }
            border.color: {
                var v = (root._verdict || "").toLowerCase()
                if (v.includes("clean") || v.includes("safe")) return "#16a34a"
                if (v.includes("malicious") || v.includes("threat")) return "#dc2626"
                if (v.includes("suspicious")) return "#ca8a04"
                return ThemeManager.border()
            }
            border.width: 1

            ColumnLayout {
                id: verdictContent
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14; spacing: 6
                Text { text: "\uD83C\uDFC1  Sandbox Verdict"; color: ThemeManager.muted(); font.pixelSize: 12; font.weight: (Font.Medium || 500) }
                Text { text: root._verdict; color: ThemeManager.foreground(); font.pixelSize: 16; font.weight: (Font.Bold || 700); wrapMode: Text.WordWrap; Layout.fillWidth: true }
            }
        }

        // ── Result metrics ────────────────────────────────────────────────────
        Rectangle {
            visible: Object.keys(root._result || {}).length > 0 && !root._busy
            Layout.fillWidth: true; Layout.bottomMargin: 16
            implicitHeight: metricsGrid.implicitHeight + 28; radius: 12
            color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1

            GridLayout {
                id: metricsGrid
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14; columns: 5; rowSpacing: 12; columnSpacing: 12

                Repeater {
                    model: [
                        { label: "Processes",   key: "new_processes",    icon: "\u2699" },
                        { label: "New Files",    key: "new_files",        icon: "\uD83D\uDCC4" },
                        { label: "Connections",  key: "new_connections",  icon: "\uD83C\uDF10" },
                        { label: "Registry",     key: "registry_changes", icon: "\uD83D\uDD11" },
                        { label: "Alerts",       key: "alerts",           icon: "\u26A0" },
                    ]
                    delegate: Rectangle {
                        implicitWidth: (metricsGrid.width - metricsGrid.columnSpacing * 4) / 5
                        implicitHeight: 64; radius: 10
                        color: ThemeManager.surface(); border.color: ThemeManager.border(); border.width: 1
                        ColumnLayout {
                            anchors.centerIn: parent; spacing: 2
                            Text { text: modelData.icon; font.pixelSize: 20; Layout.alignment: Qt.AlignHCenter }
                            Text {
                                text: { var arr = (root._result || {})[modelData.key]; return (arr && arr.length !== undefined) ? String(arr.length) : "0" }
                                color: { var arr = (root._result || {})[modelData.key]; var cnt = (arr && arr.length !== undefined) ? arr.length : 0; return (cnt > 0 && modelData.key === "alerts") ? ThemeManager.warning : ThemeManager.foreground() }
                                font.pixelSize: 20; font.weight: (Font.Bold || 700); Layout.alignment: Qt.AlignHCenter
                            }
                            Text { text: modelData.label; color: ThemeManager.muted(); font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter }
                        }
                    }
                }
            }
        }

        // ── Result detail sections ────────────────────────────────────────────
        Repeater {
            model: [
                { title: "\u2699  New Processes",      key: "new_processes",    color: ThemeManager.foreground() },
                { title: "\uD83D\uDCC4  File System Changes", key: "new_files",        color: ThemeManager.foreground() },
                { title: "\uD83C\uDF10  Network Connections", key: "new_connections",  color: ThemeManager.primary },
                { title: "\uD83D\uDD11  Registry Changes",    key: "registry_changes", color: ThemeManager.foreground() },
                { title: "\u26A0  Alerts",               key: "alerts",           color: ThemeManager.warning },
                { title: "\u2715  Errors",               key: "errors",           color: "#ef4444" },
            ]
            delegate: Rectangle {
                property var items: ((root._result || {})[modelData.key]) || []
                visible: items.length > 0 && !root._busy
                Layout.fillWidth: true; Layout.bottomMargin: 10
                implicitHeight: detailCol.implicitHeight + 28; radius: 12
                color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1

                ColumnLayout {
                    id: detailCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 14; spacing: 6
                    Text { text: modelData.title; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600) }
                    Repeater {
                        model: items
                        Text { text: "  \u2022 " + modelData; color: ThemeManager.muted(); font.pixelSize: 12; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                    }
                }
            }
        }

        // ── Step log ──────────────────────────────────────────────────────────
        Rectangle {
            visible: root._steps.length > 0
            Layout.fillWidth: true; Layout.bottomMargin: 10
            implicitHeight: logHeader.implicitHeight + (root.showLog ? logBody.implicitHeight + 6 : 0) + 28
            radius: 12; color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1

            ColumnLayout {
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14; spacing: 6

                RowLayout {
                    id: logHeader; spacing: 8; Layout.fillWidth: true
                    Text { text: "\uD83D\uDCCB  Execution Log (" + root._steps.length + " events)"; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600) }
                    Item { Layout.fillWidth: true }
                    Text { text: root.showLog ? "\u25B2 Hide" : "\u25BC Show"; color: ThemeManager.primary; font.pixelSize: 12; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showLog = !root.showLog } }
                }

                ColumnLayout {
                    id: logBody; visible: root.showLog; spacing: 3; Layout.fillWidth: true
                    Repeater {
                        model: root._steps
                        RowLayout {
                            spacing: 8; Layout.fillWidth: true
                            Text { text: modelData.time || ""; color: ThemeManager.muted(); font.pixelSize: 10; font.family: "Consolas"; Layout.preferredWidth: 70 }
                            Rectangle {
                                implicitWidth: statusLogTxt.implicitWidth + 12; implicitHeight: 18; radius: 4
                                color: { var s = (modelData.status || "").toLowerCase(); if (s === "ok") return "#16a34a22"; if (s === "error" || s === "fail") return "#dc262622"; if (s === "warn") return "#ca8a0422"; return ThemeManager.surface() }
                                Text {
                                    id: statusLogTxt; anchors.centerIn: parent
                                    text: (modelData.status || "").toUpperCase()
                                    color: { var s = (modelData.status || "").toLowerCase(); if (s === "ok") return "#22c55e"; if (s === "error" || s === "fail") return "#ef4444"; if (s === "warn") return "#eab308"; return ThemeManager.muted() }
                                    font.pixelSize: 9; font.weight: (Font.Bold || 700)
                                }
                            }
                            Text { text: modelData.message || ""; color: ThemeManager.foreground(); font.pixelSize: 12; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                        }
                    }
                }
            }
        }

        // ── Diagnostics results ───────────────────────────────────────────────
        Rectangle {
            visible: root.showDiag && root._diagChecks.length > 0
            Layout.fillWidth: true; Layout.bottomMargin: 10
            implicitHeight: diagCol.implicitHeight + 28; radius: 12
            color: ThemeManager.panel(); border.color: ThemeManager.border(); border.width: 1

            ColumnLayout {
                id: diagCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14; spacing: 10

                RowLayout {
                    spacing: 8; Layout.fillWidth: true
                    Text { text: "\uD83D\uDD2C  Diagnostics"; color: ThemeManager.foreground(); font.pixelSize: 14; font.weight: (Font.SemiBold || 600) }
                    Item { Layout.fillWidth: true }
                    Text { text: "\u2715"; color: ThemeManager.muted(); font.pixelSize: 16; MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showDiag = false } }
                }

                Repeater {
                    model: root._diagChecks
                    delegate: Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: diagItemCol.implicitHeight + 16; radius: 8
                        color: modelData.passed ? "#16a34a12" : "#dc262612"
                        border.color: modelData.passed ? "#16a34a" : "#dc2626"; border.width: 1
                        ColumnLayout {
                            id: diagItemCol
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; spacing: 4
                            RowLayout {
                                spacing: 8; Layout.fillWidth: true
                                Text { text: modelData.passed ? "\u2713" : "\u2717"; color: modelData.passed ? "#22c55e" : "#ef4444"; font.pixelSize: 14; font.weight: (Font.Bold || 700) }
                                Text { text: modelData.check || ""; color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600); Layout.fillWidth: true }
                            }
                            Text { text: modelData.message || ""; color: ThemeManager.muted(); font.pixelSize: 12; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; Layout.leftMargin: 22 }
                            Text { visible: !modelData.passed && (modelData.fix || "") !== ""; text: "Fix: " + (modelData.fix || ""); color: "#f59e0b"; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.leftMargin: 22 }
                        }
                    }
                }
            }
        }

        // ── Open run folder ───────────────────────────────────────────────────
        RowLayout {
            visible: !root._busy && (typeof SandboxLab !== "undefined" && SandboxLab !== null) && SandboxLab.lastRunFolder !== ""
            Layout.fillWidth: true; Layout.topMargin: 4; spacing: 10
            Text { text: "Last run folder:"; color: ThemeManager.muted(); font.pixelSize: 12 }
            Text {
                text: (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.lastRunFolder : ""
                color: ThemeManager.primary; font.pixelSize: 12; font.underline: true; elide: Text.ElideLeft; Layout.fillWidth: true
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.openLastRunFolder() }
            }
        }

        Item { height: 40 }
    }
}