import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Rectangle {
    id: card
    
    property string driveName: ""
    property string driveLetter: ""
    property string mountLabel: ""
    property string detail: ""
    property string category: ""
    property bool readOnly: false
    property bool usageAvailable: true
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
                    property string location: mountLabel || driveLetter
                    text: location ? (driveName + " (" + location + ")") : driveName
                    color: ThemeManager.foreground()
                    font.pixelSize: ThemeManager.fontSize_small
                    font.bold: true
                }

                Text {
                    text: card.usageAvailable
                          ? (used.toFixed(1) + " GB / " + total.toFixed(1) + " GB")
                          : "Usage unavailable"
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_small
                }

                Text {
                    text: detail || (category ? category : "")
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_caption
                    visible: text !== ""
                }
            }

            Text {
                text: card.usageAvailable ? (percent.toFixed(0) + "%") : "N/A"
                color: !card.usageAvailable ? ThemeManager.muted() :
                       percent > 80 ? ThemeManager.danger :
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
                width: card.usageAvailable ? parent.width * (card.percent / 100) : 0
                color: card.percent > 80 ? ThemeManager.danger :
                       card.percent > 60 ? ThemeManager.warning :
                       ThemeManager.success
                radius: 4
            }
        }
    }
}
