import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../theme"

// ── VMware Sandbox Lab ────────────────────────────────────────────────────────
// Full-featured sandbox detonation and analysis page.
// Wraps the SandboxLabController context property exposed by the Python backend.
// ─────────────────────────────────────────────────────────────────────────────
ScrollView {
    id: root
    clip: true

    // ── local UI state ────────────────────────────────────────────────────────
    property bool   _busy:      (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.busy       : false
    property bool   _available: (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.available  : false
    property bool   _guestOk:   (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.guestReady : false
    property string _status:    (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.statusText : "SandboxLab not registered"
    property int    _progress:  (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.progressValue : 0
    property string _step:      (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.currentStep  : ""
    property string _verdict:   (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.verdictSummary : ""
    property var    _result:    (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.resultSummary  : ({})
    property string _liveFrame:          (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.liveFrameSource    : ""
    property int    _pvFrame:            0    // frame counter for image://sandboxpreview/ cache-bust
    property bool   _pvLive:             false
    property string _lastError:          (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.lastError          : ""
    property var    _steps:              (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.stepsModel          : []
    property bool   _automationVisible:  (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.automationVisible   : false
    property string _uiRunnerStatus:     (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.uiRunnerStatus      : ""
    property var    _replayFrames:       (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.replayFramesModel    : []
    property int    _replayIndex:        0
    property var    _diagChecks: []

    // input
    property int    inputMode:       0   // 0=File, 1=URL
    property string selectedFile:    ""
    property string urlText:         ""
    property int    monitorSecs:     60
    property bool   disableNet:          true
    property bool   allowExec:           false
    property bool   allowInteractiveGui: false   // follows allowExec; user can disable independently
    property bool   showLog:             false
    property bool   showDiag:        false
    property bool   showExecWarning: false

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
        function onUiRunnerStatusChanged(s)    { root._uiRunnerStatus   = s }
        function onReplayFramesModelChanged()  {
            root._replayFrames = SandboxLab.replayFramesModel
            root._replayIndex  = Math.max(0, SandboxLab.replayFramesModel.length - 1)
        }
    }

    // ── SandboxPreview image-provider connections (live feed) ─────────────────
    Connections {
        target: (typeof SandboxPreview !== "undefined" && SandboxPreview !== null)
                ? SandboxPreview : null
        enabled: target !== null
        function onFrameUpdated()  { root._pvFrame++; root._pvLive = true  }
        function onPreviewStopped(){ root._pvLive = false }
    }

    // ── File picker dialog ────────────────────────────────────────────────────
    FileDialog {
        id: filePicker
        title: "Select file to analyse"
        nameFilters: ["All files (*)"]
        fileMode: FileDialog.OpenFile
        onAccepted: root.selectedFile = selectedFile.toString().replace("file:///", "")
    }

    // ── Execution confirm dialog ──────────────────────────────────────────────
    Dialog {
        id: execConfirmDlg
        title: "Allow Execution — Safety Warning"
        modal: true
        anchors.centerIn: parent
        width: 440
        padding: 24
        background: Rectangle { color: ThemeManager.panel(); radius: 12; border.color: ThemeManager.border(); border.width: 1 }
        header: Item {}
        footer: Item {}
        ColumnLayout {
            anchors.fill: parent
            spacing: 16
            Text {
                text: "⚠  Execute sample in sandbox?"
                color: ThemeManager.warning; font.pixelSize: 16; font.weight: (Font.Bold || 700)
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            Text {
                text: "The sample will run with its normal code path inside the isolated VM.\n\nOnly proceed if you are confident in the sandbox isolation and understand the risks."
                color: ThemeManager.foreground(); font.pixelSize: 13
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            RowLayout {
                spacing: 10; Layout.fillWidth: true; Layout.topMargin: 8
                Item { Layout.fillWidth: true }
                Button {
                    text: "Cancel"
                    onClicked: { root.allowExec = false; execConfirmDlg.close() }
                    background: Rectangle { color: ThemeManager.surface(); radius: 6; border.color: ThemeManager.border(); border.width: 1 }
                    contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
                Button {
                    text: "Allow Execution"
                    onClicked: { root.allowExec = true; root.allowInteractiveGui = true; execConfirmDlg.close() }
                    background: Rectangle { color: ThemeManager.danger; radius: 6 }
                    contentItem: Text { text: parent.text; color: "white"; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
            }
        }
    }

    // ── Page content ──────────────────────────────────────────────────────────
    ColumnLayout {
        width: Math.min(960, root.availableWidth - 48)
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
                    text: "🖥  VMware Sandbox Lab"
                    color: ThemeManager.foreground()
                    font.pixelSize: (ThemeManager.fontSize_h2() || 24)
                    font.weight: (Font.Bold || 700)
                }
                Text {
                    text: "Detonate files and URLs in an isolated Windows VM. Capture behavioral evidence."
                    color: ThemeManager.muted()
                    font.pixelSize: (ThemeManager.fontSize_small() || 12)
                }
            }

            // Availability badge
            Rectangle {
                implicitWidth: badgeRow.implicitWidth + 20
                implicitHeight: 32
                radius: 16
                color: root._available ? "#16a34a22" : "#dc262622"
                border.color: root._available ? "#16a34a" : "#dc2626"
                border.width: 1
                RowLayout {
                    id: badgeRow
                    anchors.centerIn: parent
                    spacing: 6
                    Rectangle {
                        width: 8; height: 8; radius: 4
                        color: root._available ? "#22c55e" : "#ef4444"
                    }
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
                implicitHeight: 32
                radius: 16
                color: root._guestOk ? "#16a34a22" : "#ca8a0422"
                border.color: root._guestOk ? "#16a34a" : "#ca8a04"
                border.width: 1
                RowLayout {
                    id: guestRow
                    anchors.centerIn: parent
                    spacing: 6
                    Rectangle {
                        width: 8; height: 8; radius: 4
                        color: root._guestOk ? "#22c55e" : "#eab308"
                    }
                    Text {
                        text: root._guestOk ? "Guest Auth OK" : "Guest Auth Missing"
                        color: root._guestOk ? "#22c55e" : "#eab308"
                        font.pixelSize: 12; font.weight: (Font.Medium || 500)
                    }
                }
            }

            // Refresh capabilities
            Button {
                enabled: !root._busy
                text: "↺"
                implicitWidth: 36; implicitHeight: 36
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.refreshStatus()
                background: Rectangle { color: parent.pressed ? ThemeManager.elevated() : (parent.hovered ? ThemeManager.surface() : "transparent"); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.muted(); font.pixelSize: 18; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Re-check VMware availability"
            }
        }

        // Status bar
        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: 12
            implicitHeight: 38
            radius: 8
            color: ThemeManager.surface()
            border.color: ThemeManager.border(); border.width: 1
            RowLayout {
                anchors.fill: parent; anchors.margins: 10
                spacing: 8
                Text {
                    text: "🔵"
                    font.pixelSize: 11
                    visible: root._busy
                }
                Text {
                    text: root._status
                    color: ThemeManager.muted()
                    font.pixelSize: 12
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                Text {
                    visible: root._step !== ""
                    text: root._step
                    color: ThemeManager.primary
                    font.pixelSize: 11; font.weight: (Font.Medium || 500)
                    elide: Text.ElideRight
                    Layout.preferredWidth: 200
                    horizontalAlignment: Text.AlignRight
                }
            }
        }

        Item { height: 20 }

        // ── Error banner ─────────────────────────────────────────────────────
        Rectangle {
            visible: root._lastError !== ""
            Layout.fillWidth: true
            Layout.bottomMargin: 12
            implicitHeight: errCol.implicitHeight + 20
            radius: 8
            color: "#dc262218"; border.color: "#dc2626"; border.width: 1
            ColumnLayout {
                id: errCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                spacing: 4
                RowLayout {
                    spacing: 8; Layout.fillWidth: true
                    Text { text: "⚠  Error"; color: "#ef4444"; font.pixelSize: 13; font.weight: (Font.SemiBold || 600) }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "✕"; color: ThemeManager.muted(); font.pixelSize: 14
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root._lastError = "" }
                    }
                }
                Text {
                    text: root._lastError
                    color: "#fca5a5"; font.pixelSize: 12; wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        // ── Input panel ───────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: inputCol.implicitHeight + 28
            radius: 12
            color: ThemeManager.panel()
            border.color: ThemeManager.border(); border.width: 1

            ColumnLayout {
                id: inputCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14
                spacing: 14

                // Mode selector
                RowLayout {
                    spacing: 8
                    Repeater {
                        model: ["📄  File", "🌐  URL"]
                        delegate: Rectangle {
                            implicitWidth: modeText.implicitWidth + 24
                            implicitHeight: 34
                            radius: 8
                            color: root.inputMode === index ? ThemeManager.primary : ThemeManager.surface()
                            border.color: root.inputMode === index ? ThemeManager.primary : ThemeManager.border()
                            border.width: 1
                            Text {
                                id: modeText
                                anchors.centerIn: parent
                                text: modelData
                                color: root.inputMode === index ? "white" : ThemeManager.foreground()
                                font.pixelSize: 13; font.weight: (Font.Medium || 500)
                            }
                            MouseArea {
                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: { root.inputMode = index; root._lastError = "" }
                            }
                        }
                    }
                }

                // File input
                RowLayout {
                    visible: root.inputMode === 0
                    spacing: 8; Layout.fillWidth: true
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: 38; radius: 8
                        color: ThemeManager.background(); border.color: ThemeManager.border(); border.width: 1
                        TextInput {
                            id: fileInput
                            anchors.fill: parent; anchors.margins: 10
                            color: ThemeManager.foreground(); font.pixelSize: 13
                            text: root.selectedFile
                            onTextChanged: root.selectedFile = text
                            clip: true
                            Text {
                                visible: parent.text === ""; anchors.fill: parent
                                text: "Drop a file or click Browse…"
                                color: ThemeManager.muted(); font.pixelSize: 13
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                        DropArea {
                            anchors.fill: parent
                            onDropped: (drop) => {
                                if (drop.hasUrls && drop.urls.length > 0) {
                                    root.selectedFile = drop.urls[0].toString().replace("file:///", "")
                                }
                            }
                        }
                    }
                    Button {
                        text: "Browse"
                        implicitHeight: 38
                        enabled: !root._busy
                        onClicked: filePicker.open()
                        background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                        contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                    }
                }

                // URL input
                Rectangle {
                    visible: root.inputMode === 1
                    Layout.fillWidth: true; implicitHeight: 38; radius: 8
                    color: ThemeManager.background(); border.color: ThemeManager.border(); border.width: 1
                    TextInput {
                        anchors.fill: parent; anchors.margins: 10
                        color: ThemeManager.foreground(); font.pixelSize: 13
                        text: root.urlText; onTextChanged: root.urlText = text
                        clip: true; inputMethodHints: Qt.ImhUrlCharactersOnly
                        Text {
                            visible: parent.text === ""; anchors.fill: parent
                            text: "https://example.com/suspicious.exe"
                            color: ThemeManager.muted(); font.pixelSize: 13
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                // Options row
                RowLayout {
                    spacing: 20; Layout.fillWidth: true

                    // Monitor seconds
                    RowLayout {
                        spacing: 8
                        Text { text: "Monitor:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                        Slider {
                            id: monSlider
                            from: 30; to: 300; stepSize: 15
                            value: root.monitorSecs
                            implicitWidth: 120
                            onValueChanged: root.monitorSecs = value
                        }
                        Text {
                            text: root.monitorSecs + "s"
                            color: ThemeManager.foreground(); font.pixelSize: 12; font.weight: (Font.Medium || 500)
                            Layout.preferredWidth: 38
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // Disable network
                    RowLayout {
                        spacing: 6
                        Switch {
                            id: netSwitch
                            checked: root.disableNet
                            onToggled: root.disableNet = checked
                        }
                        Text {
                            text: "Block network"
                            color: ThemeManager.foreground(); font.pixelSize: 12
                        }
                    }

                    // Allow execution
                    RowLayout {
                        spacing: 6
                        Switch {
                            id: execSwitch
                            checked: root.allowExec
                            onToggled: {
                                if (checked && !root.allowExec) {
                                    execSwitch.checked = false
                                    execConfirmDlg.open()
                                } else if (!checked) {
                                    root.allowExec = false
                                    root.allowInteractiveGui = false   // reset linked toggle
                                }
                            }
                        }
                        Text {
                            text: "Allow execution"
                            color: root.allowExec ? ThemeManager.warning : ThemeManager.foreground()
                            font.pixelSize: 12; font.weight: root.allowExec ? Font.SemiBold : Font.Normal
                        }
                    }

                    // Visible GUI automation (only meaningful when execution is enabled)
                    RowLayout {
                        spacing: 6
                        visible: root.allowExec
                        Switch {
                            id: interactiveSwitch
                            checked: root.allowInteractiveGui
                            onToggled: root.allowInteractiveGui = checked
                        }
                        Text {
                            text: "Visible GUI automation"
                            color: root.allowInteractiveGui ? "#16a34a" : ThemeManager.foreground()
                            font.pixelSize: 12
                            font.weight: root.allowInteractiveGui ? Font.SemiBold : Font.Normal
                        }
                        ToolTip.visible: interactiveSwitch.hovered
                        ToolTip.delay: 400
                        ToolTip.text: "Run sample in the active desktop session so automation is visible on screen"
                    }
                }
            }
        }

        // ── Control bar ───────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 12
            spacing: 10

            // Run button
            Button {
                text: root.inputMode === 0 ? "▶  Detonate File" : "▶  Detonate URL"
                implicitHeight: 44
                enabled: !root._busy && root._available && (root.inputMode === 0 ? root.selectedFile !== "" : root.urlText !== "")
                onClicked: {
                    root._lastError = ""
                    if (!root._available) {
                        root._lastError = "VMware Sandbox is not available. Check configuration."
                        return
                    }
                    if (typeof SandboxLab === "undefined" || SandboxLab === null) { return }
                    if (root.inputMode === 0) {
                        SandboxLab.runFileInSandbox(root.selectedFile, root.monitorSecs, root.disableNet, true, root.allowExec, root.allowInteractiveGui)
                    } else {
                        SandboxLab.runUrlInSandbox(root.urlText)
                    }
                }
                background: Rectangle {
                    color: parent.enabled ? (parent.hovered ? Qt.darker(ThemeManager.primary, 1.1) : ThemeManager.primary) : ThemeManager.surface()
                    radius: 10
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                contentItem: Text {
                    text: parent.text; color: parent.enabled ? "white" : ThemeManager.muted()
                    font.pixelSize: 14; font.weight: (Font.SemiBold || 600)
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    leftPadding: 16; rightPadding: 16
                }
            }

            // Cancel button
            Button {
                text: "✕  Cancel"
                implicitHeight: 44
                visible: root._busy
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.cancelRun()
                background: Rectangle { color: parent.hovered ? "#9f1239" : "#be123c"; radius: 10 }
                contentItem: Text { text: parent.text; color: "white"; font.pixelSize: 14; font.weight: (Font.SemiBold || 600); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 16; rightPadding: 16 }
            }

            Item { Layout.fillWidth: true }

            // VM Controls
            Button {
                text: "⚡ Start VM"
                implicitHeight: 38; enabled: !root._busy && root._available
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.startVm()
                background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Start the sandbox VM"
            }

            Button {
                text: "⬛ Stop VM"
                implicitHeight: 38; enabled: !root._busy
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.stopVm()
                background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Force stop the sandbox VM"
            }

            Button {
                text: "↺ Revert"
                implicitHeight: 38; enabled: !root._busy && root._available
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.resetToClean()
                background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Revert VM to clean snapshot"
            }

            Button {
                text: "🔬 Diagnose"
                implicitHeight: 38; enabled: !root._busy
                onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.runVmwareDiagnostics()
                background: Rectangle { color: parent.hovered ? ThemeManager.elevated() : ThemeManager.surface(); radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Run VMware prerequisite checks"
            }
        }

        Item { height: 16 }

        // ── Progress section (visible while busy) ─────────────────────────────
        Rectangle {
            visible: root._busy
            Layout.fillWidth: true
            Layout.bottomMargin: 16
            implicitHeight: progCol.implicitHeight + 28
            radius: 12
            color: ThemeManager.panel()
            border.color: ThemeManager.primary; border.width: 1

            ColumnLayout {
                id: progCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    spacing: 8; Layout.fillWidth: true
                    Text { text: "⚙  Running…"; color: ThemeManager.primary; font.pixelSize: 14; font.weight: (Font.SemiBold || 600) }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root._progress + "%"
                        color: ThemeManager.muted(); font.pixelSize: 12
                    }
                }

                // Progress bar
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 6; radius: 3
                    color: ThemeManager.surface()
                    Rectangle {
                        width: parent.width * Math.min(1, root._progress / 100)
                        height: parent.height; radius: 3
                        color: ThemeManager.primary
                        Behavior on width { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
                    }
                }

                Text {
                    visible: root._step !== ""
                    text: root._step
                    color: ThemeManager.foreground(); font.pixelSize: 12; wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        // ── Live frame viewer ─────────────────────────────────────────────────
        Rectangle {
            visible: root._liveFrame !== "" && root._busy
            Layout.fillWidth: true
            Layout.bottomMargin: 16
            implicitHeight: liveViewerCol.implicitHeight + 28
            radius: 12
            color: ThemeManager.panel()
            border.color: root._automationVisible ? "#16a34a" : ThemeManager.border()
            border.width: root._automationVisible ? 2 : 1

            // Subtle green glow when automation is actively running
            Behavior on border.color { ColorAnimation { duration: 300 } }

            ColumnLayout {
                id: liveViewerCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14
                spacing: 8

                // Header with automation badge
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        id: liveHdr
                        text: "\uD83D\uDCF9  Live VM View"
                        color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600)
                    }

                    // "VM Running" chip
                    Rectangle {
                        visible: root._busy
                        implicitWidth: vmRunningRow.implicitWidth + 12
                        implicitHeight: 20; radius: 10
                        color: "#1d4ed828"
                        border.color: "#1d4ed8"; border.width: 1
                        RowLayout {
                            id: vmRunningRow
                            anchors.centerIn: parent
                            spacing: 4
                            Rectangle {
                                width: 6; height: 6; radius: 3
                                color: "#60a5fa"
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite; running: root._busy
                                    NumberAnimation { to: 0.3; duration: 600 }
                                    NumberAnimation { to: 1.0; duration: 600 }
                                }
                            }
                            Text {
                                text: "VM Running"
                                color: "#1d4ed8"; font.pixelSize: 10; font.weight: (Font.Medium || 500)
                            }
                        }
                    }

                    // "Automation visible ✅" badge — only when UI runner is active
                    Rectangle {
                        visible: root._automationVisible
                        implicitWidth: autoVisBadgeRow.implicitWidth + 12
                        implicitHeight: 20; radius: 10
                        color: "#16a34a28"
                        border.color: "#16a34a"; border.width: 1

                        RowLayout {
                            id: autoVisBadgeRow
                            anchors.centerIn: parent
                            spacing: 4

                            Rectangle {
                                width: 6; height: 6; radius: 3
                                color: "#22c55e"
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite; running: root._automationVisible
                                    NumberAnimation { to: 0.2; duration: 500 }
                                    NumberAnimation { to: 1.0; duration: 500 }
                                }
                            }
                            Text {
                                text: "Automation visible"
                                color: "#16a34a"; font.pixelSize: 10; font.weight: (Font.Medium || 500)
                            }
                        }
                    }

                    // "No visible automation ⚠" chip — execution enabled but automation hidden
                    Rectangle {
                        visible: root._busy && root.allowExec && root.allowInteractiveGui && !root._automationVisible
                        implicitWidth: noAutoRow.implicitWidth + 12
                        implicitHeight: 20; radius: 10
                        color: "#ca8a0420"
                        border.color: "#ca8a04"; border.width: 1
                        RowLayout {
                            id: noAutoRow
                            anchors.centerIn: parent
                            spacing: 4
                            Text {
                                text: "⚠  No visible automation"
                                color: "#ca8a04"; font.pixelSize: 10; font.weight: (Font.Medium || 500)
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // Small frame counter
                    Text {
                        visible: root._replayFrames.length > 0
                        text: root._replayFrames.length + " frame" + (root._replayFrames.length !== 1 ? "s" : "")
                        color: ThemeManager.muted(); font.pixelSize: 10
                    }
                }

                // Live screenshot — image provider (smooth) with file:/// fallback
                Image {
                    id: frameImg
                    source: root._pvLive
                        ? "image://sandboxpreview/frame?t=" + root._pvFrame
                        : (root._liveFrame !== "" ? ("file:///" + root._liveFrame) : "")
                    Layout.fillWidth: true
                    Layout.preferredHeight: 280
                    fillMode: Image.PreserveAspectFit
                    cache: false
                }

                // UI runner warning — desktop not available
                Rectangle {
                    visible: root._uiRunnerStatus !== "" &&
                             (root._uiRunnerStatus.toLowerCase().indexOf("not logged") !== -1 ||
                              root._uiRunnerStatus.toLowerCase().indexOf("disconnected") !== -1 ||
                              root._uiRunnerStatus.toLowerCase().indexOf("no interactive") !== -1 ||
                              root._uiRunnerStatus.toLowerCase().indexOf("preflight") !== -1)
                    Layout.fillWidth: true
                    implicitHeight: uiWarnText.implicitHeight + 16
                    radius: 8
                    color: "#ca8a0420"
                    border.color: "#ca8a04"; border.width: 1

                    Text {
                        id: uiWarnText
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 10; anchors.rightMargin: 10
                        text: "\u26A0\uFE0F  " + root._uiRunnerStatus
                        color: "#ca8a04"; font.pixelSize: 11; wrapMode: Text.WordWrap
                    }
                }
            }
        }

        // ── Automation Replay Carousel ────────────────────────────────────────
        // Shown after scan completes when the UI runner captured key frames.
        // Thumbnails scroll horizontally; click any to see full view; prev/next
        // arrows walk the selection one at a time.
        Rectangle {
            id: replayCard
            visible: !root._busy && root._replayFrames.length > 0
            Layout.fillWidth: true
            Layout.bottomMargin: 16
            implicitHeight: replayCardCol.implicitHeight + 28
            radius: 12
            color: ThemeManager.panel()
            border.color: ThemeManager.border(); border.width: 1

            ColumnLayout {
                id: replayCardCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14
                spacing: 10

                // Header
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "\uD83C\uDFAC  Automation Replay"
                        color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600)
                    }
                    Text {
                        text: root._replayFrames.length + " frame" + (root._replayFrames.length !== 1 ? "s" : "")
                        color: ThemeManager.muted(); font.pixelSize: 11
                    }

                    Item { Layout.fillWidth: true }

                    // Prev button
                    Rectangle {
                        implicitWidth: 28; implicitHeight: 28; radius: 6
                        color: prevMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                        border.color: ThemeManager.border(); border.width: 1
                        enabled: root._replayIndex > 0
                        opacity: root._replayIndex > 0 ? 1 : 0.35
                        Behavior on color { ColorAnimation { duration: 80 } }
                        Text { anchors.centerIn: parent; text: "\u2039"; color: ThemeManager.foreground(); font.pixelSize: 16 }
                        MouseArea {
                            id: prevMa; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (root._replayIndex > 0) root._replayIndex--
                        }
                    }

                    // Frame counter
                    Text {
                        text: (root._replayIndex + 1) + " / " + root._replayFrames.length
                        color: ThemeManager.foreground(); font.pixelSize: 11
                        Layout.preferredWidth: 44
                        horizontalAlignment: Text.AlignHCenter
                    }

                    // Next button
                    Rectangle {
                        implicitWidth: 28; implicitHeight: 28; radius: 6
                        color: nextMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface()
                        border.color: ThemeManager.border(); border.width: 1
                        enabled: root._replayIndex < root._replayFrames.length - 1
                        opacity: root._replayIndex < root._replayFrames.length - 1 ? 1 : 0.35
                        Behavior on color { ColorAnimation { duration: 80 } }
                        Text { anchors.centerIn: parent; text: "\u203A"; color: ThemeManager.foreground(); font.pixelSize: 16 }
                        MouseArea {
                            id: nextMa; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (root._replayIndex < root._replayFrames.length - 1) root._replayIndex++
                        }
                    }
                }

                // Large selected frame
                Image {
                    id: replayMainImg
                    source: root._replayFrames.length > 0 ? root._replayFrames[root._replayIndex] : ""
                    Layout.fillWidth: true
                    Layout.preferredHeight: 300
                    fillMode: Image.PreserveAspectFit
                    cache: false
                    asynchronous: true

                    // Fade on frame change
                    NumberAnimation on opacity {
                        id: replayFade
                        from: 0.4; to: 1.0; duration: 160
                    }

                    onSourceChanged: replayFade.restart()

                    Rectangle {
                        anchors.fill: parent; visible: replayMainImg.status === Image.Loading
                        color: ThemeManager.surface(); radius: 6
                        Text { anchors.centerIn: parent; text: "Loading\u2026"; color: ThemeManager.muted(); font.pixelSize: 11 }
                    }
                }

                // Thumbnail strip
                ScrollView {
                    Layout.fillWidth: true
                    implicitHeight: 64
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AsNeeded
                    ScrollBar.vertical.policy:   ScrollBar.AlwaysOff

                    Row {
                        spacing: 6
                        Repeater {
                            model: root._replayFrames
                            delegate: Rectangle {
                                width: 90; height: 58; radius: 6
                                border.color: index === root._replayIndex ? "#7c3aed" : ThemeManager.border()
                                border.width: index === root._replayIndex ? 2 : 1
                                color: ThemeManager.surface()

                                Image {
                                    anchors.fill: parent; anchors.margins: 2
                                    source: modelData
                                    fillMode: Image.PreserveAspectCrop
                                    cache: false; asynchronous: true
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root._replayIndex = index
                                }
                            }
                        }
                    }
                }

                // "No frames changed" warning
                Rectangle {
                    visible: root._replayFrames.length > 0 &&
                             root._uiRunnerStatus !== "" &&
                             root._uiRunnerStatus.toLowerCase().indexOf("background") !== -1
                    Layout.fillWidth: true
                    implicitHeight: bgWarnTxt.implicitHeight + 14
                    radius: 8; color: "#78716c20"
                    border.color: "#78716c"; border.width: 1
                    Text {
                        id: bgWarnTxt
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 10; anchors.rightMargin: 10
                        text: "\u26A0\uFE0F  Automation ran in background / no interactive desktop detected. Frames may show no visible UI changes."
                        color: "#a8a29e"; font.pixelSize: 11; wrapMode: Text.WordWrap
                    }
                }
            }
        }

        // ── Verdict card ──────────────────────────────────────────────────────
        Rectangle {
            visible: root._verdict !== "" && !root._busy
            Layout.fillWidth: true
            Layout.bottomMargin: 16
            implicitHeight: verdictContent.implicitHeight + 28
            radius: 12
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
                anchors.margins: 14
                spacing: 6
                Text {
                    text: "🏁  Sandbox Verdict"
                    color: ThemeManager.muted(); font.pixelSize: 12; font.weight: (Font.Medium || 500)
                }
                Text {
                    text: root._verdict
                    color: ThemeManager.foreground(); font.pixelSize: 16; font.weight: (Font.Bold || 700)
                    wrapMode: Text.WordWrap; Layout.fillWidth: true
                }
            }
        }

        // ── Result metrics ────────────────────────────────────────────────────
        Rectangle {
            visible: Object.keys(root._result || {}).length > 0 && !root._busy
            Layout.fillWidth: true
            Layout.bottomMargin: 16
            implicitHeight: metricsGrid.implicitHeight + 28
            radius: 12
            color: ThemeManager.panel()
            border.color: ThemeManager.border(); border.width: 1

            GridLayout {
                id: metricsGrid
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14
                columns: 5
                rowSpacing: 12; columnSpacing: 12

                Repeater {
                    model: [
                        { label: "Processes",   key: "new_processes",    icon: "⚙" },
                        { label: "New Files",    key: "new_files",        icon: "📄" },
                        { label: "Connections",  key: "new_connections",  icon: "🌐" },
                        { label: "Registry",     key: "registry_changes", icon: "🔑" },
                        { label: "Alerts",       key: "alerts",           icon: "⚠" },
                    ]
                    delegate: Rectangle {
                        implicitWidth: (metricsGrid.width - metricsGrid.columnSpacing * 4) / 5
                        implicitHeight: 64
                        radius: 10
                        color: ThemeManager.surface()
                        border.color: ThemeManager.border(); border.width: 1
                        ColumnLayout {
                            anchors.centerIn: parent; spacing: 2
                            Text {
                                text: modelData.icon
                                font.pixelSize: 20
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: {
                                    var arr = (root._result || {})[modelData.key]
                                    return (arr && arr.length !== undefined) ? String(arr.length) : "0"
                                }
                                color: {
                                    var arr = (root._result || {})[modelData.key]
                                    var cnt = (arr && arr.length !== undefined) ? arr.length : 0
                                    return (cnt > 0 && modelData.key === "alerts") ? ThemeManager.warning : ThemeManager.foreground()
                                }
                                font.pixelSize: 20; font.weight: (Font.Bold || 700)
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: modelData.label
                                color: ThemeManager.muted(); font.pixelSize: 11
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }
            }
        }

        // ── Result detail sections ────────────────────────────────────────────
        Repeater {
            model: [
                { title: "⚙  New Processes",      key: "new_processes",    color: ThemeManager.foreground() },
                { title: "📄  File System Changes", key: "new_files",        color: ThemeManager.foreground() },
                { title: "🌐  Network Connections", key: "new_connections",  color: ThemeManager.primary },
                { title: "🔑  Registry Changes",    key: "registry_changes", color: ThemeManager.foreground() },
                { title: "⚠  Alerts",               key: "alerts",           color: ThemeManager.warning },
                { title: "✕  Errors",               key: "errors",           color: "#ef4444" },
            ]
            delegate: Rectangle {
                property var items: ((root._result || {})[modelData.key]) || []
                visible: items.length > 0 && !root._busy
                Layout.fillWidth: true
                Layout.bottomMargin: 10
                implicitHeight: detailCol.implicitHeight + 28
                radius: 12
                color: ThemeManager.panel()
                border.color: ThemeManager.border(); border.width: 1

                ColumnLayout {
                    id: detailCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 6
                    Text {
                        text: modelData.title
                        color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600)
                    }
                    Repeater {
                        model: items
                        Text {
                            text: "  • " + modelData
                            color: ThemeManager.muted(); font.pixelSize: 12; font.family: "Consolas"
                            wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
                        }
                    }
                }
            }
        }

        // ── Step log ──────────────────────────────────────────────────────────
        Rectangle {
            visible: root._steps.length > 0
            Layout.fillWidth: true
            Layout.bottomMargin: 10
            implicitHeight: logHeader.implicitHeight + (root.showLog ? logBody.implicitHeight + 6 : 0) + 28
            radius: 12
            color: ThemeManager.panel()
            border.color: ThemeManager.border(); border.width: 1

            ColumnLayout {
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14
                spacing: 6

                RowLayout {
                    id: logHeader
                    spacing: 8; Layout.fillWidth: true
                    Text {
                        text: "📋  Execution Log (" + root._steps.length + " events)"
                        color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600)
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root.showLog ? "▲ Hide" : "▼ Show"
                        color: ThemeManager.primary; font.pixelSize: 12
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showLog = !root.showLog }
                    }
                }

                ColumnLayout {
                    id: logBody
                    visible: root.showLog
                    spacing: 3; Layout.fillWidth: true
                    Repeater {
                        model: root._steps
                        RowLayout {
                            spacing: 8; Layout.fillWidth: true
                            Text {
                                text: modelData.time || ""
                                color: ThemeManager.muted(); font.pixelSize: 10; font.family: "Consolas"
                                Layout.preferredWidth: 70
                            }
                            Rectangle {
                                implicitWidth: statusTxt.implicitWidth + 12; implicitHeight: 18; radius: 4
                                color: {
                                    var s = (modelData.status || "").toLowerCase()
                                    if (s === "ok") return "#16a34a22"
                                    if (s === "error" || s === "fail") return "#dc262622"
                                    if (s === "warn") return "#ca8a0422"
                                    return ThemeManager.surface()
                                }
                                Text {
                                    id: statusTxt
                                    anchors.centerIn: parent
                                    text: (modelData.status || "").toUpperCase()
                                    color: {
                                        var s = (modelData.status || "").toLowerCase()
                                        if (s === "ok") return "#22c55e"
                                        if (s === "error" || s === "fail") return "#ef4444"
                                        if (s === "warn") return "#eab308"
                                        return ThemeManager.muted()
                                    }
                                    font.pixelSize: 9; font.weight: (Font.Bold || 700)
                                }
                            }
                            Text {
                                text: modelData.message || ""
                                color: ThemeManager.foreground(); font.pixelSize: 12; font.family: "Consolas"
                                wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }

        // ── Diagnostics results ───────────────────────────────────────────────
        Rectangle {
            visible: root.showDiag && root._diagChecks.length > 0
            Layout.fillWidth: true
            Layout.bottomMargin: 10
            implicitHeight: diagCol.implicitHeight + 28
            radius: 12
            color: ThemeManager.panel()
            border.color: ThemeManager.border(); border.width: 1

            ColumnLayout {
                id: diagCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    spacing: 8; Layout.fillWidth: true
                    Text { text: "🔬  Diagnostics"; color: ThemeManager.foreground(); font.pixelSize: 14; font.weight: (Font.SemiBold || 600) }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "✕"; color: ThemeManager.muted(); font.pixelSize: 16
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showDiag = false }
                    }
                }

                Repeater {
                    model: root._diagChecks
                    delegate: Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: diagItemCol.implicitHeight + 16
                        radius: 8
                        color: modelData.passed ? "#16a34a12" : "#dc262612"
                        border.color: modelData.passed ? "#16a34a" : "#dc2626"
                        border.width: 1

                        ColumnLayout {
                            id: diagItemCol
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                            anchors.margins: 12
                            spacing: 4

                            RowLayout {
                                spacing: 8; Layout.fillWidth: true
                                Text {
                                    text: modelData.passed ? "✓" : "✗"
                                    color: modelData.passed ? "#22c55e" : "#ef4444"
                                    font.pixelSize: 14; font.weight: (Font.Bold || 700)
                                }
                                Text {
                                    text: modelData.check || ""
                                    color: ThemeManager.foreground(); font.pixelSize: 13; font.weight: (Font.SemiBold || 600)
                                    Layout.fillWidth: true
                                }
                            }
                            Text {
                                text: modelData.message || ""
                                color: ThemeManager.muted(); font.pixelSize: 12; font.family: "Consolas"
                                wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
                                Layout.leftMargin: 22
                            }
                            Text {
                                visible: !modelData.passed && (modelData.fix || "") !== ""
                                text: "Fix: " + (modelData.fix || "")
                                color: "#f59e0b"; font.pixelSize: 11; wrapMode: Text.WordWrap
                                Layout.fillWidth: true; Layout.leftMargin: 22
                            }
                        }
                    }
                }
            }
        }

        // ── Open run folder ───────────────────────────────────────────────────
        RowLayout {
            visible: !root._busy && (typeof SandboxLab !== "undefined" && SandboxLab !== null) && SandboxLab.lastRunFolder !== ""
            Layout.fillWidth: true
            Layout.topMargin: 4
            spacing: 10
            Text {
                text: "Last run folder:"
                color: ThemeManager.muted(); font.pixelSize: 12
            }
            Text {
                text: (typeof SandboxLab !== "undefined" && SandboxLab !== null) ? SandboxLab.lastRunFolder : ""
                color: ThemeManager.primary; font.pixelSize: 12; font.underline: true
                elide: Text.ElideLeft; Layout.fillWidth: true
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: if (typeof SandboxLab !== "undefined" && SandboxLab !== null) SandboxLab.openLastRunFolder()
                }
            }
        }

        Item { height: 40 }
    }
}
