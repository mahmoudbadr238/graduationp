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
            selectedFilePath = s
            filePathInput.text = s
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
        filePathInput.text = ""
        selectedFileSize = ""
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TabBar {
            id: navBar
            Layout.fillWidth: true
            background: Rectangle { color: ThemeManager.panel() }

            TabButton {
                text: qsTr("File Permanent Delete")
                contentItem: Text {
                    text: parent.text
                    color: ThemeManager.foreground()
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
            TabButton {
                text: qsTr("File Recovery")
                contentItem: Text {
                    text: parent.text
                    color: ThemeManager.foreground()
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        StackLayout {
            id: viewStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: navBar.currentIndex

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
                            color: ThemeManager.surface()
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
                                    font.pixelSize: ThemeManager.fontSize_h2()
                                    font.bold: true
                                    color: ThemeManager.foreground()
                                }

                                // ── Drop zone + file picker ────────────
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 110
                                    radius: 10
                                    color: dropArea.containsDrag
                                           ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.08)
                                           : ThemeManager.elevated()
                                    border.color: dropArea.containsDrag ? ThemeManager.accent : ThemeManager.border()
                                    border.width: dropArea.containsDrag ? 2 : 1

                                    DropArea {
                                        id: dropArea
                                        anchors.fill: parent
                                        onDropped: function(drop) {
                                            if (drop.urls.length > 0) {
                                                var s = drop.urls[0].toString()
                                                            .replace(/^file:\/\/\//i, "")
                                                            .replace(/\//g, "\\")
                                                selectedFilePath = s
                                                filePathInput.text = s
                                                shredDone = false
                                            }
                                        }
                                    }

                                    ColumnLayout {
                                        anchors.centerIn: parent
                                        spacing: 8

                                        Text {
                                            text: "Drag and drop a file here, or click Browse"
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_body()
                                            Layout.alignment: Qt.AlignHCenter
                                        }

                                        RowLayout {
                                            Layout.alignment: Qt.AlignHCenter
                                            spacing: 8

                                            StyledTextField {
                                                id: filePathInput
                                                readOnly: true
                                                placeholderText: "No file selected"
                                                Layout.preferredWidth: 380
                                            }

                                            Button {
                                                text: "Browse"
                                                font.pixelSize: ThemeManager.fontSize_body()
                                                background: Rectangle {
                                                    implicitHeight: 36
                                                    radius: 8
                                                    color: ThemeManager.accent
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
                                }

                                // ── Options row ────────────────────────
                                Text {
                                    text: "Options"
                                    font.pixelSize: ThemeManager.fontSize_body()
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
                                        font.pixelSize: ThemeManager.fontSize_body()
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
                                        font.pixelSize: ThemeManager.fontSize_body()
                                    }
                                    Switch {
                                        id: toggleVerify
                                        checked: true
                                    }

                                    // Rename toggle
                                    Text {
                                        text: "Rename before delete:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body()
                                    }
                                    Switch {
                                        id: toggleRename
                                        checked: true
                                    }

                                    // Log toggle
                                    Text {
                                        text: "Write log file:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body()
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
                                    font.pixelSize: ThemeManager.fontSize_body()
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
                                            font.pixelSize: ThemeManager.fontSize_body()
                                            leftPadding: (confirmCheck.indicator ? confirmCheck.indicator.width : 18) + 6
                                        }
                                    }
                                }

                                RowLayout {
                                    spacing: 8
                                    Text {
                                        text: "Type DELETE to confirm:"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body()
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
                                             && confirmCheck.checked
                                             && confirmInput.text === "DELETE"
                                             && !shredRunning
                                             && !shredDone
                                    font.bold: true
                                    font.pixelSize: ThemeManager.fontSize_body()

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
                                            font.pixelSize: ThemeManager.fontSize_body()
                                        }
                                        Item { Layout.fillWidth: true }
                                        Button {
                                            text: "Cancel"
                                            font.pixelSize: ThemeManager.fontSize_small()
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
                                            font.pixelSize: ThemeManager.fontSize_body()
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            visible: shredLogPath !== ""
                                            text: "Log: " + shredLogPath
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small()
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
                                            font.pixelSize: ThemeManager.fontSize_body()
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
                                    font.pixelSize: ThemeManager.fontSize_body()
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
                                    font.pixelSize: ThemeManager.fontSize_small()
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
            // TAB 1 — FILE RECOVERY (CARVER)
            // ════════════════════════════════════════════════════════════
            Item {
                id: tabRecovery

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 15

                    Text {
                        text: "System-Wide File Recovery"
                        font.pixelSize: 22
                        font.bold: true
                        color: ThemeManager.foreground()
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 15

                        Label {
                            text: "Target Extension:"
                            color: ThemeManager.foreground()
                        }

                        StyledComboBox {
                            id: comboSignature
                            editable: true
                            model: [".pdf", ".jpg", ".png", ".txt", ".docx", ".xlsx",
                                    ".pptx", ".mp4", ".mp3", ".zip", ".rar", ".7z",
                                    ".exe", ".gif", ".bmp", ".wav", ".avi"]
                            Layout.preferredWidth: 220
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            id: btnRecover
                            text: "START FILE RECOVERY"
                            font.bold: true
                            background: Rectangle {
                                color: ThemeManager.accent
                                radius: 4
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "#ffffff"
                                font: parent.font
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            onClicked: backend.start_recovery(comboSignature.editText)
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: ThemeManager.surface()
                        border.color: ThemeManager.border()
                        radius: 4

                        ScrollView {
                            anchors.fill: parent
                            anchors.margins: 10
                            clip: true

                            TextArea {
                                id: terminalOutput
                                text: "Ready to scan all mounted physical drives...\nRequires Administrator privileges.\n\nSelect an extension from the list or type any extension (e.g. .mp4, .zip, .docx)."
                                color: ThemeManager.foreground()
                                font.family: "Consolas"
                                font.pixelSize: 13
                                readOnly: true
                                background: null
                            }
                        }
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

        function onCarverLogUpdated(msg) {
            terminalOutput.text += "\n" + msg
            terminalOutput.cursorPosition = terminalOutput.length
        }
    }
}
