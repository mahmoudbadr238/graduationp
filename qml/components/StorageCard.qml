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

    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
    radius: 12
    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
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
                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                    font.pixelSize: 13
                    font.bold: true
                }

                Text {
                    text: used.toFixed(1) + " GB / " + total.toFixed(1) + " GB"
                    color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                    font.pixelSize: 11
                }
            }

            Text {
                text: percent.toFixed(0) + "%"
                color: percent > 80 ? ThemeManager.danger :
                       percent > 60 ? ThemeManager.warning :
                       ThemeManager.success
                font.pixelSize: 16
                font.bold: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 8
            color: ThemeManager.isDark() ? ThemeManager.darkElevated : ThemeManager.lightElevated
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
