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

    FileDialog {
        id: filePicker
        title: "Select file to permanently destroy"
        onAccepted: {
            var s = selectedFile.toString()
                        .replace(/^file:\/\/\//i, "")
                        .replace(/\//g, "\\")
            filePathInput.text = s
        }
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

            // TAB 0: PERMANENT DELETE (SHREDDER)
            Item {
                id: tabDelete

                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(600, parent.width * 0.8)
                    spacing: 20

                    Text {
                        text: "Secure File Shredder"
                        font.pixelSize: 22
                        font.bold: true
                        color: ThemeManager.foreground()
                        Layout.alignment: Qt.AlignHCenter
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        StyledTextField {
                            id: filePathInput
                            placeholderText: "Select a file to permanently destroy..."
                            Layout.fillWidth: true
                        }
                        Button {
                            text: "Browse"
                            onClicked: filePicker.open()
                        }
                    }

                    Button {
                        id: btnShred
                        text: "PERMANENTLY DELETE FILE"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 45
                        font.bold: true
                        background: Rectangle {
                            color: Qt.tint(ThemeManager.surface(), Qt.rgba(0.9, 0.15, 0.15, 0.85))
                            radius: 4
                            border.color: ThemeManager.border()
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font: parent.font
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (filePathInput.text !== "") {
                                backend.start_shredding(filePathInput.text)
                            }
                        }
                    }

                    Text {
                        text: "Warning: Data destruction bypasses the Recycle Bin and cannot be undone."
                        color: Qt.tint(ThemeManager.foreground(), Qt.rgba(0.9, 0.15, 0.15, 0.8))
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }

                    ProgressBar {
                        id: shredProgress
                        Layout.fillWidth: true
                        value: 0.0
                    }
                }
            }

            // TAB 1: FILE RECOVERY (CARVER)
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

        function onShredProgressUpdated(val) {
            shredProgress.value = val / 100.0
        }

        function onCarverLogUpdated(msg) {
            terminalOutput.text += "\n" + msg
            terminalOutput.cursorPosition = terminalOutput.length
        }
    }
}
