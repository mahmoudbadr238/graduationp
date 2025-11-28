import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Item {
    id: root
    anchors.fill: parent

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        Text {
            text: "Scan History"
            font.pixelSize: 28
            font.bold: true
            color: ThemeManager.foreground()
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

                Rectangle {
                    Layout.fillWidth: true
                    height: 50
                    color: ThemeManager.surface()
                    radius: 6
                    border.color: ThemeManager.border()
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 20

                        Text {
                            text: "Date"
                            font.pixelSize: 12
                            font.bold: true
                            color: ThemeManager.foreground()
                            Layout.preferredWidth: parent.width * 0.25
                        }

                        Text {
                            text: "Type"
                            font.pixelSize: 12
                            font.bold: true
                            color: ThemeManager.foreground()
                            Layout.preferredWidth: parent.width * 0.25
                        }

                        Text {
                            text: "Findings"
                            font.pixelSize: 12
                            font.bold: true
                            color: ThemeManager.foreground()
                            Layout.preferredWidth: parent.width * 0.25
                        }

                        Text {
                            text: "Type"
                            font.pixelSize: 12
                            font.bold: true
                            color: ThemeManager.foreground()
                            Layout.preferredWidth: parent.width * 0.25
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "transparent"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.topMargin: 20
                        spacing: 12

                        Text {
                            text: "No scans yet"
                            font.pixelSize: 14
                            color: ThemeManager.muted()
                            horizontalAlignment: Text.AlignHCenter
                            Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
                        }

                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }
}

