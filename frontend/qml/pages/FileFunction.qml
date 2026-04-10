import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import QtQuick.Dialogs
import "../ui"
import "../components"

Rectangle {
    id: root
    width: parent.width
    height: parent.height
    color: ThemeManager.background()

    // ── State properties ───────────────────────────────────────────────
    property string selectedFilePath: ""
    property string selectedFileSize: ""
    property bool shredRunning: false
    property bool shredDone: false
    property bool shredSuccess: false
    property string shredMessage: ""
    property string shredLogPath: ""
    property string shredPhase: ""
    property real shredPercent: 0
    property int shredPassIdx: 0
    property int shredTotalPasses: 1

    FileDialog {
        id: filePicker
        title: "Select file to permanently destroy"
        onAccepted: {
            var s = selectedFile.toString()
                        .replace(/^file:\/\/\//i, "")
                        .replace(/\//g, "\\")
            s = decodeURIComponent(s)
            selectedFilePath = s
            shredDone = false
        }
    }

    function _resetShredder() {
        shredRunning = false
        shredDone = false
        shredSuccess = false
        shredMessage = ""
        shredLogPath = ""
        shredPhase = ""
        shredPercent = 0
        shredPassIdx = 0
        shredTotalPasses = 1
        confirmCheck.checked = false
        confirmInput.text = ""
        selectedFilePath = ""
        selectedFileSize = ""
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Tab bar (manual, avoids Fusion style quirks) ───────────
        Rectangle {
            id: tabBarBg
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            color: ThemeManager.panel()
            z: 10

            property int currentIndex: 0

            Row {
                anchors.fill: parent

                Repeater {
                    model: [qsTr("File Permanent Delete"), qsTr("File Recovery")]

                    Rectangle {
                        width: tabBarBg.width / 2
                        height: tabBarBg.height
                        color: "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            color: tabBarBg.currentIndex === index ? ThemeManager.accent : ThemeManager.muted()
                            font.bold: tabBarBg.currentIndex === index
                            font.pixelSize: ThemeManager.fontSize_body
                        }

                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: 3
                            color: tabBarBg.currentIndex === index ? ThemeManager.accent : "transparent"
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: tabBarBg.currentIndex = index
                        }
                    }
                }
            }
        }

        StackLayout {
            id: viewStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBarBg.currentIndex

            // ════════════════════════════════════════════════════════════
            // TAB 0 — SECURE FILE SHREDDER (market-ready)
            // ════════════════════════════════════════════════════════════
            ScrollView {
                id: shredScroll
                clip: true

                Flickable {
                    contentWidth: shredScroll.width
                    contentHeight: shredColumn.implicitHeight + 40

                    ColumnLayout {
                        id: shredColumn
                        width: Math.min(680, shredScroll.width - 40)
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.topMargin: 20
                        anchors.top: parent.top
                        spacing: 0

                        // ── Card wrapper ───────────────────────────────
                        Rectangle {
                            id: shredCard
                            Layout.fillWidth: true
                            Layout.preferredHeight: cardContent.implicitHeight + 48
                            radius: 14
                            color: ThemeManager.panel()
                            border.color: ThemeManager.border()
                            border.width: 1

                            ColumnLayout {
                                id: cardContent
                                anchors.fill: parent
                                anchors.margins: 24
                                spacing: 20

                                // ── Title ──────────────────────────────
                                Text {
                                    text: "\uD83D\uDD12  Secure File Shredder"
                                    font.pixelSize: ThemeManager.fontSize_h2
                                    font.bold: true
                                    color: ThemeManager.foreground()
                                }

                                // ── Drop zone + file picker ────────────
                                Rectangle {
                                    id: dropZoneRect
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 120
                                    radius: 10
                                    color: dropArea.containsDrag
                                           ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.12)
                                           : ThemeManager.elevated()
                                    border.color: dropArea.containsDrag ? ThemeManager.accent : ThemeManager.border()
                                    border.width: dropArea.containsDrag ? 2 : 1

                                    ColumnLayout {
                                        anchors.centerIn: parent
                                        spacing: 10

                                        Text {
                                            text: dropArea.containsDrag
                                                  ? "\uD83D\uDCE5  Release to select file"
                                                  : "\uD83D\uDCC1  Drag and drop a file here, or click Browse"
                                            color: dropArea.containsDrag ? ThemeManager.accent : ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_body
                                            font.bold: dropArea.containsDrag
                                            Layout.alignment: Qt.AlignHCenter
                                        }

                                        RowLayout {
                                            Layout.alignment: Qt.AlignHCenter
                                            spacing: 10

                                            Rectangle {
                                                Layout.preferredWidth: 380
                                                Layout.preferredHeight: 36
                                                radius: 8
                                                color: ThemeManager.elevated()
                                                border.color: ThemeManager.border()

                                                Text {
                                                    id: filePathDisplay
                                                    anchors.fill: parent
                                                    anchors.leftMargin: 12
                                                    anchors.rightMargin: 12
                                                    verticalAlignment: Text.AlignVCenter
                                                    text: selectedFilePath || "No file selected"
                                                    color: selectedFilePath ? ThemeManager.foreground() : ThemeManager.muted()
                                                    font.pixelSize: ThemeManager.fontSize_body
                                                    elide: Text.ElideMiddle
                                                }
                                            }

                                            Button {
                                                id: browseBtn
                                                text: "\uD83D\uDCC2  Browse"
                                                font.pixelSize: ThemeManager.fontSize_body
                                                font.bold: true
                                                z: 20
                                                background: Rectangle {
                                                    implicitHeight: 36
                                                    implicitWidth: 100
                                                    radius: 8
                                                    color: browseBtn.hovered ? Qt.lighter(ThemeManager.accent, 1.15) : ThemeManager.accent
                                                    Behavior on color { ColorAnimation { duration: 120 } }
                                                }
                                                contentItem: Text {
                                                    text: parent.text
                                                    color: "#ffffff"
                                                    font: parent.font
                                                    horizontalAlignment: Text.AlignHCenter
                                                    verticalAlignment: Text.AlignVCenter
                                                }
                                                onClicked: filePicker.open()
                                            }
                                        }
                                    }

                                    DropArea {
                                        id: dropArea
                                        anchors.fill: parent
                                        keys: ["text/uri-list"]
                                        onDropped: function(drop) {
                                            if (drop.hasUrls && drop.urls.length > 0) {
                                                var raw = drop.urls[0].toString()
                                                var s = raw.replace(/^file:\/\/\//i, "")
                                                           .replace(/\//g, "\\")
                                                s = decodeURIComponent(s)
                                                // Ensure Windows drive letter format (C:\...)
                                                if (/^[A-Za-z]:\\/.test(s) === false && /^[A-Za-z]:/.test(s)) {
                                                    s = s  // already ok like C:file
                                                }
                                                selectedFilePath = s
                                                shredDone = false
                                            }
                                        }
                                    }
                                }

                                // ── Selected file info ─────────────────
                                Rectangle {
                                    visible: selectedFilePath !== ""
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: fileInfoCol.implicitHeight + 20
                                    radius: 10
                                    color: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.08)
                                    border.color: ThemeManager.accent
                                    border.width: 1

                                    ColumnLayout {
                                        id: fileInfoCol
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 4

                                        Text {
                                            text: "\uD83D\uDCC4  Selected File"
                                            color: ThemeManager.accent
                                            font.pixelSize: ThemeManager.fontSize_body
                                            font.bold: true
                                        }
                                        Text {
                                            text: selectedFilePath
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.family: "Consolas"
                                            wrapMode: Text.WrapAnywhere
                                            Layout.fillWidth: true
                                        }
                                    }
                                }

                                // ── Options row ────────────────────────
                                Text {
                                    text: "Options"
                                    font.pixelSize: ThemeManager.fontSize_body
                                    font.bold: true
                                    color: ThemeManager.foreground()
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 4
                                    columnSpacing: 16
                                    rowSpacing: 10

                                    // Passes
                                    Text {
                                        text: "Overwrite passes:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    StyledComboBox {
                                        id: comboPasses
                                        model: ["1", "3", "7"]
                                        currentIndex: 1
                                        Layout.preferredWidth: 80
                                    }

                                    // Verify toggle
                                    Text {
                                        text: "Verify after delete:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    Switch {
                                        id: toggleVerify
                                        checked: true
                                    }

                                    // Rename toggle
                                    Text {
                                        text: "Rename before delete:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    Switch {
                                        id: toggleRename
                                        checked: true
                                    }

                                    // Log toggle
                                    Text {
                                        text: "Write log file:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    Switch {
                                        id: toggleLog
                                        checked: true
                                    }
                                }

                                // ── Separator ──────────────────────────
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 1
                                    color: ThemeManager.border()
                                }

                                // ── Confirmation section ───────────────
                                Text {
                                    text: "Confirmation"
                                    font.pixelSize: ThemeManager.fontSize_body
                                    font.bold: true
                                    color: ThemeManager.danger
                                }

                                RowLayout {
                                    spacing: 8
                                    CheckBox {
                                        id: confirmCheck
                                        enabled: !shredRunning && !shredDone
                                        contentItem: Text {
                                            text: "I understand this action is irreversible"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_body
                                            leftPadding: (confirmCheck.indicator ? confirmCheck.indicator.width : 18) + 6
                                        }
                                    }
                                }

                                RowLayout {
                                    spacing: 8
                                    Text {
                                        text: "Type DELETE to confirm:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    StyledTextField {
                                        id: confirmInput
                                        Layout.preferredWidth: 140
                                        enabled: !shredRunning && !shredDone
                                        placeholderText: "DELETE"
                                    }
                                }

                                // ── Action button ──────────────────────
                                Button {
                                    id: btnShred
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 48
                                    enabled: selectedFilePath !== ""
                                             && confirmInput.text === "DELETE"
                                             && !shredRunning
                                             && !shredDone
                                    font.bold: true
                                    font.pixelSize: ThemeManager.fontSize_body

                                    background: Rectangle {
                                        radius: 10
                                        color: btnShred.enabled
                                               ? ThemeManager.danger
                                               : ThemeManager.muted()
                                        opacity: btnShred.enabled ? 1 : 0.5

                                        Behavior on color { ColorAnimation { duration: 150 } }
                                    }
                                    contentItem: Text {
                                        text: "\uD83D\uDDD1  PERMANENTLY DESTROY FILE"
                                        color: "#ffffff"
                                        font: btnShred.font
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    onClicked: {
                                        shredRunning = true
                                        shredDone = false
                                        shredPercent = 0
                                        shredPhase = "starting"
                                        var passes = parseInt(comboPasses.currentText)
                                        backend.startSecureDelete(
                                            selectedFilePath,
                                            passes,
                                            toggleRename.checked,
                                            toggleVerify.checked,
                                            toggleLog.checked
                                        )
                                    }
                                }

                                // ── Progress section ───────────────────
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    visible: shredRunning

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            text: {
                                                if (shredPhase === "rename") return "Renaming file…"
                                                if (shredPhase === "overwrite")
                                                    return "Overwriting — pass " + shredPassIdx + "/" + shredTotalPasses + "  (" + Math.round(shredPercent) + "%)"
                                                if (shredPhase === "delete") return "Deleting file…"
                                                if (shredPhase === "verify") return "Verifying deletion…"
                                                return "Preparing…"
                                            }
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_body
                                        }
                                        Item { Layout.fillWidth: true }
                                        Button {
                                            text: "Cancel"
                                            font.pixelSize: ThemeManager.fontSize_small
                                            background: Rectangle {
                                                implicitHeight: 30
                                                radius: 6
                                                color: ThemeManager.elevated()
                                                border.color: ThemeManager.border()
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: ThemeManager.foreground()
                                                font: parent.font
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            onClicked: backend.cancelSecureDelete()
                                        }
                                    }

                                    ProgressBar {
                                        id: shredProgressBar
                                        Layout.fillWidth: true
                                        from: 0; to: 1
                                        value: {
                                            if (shredTotalPasses <= 0) return 0
                                            var passWeight = 1.0 / shredTotalPasses
                                            return (shredPassIdx - 1) * passWeight + (shredPercent / 100) * passWeight
                                        }

                                        Behavior on value { NumberAnimation { duration: 200 } }

                                        background: Rectangle {
                                            implicitHeight: 14
                                            radius: 7
                                            color: ThemeManager.elevated()
                                        }
                                        contentItem: Item {
                                            implicitHeight: 14
                                            Rectangle {
                                                width: shredProgressBar.visualPosition * parent.width
                                                height: parent.height
                                                radius: 7
                                                color: ThemeManager.danger

                                                Behavior on width { NumberAnimation { duration: 200 } }

                                                Rectangle {
                                                    anchors.fill: parent
                                                    radius: parent.radius
                                                    gradient: Gradient {
                                                        orientation: Gradient.Horizontal
                                                        GradientStop { position: 0.0; color: "transparent" }
                                                        GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.15) }
                                                        GradientStop { position: 1.0; color: "transparent" }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                // ── Result panel: SUCCESS ──────────────
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: successCol.implicitHeight + 24
                                    radius: 10
                                    color: Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.10)
                                    border.color: ThemeManager.success
                                    visible: shredDone && shredSuccess

                                    ColumnLayout {
                                        id: successCol
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 6

                                        Text {
                                            text: "\u2705  " + shredMessage
                                            color: ThemeManager.success
                                            font.pixelSize: ThemeManager.fontSize_body
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            visible: shredLogPath !== ""
                                            text: "Log: " + shredLogPath
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }
                                    }
                                }

                                // ── Result panel: FAILURE ──────────────
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: failCol.implicitHeight + 24
                                    radius: 10
                                    color: Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.10)
                                    border.color: ThemeManager.danger
                                    visible: shredDone && !shredSuccess

                                    ColumnLayout {
                                        id: failCol
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 6

                                        Text {
                                            text: "\u274C  " + shredMessage
                                            color: ThemeManager.danger
                                            font.pixelSize: ThemeManager.fontSize_body
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }
                                    }
                                }

                                // ── Reset button after completion ──────
                                Button {
                                    visible: shredDone
                                    Layout.alignment: Qt.AlignHCenter
                                    text: "Shred Another File"
                                    font.pixelSize: ThemeManager.fontSize_body
                                    background: Rectangle {
                                        implicitHeight: 36
                                        radius: 8
                                        color: ThemeManager.elevated()
                                        border.color: ThemeManager.border()
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: ThemeManager.foreground()
                                        font: parent.font
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    onClicked: _resetShredder()
                                }

                                // ── SSD disclaimer ─────────────────────
                                Text {
                                    Layout.fillWidth: true
                                    text: "Note: On SSDs with wear-levelling, overwritten data may persist in " +
                                          "remapped sectors. For maximum assurance use full-disk encryption."
                                    color: ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_small
                                    wrapMode: Text.Wrap
                                    horizontalAlignment: Text.AlignHCenter
                                    topPadding: 4
                                }
                            }
                        }
                    }
                }
            }

            // ════════════════════════════════════════════════════════════
            // TAB 1 — FILE RECOVERY (ENHANCED)
            // ════════════════════════════════════════════════════════════
            Item {
                id: tabRecovery

                // ── Recovery state ─────────────────────────────────────
                property bool isAdmin: false
                property bool scanning: false
                property bool scanDone: false
                property int scanPercent: 0
                property string scanStage: ""
                property string scanDrive: ""
                property int scanFoundCount: 0
                property real scanSpeedMbps: 0
                property var selectedIds: ({})
                property int selectedCount: 0
                property bool recovering: false
                property bool recoverDone: false
                property int recoverPercent: 0
                property int recoverDoneCount: 0
                property int recoverTotal: 0
                property string outputDir: ""
                property var recoveredPaths: []
                property string errorMsg: ""

                // Dynamic ListModel for real-time candidate streaming
                ListModel { id: candidateModel }

                function resetRecovery() {
                    scanning = false
                    scanDone = false
                    scanPercent = 0
                    scanStage = ""
                    scanDrive = ""
                    scanFoundCount = 0
                    scanSpeedMbps = 0
                    candidateModel.clear()
                    selectedIds = ({})
                    selectedCount = 0
                    recovering = false
                    recoverDone = false
                    recoverPercent = 0
                    recoverDoneCount = 0
                    recoverTotal = 0
                    outputDir = ""
                    recoveredPaths = []
                    errorMsg = ""
                }

                function toggleCandidate(cid) {
                    var s = selectedIds
                    if (s[cid]) {
                        delete s[cid]
                    } else {
                        s[cid] = true
                    }
                    selectedIds = s
                    selectedCount = Object.keys(s).length
                }
                function selectAll() {
                    var s = {}
                    for (var i = 0; i < candidateModel.count; i++)
                        s[candidateModel.get(i).cid] = true
                    selectedIds = s
                    selectedCount = Object.keys(s).length
                }
                function selectNone() {
                    selectedIds = ({})
                    selectedCount = 0
                }

                function _formatSize(bytes) {
                    if (bytes > 1048576) return (bytes / 1048576).toFixed(1) + " MB"
                    if (bytes > 1024) return (bytes / 1024).toFixed(1) + " KB"
                    return bytes + " B"
                }

                function _typeBadgeColor(t) {
                    if (t === "pdf") return "#E74C3C"
                    if (t === "jpg") return "#F39C12"
                    if (t === "png") return "#27AE60"
                    if (t === "mp4") return "#9B59B6"
                    if (t === "zip" || t === "docx") return "#3498DB"
                    return ThemeManager.accent
                }

                function _confidenceColor(c) {
                    if (c >= 70) return ThemeManager.success
                    if (c >= 40) return ThemeManager.warning
                    return ThemeManager.danger
                }

                Component.onCompleted: {
                    if (RecoveryService) tabRecovery.isAdmin = RecoveryService.checkAdmin()
                }

                ScrollView {
                    anchors.fill: parent
                    clip: true

                    Flickable {
                        contentWidth: parent.width
                        contentHeight: recoveryCol.implicitHeight + 48

                        ColumnLayout {
                            id: recoveryCol
                            width: Math.min(860, tabRecovery.width - 48)
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: 24
                            spacing: 16

                            // ── Title ──────────────────────────────────
                            Text {
                                text: "\uD83D\uDD0D  System-Wide File Recovery"
                                font.pixelSize: ThemeManager.fontSize_h2
                                font.bold: true
                                color: ThemeManager.foreground()
                            }
                            Text {
                                text: "Scan raw disk sectors for deleted file signatures. Files appear in real-time as they are found — select which to recover."
                                color: ThemeManager.muted()
                                font.pixelSize: ThemeManager.fontSize_body
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

                            // ── Admin warning ──────────────────────────
                            Rectangle {
                                visible: !tabRecovery.isAdmin
                                Layout.fillWidth: true
                                Layout.preferredHeight: adminWarnCol.implicitHeight + 20
                                radius: 10
                                color: Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.20)
                                border.color: ThemeManager.warning

                                ColumnLayout {
                                    id: adminWarnCol
                                    anchors.fill: parent
                                    anchors.margins: 12

                                    Text {
                                        text: "\u26A0  Not running as Administrator"
                                        color: ThemeManager.warning
                                        font.bold: true
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    Text {
                                        text: "Raw disk scanning requires admin privileges. Running in demo mode instead."
                                        color: ThemeManager.warning
                                        font.pixelSize: ThemeManager.fontSize_small
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                }
                            }

                            // ── Error banner ───────────────────────────
                            Rectangle {
                                visible: tabRecovery.errorMsg !== ""
                                Layout.fillWidth: true
                                Layout.preferredHeight: errText.implicitHeight + 24
                                radius: 10
                                color: Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.20)
                                border.color: ThemeManager.danger

                                Text {
                                    id: errText
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    text: "\u274C  " + tabRecovery.errorMsg
                                    color: ThemeManager.danger
                                    font.pixelSize: ThemeManager.fontSize_body
                                    wrapMode: Text.Wrap
                                }
                            }

                            // ── Controls panel ─────────────────────────
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: controlsRow.implicitHeight + 28
                                radius: 10
                                color: ThemeManager.panel()
                                border.color: ThemeManager.border()

                                RowLayout {
                                    id: controlsRow
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.margins: 14
                                    spacing: 14

                                    Text {
                                        text: "File Type:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                        font.bold: true
                                        verticalAlignment: Text.AlignVCenter
                                    }

                                    StyledComboBox {
                                        id: recoveryTypeCombo
                                        model: ["any", "pdf", "jpg", "png", "mp4", "zip", "docx"]
                                        Layout.preferredWidth: 120
                                    }

                                    Item { Layout.preferredWidth: 8 }

                                    Button {
                                        id: btnScan
                                        text: tabRecovery.scanning ? "\u23F3  Scanning…" : "\uD83D\uDD0E  Start Scan"
                                        enabled: !tabRecovery.scanning && !tabRecovery.recovering
                                        font.bold: true
                                        font.pixelSize: ThemeManager.fontSize_body
                                        background: Rectangle {
                                            implicitHeight: 40
                                            implicitWidth: 150
                                            radius: 8
                                            color: btnScan.enabled ? ThemeManager.accent : ThemeManager.elevated()
                                            Behavior on color { ColorAnimation { duration: 150 } }
                                        }
                                        contentItem: Text {
                                            text: parent.text
                                            color: btnScan.enabled ? "#ffffff" : ThemeManager.muted()
                                            font: parent.font
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        onClicked: {
                                            tabRecovery.resetRecovery()
                                            tabRecovery.scanning = true
                                            tabRecovery.errorMsg = ""
                                            RecoveryService.startRecoveryScan(recoveryTypeCombo.currentText)
                                        }
                                    }

                                    Button {
                                        visible: tabRecovery.scanning
                                        text: "\u2716  Cancel"
                                        font.pixelSize: ThemeManager.fontSize_body
                                        background: Rectangle {
                                            implicitHeight: 40
                                            radius: 8
                                            color: ThemeManager.elevated()
                                            border.color: ThemeManager.danger
                                        }
                                        contentItem: Text {
                                            text: parent.text
                                            color: ThemeManager.danger
                                            font: parent.font
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        onClicked: RecoveryService.cancelRecoveryScan()
                                    }

                                    Item { Layout.fillWidth: true }
                                }
                            }

                            // ── Scan progress panel ────────────────────
                            Rectangle {
                                visible: tabRecovery.scanning
                                Layout.fillWidth: true
                                Layout.preferredHeight: progressCol.implicitHeight + 28
                                radius: 10
                                color: ThemeManager.panel()
                                border.color: ThemeManager.border()

                                ColumnLayout {
                                    id: progressCol
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 10

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        Text {
                                            text: tabRecovery.scanStage || "Preparing scan…"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_body
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }
                                        Text {
                                            text: tabRecovery.scanPercent + "% complete"
                                            color: ThemeManager.accent
                                            font.bold: true
                                            font.pixelSize: ThemeManager.fontSize_body
                                        }
                                    }

                                    ProgressBar {
                                        id: scanProgressBar
                                        Layout.fillWidth: true
                                        from: 0; to: 100
                                        value: tabRecovery.scanPercent

                                        Behavior on value { NumberAnimation { duration: 200 } }

                                        background: Rectangle {
                                            implicitHeight: 14
                                            radius: 7
                                            color: ThemeManager.elevated()
                                        }
                                        contentItem: Item {
                                            implicitHeight: 14
                                            Rectangle {
                                                width: scanProgressBar.visualPosition * parent.width
                                                height: parent.height
                                                radius: 7
                                                color: ThemeManager.accent

                                                Behavior on width { NumberAnimation { duration: 200 } }

                                                // Animated shine overlay
                                                Rectangle {
                                                    anchors.fill: parent
                                                    radius: parent.radius
                                                    gradient: Gradient {
                                                        orientation: Gradient.Horizontal
                                                        GradientStop { position: 0.0; color: "transparent" }
                                                        GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.15) }
                                                        GradientStop { position: 1.0; color: "transparent" }
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    // Stats row
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 24

                                        // Drive indicator
                                        Row {
                                            spacing: 6
                                            Rectangle {
                                                width: 8; height: 8; radius: 4
                                                color: ThemeManager.accent
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            Text {
                                                text: "Drive: " + (tabRecovery.scanDrive || "—")
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_small
                                            }
                                        }

                                        // Files found
                                        Row {
                                            spacing: 6
                                            Rectangle {
                                                width: 8; height: 8; radius: 4
                                                color: ThemeManager.success
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            Text {
                                                text: tabRecovery.scanFoundCount + " files found"
                                                color: ThemeManager.success
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.bold: true
                                            }
                                        }

                                        // Speed
                                        Row {
                                            visible: tabRecovery.scanSpeedMbps > 0
                                            spacing: 6
                                            Text {
                                                text: "\u26A1"
                                                font.pixelSize: ThemeManager.fontSize_small
                                            }
                                            Text {
                                                text: tabRecovery.scanSpeedMbps.toFixed(1) + " MB/s"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_small
                                            }
                                        }

                                        Item { Layout.fillWidth: true }
                                    }
                                }
                            }

                            // ── Results section (visible during scan + after) ──
                            Rectangle {
                                visible: candidateModel.count > 0
                                Layout.fillWidth: true
                                Layout.preferredHeight: resultsCol.implicitHeight + 28
                                radius: 10
                                color: ThemeManager.panel()
                                border.color: ThemeManager.border()

                                ColumnLayout {
                                    id: resultsCol
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 12

                                    // Header row with title + bulk actions
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10

                                        Text {
                                            text: "\uD83D\uDCC1  " + candidateModel.count + " Candidates Found"
                                            font.pixelSize: ThemeManager.fontSize_h3
                                            font.bold: true
                                            color: ThemeManager.foreground()
                                        }

                                        // Scanning indicator dot
                                        Rectangle {
                                            visible: tabRecovery.scanning
                                            width: 10; height: 10; radius: 5
                                            color: ThemeManager.accent
                                            SequentialAnimation on opacity {
                                                loops: Animation.Infinite
                                                NumberAnimation { to: 0.3; duration: 600 }
                                                NumberAnimation { to: 1.0; duration: 600 }
                                            }
                                        }
                                        Text {
                                            visible: tabRecovery.scanning
                                            text: "scanning…"
                                            color: ThemeManager.accent
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.italic: true
                                        }

                                        Item { Layout.fillWidth: true }

                                        // ── Select All button ──────────
                                        Button {
                                            id: btnSelectAll
                                            text: "\u2611  Select All"
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.bold: true
                                            background: Rectangle {
                                                implicitHeight: 32
                                                implicitWidth: 100
                                                radius: 6
                                                color: btnSelectAll.hovered
                                                       ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.15)
                                                       : ThemeManager.elevated()
                                                border.color: ThemeManager.accent
                                                border.width: 1
                                                Behavior on color { ColorAnimation { duration: 120 } }
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: ThemeManager.accent
                                                font: parent.font
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            onClicked: tabRecovery.selectAll()
                                        }

                                        // ── Unselect All button ────────
                                        Button {
                                            id: btnUnselectAll
                                            text: "\u2610  Unselect All"
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.bold: true
                                            background: Rectangle {
                                                implicitHeight: 32
                                                implicitWidth: 110
                                                radius: 6
                                                color: btnUnselectAll.hovered
                                                       ? Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.12)
                                                       : ThemeManager.elevated()
                                                border.color: ThemeManager.border()
                                                Behavior on color { ColorAnimation { duration: 120 } }
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: ThemeManager.foreground()
                                                font: parent.font
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            onClicked: tabRecovery.selectNone()
                                        }
                                    }

                                    // Selection summary
                                    Text {
                                        visible: tabRecovery.selectedCount > 0
                                        text: tabRecovery.selectedCount + " of " + candidateModel.count + " files selected for recovery"
                                        color: ThemeManager.accent
                                        font.pixelSize: ThemeManager.fontSize_small
                                        font.bold: true
                                    }

                                    // Column headers
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 34
                                        color: ThemeManager.elevated()
                                        radius: 6

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 10
                                            anchors.rightMargin: 10
                                            spacing: 6

                                            Text { text: ""; Layout.preferredWidth: 32 }
                                            Text {
                                                text: "Type"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.bold: true
                                                Layout.preferredWidth: 58
                                            }
                                            Text {
                                                text: "Size"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.bold: true
                                                Layout.preferredWidth: 78
                                            }
                                            Text {
                                                text: "Confidence"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.bold: true
                                                Layout.preferredWidth: 82
                                            }
                                            Text {
                                                text: "Drive"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.bold: true
                                                Layout.preferredWidth: 60
                                            }
                                            Text {
                                                text: "Offset"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.bold: true
                                                Layout.preferredWidth: 95
                                            }
                                            Text {
                                                text: "Preview"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_small
                                                font.bold: true
                                                Layout.fillWidth: true
                                            }
                                        }
                                    }

                                    // ── Candidate list (ListView for performance) ──
                                    ListView {
                                        id: candidateListView
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: Math.min(candidateModel.count * 44, 480)
                                        model: candidateModel
                                        clip: true
                                        spacing: 2
                                        boundsBehavior: Flickable.StopAtBounds
                                        cacheBuffer: 600

                                        ScrollBar.vertical: ScrollBar {
                                            policy: candidateModel.count > 10 ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
                                        }

                                        delegate: Rectangle {
                                            id: candidateRow
                                            width: candidateListView.width
                                            height: 42
                                            radius: 6
                                            color: tabRecovery.selectedIds[model.cid]
                                                   ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.10)
                                                   : (model.index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02))
                                            border.color: tabRecovery.selectedIds[model.cid] ? ThemeManager.accent : "transparent"
                                            border.width: tabRecovery.selectedIds[model.cid] ? 1 : 0

                                            Behavior on color { ColorAnimation { duration: 120 } }

                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: tabRecovery.toggleCandidate(model.cid)
                                            }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: 10
                                                anchors.rightMargin: 10
                                                spacing: 6

                                                CheckBox {
                                                    checked: tabRecovery.selectedIds[model.cid] === true
                                                    onToggled: tabRecovery.toggleCandidate(model.cid)
                                                    Layout.preferredWidth: 32
                                                }

                                                // Type badge
                                                Rectangle {
                                                    Layout.preferredWidth: 52
                                                    Layout.preferredHeight: 24
                                                    radius: 4
                                                    color: tabRecovery._typeBadgeColor(model.ctype)
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: model.ctype.toUpperCase()
                                                        color: "#ffffff"
                                                        font.pixelSize: ThemeManager.fontSize_caption
                                                        font.bold: true
                                                    }
                                                }

                                                // Size
                                                Text {
                                                    text: tabRecovery._formatSize(model.sizeGuess)
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    Layout.preferredWidth: 78
                                                }

                                                // Confidence
                                                Text {
                                                    text: model.confidence + "%"
                                                    color: tabRecovery._confidenceColor(model.confidence)
                                                    font.bold: true
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    Layout.preferredWidth: 82
                                                }

                                                // Drive
                                                Text {
                                                    text: model.drive
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    Layout.preferredWidth: 60
                                                }

                                                // Offset
                                                Text {
                                                    text: model.offsetHex
                                                    color: ThemeManager.muted()
                                                    font.family: "Consolas"
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    Layout.preferredWidth: 95
                                                }

                                                // Preview
                                                Text {
                                                    text: model.preview || "\u2014"
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }
                                    }

                                    // ── Action buttons row ─────────────
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.topMargin: 4
                                        spacing: 12

                                        Button {
                                            id: btnRecoverSelected
                                            enabled: tabRecovery.selectedCount > 0 && !tabRecovery.recovering && !tabRecovery.scanning
                                            text: "\uD83D\uDCBE  Recover Selected (" + tabRecovery.selectedCount + ")"
                                            font.bold: true
                                            font.pixelSize: ThemeManager.fontSize_body
                                            background: Rectangle {
                                                implicitHeight: 42
                                                implicitWidth: 240
                                                radius: 8
                                                color: btnRecoverSelected.enabled ? ThemeManager.success : ThemeManager.elevated()
                                                Behavior on color { ColorAnimation { duration: 150 } }
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: btnRecoverSelected.enabled ? "#ffffff" : ThemeManager.muted()
                                                font: parent.font
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            onClicked: {
                                                var ids = Object.keys(tabRecovery.selectedIds).map(function(k) { return parseInt(k) })
                                                tabRecovery.recovering = true
                                                tabRecovery.recoverTotal = ids.length
                                                RecoveryService.recoverSelected(JSON.stringify(ids))
                                            }
                                        }

                                        Item { Layout.fillWidth: true }

                                        Button {
                                            text: "\uD83D\uDD04  New Scan"
                                            font.pixelSize: ThemeManager.fontSize_body
                                            enabled: !tabRecovery.scanning
                                            background: Rectangle {
                                                implicitHeight: 42
                                                radius: 8
                                                color: ThemeManager.elevated()
                                                border.color: ThemeManager.border()
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: ThemeManager.foreground()
                                                font: parent.font
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            onClicked: tabRecovery.resetRecovery()
                                        }
                                    }
                                }
                            }

                            // ── Initial empty state (before any scan) ───
                            Rectangle {
                                visible: !tabRecovery.scanning && !tabRecovery.scanDone && candidateModel.count === 0
                                Layout.fillWidth: true
                                Layout.preferredHeight: emptyStateCol.implicitHeight + 48
                                radius: 10
                                color: ThemeManager.panel()
                                border.color: ThemeManager.border()

                                ColumnLayout {
                                    id: emptyStateCol
                                    anchors.centerIn: parent
                                    spacing: 12

                                    Text {
                                        text: "\uD83D\uDCC2"
                                        font.pixelSize: 40
                                        Layout.alignment: Qt.AlignHCenter
                                    }

                                    Text {
                                        text: "Ready to Scan"
                                        font.pixelSize: ThemeManager.fontSize_h3
                                        font.bold: true
                                        color: ThemeManager.foreground()
                                        Layout.alignment: Qt.AlignHCenter
                                    }

                                    Text {
                                        text: "Select a file type above and click Start Scan to search for\ndeleted files on your disk. Recovered candidates will appear here."
                                        color: ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_body
                                        horizontalAlignment: Text.AlignHCenter
                                        wrapMode: Text.Wrap
                                        Layout.alignment: Qt.AlignHCenter
                                        Layout.maximumWidth: 480
                                    }
                                }
                            }

                            // ── No candidates message ──────────────────
                            Rectangle {
                                visible: tabRecovery.scanDone && candidateModel.count === 0
                                Layout.fillWidth: true
                                Layout.preferredHeight: 90
                                radius: 10
                                color: ThemeManager.panel()
                                border.color: ThemeManager.border()

                                Text {
                                    anchors.centerIn: parent
                                    text: "No file signatures found. Try a different file type or scan as Administrator on a drive with deleted files."
                                    color: ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    wrapMode: Text.Wrap
                                    width: parent.width - 40
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }

                            // ── Recovery progress ──────────────────────
                            Rectangle {
                                visible: tabRecovery.recovering
                                Layout.fillWidth: true
                                Layout.preferredHeight: recoverProgCol.implicitHeight + 28
                                radius: 10
                                color: ThemeManager.panel()
                                border.color: ThemeManager.success

                                ColumnLayout {
                                    id: recoverProgCol
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 10

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            text: "\uD83D\uDCBE  Recovering files: " + tabRecovery.recoverDoneCount + " / " + tabRecovery.recoverTotal
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_body
                                            font.bold: true
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: tabRecovery.recoverPercent + "%"
                                            color: ThemeManager.success
                                            font.bold: true
                                            font.pixelSize: ThemeManager.fontSize_body
                                        }
                                    }

                                    ProgressBar {
                                        id: recoverProgressBar
                                        Layout.fillWidth: true
                                        from: 0; to: 100
                                        value: tabRecovery.recoverPercent

                                        Behavior on value { NumberAnimation { duration: 200 } }

                                        background: Rectangle {
                                            implicitHeight: 14
                                            radius: 7
                                            color: ThemeManager.elevated()
                                        }
                                        contentItem: Item {
                                            implicitHeight: 14
                                            Rectangle {
                                                width: recoverProgressBar.visualPosition * parent.width
                                                height: parent.height
                                                radius: 7
                                                color: ThemeManager.success

                                                Behavior on width { NumberAnimation { duration: 200 } }

                                                Rectangle {
                                                    anchors.fill: parent
                                                    radius: parent.radius
                                                    gradient: Gradient {
                                                        orientation: Gradient.Horizontal
                                                        GradientStop { position: 0.0; color: "transparent" }
                                                        GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.15) }
                                                        GradientStop { position: 1.0; color: "transparent" }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // ── Recovery complete ──────────────────────
                            Rectangle {
                                visible: tabRecovery.recoverDone
                                Layout.fillWidth: true
                                Layout.preferredHeight: doneCol.implicitHeight + 28
                                radius: 10
                                color: Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.10)
                                border.color: ThemeManager.success

                                ColumnLayout {
                                    id: doneCol
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 10

                                    Text {
                                        text: "\u2705  Recovery Complete — " + tabRecovery.recoveredPaths.length + " files recovered"
                                        color: ThemeManager.success
                                        font.pixelSize: ThemeManager.fontSize_body
                                        font.bold: true
                                    }

                                    RowLayout {
                                        spacing: 12
                                        Text {
                                            text: "Output: " + tabRecovery.outputDir
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }
                                        Button {
                                            text: "\uD83D\uDCC2  Open Folder"
                                            font.pixelSize: ThemeManager.fontSize_small
                                            background: Rectangle {
                                                implicitHeight: 32
                                                radius: 6
                                                color: ThemeManager.elevated()
                                                border.color: ThemeManager.border()
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: ThemeManager.foreground()
                                                font: parent.font
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            onClicked: RecoveryService.openRecoveryFolder(tabRecovery.outputDir)
                                        }
                                    }
                                }
                            }

                            // Bottom spacer
                            Item { Layout.preferredHeight: 16 }
                        }
                    }
                }

                // ── Recovery service connections ────────────────────────
                Connections {
                    target: RecoveryService

                    function onRecoveryScanProgressChanged(jsonStr) {
                        var d = JSON.parse(jsonStr)
                        tabRecovery.scanPercent = d.percent
                        tabRecovery.scanStage = d.stage
                        tabRecovery.scanDrive = d.drive
                        tabRecovery.scanFoundCount = d.found_count
                        if (d.speed_mbps !== undefined) tabRecovery.scanSpeedMbps = d.speed_mbps
                    }

                    function onRecoveryScanCandidateFound(jsonStr) {
                        var c = JSON.parse(jsonStr)
                        candidateModel.append({
                            cid:         c.id,
                            ctype:       c.type,
                            sizeGuess:   c.size_guess,
                            confidence:  c.confidence,
                            drive:       c.drive,
                            offsetHex:   c.offset_hex || "0x0",
                            preview:     c.preview_text || ""
                        })
                    }

                    function onRecoveryScanCandidateBatch(jsonStr) {
                        var arr = JSON.parse(jsonStr)
                        for (var i = 0; i < arr.length; i++) {
                            var c = arr[i]
                            candidateModel.append({
                                cid:         c.id,
                                ctype:       c.type,
                                sizeGuess:   c.size_guess,
                                confidence:  c.confidence,
                                drive:       c.drive,
                                offsetHex:   c.offset_hex || "0x0",
                                preview:     c.preview_text || ""
                            })
                        }
                    }

                    function onRecoveryScanFinished(jsonStr) {
                        var d = JSON.parse(jsonStr)
                        tabRecovery.scanning = false
                        tabRecovery.scanDone = true
                        tabRecovery.outputDir = d.output_dir
                    }

                    function onRecoveryScanError(msg) {
                        tabRecovery.errorMsg = msg
                        // The scan worker only emits error for truly fatal
                        // conditions (not per-drive skip).  Mark scan done.
                        tabRecovery.scanning = false
                        tabRecovery.scanDone = true
                    }

                    function onRecoveryRecoverProgressChanged(jsonStr) {
                        var d = JSON.parse(jsonStr)
                        tabRecovery.recoverPercent = d.percent
                        tabRecovery.recoverDoneCount = d.done
                    }

                    function onRecoveryRecoverFinished(jsonStr) {
                        var d = JSON.parse(jsonStr)
                        tabRecovery.recovering = false
                        tabRecovery.recoverDone = true
                        tabRecovery.recoveredPaths = d.recovered_paths
                        tabRecovery.outputDir = d.output_dir
                    }

                    function onRecoveryRecoverError(msg) {
                        tabRecovery.recovering = false
                        tabRecovery.errorMsg = msg
                    }
                }
            }
        }
    }

    Connections {
        target: backend

        function onShredderProgressChanged(jsonStr) {
            var d = JSON.parse(jsonStr)
            shredPhase = d.phase
            shredPercent = d.percent
            shredPassIdx = d.pass_idx
            shredTotalPasses = d.total_passes
        }

        function onShredderFinished(jsonStr) {
            var d = JSON.parse(jsonStr)
            shredRunning = false
            shredDone = true
            shredSuccess = true
            shredMessage = d.message || "File securely destroyed."
            shredLogPath = d.log_path || ""
        }

        function onShredderFailed(jsonStr) {
            var d = JSON.parse(jsonStr)
            shredRunning = false
            shredDone = true
            shredSuccess = false
            shredMessage = d.message || "Shredding failed."
            shredLogPath = ""
        }
    }
}
