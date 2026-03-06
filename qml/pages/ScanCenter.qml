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
    property bool   optGuiAuto:  false   // "Visible GUI automation" toggle
    property bool   optNet:      true
    property var    explainData: null

    // ── Sandbox live-preview state ──────────────────────────────────────
    property string sandboxPreviewUrl:    ""   // cache-busted file:/// URL or ""
    property real   sandboxPreviewLastMs: 0    // Date.now() of last good capture
    property bool   showPreview:          true // user toggle (persists while page is open)
    property bool   sandboxPanelVisible:  false // true when sandbox panel is open

    // ── Agent Timeline state ────────────────────────────────────────────
    property bool replayActive:      false
    property int  replayCurrentStep: -1

    // ── URL-scan state ─────────────────────────────────────────────────────
    property string urlInput:         ""
    property var    urlResult:        null
    property bool   urlScanning:      false
    property int    urlPct:           0
    property string urlStage:         ""
    property bool   urlOptSandbox:    false
    property bool   urlOptBlockDl:    true
    property bool   urlOptBlockPvt:   true

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

    // ── Backend connections ────────────────────────────────────────────────
    Connections {
        target: (typeof Backend !== "undefined") ? Backend : null
        enabled: target !== null

        // File scan
        function onScanCenterProgress(pct, stage) {
            root.filePct = pct; root.fileStage = stage
        }
        function onScanCenterFinished(r) {
            root.fileReport = r; root.fileScanning = false
            fileSubBar.currentIndex = 0
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
        }
        function onScanCenterExported(result) {
            if (result.ok) expOkLabel.text = "Exported → " + (result.report_path || "")
        }

        // Sandbox live preview ─ emitted by preview_stream.py thread
        function onScanCenterPreviewUpdated(url) {
            if (url !== "") {
                root.sandboxPreviewUrl    = url
                root.sandboxPreviewLastMs = Date.now()
                sandboxAgeTimer.restart()
                root.sandboxPanelVisible = true  // show panel as soon as first frame arrives
            } else {
                // Preview stream stopped — keep the last screenshot; it stays in the panel
                root.sandboxPreviewUrl    = ""
                root.sandboxPreviewLastMs = 0
                sandboxAgeTimer.stop()
            }
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
                // Show the sandbox split panel as soon as steps start arriving
                if (root.optSandbox)
                    root.sandboxPanelVisible = true
            } catch (_e) {}
        }
        function onAgentStepsCleared() {
            agentTimelineListModel.clear()
            root.replayActive      = false
            root.replayCurrentStep = -1
            root.sandboxPreviewUrl = ""  // reset image (new scan starting)
        }

        // When the app navigates back to scan-tool (e.g. notification action),
        // re-show the sandbox panel if there is data to display.
        function onNavigateTo(route) {
            if (route === "scan-tool") {
                if (agentTimelineListModel.count > 0 || root.sandboxPreviewUrl !== "")
                    root.sandboxPanelVisible = true
            }
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

    // Ticks every second while preview is active — drives the "N s ago" label.
    Timer {
        id: sandboxAgeTimer
        interval: 1000
        repeat: true
        running: false
        property int tick: 0   // binding anchor: any expression that reads
        onTriggered: tick++    // this will re-evaluate on every tick
    }

    // Advances replayCurrentStep once per interval during Timeline replay.
    Timer {
        id: replayTimer
        interval: 700
        repeat: true
        running: root.replayActive
        onTriggered: {
            if (root.replayCurrentStep < agentTimelineListModel.count - 1) {
                root.replayCurrentStep++
            } else {
                root.replayActive      = false
                root.replayCurrentStep = -1
            }
        }
    }

    // ── Overlays / dialogs ─────────────────────────────────────────────────
    // Execute-mode confirmation dialog
    Dialog {
        id: execConfirmDlg
        parent: Overlay.overlay
        title: "Allow Sample Execution"
        modal: true
        anchors.centerIn: parent
        width: 420
        standardButtons: Dialog.Yes | Dialog.No

        ColumnLayout {
            spacing: 12
            width: 380

            Text {
                text: "⚠  This will run the sample inside an isolated VM."
                color: ThemeManager.warning
                font.pixelSize: (ThemeManager.fontSize_body() || 14)
                font.weight: (Font.SemiBold || 600)
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Text {
                text: "Only proceed if you trust your sandbox environment and understand that the sample will execute with its normal code path."
                color: ThemeManager.foreground()
                font.pixelSize: (ThemeManager.fontSize_small() || 12)
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        onAccepted: {
            root.optExec = true
        }
        onRejected: {
            root.optExec = false
            root.optGuiAuto = false
        }
    }

    Dialog {
        id: errDlg
        parent: Overlay.overlay
        property string msg: ""
        title: "Scan Failed"
        standardButtons: Dialog.Ok
        modal: true
        anchors.centerIn: parent
        width: 380
        Label {
            text: errDlg.msg
            color: ThemeManager.foreground()
            wrapMode: Text.WordWrap
            width: 340
        }
    }

    FileDialog {
        id: filePicker
        title: "Select file to scan"
        fileMode: FileDialog.OpenFile
        onAccepted: {
            var s = selectedFile.toString()
                         .replace(/^file:\/\/\//i, "")
                         .replace(/\//g, "\\")
            root.filePath   = s
            root.fileName   = s.split("\\").pop()
            root.fileReport = null
            root.filePct    = 0
            root.explainData = null
        }
    }

    ListModel { id: histModel }
    ListModel { id: agentTimelineListModel }

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
                            font.pixelSize: (ThemeManager.fontSize_body() || 14)
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
                                root.segment = index
                                if (index === 2 && histModel.count === 0
                                        && typeof Backend !== "undefined")
                                    Backend.loadScanCenterHistory(200)
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
                                                .replace(/^file:\/\/\//i, "")
                                                .replace(/\//g, "\\")
                                            root.filePath   = s
                                            root.fileName   = s.split("\\").pop()
                                            root.fileReport = null
                                            root.filePct    = 0
                                            root.explainData = null
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
                                        font.pixelSize: (ThemeManager.fontSize_body() || 14)
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
                                    font.pixelSize: (ThemeManager.fontSize_body() || 14)
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
                                    color: fScanBtn.enabled ? "#ffffff" : ThemeManager.muted()
                                    font.pixelSize: (ThemeManager.fontSize_body() || 14)
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
                                    if (root.optSandbox) root.sandboxPanelVisible = true
                                    if (typeof Backend !== "undefined")
                                        Backend.startScanCenter(root.filePath,
                                            JSON.stringify({
                                                use_sandbox:     root.optSandbox,
                                                allow_execution: root.optExec,
                                                disable_network: root.optNet,
                                                run_clamav:      root.optClamAV,
                                                use_visible_gui: root.optGuiAuto
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
                                    font.pixelSize: 16
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    color: parent.parent.hovered ? Qt.rgba(1, 0, 0, .1) : "transparent"
                                    radius: 8
                                }
                                onClicked: {
                                    if (typeof Backend !== "undefined") Backend.cancelScanCenter()
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
                                implicitWidth: ckClamAVLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optClamAV
                                enabled: true
                                opacity: root.fileScanning ? 0.4 : 1.0
                                onToggled: { if (!root.fileScanning) root.optClamAV = checked }
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
                                        font.pixelSize: 11
                                        visible: ckClamAV.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckClamAVLabel
                                    leftPadding: 24
                                    text: "ClamAV"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: (ThemeManager.fontSize_body() || 14)
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            CheckBox {
                                id: ckSandbox
                                implicitWidth: ckSandboxLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optSandbox
                                enabled: true
                                opacity: root.fileScanning ? 0.4 : 1.0
                                onToggled: {
                                    if (root.fileScanning) return
                                    root.optSandbox = checked
                                    if (!checked) { root.optExec = false; root.optGuiAuto = false }
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
                                        font.pixelSize: 11
                                        visible: ckSandbox.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckSandboxLabel
                                    leftPadding: 24
                                    text: "VMware Sandbox"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: (ThemeManager.fontSize_body() || 14)
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Item { Layout.fillWidth: true }
                        } // Row 2a

                        // ── Row 2b: Allow execution + Disable guest network
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.preferredHeight: 32
                            spacing: 24

                            CheckBox {
                                id: ckExec
                                implicitWidth: ckExecLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optExec
                                enabled: root.optSandbox
                                opacity: (root.optSandbox && !root.fileScanning) ? 1.0 : 0.4
                                onToggled: {
                                    if (root.fileScanning) return
                                    if (checked) {
                                        execConfirmDlg.open()
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
                                    color: ckExec.checked ? ThemeManager.accent : ThemeManager.surface()
                                    border.color: ckExec.checked ? ThemeManager.accent : ThemeManager.border()
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"; color: "white"
                                        font.pixelSize: 11
                                        visible: ckExec.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckExecLabel
                                    leftPadding: 24
                                    text: "Allow execution"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: (ThemeManager.fontSize_body() || 14)
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
                                        font.pixelSize: 11
                                        visible: ckNet.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckNetLabel
                                    leftPadding: 24
                                    text: "Disable guest network"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: (ThemeManager.fontSize_body() || 14)
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Item { Layout.fillWidth: true }
                        } // Row 2b

                        // ── Row 2c: Visible GUI automation (only visible when optExec) ──
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 16
                            Layout.rightMargin: 16
                            Layout.preferredHeight: root.optExec ? 32 : 0
                            visible: root.optExec
                            spacing: 24
                            clip: true
                            Behavior on Layout.preferredHeight { NumberAnimation { duration: 160 } }

                            CheckBox {
                                id: ckGuiAuto
                                implicitWidth: ckGuiAutoLabel.implicitWidth + 24
                                implicitHeight: 28
                                checked: root.optGuiAuto
                                enabled: root.optExec
                                opacity: (root.optExec && !root.fileScanning) ? 1.0 : 0.4
                                onToggled: { if (!root.fileScanning) root.optGuiAuto = checked }
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
                                        font.pixelSize: 11
                                        visible: ckGuiAuto.checked
                                    }
                                }
                                contentItem: Text {
                                    id: ckGuiAutoLabel
                                    leftPadding: 24
                                    text: "Visible GUI automation (Win10)"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: (ThemeManager.fontSize_body() || 14)
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
                                font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                Layout.preferredWidth: 180; elide: Text.ElideRight
                            }
                            ProgressBar { Layout.fillWidth: true; value: root.filePct / 100 }
                            Text {
                                text: root.filePct + "%"; color: ThemeManager.muted()
                                font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                Layout.preferredWidth: 34
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }

                    // ── Sandbox Live View: Preview + Timeline split panel ──
                    // Auto-appears when sandbox is enabled and steps start streaming.
                    // Persists after scan ends; user closes with ✕.
                    Rectangle {
                        id: sandboxSplitPanel
                        Layout.fillWidth: true
                        clip: true
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1

                        property real _ph: (root.optSandbox && root.sandboxPanelVisible) ? 360 : 0
                        Behavior on _ph { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
                        implicitHeight: _ph
                        visible: _ph > 1

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 0

                            // ─ Header bar
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 36
                                color: ThemeManager.elevated()
                                border.color: ThemeManager.border(); border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12; anchors.rightMargin: 12
                                    spacing: 8

                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        color: root.sandboxPreviewUrl !== ""
                                               ? ThemeManager.success : ThemeManager.warning
                                        SequentialAnimation on opacity {
                                            loops: Animation.Infinite
                                            running: root.fileScanning
                                            NumberAnimation { to: 0.2; duration: 600 }
                                            NumberAnimation { to: 1.0; duration: 600 }
                                        }
                                    }

                                    Text {
                                        text: "🖵  Sandbox Live Preview"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                        font.weight: (Font.SemiBold || 600)
                                    }

                                    // Automation visible badges
                                    Rectangle {
                                        visible: root.fileReport !== null &&
                                                 root.optExec &&
                                                 (root.fileReport.sandbox || {}).automation_visible === true
                                        implicitWidth: autoVisTxt.implicitWidth + 12
                                        implicitHeight: 18; radius: 9
                                        color: Qt.rgba(0.07, 0.75, 0.32, 0.18)
                                        border.color: ThemeManager.success; border.width: 1
                                        Text {
                                            id: autoVisTxt; anchors.centerIn: parent
                                            text: "Automation Visible ✅"
                                            color: ThemeManager.success; font.pixelSize: 9
                                            font.weight: Font.SemiBold
                                        }
                                    }
                                    Rectangle {
                                        visible: root.fileReport !== null &&
                                                 root.optExec &&
                                                 (root.fileReport.sandbox || {}).automation_visible !== true
                                        implicitWidth: noVisTxt.implicitWidth + 12
                                        implicitHeight: 18; radius: 9
                                        color: Qt.rgba(0.97, 0.75, 0.10, 0.13)
                                        border.color: ThemeManager.warning; border.width: 1
                                        Text {
                                            id: noVisTxt; anchors.centerIn: parent
                                            text: "No visible automation ⚠"
                                            color: ThemeManager.warning; font.pixelSize: 9
                                            font.weight: Font.SemiBold
                                        }
                                    }

                                    Rectangle { width: 1; height: 16; color: ThemeManager.border() }

                                    Text {
                                        text: "📡  Agent Timeline"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                        font.weight: (Font.SemiBold || 600)
                                    }

                                    Text {
                                        visible: agentTimelineListModel.count > 0
                                        text: agentTimelineListModel.count + " step" +
                                              (agentTimelineListModel.count !== 1 ? "s" : "")
                                        color: ThemeManager.muted(); font.pixelSize: 11
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        visible: root.sandboxPreviewUrl !== ""
                                        text: {
                                            var _ignored = sandboxAgeTimer.tick
                                            var dt = root.sandboxPreviewLastMs > 0
                                                ? Math.round((Date.now() - root.sandboxPreviewLastMs) / 1000) : 0
                                            return "Last updated: " + dt + "s ago"
                                        }
                                        color: ThemeManager.muted(); font.pixelSize: 10
                                    }

                                    // Open VM Window
                                    Rectangle {
                                        visible: root.fileScanning
                                        implicitWidth: openVmTxt.implicitWidth + 14; implicitHeight: 24; radius: 5
                                        color: openVmMa.containsMouse ? ThemeManager.accent : ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        Text {
                                            id: openVmTxt; anchors.centerIn: parent
                                            text: "↗  Open VM"
                                            color: openVmMa.containsMouse ? "#ffffff" : ThemeManager.foreground()
                                            font.pixelSize: 10
                                        }
                                        MouseArea {
                                            id: openVmMa; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (typeof Backend !== "undefined" && Backend !== null)
                                                    Backend.openVmWindowInScanCenter()
                                            }
                                        }
                                    }

                                    // Copy steps
                                    Rectangle {
                                        visible: agentTimelineListModel.count > 0
                                        implicitWidth: cpTxt.implicitWidth + 14; implicitHeight: 24; radius: 5
                                        color: cpMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        Text {
                                            id: cpTxt; anchors.centerIn: parent
                                            text: "📋  Copy"; color: ThemeManager.foreground(); font.pixelSize: 10
                                        }
                                        MouseArea {
                                            id: cpMa; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                var lines = []
                                                for (var i = 0; i < agentTimelineListModel.count; i++) {
                                                    var s = agentTimelineListModel.get(i)
                                                    lines.push("[" + (s.ts||"") + "] [" + (s.stage||"") + "] " +
                                                               (s.title||"") + (s.result ? " → " + s.result : ""))
                                                }
                                                if (typeof Backend !== "undefined")
                                                    Backend.copyToClipboard(lines.join("\n"))
                                            }
                                        }
                                    }

                                    // Open run folder
                                    Rectangle {
                                        visible: root.fileReport !== null
                                        implicitWidth: rfTxt.implicitWidth + 14; implicitHeight: 24; radius: 5
                                        color: rfMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        Text {
                                            id: rfTxt; anchors.centerIn: parent
                                            text: "📂  Run folder"; color: ThemeManager.foreground(); font.pixelSize: 10
                                        }
                                        MouseArea {
                                            id: rfMa; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (typeof Backend !== "undefined")
                                                    Backend.openScanCenterRunDir()
                                            }
                                        }
                                    }

                                    // ✕ Close
                                    Rectangle {
                                        implicitWidth: 24; implicitHeight: 24; radius: 5
                                        color: closeMa.containsMouse ? Qt.rgba(1,0,0,0.2) : ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        Text { anchors.centerIn: parent; text: "✕"; color: ThemeManager.muted(); font.pixelSize: 11 }
                                        MouseArea {
                                            id: closeMa; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.sandboxPanelVisible = false
                                        }
                                    }
                                }
                            } // header bar

                            // ─ LEFT = VM screenshot | RIGHT = Agent Timeline
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 0

                                Item {
                                    Layout.preferredWidth: Math.round(parent.width * 0.45)
                                    Layout.fillHeight: true

                                    Image {
                                        id: pvImg
                                        anchors.fill: parent; anchors.margins: 8
                                        fillMode: Image.PreserveAspectFit
                                        cache: false; asynchronous: true
                                        source: root.sandboxPreviewUrl
                                        visible: root.sandboxPreviewUrl !== ""
                                    }

                                    Rectangle {
                                        anchors.left: pvImg.left; anchors.bottom: pvImg.bottom
                                        anchors.margins: 12
                                        visible: root.sandboxPreviewUrl !== ""
                                        implicitWidth: ageOvTxt.implicitWidth + 10; implicitHeight: 18; radius: 4
                                        color: Qt.rgba(0, 0, 0, 0.58)
                                        Text {
                                            id: ageOvTxt; anchors.centerIn: parent
                                            text: {
                                                var _ignored = sandboxAgeTimer.tick
                                                var dt = root.sandboxPreviewLastMs > 0
                                                    ? Math.round((Date.now() - root.sandboxPreviewLastMs) / 1000) : 0
                                                return "Last updated: " + dt + "s ago"
                                            }
                                            color: "white"; font.pixelSize: 9
                                        }
                                    }

                                    Rectangle {
                                        anchors.fill: parent; anchors.margins: 8
                                        visible: root.sandboxPreviewUrl === ""
                                        color: ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1; radius: 6
                                        ColumnLayout {
                                            anchors.centerIn: parent; spacing: 8
                                            Text {
                                                text: root.fileScanning ? "🖵" : "🔒"
                                                font.pixelSize: 36; opacity: 0.3
                                                Layout.alignment: Qt.AlignHCenter
                                            }
                                            Text {
                                                text: root.fileScanning
                                                      ? "Preview starting… (VM powering on)"
                                                      : "Preview unavailable"
                                                color: ThemeManager.muted(); font.pixelSize: 11
                                                Layout.alignment: Qt.AlignHCenter
                                            }
                                        }
                                    }
                                } // left preview

                                Rectangle { width: 1; Layout.fillHeight: true; color: ThemeManager.border() }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 0

                                    Item {
                                        visible: agentTimelineListModel.count === 0
                                        Layout.fillWidth: true; Layout.fillHeight: true
                                        ColumnLayout {
                                            anchors.centerIn: parent; spacing: 8
                                            Text { text: "📡"; font.pixelSize: 32; opacity: 0.25; Layout.alignment: Qt.AlignHCenter }
                                            Text {
                                                text: root.fileScanning
                                                      ? "Steps streaming…"
                                                      : "Run a sandbox scan to see the agent timeline."
                                                color: ThemeManager.muted(); font.pixelSize: 11
                                                Layout.alignment: Qt.AlignHCenter
                                            }
                                        }
                                    }

                                    ListView {
                                        id: splitTlList
                                        visible: agentTimelineListModel.count > 0
                                        Layout.fillWidth: true; Layout.fillHeight: true
                                        model: agentTimelineListModel
                                        clip: true; spacing: 2
                                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                                        onCountChanged: {
                                            if (root.fileScanning) splitTlList.positionViewAtEnd()
                                        }

                                        delegate: Rectangle {
                                            width: splitTlList.width
                                            implicitHeight: splTlRow.implicitHeight + 10
                                            radius: 5
                                            color: index % 2 === 0 ? "transparent" : ThemeManager.elevated()

                                            RowLayout {
                                                id: splTlRow
                                                anchors.left: parent.left; anchors.right: parent.right
                                                anchors.verticalCenter: parent.verticalCenter
                                                anchors.leftMargin: 8; anchors.rightMargin: 8
                                                spacing: 6

                                                Rectangle {
                                                    width: 8; height: 8; radius: 4
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

                                                Text {
                                                    text: model.ts || ""
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: 9; font.family: "Consolas"
                                                    Layout.preferredWidth: 50
                                                }

                                                Rectangle {
                                                    implicitWidth: splStageTxt.implicitWidth + 10
                                                    implicitHeight: 15; radius: 7
                                                    color: ThemeManager.elevated()
                                                    Text {
                                                        id: splStageTxt; anchors.centerIn: parent
                                                        text: (model.stage || "").toUpperCase()
                                                        color: ThemeManager.accent
                                                        font.pixelSize: 8; font.weight: (Font.Bold || 700)
                                                    }
                                                }

                                                ColumnLayout {
                                                    Layout.fillWidth: true; spacing: 0
                                                    Text {
                                                        text: model.title || ""
                                                        color: ThemeManager.foreground()
                                                        font.pixelSize: 11; font.weight: (Font.Medium || 500)
                                                        elide: Text.ElideRight; Layout.fillWidth: true
                                                    }
                                                    Text {
                                                        visible: (model.result || "") !== ""
                                                        text: model.result || ""
                                                        color: ThemeManager.muted()
                                                        font.pixelSize: 9; font.family: "Consolas"
                                                        elide: Text.ElideRight; Layout.fillWidth: true
                                                    }
                                                }
                                            }
                                        } // delegate
                                    } // splitTlList
                                } // right timeline
                            } // content RowLayout
                        } // inner ColumnLayout
                    } // sandboxSplitPanel

                    // ── Frames Playback Card (post-scan, when frames_paths is populated) ──
                    Rectangle {
                        id: framesPlaybackCard
                        Layout.fillWidth: true
                        property var frameFiles: (root.fileReport !== null) ? ((root.fileReport.sandbox || {}).frames_paths || []) : []
                        property int frameIndex: 0

                        onFrameFilesChanged: frameIndex = 0

                        implicitHeight: frameFiles.length > 0 ? 200 : 0
                        visible: frameFiles.length > 0
                        clip: true
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border(); border.width: 1
                        Behavior on implicitHeight { NumberAnimation { duration: 200 } }

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 0

                            // header
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 30
                                color: ThemeManager.elevated()
                                border.color: ThemeManager.border(); border.width: 1
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12; anchors.rightMargin: 12
                                    spacing: 8
                                    Text {
                                        text: "🎬  GUI Frames Replay"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                        font.weight: (Font.SemiBold || 600)
                                    }
                                    Text {
                                        text: framesPlaybackCard.frameFiles.length > 0
                                              ? (framesPlaybackCard.frameIndex + 1) + " / " + framesPlaybackCard.frameFiles.length
                                              : "No frames"
                                        color: ThemeManager.muted(); font.pixelSize: 10
                                    }
                                    Item { Layout.fillWidth: true }
                                    // Prev
                                    Rectangle {
                                        implicitWidth: 24; implicitHeight: 22; radius: 4
                                        color: prevFrMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1
                                        opacity: framesPlaybackCard.frameIndex > 0 ? 1.0 : 0.3
                                        Text { anchors.centerIn: parent; text: "‹"; color: ThemeManager.foreground(); font.pixelSize: 14 }
                                        MouseArea {
                                            id: prevFrMa; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (framesPlaybackCard.frameIndex > 0) framesPlaybackCard.frameIndex--
                                        }
                                    }
                                    // Next
                                    Rectangle {
                                        implicitWidth: 24; implicitHeight: 22; radius: 4
                                        color: nextFrMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1
                                        opacity: (framesPlaybackCard.frameFiles.length > 0 && framesPlaybackCard.frameIndex < framesPlaybackCard.frameFiles.length - 1) ? 1.0 : 0.3
                                        Text { anchors.centerIn: parent; text: "›"; color: ThemeManager.foreground(); font.pixelSize: 14 }
                                        MouseArea {
                                            id: nextFrMa; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (framesPlaybackCard.frameIndex < framesPlaybackCard.frameFiles.length - 1) framesPlaybackCard.frameIndex++
                                        }
                                    }
                                    // Latest
                                    Rectangle {
                                        implicitWidth: latFrTxt.implicitWidth + 12; implicitHeight: 22; radius: 4
                                        color: latFrMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1
                                        Text { id: latFrTxt; anchors.centerIn: parent; text: "Latest"; color: ThemeManager.foreground(); font.pixelSize: 10 }
                                        MouseArea {
                                            id: latFrMa; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: framesPlaybackCard.frameIndex = Math.max(0, framesPlaybackCard.frameFiles.length - 1)
                                        }
                                    }
                                }
                            }

                            // Frame image area
                            Item {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Image {
                                    anchors.fill: parent; anchors.margins: 6
                                    fillMode: Image.PreserveAspectFit
                                    cache: false; asynchronous: true
                                    source: framesPlaybackCard.frameFiles.length > 0
                                            ? "file:///" + framesPlaybackCard.frameFiles[framesPlaybackCard.frameIndex].replace(/\\/g, "/")
                                            : ""
                                    visible: framesPlaybackCard.frameFiles.length > 0
                                }
                                Rectangle {
                                    anchors.fill: parent; anchors.margins: 6
                                    color: ThemeManager.surface(); radius: 4
                                    border.color: ThemeManager.border(); border.width: 1
                                    visible: framesPlaybackCard.frameFiles.length === 0
                                    Text {
                                        anchors.centerIn: parent
                                        text: "No frames available"
                                        color: ThemeManager.muted(); font.pixelSize: 11
                                    }
                                }
                            }
                        }
                    } // framesPlaybackCard

                    // ── UAC Secure Desktop Warning Banner ──────────────────
                    Rectangle {
                        id: uacWarningBanner
                        Layout.fillWidth: true
                        Layout.leftMargin: 8; Layout.rightMargin: 8
                        property bool showBanner: (root.fileReport !== null) &&
                                                  ((root.fileReport.sandbox || {}).uac_secure_desktop === 1)
                        implicitHeight: showBanner ? uacBannerCol.implicitHeight + 20 : 0
                        visible: showBanner
                        clip: true
                        color: Qt.rgba(0.97, 0.75, 0.10, 0.08)
                        border.color: ThemeManager.warning; border.width: 1
                        radius: 6
                        Behavior on implicitHeight { NumberAnimation { duration: 180 } }

                        ColumnLayout {
                            id: uacBannerCol
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 12
                            spacing: 6

                            RowLayout {
                                spacing: 8
                                Text { text: "⚠️"; font.pixelSize: 14 }
                                Text {
                                    text: "UAC Secure Desktop enabled — GUI automation cannot interact with UAC prompts"
                                    color: ThemeManager.warning
                                    font.pixelSize: (ThemeManager.fontSize_body() || 14)
                                    font.weight: (Font.SemiBold || 600)
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }

                            Text {
                                text: "Inside the sandbox VM only, run this as Administrator to disable UAC secure desktop:"
                                color: ThemeManager.foreground()
                                font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: uacCmdTxt.implicitHeight + 10
                                color: ThemeManager.surface()
                                border.color: ThemeManager.border(); border.width: 1
                                radius: 4
                                RowLayout {
                                    anchors.fill: parent; anchors.margins: 6; spacing: 8
                                    Text {
                                        id: uacCmdTxt
                                        Layout.fillWidth: true
                                        text: 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v PromptOnSecureDesktop /t REG_DWORD /d 0 /f'
                                        color: ThemeManager.accent
                                        font.family: "Consolas"
                                        font.pixelSize: 10
                                        wrapMode: Text.WrapAnywhere
                                    }
                                    Rectangle {
                                        implicitWidth: uacCpTxt.implicitWidth + 10; implicitHeight: 20; radius: 4
                                        color: uacCpMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                                        border.color: ThemeManager.border(); border.width: 1
                                        Text { id: uacCpTxt; anchors.centerIn: parent; text: "Copy"; color: ThemeManager.foreground(); font.pixelSize: 9 }
                                        MouseArea {
                                            id: uacCpMa; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (typeof Backend !== "undefined")
                                                    Backend.copyToClipboard(uacCmdTxt.text)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    } // uacWarningBanner

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
                                font.pixelSize: (ThemeManager.fontSize_body() || 14)
                                elide: Text.ElideRight
                            }
                            Text {
                                visible: root.fileReport !== null
                                text: "Score: " + (((root.fileReport || {}).verdict || {}).score || 0) + " / 100"
                                color: ThemeManager.muted()
                                font.pixelSize: (ThemeManager.fontSize_small() || 12)
                            }
                            Text {
                                visible: root.fileReport !== null
                                text: "⏱ " + Math.round(((root.fileReport || {}).job || {}).duration_sec || 0) + "s"
                                color: ThemeManager.muted()
                                font.pixelSize: (ThemeManager.fontSize_small() || 12)
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
                                    font.pixelSize: (ThemeManager.fontSize_small() || 12)
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
                                        Text { text: "No file scanned yet"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_body() || 14); Layout.alignment: Qt.AlignHCenter }
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

                                        Text { text: "File Information"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }

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
                                                    Text { text: modelData[1]; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
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

                                        Text { text: "Top Findings"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: {
                                                var v = ((root.fileReport || {}).verdict || {}).reasons || []
                                                return v.length > 0 ? v : ["No significant findings"]
                                            }
                                            RowLayout {
                                                spacing: 8; Layout.fillWidth: true
                                                Text { text: "•"; color: root.fileReport ? root.riskColor(((root.fileReport.verdict) || {}).risk || "") : ThemeManager.muted(); font.pixelSize: 16 }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

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

                                        Text { text: "Score Breakdown"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }

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
                                            Text { text: String((((root.fileReport || {}).verdict || {}).score || 0)) + "/100"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); font.weight: (Font.SemiBold || 600); Layout.preferredWidth: 48; horizontalAlignment: Text.AlignRight }
                                        }

                                        // Source rows
                                        Repeater {
                                            model: {
                                                var bd = (((root.fileReport || {}).verdict || {}).breakdown) || {}
                                                var order = ["defender", "clamav", "yara", "sandbox"]
                                                var nice  = { defender: "Windows Defender", clamav: "ClamAV", yara: "YARA Rules", sandbox: "Sandbox" }
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
                                                    font.pixelSize: (ThemeManager.fontSize_small() || 12)
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
                                                    color: ThemeManager.muted(); font.pixelSize: 10
                                                    Layout.fillWidth: true
                                                }
                                                Text {
                                                    text: modelData.avail ? (modelData.score + "/100") : ""
                                                    color: ThemeManager.muted(); font.pixelSize: 10
                                                    Layout.preferredWidth: 48; horizontalAlignment: Text.AlignRight
                                                }
                                                Text {
                                                    text: modelData.avail ? (modelData.wt + "%") : ""
                                                    color: ThemeManager.muted(); font.pixelSize: 10
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
                                        Text { text: "No scan results"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_body() || 14); Layout.alignment: Qt.AlignHCenter }
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
                                            Text { text: modelData.name || ""; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); font.weight: (Font.Medium || 500); Layout.preferredWidth: 170; elide: Text.ElideRight }
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
                                            Text { text: modelData.score !== undefined ? modelData.score.toFixed(0) : "—"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.preferredWidth: 58 }
                                            Text { text: modelData.details || "—"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); elide: Text.ElideRight; Layout.fillWidth: true }
                                            Text { text: modelData.time_ms !== undefined ? modelData.time_ms + "" : "—"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.preferredWidth: 52; horizontalAlignment: Text.AlignRight }
                                        }
                                    }
                                }

                                // YARA card
                                Rectangle {
                                    visible: root.fileReport !== null
                                    Layout.fillWidth: true
                                    implicitHeight: yaraCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10
                                    border.color: ThemeManager.border(); border.width: 1

                                    ColumnLayout {
                                        id: yaraCol
                                        anchors.left: parent.left; anchors.right: parent.right
                                        anchors.top: parent.top; anchors.margins: 14
                                        spacing: 6

                                        Text { text: "YARA Matches"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: root.fileReport ? (((root.fileReport.static) || {}).yara_matches || []) : []
                                            RowLayout {
                                                spacing: 6; Layout.fillWidth: true
                                                Text { text: "⚑"; color: ThemeManager.warning; font.pixelSize: 13 }
                                                Text { text: typeof modelData === "string" ? modelData : (modelData.rule_name || modelData.name || JSON.stringify(modelData)); color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                            }
                                        }
                                        Text {
                                            visible: !(root.fileReport && (((root.fileReport.static) || {}).yara_matches || []).length > 0)
                                            text: "No YARA matches ✓"
                                            color: ThemeManager.success
                                            font.pixelSize: (ThemeManager.fontSize_small() || 12)
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
                                            color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_body() || 14); Layout.alignment: Qt.AlignHCenter
                                        }
                                        Text {
                                            visible: root.fileReport !== null
                                            text: "Enable the VMware Sandbox option and re-scan to collect behavioral data."
                                            color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.alignment: Qt.AlignHCenter
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
                                        Text { text: "⚙  New Processes"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "📁  File System Changes"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "🔑  Registry Changes"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "🌐  Network Activity"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "⚠  Highlights"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: parent.parent.items
                                            RowLayout { spacing: 8; Layout.fillWidth: true
                                                Text { text: "⚠"; color: ThemeManager.warning; font.pixelSize: 13 }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WordWrap; Layout.fillWidth: true }
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
                                        Text { text: "No scan results"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_body() || 14); Layout.alignment: Qt.AlignHCenter }
                                    }
                                }

                                // URLs
                                Rectangle {
                                    property var items: root.fileReport ? ((root.fileReport.iocs || {}).urls || []) : []
                                    visible: items.length > 0
                                    Layout.fillWidth: true; implicitHeight: iocUrlCol.implicitHeight + 28
                                    color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                    ColumnLayout { id: iocUrlCol; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 4
                                        Text { text: "🌐  URLs (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "🔗  Domains (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "📡  IP Addresses (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "📁  File Paths (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "🔑  Registry Keys (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "🔢  Hashes (" + parent.parent.items.length + ")"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                        Text { text: "No IOCs found"; color: ThemeManager.success; font.pixelSize: (ThemeManager.fontSize_body() || 14); Layout.alignment: Qt.AlignHCenter }
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
                                        Text { text: "No report loaded"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_body() || 14); Layout.alignment: Qt.AlignHCenter }
                                    }
                                }

                                Button {
                                    visible: root.fileReport !== null && root.explainData === null && !explainBusy.running
                                    Layout.alignment: Qt.AlignHCenter
                                    text: "✨  Get AI Explanation"
                                    implicitWidth: 218; implicitHeight: 44
                                    contentItem: Text {
                                        text: parent.text; color: "#ffffff"
                                        font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600)
                                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle {
                                        color: parent.parent.hovered ? Qt.darker(ThemeManager.accent, 1.08) : ThemeManager.accent
                                        radius: 8; Behavior on color { ColorAnimation { duration: 120 } }
                                    }
                                    onClicked: {
                                        if (root.fileReport && typeof Backend !== "undefined") {
                                            explainBusy.running = true
                                            Backend.explainScanCenterReport(JSON.stringify(root.fileReport))
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
                                        Text { text: "Summary"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                        Text { text: (root.explainData || {}).one_line_summary || ""; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.Medium || 500); wrapMode: Text.WordWrap; Layout.fillWidth: true }
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
                                        Text { text: "Why This Risk Level?"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: (root.explainData || {}).top_reasons || []
                                            RowLayout { spacing: 8; Layout.fillWidth: true
                                                Text { text: "•"; color: ThemeManager.accent; font.pixelSize: 16 }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WordWrap; Layout.fillWidth: true }
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
                                        Text { text: "Recommended Actions"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                        Repeater {
                                            model: (root.explainData || {}).what_to_do || []
                                            RowLayout { spacing: 8; Layout.fillWidth: true
                                                Text { text: "→"; color: ThemeManager.success; font.pixelSize: 14; font.weight: (Font.Bold || 700) }
                                                Text { text: modelData; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WordWrap; Layout.fillWidth: true }
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
                                        color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WordWrap
                                    }
                                }

                                RowLayout {
                                    visible: root.fileReport !== null
                                    Layout.fillWidth: true; spacing: 12
                                    Button {
                                        text: "Export Report…"; flat: true
                                        contentItem: Text { text: parent.text; color: ThemeManager.accent; font.pixelSize: (ThemeManager.fontSize_small() || 12); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                        background: Rectangle { color: parent.parent.hovered ? ThemeManager.surface() : "transparent"; radius: 8 }
                                        onClicked: {
                                            var jid = ((root.fileReport || {}).job || {}).job_id || ""
                                            if (jid && typeof Backend !== "undefined") Backend.exportScanCenterReport(jid, "")
                                        }
                                    }
                                    Text { id: expOkLabel; text: ""; color: ThemeManager.success; font.pixelSize: (ThemeManager.fontSize_small() || 12); elide: Text.ElideRight; Layout.fillWidth: true }
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
                                        font.pixelSize: (ThemeManager.fontSize_h3() || 18)
                                        font.weight: (Font.SemiBold || 600)
                                    }
                                    Text {
                                        visible: agentTimelineListModel.count > 0
                                        text: agentTimelineListModel.count + " step" +
                                              (agentTimelineListModel.count !== 1 ? "s" : "")
                                        color: ThemeManager.muted()
                                        font.pixelSize: (ThemeManager.fontSize_small() || 12)
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
                                            font.pixelSize: 11
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
                                            font.pixelSize: (ThemeManager.fontSize_body() || 14)
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
                                                    font.pixelSize: (ThemeManager.fontSize_small() || 12)
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
                                                font.pixelSize: (ThemeManager.fontSize_body() || 14)
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            TextInput {
                                                id: urlField
                                                anchors.fill: parent
                                                anchors.topMargin: 1; anchors.bottomMargin: 1
                                                text: root.urlInput
                                                color: ThemeManager.foreground()
                                                font.pixelSize: (ThemeManager.fontSize_body() || 14)
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
                                            text: "✕"; color: ThemeManager.muted(); font.pixelSize: 12
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
                                        if (typeof Backend !== "undefined") {
                                            if (root.urlOptSandbox)
                                                Backend.scanUrlSandbox(root.urlInput.trim(),
                                                    root.urlOptBlockDl, root.urlOptBlockPvt, true, 30)
                                            else
                                                Backend.scanUrlStatic(root.urlInput.trim(),
                                                    root.urlOptBlockPvt, true, 30)
                                        }
                                    }

                                    contentItem: Text {
                                        text: uScanBtn.text; color: uScanBtn.enabled ? "#ffffff" : ThemeManager.muted()
                                        font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600)
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
                                    onClicked: { if (typeof Backend !== "undefined") Backend.cancelUrlScan(); root.urlScanning = false }
                                }
                            }

                            // URL options — Flow wraps automatically on narrow windows
                            Flow {
                                Layout.fillWidth: true
                                spacing: 12

                                CheckBox {
                                    id: ckUrlSb
                                    text: "Detonate in sandbox"
                                    checked: root.urlOptSandbox
                                    enabled: !root.urlScanning
                                    onToggled: root.urlOptSandbox = checked
                                    contentItem: Text {
                                        leftPadding: ((ckUrlSb.indicator ? ckUrlSb.indicator.width : 18) + (ckUrlSb.spacing || 4))
                                        text: ckUrlSb.text
                                        color: ThemeManager.foreground()
                                        font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                        verticalAlignment: Text.AlignVCenter
                                        wrapMode: Text.NoWrap
                                    }
                                }

                                CheckBox {
                                    id: ckUrlBl
                                    text: "Block downloads"
                                    checked: root.urlOptBlockDl
                                    enabled: !root.urlScanning && root.urlOptSandbox
                                    opacity: enabled ? 1.0 : 0.4
                                    onToggled: root.urlOptBlockDl = checked
                                    contentItem: Text {
                                        leftPadding: ((ckUrlBl.indicator ? ckUrlBl.indicator.width : 18) + (ckUrlBl.spacing || 4))
                                        text: ckUrlBl.text
                                        color: ThemeManager.foreground()
                                        font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                        verticalAlignment: Text.AlignVCenter
                                        wrapMode: Text.NoWrap
                                        opacity: ckUrlBl.opacity
                                    }
                                }

                                CheckBox {
                                    id: ckUrlPv
                                    text: "Block private IPs"
                                    checked: root.urlOptBlockPvt
                                    enabled: !root.urlScanning
                                    onToggled: root.urlOptBlockPvt = checked
                                    contentItem: Text {
                                        leftPadding: ((ckUrlPv.indicator ? ckUrlPv.indicator.width : 18) + (ckUrlPv.spacing || 4))
                                        text: ckUrlPv.text
                                        color: ThemeManager.foreground()
                                        font.pixelSize: (ThemeManager.fontSize_small() || 12)
                                        verticalAlignment: Text.AlignVCenter
                                        wrapMode: Text.NoWrap
                                    }
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
                            Text { text: root.urlStage; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.preferredWidth: 200; elide: Text.ElideRight }
                            ProgressBar { Layout.fillWidth: true; value: root.urlPct / 100 }
                            Text { text: root.urlPct + "%"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.preferredWidth: 34; horizontalAlignment: Text.AlignRight }
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
                            Text { Layout.fillWidth: true; text: root.urlResult ? ((root.urlResult.normalized_url) || "") : ""; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); elide: Text.ElideRight }
                            Text { visible: root.urlResult !== null; text: "Score: " + ((root.urlResult || {}).score || 0) + " / 100"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12) }
                        }
                    }

                    // ── URL results scroll ────────────────────────────────
                    ScrollView {
                        id: urlScroll
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true

                        ColumnLayout {
                            width: Math.min(800, urlScroll.availableWidth - 32)
                            x: Math.max(16, (urlScroll.availableWidth - width) / 2)
                            spacing: 12

                            Item { height: 10 }

                            // Empty
                            Item {
                                visible: root.urlResult === null && !root.urlScanning
                                Layout.fillWidth: true; implicitHeight: 200
                                ColumnLayout { anchors.centerIn: parent; spacing: 10
                                    Text { text: "🌐"; font.pixelSize: 48; opacity: 0.4; Layout.alignment: Qt.AlignHCenter }
                                    Text { text: "Enter a URL above and click Scan URL"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_body() || 14); Layout.alignment: Qt.AlignHCenter }
                                    Text { text: "Static analysis is fast and safe by default. Sandbox detonation is optional."; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.alignment: Qt.AlignHCenter }
                                }
                            }

                            // URL details card
                            Rectangle {
                                visible: root.urlResult !== null
                                Layout.fillWidth: true; implicitHeight: urlMetaCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlMetaCol
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 8
                                    Text { text: "URL Details"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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
                                                Text { text: modelData[1]; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }
                            }

                            // Evidence / findings
                            Rectangle {
                                visible: root.urlResult !== null && ((root.urlResult || {}).evidence || []).length > 0
                                Layout.fillWidth: true; implicitHeight: urlEvCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlEvCol
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 8
                                    Text { text: "Findings (" + ((root.urlResult || {}).evidence_count || 0) + ")"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                    Repeater {
                                        model: (root.urlResult || {}).evidence || []
                                        Rectangle {
                                            Layout.fillWidth: true; implicitHeight: evInner.implicitHeight + 16
                                            color: ThemeManager.surface(); radius: 8
                                            ColumnLayout {
                                                id: evInner
                                                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; spacing: 3
                                                RowLayout { spacing: 8; Layout.fillWidth: true
                                                    Rectangle {
                                                        implicitWidth: sevLbl.implicitWidth + 12; implicitHeight: 18; radius: 9
                                                        color: {
                                                            var s = (modelData.severity || "").toLowerCase()
                                                            if (s === "high" || s === "critical") return Qt.rgba(ThemeManager.danger.r,  ThemeManager.danger.g,  ThemeManager.danger.b,  0.2)
                                                            if (s === "medium")                   return Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.2)
                                                            return ThemeManager.surface()
                                                        }
                                                        Text {
                                                            id: sevLbl; anchors.centerIn: parent
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
                                                    Text { text: modelData.title || ""; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); font.weight: (Font.Medium || 500); Layout.fillWidth: true; wrapMode: Text.WordWrap }
                                                }
                                                Text { visible: (modelData.detail || "") !== ""; text: modelData.detail || ""; color: ThemeManager.muted(); font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }
                            }

                            // Redirect chain
                            Rectangle {
                                visible: root.urlResult !== null && ((root.urlResult || {}).redirects || []).length > 0
                                Layout.fillWidth: true; implicitHeight: urlRedCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlRedCol
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 5
                                    Text { text: "Redirect Chain"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                    Repeater {
                                        model: (root.urlResult || {}).redirects || []
                                        RowLayout { spacing: 6; Layout.fillWidth: true
                                            Text { text: (index + 1) + "."; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.preferredWidth: 22 }
                                            Text { text: modelData; color: ThemeManager.accent; font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                                        }
                                    }
                                }
                            }

                            // Sandbox detonation results
                            Rectangle {
                                visible: root.urlResult !== null && (root.urlResult || {}).has_sandbox
                                Layout.fillWidth: true; implicitHeight: urlSbCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlSbCol
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 6
                                    Text { text: "🖥  Sandbox Detonation"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                    Text {
                                        text: JSON.stringify((root.urlResult || {}).sandbox_result || {}, null, 2)
                                        color: ThemeManager.muted(); font.pixelSize: 11; font.family: "Consolas"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
                                    }
                                }
                            }

                            // IOCs
                            Rectangle {
                                visible: root.urlResult !== null && (root.urlResult || {}).has_iocs
                                Layout.fillWidth: true; implicitHeight: urlIocCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlIocCol
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 5
                                    Text { text: "Extracted IOCs"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
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

                            // Analysis / explanation
                            Rectangle {
                                visible: root.urlResult !== null && (root.urlResult || {}).explanation !== null && (root.urlResult || {}).explanation !== undefined
                                Layout.fillWidth: true; implicitHeight: urlExCol.implicitHeight + 28
                                color: ThemeManager.panel(); radius: 10; border.color: ThemeManager.border(); border.width: 1
                                ColumnLayout {
                                    id: urlExCol
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 6
                                    Text { text: "Analysis"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_body() || 14); font.weight: (Font.SemiBold || 600) }
                                    Text {
                                        text: ((root.urlResult || {}).explanation || {}).summary
                                              || ((root.urlResult || {}).explanation || {}).text || ""
                                        color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); wrapMode: Text.WordWrap; Layout.fillWidth: true
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
                        Text { text: "Scan History"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_h3() || 18); font.weight: (Font.SemiBold || 600) }
                        Text { visible: histModel.count > 0; text: histModel.count + " scan" + (histModel.count !== 1 ? "s" : ""); color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.alignment: Qt.AlignVCenter }
                        Item { Layout.fillWidth: true }
                        Button {
                            text: "↻ Refresh"; flat: true
                            contentItem: Text { text: parent.text; color: ThemeManager.accent; font.pixelSize: (ThemeManager.fontSize_small() || 12); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            background: Rectangle { color: parent.parent.hovered ? ThemeManager.surface() : "transparent"; radius: 8 }
                            onClicked: { histModel.clear(); if (typeof Backend !== "undefined") Backend.loadScanCenterHistory(200) }
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
                            Text { text: "No scan history"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_body() || 14); Layout.alignment: Qt.AlignHCenter }
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
                                    if (model.report_path && typeof Backend !== "undefined") {
                                        Backend.openScanCenterReport(model.report_path)
                                        root.segment = 0
                                    }
                                }
                            }

                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 0
                                ColumnLayout { spacing: 1; Layout.fillWidth: true
                                    Text { text: model.file_name || "—"; color: ThemeManager.foreground(); font.pixelSize: (ThemeManager.fontSize_small() || 12); font.weight: (Font.Medium || 500); elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: (model.file_type || "") + (model.sha256 ? "  •  " + (model.sha256 || "").slice(0, 10) + "…" : ""); color: ThemeManager.muted(); font.pixelSize: 10; elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                                Rectangle {
                                    Layout.preferredWidth: 90; implicitHeight: 20; radius: 10
                                    color: root.riskColor(model.verdict_risk || ""); opacity: 0.85
                                    Text { anchors.centerIn: parent; text: (model.verdict_risk || "—").toUpperCase(); color: "#ffffff"; font.pixelSize: 9; font.weight: (Font.Bold || 700) }
                                }
                                Text { text: model.mode || "—"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.preferredWidth: 68 }
                                Text { text: String(model.score || "—"); color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.preferredWidth: 52 }
                                Text { text: model.created_at ? model.created_at.slice(0, 16).replace("T", " ") : "—"; color: ThemeManager.muted(); font.pixelSize: (ThemeManager.fontSize_small() || 12); Layout.preferredWidth: 130 }
                            }
                        }
                    }
                }
            } // History Item

        } // main StackLayout
    } // root ColumnLayout
}
