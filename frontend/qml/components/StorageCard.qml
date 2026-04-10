import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Rectangle {
    id: card
    
    property string driveName: ""
    property string driveLetter: ""
    property real total: 0
    property real used: 0
    property real percent: 0

    color: ThemeManager.panel()
    radius: 12
    border.color: ThemeManager.border()
    border.width: 1
    implicitWidth: 400
    implicitHeight: 120

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: driveName + " (" + driveLetter + ":)"
                    color: ThemeManager.foreground()
                    font.pixelSize: ThemeManager.fontSize_small
                    font.bold: true
                }

                Text {
                    text: used.toFixed(1) + " GB / " + total.toFixed(1) + " GB"
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_small
                }
            }

            Text {
                text: percent.toFixed(0) + "%"
                color: percent > 80 ? ThemeManager.danger :
                       percent > 60 ? ThemeManager.warning :
                       ThemeManager.success
                font.pixelSize: ThemeManager.fontSize_h4
                font.bold: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 8
            color: ThemeManager.elevated()
            radius: 4

            Rectangle {
                height: parent.height
                width: parent.width * (card.percent / 100)
                color: card.percent > 80 ? ThemeManager.danger :
                       card.percent > 60 ? ThemeManager.warning :
                       ThemeManager.success
                radius: 4
            }
        }
    }
}
