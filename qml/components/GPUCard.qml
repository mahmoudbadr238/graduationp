import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Rectangle {
    id: card
    
    property string gpuName: ""
    property real usagePercent: 0
    property real vramUsed: 0
    property real vramTotal: 0
    property real temperature: 0
    property bool isActive: true

    color: ThemeManager.panel()
    radius: 12
    border.color: ThemeManager.border()
    border.width: 1
    implicitWidth: 400
    implicitHeight: 140

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: card.gpuName
                    color: ThemeManager.foreground()
                    font.pixelSize: 13
                    font.bold: true
                }

                Text {
                    text: card.isActive ? "Active" : "Inactive"
                    color: card.isActive ? ThemeManager.success : ThemeManager.muted()
                    font.pixelSize: 11
                }
            }

            Rectangle {
                width: 12
                height: 12
                radius: 6
                color: card.isActive ? ThemeManager.success : (ThemeManager.muted())
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: 12
            rowSpacing: 8

            Column {
                Text {
                    text: "Usage"
                    color: ThemeManager.muted()
                    font.pixelSize: 10
                }
                Text {
                    text: usagePercent.toFixed(0) + "%"
                    color: ThemeManager.accent
                    font.pixelSize: 14
                    font.bold: true
                }
            }

            Column {
                Text {
                    text: "VRAM"
                    color: ThemeManager.muted()
                    font.pixelSize: 10
                }
                Text {
                    text: vramUsed.toFixed(1) + " / " + vramTotal.toFixed(1) + " GB"
                    color: ThemeManager.accent
                    font.pixelSize: 14
                    font.bold: true
                    elide: Text.ElideRight
                }
            }

            Column {
                Text {
                    text: "Temp"
                    color: ThemeManager.muted()
                    font.pixelSize: 10
                }
                Text {
                    text: temperature > 0 ? temperature.toFixed(0) + "°C" : "N/A"
                    color: temperature > 80 ? ThemeManager.danger :
                           temperature > 60 ? ThemeManager.warning :
                           ThemeManager.success
                    font.pixelSize: 14
                    font.bold: true
                }
            }
        }
    }
}
