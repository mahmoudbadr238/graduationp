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

    // â”€â”€ Shredder state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    property bool isLinux: typeof Backend !== 'undefined' && Backend ? Backend.isLinux : false

    FileDialog {
        id: filePicker
        title: "Select file to permanently destroy"
        onAccepted: {
            var raw = selectedFile.toString()
            var s = ""
            if (root.isLinux) {
                s = raw.replace(/^file:\/\//i, "")
            } else {
                s = raw.replace(/^file:\/\/\//i, "")
                s = s.replace(/\//g, "\\")
            }
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

        // â”€â”€ Tab bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        Rectangle {
            id: tabBarBg
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            color: ThemeManager.panel()
            z: 10
            property int currentIndex: 0
            property var tabModel: [qsTr("File Permanent Delete"), qsTr("File Recovery")]

            Row {
                anchors.fill: parent
                Repeater {
                    model: tabBarBg.tabModel
                    Rectangle {
                        width: tabBarBg.width / tabBarBg.tabModel.length
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
                            width: parent.width; height: 3
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

            // â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            // TAB 0 â€” SECURE FILE SHREDDER
            // â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            Flickable {
                id: shredFlick
                clip: true
                contentWidth: width
                contentHeight: shredColumn.implicitHeight + 40
                flickableDirection: Flickable.VerticalFlick
                boundsBehavior: Flickable.StopAtBounds
                interactive: true
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: shredColumn
                    width: Math.min(680, shredFlick.width - 40)
                    x: (shredFlick.width - width) / 2
                    y: 20
                    spacing: 0

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

                            // â”€â”€ Title â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                            Text {
                                text: "\uD83D\uDD12  Secure File Shredder"
                                font.pixelSize: ThemeManager.fontSize_h2
                                font.bold: true
                                color: ThemeManager.foreground()
                            }

                            // -- Drop zone (drag-and-drop only) --
                            Rectangle {
                                id: dropZoneRect
                                Layout.fillWidth: true
                                Layout.preferredHeight: 100
                                radius: 10
                                color: dropArea.containsDrag
                                       ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.12)
                                       : ThemeManager.elevated()
                                border.color: dropArea.containsDrag ? ThemeManager.accent : ThemeManager.border()
                                border.width: dropArea.containsDrag ? 2 : 1

                                DropArea {
                                    id: dropArea
                                    anchors.fill: parent
                                    keys: ["text/uri-list"]
                                    onEntered: function(drag) {
                                        drag.accept()
                                    }
                                    onDropped: function(drop) {
                                        if (drop.hasUrls && drop.urls.length > 0) {
                                            var raw = drop.urls[0].toString()
                                            var s = ""
                                            if (root.isLinux) {
                                                s = raw.replace(/^file:\/\//i, "")
                                            } else {
                                                s = raw.replace(/^file:\/\/\//i, "")
                                                s = s.replace(/\//g, "\\")
                                            }
                                            s = decodeURIComponent(s)
                                            selectedFilePath = s
                                            shredDone = false
                                        }
                                    }
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: dropArea.containsDrag
                                          ? "\uD83D\uDCE5  Release to select file"
                                          : "\uD83D\uDCC1  Drag and drop a file here"
                                    color: dropArea.containsDrag ? ThemeManager.accent : ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    font.bold: dropArea.containsDrag
                                }
                            }

                            // -- File picker row (outside DropArea) --
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                Rectangle {
                                    Layout.fillWidth: true
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

                                Rectangle {
                                    id: browseBtn
                                    Layout.preferredWidth: 110
                                    Layout.preferredHeight: 36
                                    radius: 8
                                    color: browseMa.containsMouse ? Qt.lighter(ThemeManager.accent, 1.15) : ThemeManager.accent
                                    Behavior on color { ColorAnimation { duration: 120 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "\uD83D\uDCC2  Browse"
                                        color: "#ffffff"
                                        font.pixelSize: ThemeManager.fontSize_body
                                        font.bold: true
                                    }

                                    MouseArea {
                                        id: browseMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            filePicker.open()
                                        }
                                    }
                                }
                            }

                            // â”€â”€ Selected file info â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

                            // â”€â”€ Options â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

                                Text { text: "Overwrite passes:"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body }
                                StyledComboBox { id: comboPasses; model: ["1", "3", "7"]; currentIndex: 1; Layout.preferredWidth: 80 }

                                Text { text: "Verify after delete:"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body }
                                StyledSwitch { id: toggleVerify; checked: true }

                                Text { text: "Rename before delete:"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body }
                                StyledSwitch { id: toggleRename; checked: true }

                                Text { text: "Write log file:"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body }
                                StyledSwitch { id: toggleLog; checked: true }
                            }

                            // â”€â”€ Separator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: ThemeManager.border() }

                            // â”€â”€ Confirmation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                            Text {
                                text: "Confirmation"
                                font.pixelSize: ThemeManager.fontSize_body
                                font.bold: true
                                color: ThemeManager.danger
                            }

                            RowLayout {
                                spacing: 12
                                StyledCheckBox {
                                    id: confirmCheck
                                    text: "I understand this action is irreversible"
                                    enabled: !shredRunning && !shredDone
                                    Layout.fillWidth: true
                                    Layout.alignment: Qt.AlignVCenter
                                }
                            }

                            RowLayout {
                                spacing: 8
                                Text { text: "Type DELETE to confirm:"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body }
                                StyledTextField {
                                    id: confirmInput
                                    Layout.preferredWidth: 140
                                    enabled: !shredRunning && !shredDone
                                    placeholderText: "DELETE"
                                }
                            }

                            // â”€â”€ Action button â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                                                        Rectangle {
                                id: btnShred
                                property bool isEnabled: selectedFilePath !== "" && confirmInput.text === "DELETE" && !shredRunning && !shredDone
                                Layout.fillWidth: true
                                Layout.preferredHeight: 48
                                radius: 10
                                color: btnShred.isEnabled ? ThemeManager.danger : ThemeManager.muted()
                                opacity: btnShred.isEnabled ? 1 : 0.5
                                Behavior on color { ColorAnimation { duration: 150 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: "\uD83D\uDDD1  PERMANENTLY DESTROY FILE"
                                    color: "#ffffff"
                                    font.pixelSize: ThemeManager.fontSize_body
                                    font.bold: true
                                }

                                MouseArea {
                                    id: shredMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: btnShred.isEnabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    onClicked: {
                                        if (!btnShred.isEnabled) return
                                        shredRunning = true
                                        shredDone = false
                                        shredPercent = 0
                                        shredPhase = "starting"
                                        var passes = parseInt(comboPasses.currentText)
                                        backend.startSecureDelete(selectedFilePath, passes, toggleRename.checked, toggleVerify.checked, toggleLog.checked)
                                    }
                                }
                            }

                            // â”€â”€ Progress â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                visible: shredRunning

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: {
                                            if (shredPhase === "rename") return "Renaming file\u2026"
                                            if (shredPhase === "overwrite")
                                                return "Overwriting \u2014 pass " + shredPassIdx + "/" + shredTotalPasses + "  (" + Math.round(shredPercent) + "%)"
                                            if (shredPhase === "delete") return "Deleting file\u2026"
                                            if (shredPhase === "verify") return "Verifying deletion\u2026"
                                            return "Preparing\u2026"
                                        }
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    Item { Layout.fillWidth: true }
                                                                            Rectangle {
                                            Layout.preferredWidth: 80
                                            Layout.preferredHeight: 30
                                            radius: 6
                                            color: shredCancelMa.containsMouse ? Qt.lighter(ThemeManager.elevated(), 1.2) : ThemeManager.elevated()
                                            border.color: ThemeManager.border()

                                            Text {
                                                anchors.centerIn: parent
                                                text: "Cancel"
                                                color: ThemeManager.foreground()
                                                font.pixelSize: ThemeManager.fontSize_small
                                            }

                                            MouseArea {
                                                id: shredCancelMa
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: backend.cancelSecureDelete()
                                            }
                                        }
                                }

                                ProgressBar {
                                    id: shredProgressBar
                                    Layout.fillWidth: true
                                    from: 0; to: 1
                                    value: shredTotalPasses <= 0 ? 0 : (shredPassIdx - 1) / shredTotalPasses + (shredPercent / 100) / shredTotalPasses
                                    Behavior on value { NumberAnimation { duration: 200 } }
                                    background: Rectangle { implicitHeight: 14; radius: 7; color: ThemeManager.elevated() }
                                    contentItem: Item {
                                        implicitHeight: 14
                                        Rectangle {
                                            width: shredProgressBar.visualPosition * parent.width
                                            height: parent.height; radius: 7; color: ThemeManager.danger
                                            Behavior on width { NumberAnimation { duration: 200 } }
                                        }
                                    }
                                }
                            }

                            // â”€â”€ Result: SUCCESS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                            Rectangle {
                                visible: shredDone && shredSuccess
                                Layout.fillWidth: true
                                Layout.preferredHeight: successCol.implicitHeight + 24
                                radius: 10
                                color: Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.10)
                                border.color: ThemeManager.success

                                ColumnLayout {
                                    id: successCol
                                    anchors.fill: parent; anchors.margins: 12; spacing: 6
                                    Text { text: "\u2705  " + shredMessage; color: ThemeManager.success; font.pixelSize: ThemeManager.fontSize_body; font.bold: true; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                    Text { visible: shredLogPath !== ""; text: "Log: " + shredLogPath; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                }
                            }

                            // â”€â”€ Result: FAILURE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                            Rectangle {
                                visible: shredDone && !shredSuccess
                                Layout.fillWidth: true
                                Layout.preferredHeight: failCol.implicitHeight + 24
                                radius: 10
                                color: Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.10)
                                border.color: ThemeManager.danger

                                ColumnLayout {
                                    id: failCol
                                    anchors.fill: parent; anchors.margins: 12; spacing: 6
                                    Text { text: "\u274C  " + shredMessage; color: ThemeManager.danger; font.pixelSize: ThemeManager.fontSize_body; font.bold: true; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                }
                            }

                            // â”€â”€ Reset button â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                                                        Rectangle {
                                visible: shredDone
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredWidth: 160
                                Layout.preferredHeight: 36
                                radius: 8
                                color: resetMa.containsMouse ? Qt.lighter(ThemeManager.elevated(), 1.2) : ThemeManager.elevated()
                                border.color: ThemeManager.border()

                                Text {
                                    anchors.centerIn: parent
                                    text: "Shred Another File"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                }

                                MouseArea {
                                    id: resetMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: _resetShredder()
                                }
                            }

                            // â”€â”€ SSD disclaimer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                            Text {
                                Layout.fillWidth: true
                                text: "Note: On SSDs with wear-levelling, overwritten data may persist in remapped sectors. For maximum assurance use full-disk encryption."
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

            // â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            // TAB 1 â€” FILE RECOVERY
            // â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            Item {
                id: tabRecovery

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
                property var driveList: ["All Drives"]

                ListModel { id: candidateModel }

                function resetRecovery() {
                    scanning = false; scanDone = false; scanPercent = 0; scanStage = ""; scanDrive = ""
                    scanFoundCount = 0; scanSpeedMbps = 0; candidateModel.clear()
                    selectedIds = ({}); selectedCount = 0; recovering = false; recoverDone = false
                    recoverPercent = 0; recoverDoneCount = 0; recoverTotal = 0
                    outputDir = ""; recoveredPaths = []; errorMsg = ""
                }
                function toggleCandidate(cid) {
                    var s = selectedIds; if (s[cid]) { delete s[cid] } else { s[cid] = true }
                    selectedIds = s; selectedCount = Object.keys(s).length
                }
                function selectAll() {
                    var s = {}; for (var i = 0; i < candidateModel.count; i++) s[candidateModel.get(i).cid] = true
                    selectedIds = s; selectedCount = Object.keys(s).length
                }
                function selectNone() { selectedIds = ({}); selectedCount = 0 }
                function _formatSize(bytes) {
                    if (bytes > 1048576) return (bytes / 1048576).toFixed(1) + " MB"
                    if (bytes > 1024) return (bytes / 1024).toFixed(1) + " KB"
                    return bytes + " B"
                }
                function _typeBadgeColor(t) {
                    if (t === "pdf") return "#E74C3C"; if (t === "jpg") return "#F39C12"
                    if (t === "png") return "#27AE60"; if (t === "mp4") return "#9B59B6"
                    if (t === "zip" || t === "docx") return "#3498DB"; return ThemeManager.accent
                }
                function _confidenceColor(c) {
                    if (c >= 70) return ThemeManager.success; if (c >= 40) return ThemeManager.warning; return ThemeManager.danger
                }

                Component.onCompleted: {
                    if (typeof RecoveryService !== 'undefined' && RecoveryService !== null) {
                        tabRecovery.isAdmin = RecoveryService.checkAdmin()
                        var drivesJson = RecoveryService.getAvailableDrives()
                        var drives = JSON.parse(drivesJson)
                        var model = ["All Drives"]
                        for (var i = 0; i < drives.length; i++) model.push(drives[i])
                        tabRecovery.driveList = model
                    } else {
                        tabRecovery.errorMsg = "File Recovery requires the Windows Agent. This feature is not available on Linux."
                    }
                }

                Flickable {
                    id: recoveryFlick
                    anchors.fill: parent
                    clip: true
                    contentWidth: width
                    contentHeight: recoveryCol.implicitHeight + 48
                    flickableDirection: Flickable.VerticalFlick
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: true
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    ColumnLayout {
                        id: recoveryCol
                        width: Math.min(860, recoveryFlick.width - 48)
                        x: (recoveryFlick.width - width) / 2
                        y: 24
                        spacing: 16

                        Text {
                            text: "\uD83D\uDD0D  System-Wide File Recovery"
                            font.pixelSize: ThemeManager.fontSize_h2; font.bold: true; color: ThemeManager.foreground()
                        }
                        Text {
                            text: "Scan raw disk sectors for deleted file signatures. Files appear in real-time as they are found \u2014 select which to recover."
                            color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; wrapMode: Text.Wrap; Layout.fillWidth: true
                        }

                        // â”€â”€ Admin warning â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            visible: !tabRecovery.isAdmin
                            Layout.fillWidth: true
                            Layout.preferredHeight: adminWarnCol.implicitHeight + 20
                            radius: 10
                            color: Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.20)
                            border.color: ThemeManager.warning

                            ColumnLayout {
                                id: adminWarnCol
                                anchors.fill: parent; anchors.margins: 12
                                Text { text: root.isLinux ? "\u26A0  Not running as Root" : "\u26A0  Not running as Administrator"; color: ThemeManager.warning; font.bold: true; font.pixelSize: ThemeManager.fontSize_body }
                                Text { text: root.isLinux ? "Raw disk scanning requires root privileges. Sentinel is using bundled recovery sample data in this session." : "Raw disk scanning requires administrator privileges. Sentinel is using bundled recovery sample data in this session."; color: ThemeManager.warning; font.pixelSize: ThemeManager.fontSize_small; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            }
                        }

                        // â”€â”€ Error banner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            visible: tabRecovery.errorMsg !== ""
                            Layout.fillWidth: true
                            Layout.preferredHeight: errText.implicitHeight + 24
                            radius: 10
                            color: Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.20)
                            border.color: ThemeManager.danger
                            Text { id: errText; anchors.fill: parent; anchors.margins: 12; text: "\u274C  " + tabRecovery.errorMsg; color: ThemeManager.danger; font.pixelSize: ThemeManager.fontSize_body; wrapMode: Text.Wrap }
                        }

                        // â”€â”€ Controls panel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: controlsRow.implicitHeight + 28
                            radius: 10; color: ThemeManager.panel(); border.color: ThemeManager.border()

                            RowLayout {
                                id: controlsRow
                                anchors.left: parent.left; anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.margins: 14; spacing: 14

                                Text { text: "File Type:"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.bold: true; verticalAlignment: Text.AlignVCenter }
                                StyledComboBox { id: recoveryTypeCombo; model: ["any","pdf","jpg","png","mp4","zip","docx"]; Layout.preferredWidth: 120 }
                                Item { Layout.preferredWidth: 8 }
                                Text { text: "Drive:"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.bold: true; verticalAlignment: Text.AlignVCenter }
                                StyledComboBox { id: recoveryDriveCombo; model: tabRecovery.driveList; Layout.preferredWidth: 130 }
                                Item { Layout.preferredWidth: 8 }

                                Rectangle {
                                    id: btnScan
                                    property bool isEnabled: !tabRecovery.scanning && !tabRecovery.recovering
                                    Layout.preferredWidth: 150
                                    Layout.preferredHeight: 40
                                    radius: 8
                                    color: btnScan.isEnabled
                                           ? (scanMa.containsMouse ? Qt.lighter(ThemeManager.accent, 1.15) : ThemeManager.accent)
                                           : ThemeManager.elevated()
                                    Behavior on color { ColorAnimation { duration: 150 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: tabRecovery.scanning ? "\u23F3  Scanning\u2026" : "\uD83D\uDD0E  Start Scan"
                                        color: btnScan.isEnabled ? "#ffffff" : ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_body
                                        font.bold: true
                                    }

                                    MouseArea {
                                        id: scanMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: btnScan.isEnabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: {
                                            if (!btnScan.isEnabled) return
                                            if (typeof RecoveryService === 'undefined' || RecoveryService === null) {
                                                tabRecovery.errorMsg = "Recovery service unavailable. Restart the application."
                                                return
                                            }
                                            tabRecovery.resetRecovery()
                                            tabRecovery.scanning = true; tabRecovery.errorMsg = ""
                                            var drv = recoveryDriveCombo.currentText === "All Drives" ? "" : recoveryDriveCombo.currentText
                                            RecoveryService.startRecoveryScan(recoveryTypeCombo.currentText, drv)
                                        }
                                    }
                                }

                                Rectangle {
                                    visible: tabRecovery.scanning
                                    Layout.preferredWidth: 100
                                    Layout.preferredHeight: 40
                                    radius: 8
                                    color: cancelMa.containsMouse ? Qt.lighter(ThemeManager.elevated(), 1.2) : ThemeManager.elevated()
                                    border.color: ThemeManager.danger

                                    Text {
                                        anchors.centerIn: parent
                                        text: "\u2716  Cancel"
                                        color: ThemeManager.danger
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }

                                    MouseArea {
                                        id: cancelMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof RecoveryService !== 'undefined' && RecoveryService !== null)
                                                RecoveryService.cancelRecoveryScan()
                                        }
                                    }
                                }

                                Item { Layout.fillWidth: true }
                            }
                        }

                        // â”€â”€ Scan progress â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            visible: tabRecovery.scanning
                            Layout.fillWidth: true
                            Layout.preferredHeight: progressCol.implicitHeight + 28
                            radius: 10; color: ThemeManager.panel(); border.color: ThemeManager.border()

                            ColumnLayout {
                                id: progressCol
                                anchors.fill: parent; anchors.margins: 14; spacing: 10

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 8
                                    Text { text: tabRecovery.scanStage || "Preparing scan\u2026"; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.bold: true; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                    Text { text: tabRecovery.scanPercent + "% complete"; color: ThemeManager.accent; font.bold: true; font.pixelSize: ThemeManager.fontSize_body }
                                }

                                ProgressBar {
                                    id: scanProgressBar
                                    Layout.fillWidth: true; from: 0; to: 100; value: tabRecovery.scanPercent
                                    Behavior on value { NumberAnimation { duration: 200 } }
                                    background: Rectangle { implicitHeight: 14; radius: 7; color: ThemeManager.elevated() }
                                    contentItem: Item {
                                        implicitHeight: 14
                                        Rectangle { width: scanProgressBar.visualPosition * parent.width; height: parent.height; radius: 7; color: ThemeManager.accent; Behavior on width { NumberAnimation { duration: 200 } } }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 24
                                    Row {
                                        spacing: 6
                                        Rectangle { width: 8; height: 8; radius: 4; color: ThemeManager.accent; anchors.verticalCenter: parent.verticalCenter }
                                        Text { text: "Drive: " + (tabRecovery.scanDrive || "\u2014"); color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small }
                                    }
                                    Row {
                                        spacing: 6
                                        Rectangle { width: 8; height: 8; radius: 4; color: ThemeManager.success; anchors.verticalCenter: parent.verticalCenter }
                                        Text { text: tabRecovery.scanFoundCount + " files found"; color: ThemeManager.success; font.pixelSize: ThemeManager.fontSize_small; font.bold: true }
                                    }
                                    Row {
                                        visible: tabRecovery.scanSpeedMbps > 0; spacing: 6
                                        Text { text: "\u26A1"; font.pixelSize: ThemeManager.fontSize_small }
                                        Text { text: tabRecovery.scanSpeedMbps.toFixed(1) + " MB/s"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small }
                                    }
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }

                        // â”€â”€ Results section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            visible: candidateModel.count > 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: resultsCol.implicitHeight + 28
                            radius: 10; color: ThemeManager.panel(); border.color: ThemeManager.border()

                            ColumnLayout {
                                id: resultsCol
                                anchors.fill: parent; anchors.margins: 14; spacing: 12

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 10
                                    Text { text: "\uD83D\uDCC1  " + candidateModel.count + " Candidates Found"; font.pixelSize: ThemeManager.fontSize_h3; font.bold: true; color: ThemeManager.foreground() }
                                    Rectangle {
                                        visible: tabRecovery.scanning; width: 10; height: 10; radius: 5; color: ThemeManager.accent
                                        SequentialAnimation on opacity {
                                            loops: Animation.Infinite
                                            NumberAnimation { to: 0.3; duration: 600 }
                                            NumberAnimation { to: 1.0; duration: 600 }
                                        }
                                    }
                                    Text { visible: tabRecovery.scanning; text: "scanning\u2026"; color: ThemeManager.accent; font.pixelSize: ThemeManager.fontSize_small; font.italic: true }
                                    Item { Layout.fillWidth: true }

                                                                        Rectangle {
                                        id: btnSelectAll
                                        Layout.preferredWidth: 100
                                        Layout.preferredHeight: 32
                                        radius: 6
                                        color: selAllMa.containsMouse ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.15) : ThemeManager.elevated()
                                        border.color: ThemeManager.accent
                                        border.width: 1

                                        Text {
                                            anchors.centerIn: parent
                                            text: "\u2611  Select All"
                                            color: ThemeManager.accent
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.bold: true
                                        }

                                        MouseArea {
                                            id: selAllMa
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: tabRecovery.selectAll()
                                        }
                                    }
                                                                        Rectangle {
                                        id: btnUnselectAll
                                        Layout.preferredWidth: 110
                                        Layout.preferredHeight: 32
                                        radius: 6
                                        color: unselAllMa.containsMouse ? Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.12) : ThemeManager.elevated()
                                        border.color: ThemeManager.border()

                                        Text {
                                            anchors.centerIn: parent
                                            text: "\u2610  Unselect All"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.bold: true
                                        }

                                        MouseArea {
                                            id: unselAllMa
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: tabRecovery.selectNone()
                                        }
                                    }
                                }

                                Text { visible: tabRecovery.selectedCount > 0; text: tabRecovery.selectedCount + " of " + candidateModel.count + " files selected for recovery"; color: ThemeManager.accent; font.pixelSize: ThemeManager.fontSize_small; font.bold: true }

                                // Column headers
                                Rectangle {
                                    Layout.fillWidth: true; Layout.preferredHeight: 34; color: ThemeManager.elevated(); radius: 6
                                    RowLayout {
                                        anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 6
                                        Text { text: ""; Layout.preferredWidth: 30 }
                                        Text { text: "Type"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; font.bold: true; Layout.preferredWidth: 58 }
                                        Text { text: "Size"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; font.bold: true; Layout.preferredWidth: 78 }
                                        Text { text: "Confidence"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; font.bold: true; Layout.preferredWidth: 82 }
                                        Text { text: "Drive"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; font.bold: true; Layout.preferredWidth: 60 }
                                        Text { text: "Offset"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; font.bold: true; Layout.preferredWidth: 95 }
                                        Text { text: "Preview"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; font.bold: true; Layout.fillWidth: true }
                                    }
                                }

                                // Candidate list
                                ListView {
                                    id: candidateListView
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Math.min(candidateModel.count * 44, 480)
                                    model: candidateModel; clip: true; spacing: 2
                                    boundsBehavior: Flickable.StopAtBounds; cacheBuffer: 600
                                    ScrollBar.vertical: ScrollBar { policy: candidateModel.count > 10 ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded }

                                    delegate: Rectangle {
                                        id: candidateDelegate
                                        width: candidateListView.width; height: 42; radius: 6
                                        // Read selectedCount to force QML to re-evaluate when selections change
                                        property bool isSelected: { var _dep = tabRecovery.selectedCount; return tabRecovery.selectedIds[model.cid] === true }
                                        color: isSelected ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.15) : (model.index % 2 === 0 ? "transparent" : Qt.rgba(1,1,1,0.02))
                                        border.color: isSelected ? ThemeManager.accent : "transparent"
                                        border.width: isSelected ? 1.5 : 0

                                        // Left accent bar for selected items
                                        Rectangle {
                                            visible: candidateDelegate.isSelected
                                            width: 3; height: parent.height - 4; radius: 2
                                            anchors.left: parent.left; anchors.leftMargin: 2
                                            anchors.verticalCenter: parent.verticalCenter
                                            color: ThemeManager.accent
                                        }

                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: tabRecovery.toggleCandidate(model.cid) }

                                        RowLayout {
                                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 6

                                            // Styled checkbox
                                            Rectangle {
                                                Layout.preferredWidth: 22; Layout.preferredHeight: 22; radius: 4
                                                color: candidateDelegate.isSelected ? ThemeManager.accent : "transparent"
                                                border.color: candidateDelegate.isSelected ? ThemeManager.accent : ThemeManager.muted()
                                                border.width: 2
                                                Layout.alignment: Qt.AlignVCenter

                                                Text {
                                                    anchors.centerIn: parent; text: "✓"
                                                    color: "#ffffff"; font.pixelSize: 14; font.bold: true
                                                    visible: candidateDelegate.isSelected
                                                }

                                                MouseArea {
                                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                    onClicked: tabRecovery.toggleCandidate(model.cid)
                                                }

                                                Behavior on color { ColorAnimation { duration: 150 } }
                                                Behavior on border.color { ColorAnimation { duration: 150 } }
                                            }

                                            Item { Layout.preferredWidth: 4 }

                                            Rectangle { Layout.preferredWidth: 52; Layout.preferredHeight: 24; radius: 4; color: tabRecovery._typeBadgeColor(model.ctype); Text { anchors.centerIn: parent; text: model.ctype.toUpperCase(); color: "#ffffff"; font.pixelSize: ThemeManager.fontSize_caption; font.bold: true } }
                                            Text { text: tabRecovery._formatSize(model.sizeGuess); color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 78 }
                                            Text { text: model.confidence + "%"; color: tabRecovery._confidenceColor(model.confidence); font.bold: true; font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 82 }
                                            Text { text: model.drive; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 60 }
                                            Text { text: model.offsetHex; color: ThemeManager.muted(); font.family: "Consolas"; font.pixelSize: ThemeManager.fontSize_small; Layout.preferredWidth: 95 }
                                            Text { text: model.preview || "\u2014"; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; elide: Text.ElideRight; Layout.fillWidth: true }
                                        }
                                    }
                                }

                                // Action buttons
                                RowLayout {
                                    Layout.fillWidth: true; Layout.topMargin: 4; spacing: 12

                                    Rectangle {
                                        id: btnRecoverSelected
                                        property bool isEnabled: tabRecovery.selectedCount > 0 && !tabRecovery.recovering && !tabRecovery.scanning
                                        Layout.preferredWidth: 240
                                        Layout.preferredHeight: 42
                                        radius: 8
                                        color: btnRecoverSelected.isEnabled
                                               ? (recoverMa.containsMouse ? Qt.lighter(ThemeManager.success, 1.15) : ThemeManager.success)
                                               : ThemeManager.elevated()
                                        Behavior on color { ColorAnimation { duration: 150 } }

                                        Text {
                                            anchors.centerIn: parent
                                            text: "\uD83D\uDCBE  Recover Selected (" + tabRecovery.selectedCount + ")"
                                            color: btnRecoverSelected.isEnabled ? "#ffffff" : ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_body
                                            font.bold: true
                                        }

                                        MouseArea {
                                            id: recoverMa
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: btnRecoverSelected.isEnabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: {
                                                if (!btnRecoverSelected.isEnabled) return
                                                if (typeof RecoveryService === 'undefined' || RecoveryService === null) {
                                                    tabRecovery.errorMsg = "File Recovery requires the Windows Agent."
                                                    return
                                                }
                                                var ids = Object.keys(tabRecovery.selectedIds).map(function(k) { return parseInt(k) })
                                                tabRecovery.recovering = true
                                                tabRecovery.recoverTotal = ids.length
                                                RecoveryService.recoverSelected(JSON.stringify(ids))
                                            }
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Rectangle {
                                        Layout.preferredWidth: 120
                                        Layout.preferredHeight: 42
                                        radius: 8
                                        color: newScanMa.containsMouse ? Qt.lighter(ThemeManager.elevated(), 1.2) : ThemeManager.elevated()
                                        border.color: ThemeManager.border()
                                        opacity: tabRecovery.scanning ? 0.5 : 1.0

                                        Text {
                                            anchors.centerIn: parent
                                            text: "\uD83D\uDD04  New Scan"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_body
                                        }

                                        MouseArea {
                                            id: newScanMa
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            enabled: !tabRecovery.scanning
                                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: tabRecovery.resetRecovery()
                                        }
                                    }
                                }
                            }
                        }

                        // â”€â”€ Empty state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            visible: !tabRecovery.scanning && !tabRecovery.scanDone && candidateModel.count === 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: emptyStateCol.implicitHeight + 48
                            radius: 10; color: ThemeManager.panel(); border.color: ThemeManager.border()

                            ColumnLayout {
                                id: emptyStateCol; anchors.centerIn: parent; spacing: 12
                                Text { text: "\uD83D\uDCC2"; font.pixelSize: 40; Layout.alignment: Qt.AlignHCenter }
                                Text { text: "Ready to Scan"; font.pixelSize: ThemeManager.fontSize_h3; font.bold: true; color: ThemeManager.foreground(); Layout.alignment: Qt.AlignHCenter }
                                Text { text: "Select a file type above and click Start Scan to search for\ndeleted files on your disk. Recovered candidates will appear here."; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; Layout.alignment: Qt.AlignHCenter; Layout.maximumWidth: 480 }
                            }
                        }

                        // â”€â”€ No candidates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            visible: tabRecovery.scanDone && candidateModel.count === 0
                            Layout.fillWidth: true; Layout.preferredHeight: 90; radius: 10; color: ThemeManager.panel(); border.color: ThemeManager.border()
                            Text { anchors.centerIn: parent; text: "No file signatures found. Try a different file type or scan as Administrator on a drive with deleted files."; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_body; wrapMode: Text.Wrap; width: parent.width - 40; horizontalAlignment: Text.AlignHCenter }
                        }

                        // â”€â”€ Recovery progress â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            visible: tabRecovery.recovering
                            Layout.fillWidth: true
                            Layout.preferredHeight: recoverProgCol.implicitHeight + 28
                            radius: 10; color: ThemeManager.panel(); border.color: ThemeManager.success

                            ColumnLayout {
                                id: recoverProgCol; anchors.fill: parent; anchors.margins: 14; spacing: 10
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: "\uD83D\uDCBE  Recovering files: " + tabRecovery.recoverDoneCount + " / " + tabRecovery.recoverTotal; color: ThemeManager.foreground(); font.pixelSize: ThemeManager.fontSize_body; font.bold: true }
                                    Item { Layout.fillWidth: true }
                                    Text { text: tabRecovery.recoverPercent + "%"; color: ThemeManager.success; font.bold: true; font.pixelSize: ThemeManager.fontSize_body }
                                }
                                ProgressBar {
                                    id: recoverProgressBar; Layout.fillWidth: true; from: 0; to: 100; value: tabRecovery.recoverPercent
                                    Behavior on value { NumberAnimation { duration: 200 } }
                                    background: Rectangle { implicitHeight: 14; radius: 7; color: ThemeManager.elevated() }
                                    contentItem: Item { implicitHeight: 14; Rectangle { width: recoverProgressBar.visualPosition * parent.width; height: parent.height; radius: 7; color: ThemeManager.success; Behavior on width { NumberAnimation { duration: 200 } } } }
                                }
                            }
                        }

                        // â”€â”€ Recovery complete â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        Rectangle {
                            visible: tabRecovery.recoverDone
                            Layout.fillWidth: true
                            Layout.preferredHeight: doneCol.implicitHeight + 28
                            radius: 10
                            color: Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.10)
                            border.color: ThemeManager.success

                            ColumnLayout {
                                id: doneCol; anchors.fill: parent; anchors.margins: 14; spacing: 10
                                Text { text: "\u2705  Recovery Complete \u2014 " + tabRecovery.recoveredPaths.length + " files recovered"; color: ThemeManager.success; font.pixelSize: ThemeManager.fontSize_body; font.bold: true }
                                RowLayout {
                                    spacing: 12
                                    Text { text: "Output: " + tabRecovery.outputDir; color: ThemeManager.muted(); font.pixelSize: ThemeManager.fontSize_small; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                    Rectangle {
                                        Layout.preferredWidth: 120
                                        Layout.preferredHeight: 32
                                        radius: 6
                                        color: openFolderMa.containsMouse ? Qt.lighter(ThemeManager.elevated(), 1.2) : ThemeManager.elevated()
                                        border.color: ThemeManager.border()

                                        Text {
                                            anchors.centerIn: parent
                                            text: "\uD83D\uDCC2  Open Folder"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_small
                                        }

                                        MouseArea {
                                            id: openFolderMa
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: { if (typeof RecoveryService !== 'undefined' && RecoveryService !== null) RecoveryService.openRecoveryFolder(tabRecovery.outputDir) }
                                        }
                                    }
                                }
                            }
                        }

                        Item { Layout.preferredHeight: 16 }
                    }
                }

                // â”€â”€ Recovery service connections â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                Connections {
                    target: (typeof RecoveryService !== 'undefined' && RecoveryService !== null) ? RecoveryService : null
                    enabled: (typeof RecoveryService !== 'undefined' && RecoveryService !== null)

                    function onRecoveryScanProgressChanged(jsonStr) {
                        var d = JSON.parse(jsonStr)
                        tabRecovery.scanPercent = d.percent; tabRecovery.scanStage = d.stage
                        tabRecovery.scanDrive = d.drive; tabRecovery.scanFoundCount = d.found_count
                        if (d.speed_mbps !== undefined) tabRecovery.scanSpeedMbps = d.speed_mbps
                    }
                    function onRecoveryScanCandidateFound(jsonStr) {
                        var c = JSON.parse(jsonStr)
                        candidateModel.append({ cid: c.id, ctype: c.type, sizeGuess: c.size_guess, confidence: c.confidence, drive: c.drive, offsetHex: c.offset_hex || "0x0", preview: c.preview_text || "" })
                    }
                    function onRecoveryScanCandidateBatch(jsonStr) {
                        var arr = JSON.parse(jsonStr)
                        for (var i = 0; i < arr.length; i++) {
                            var c = arr[i]
                            candidateModel.append({ cid: c.id, ctype: c.type, sizeGuess: c.size_guess, confidence: c.confidence, drive: c.drive, offsetHex: c.offset_hex || "0x0", preview: c.preview_text || "" })
                        }
                    }
                    function onRecoveryScanFinished(jsonStr) {
                        var d = JSON.parse(jsonStr); tabRecovery.scanning = false; tabRecovery.scanDone = true; tabRecovery.outputDir = d.output_dir
                    }
                    function onRecoveryScanError(msg) {
                        tabRecovery.errorMsg = msg; tabRecovery.scanning = false; tabRecovery.scanDone = true
                    }
                    function onRecoveryRecoverProgressChanged(jsonStr) {
                        var d = JSON.parse(jsonStr); tabRecovery.recoverPercent = d.percent; tabRecovery.recoverDoneCount = d.done
                    }
                    function onRecoveryRecoverFinished(jsonStr) {
                        var d = JSON.parse(jsonStr); tabRecovery.recovering = false; tabRecovery.recoverDone = true
                        tabRecovery.recoveredPaths = d.recovered_paths; tabRecovery.outputDir = d.output_dir
                    }
                    function onRecoveryRecoverError(msg) { tabRecovery.recovering = false; tabRecovery.errorMsg = msg }
                }
            }
        }
    }

    // â”€â”€ Shredder backend connections â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    Connections {
        target: backend
        function onShredderProgressChanged(jsonStr) {
            var d = JSON.parse(jsonStr); shredPhase = d.phase; shredPercent = d.percent; shredPassIdx = d.pass_idx; shredTotalPasses = d.total_passes
        }
        function onShredderFinished(jsonStr) {
            var d = JSON.parse(jsonStr); shredRunning = false; shredDone = true; shredSuccess = true
            shredMessage = d.message || "File securely destroyed."; shredLogPath = d.log_path || ""
        }
        function onShredderFailed(jsonStr) {
            var d = JSON.parse(jsonStr); shredRunning = false; shredDone = true; shredSuccess = false
            shredMessage = d.message || "Shredding failed."; shredLogPath = ""
        }
        function onFileDropped(path) {
            if (tabBar.currentIndex === 0) {
                selectedFilePath = path
                shredDone = false
            }
        }
    }
}
