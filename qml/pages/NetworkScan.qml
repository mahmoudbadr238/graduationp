import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Item {
    id: root
    anchors.fill: parent
    
    property var scanResults: []
    property bool isScanning: false
    
    Connections {
        target: Backend || null
        enabled: target !== null
        function onScanFinished(results) {
            scanResults = results || []
            isScanning = false
            scanButton.enabled = true
            scanButton.text = "Start Scan"
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        Text {
            text: "Network Scan"
            font.pixelSize: 28
            font.bold: true
            color: ThemeManager.foreground()
        }

        Rectangle {
            Layout.fillWidth: true
            height: 180
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 12

                Text {
                    text: "Scan Configuration"
                    font.pixelSize: 14
                    font.bold: true
                    color: ThemeManager.foreground()
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: "Target"
                            color: ThemeManager.muted()
                            font.pixelSize: 11
                        }

                        TextField {
                            id: targetInput
                            Layout.fillWidth: true
                            placeholderText: "192.168.1.0/24"
                            maximumLength: 256
                            color: ThemeManager.foreground()
                            placeholderTextColor: ThemeManager.muted()
                            validator: RegularExpressionValidator {
                                // Allow IP, hostname, CIDR notation - no shell metacharacters
                                regularExpression: /^[a-zA-Z0-9.\-\/]+$/
                            }
                            background: Rectangle {
                                color: ThemeManager.surface()
                                radius: 6
                                border.color: targetInput.acceptableInput || targetInput.text.length === 0 ? ThemeManager.border() : ThemeManager.danger
                                border.width: 1
                            }
                        }

                        Text {
                            text: "Invalid characters in target"
                            color: ThemeManager.danger
                            font.pixelSize: 10
                            visible: targetInput.text.length > 0 && !targetInput.acceptableInput
                        }
                    }

                    Button {
                        id: scanButton
                        text: isScanning ? "Scanning..." : "Start Scan"
                        Layout.preferredWidth: 140
                        enabled: !isScanning && targetInput.text.length > 0 && targetInput.acceptableInput
                        
                        onClicked: {
                            if (Backend && targetInput.text.length > 0 && targetInput.acceptableInput) {
                                isScanning = true
                                scanButton.enabled = false
                                scanResults = []
                                Backend.runNetworkScan(targetInput.text, false)
                            }
                        }
                        
                        background: Rectangle {
                            color: parent.enabled ? ThemeManager.accent : ThemeManager.muted()
                            radius: 6
                        }

                        contentItem: Text {
                            text: parent.text
                            color: ThemeManager.foreground()
                            font.pixelSize: 12
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 16

                Text {
                    text: "Scan Results (" + scanResults.length + " hosts)"
                    font.pixelSize: 16
                    font.bold: true
                    color: ThemeManager.foreground()
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        width: parent.width
                        spacing: 8

                        Repeater {
                            model: scanResults.length

                            Rectangle {
                                Layout.fillWidth: true
                                height: 50
                                color: ThemeManager.elevated()
                                radius: 6

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 12

                                    Text {
                                        text: (scanResults[index] && scanResults[index].ip) ? scanResults[index].ip : "N/A"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 11
                                        font.bold: true
                                        Layout.preferredWidth: 150
                                    }

                                    Text {
                                        text: (scanResults[index] && scanResults[index].hostname) ? scanResults[index].hostname : "-"
                                        color: ThemeManager.muted()
                                        font.pixelSize: 10
                                        Layout.fillWidth: true
                                    }

                                    Text {
                                        text: (scanResults[index] && scanResults[index].status) ? scanResults[index].status : "up"
                                        color: (scanResults[index] && scanResults[index].status === "up") ? ThemeManager.success : ThemeManager.danger
                                        font.pixelSize: 10
                                        font.bold: true
                                    }

                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }

                        // Empty state
                        Text {
                            visible: scanResults.length === 0 && !isScanning
                            text: "Run a scan to see results"
                            color: ThemeManager.muted()
                            font.pixelSize: 14
                            Layout.alignment: Qt.AlignCenter
                            Layout.topMargin: 50
                        }

                        // Scanning state
                        Text {
                            visible: isScanning
                            text: "Scanning..."
                            color: ThemeManager.accent
                            font.pixelSize: 14
                            Layout.alignment: Qt.AlignCenter
                            Layout.topMargin: 50
                            font.bold: true
                        }
                    }
                }
            }
        }
    }
}