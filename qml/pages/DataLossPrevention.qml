import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Item {
    id: root
    anchors.fill: parent
    
    // Sample DLP rules model
    ListModel {
        id: rulesModel
        
        Component.onCompleted: {
            rulesModel.append({ name: "No USB Exports", description: "Block USB device exports", enabled: true })
            rulesModel.append({ name: "Prevent Printing", description: "Disable printing sensitive docs", enabled: true })
            rulesModel.append({ name: "Cloud Upload Block", description: "Block cloud storage uploads", enabled: true })
            rulesModel.append({ name: "Email Encryption", description: "Enforce encrypted emails", enabled: false })
            rulesModel.append({ name: "Screenshot Block", description: "Disable screenshot captures", enabled: true })
            rulesModel.append({ name: "Remote Desktop Block", description: "Block RDP/remote sessions", enabled: true })
            rulesModel.append({ name: "Webcam Block", description: "Disable webcam access", enabled: false })
            rulesModel.append({ name: "Microphone Block", description: "Disable microphone access", enabled: true })
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        Text {
            text: "Data Loss Prevention"
            font.pixelSize: 28
            font.bold: true
            color: ThemeManager.foreground()
        }

        Rectangle {
            Layout.fillWidth: true
            height: 120
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 30

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "DLP Status"
                        font.pixelSize: 12
                        color: ThemeManager.muted()
                    }

                    Text {
                        text: "Active"
                        font.pixelSize: 20
                        font.bold: true
                        color: "#22C55E"
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "Active Rules"
                        font.pixelSize: 12
                        color: ThemeManager.muted()
                    }

                    Text {
                        text: {
                            var count = 0
                            for (var i = 0; i < rulesModel.count; i++) {
                                if (rulesModel.get(i).enabled) count++
                            }
                            return count
                        }
                        font.pixelSize: 20
                        font.bold: true
                        color: ThemeManager.foreground()
                    }

                    Text {
                        text: "0"
                        font.pixelSize: 20
                        font.bold: true
                        color: ThemeManager.foreground()
                    }
                }

                Item { Layout.fillWidth: true }
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
                spacing: 12

                Text {
                    text: "Active Rules"
                    font.pixelSize: 14
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
                            model: rulesModel

                            delegate: Rectangle {
                                Layout.fillWidth: true
                                height: 60
                                color: model.enabled ? ThemeManager.elevated() : ThemeManager.surface()
                                radius: 6
                                border.color: model.enabled ? ThemeManager.border() : ThemeManager.border()
                                border.width: 1
                                opacity: model.enabled ? 1.0 : 0.6

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 12

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2

                                        Text {
                                            text: model.name
                                            color: ThemeManager.foreground()
                                            font.pixelSize: 11
                                            font.bold: true
                                        }

                                        Text {
                                            text: model.description
                                            color: ThemeManager.muted()
                                            font.pixelSize: 9
                                        }
                                    }

                                    Rectangle {
                                        width: 40
                                        height: 24
                                        color: model.enabled ? "#7C3AED" : "#4B5563"
                                        radius: 12

                                        Text {
                                            anchors.centerIn: parent
                                            text: model.enabled ? "ON" : "OFF"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: 9
                                            font.bold: true
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                rulesModel.setProperty(index, "enabled", !model.enabled)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}