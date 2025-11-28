import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Rectangle {
    id: card
    
    property string adapterName: ""
    property string ipv4: ""
    property string ipv6: ""
    property string mac: ""
    property bool isUp: false

    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
    radius: 12
    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
    border.width: 1
    implicitWidth: 350
    implicitHeight: 110

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: card.adapterName
                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                font.pixelSize: 13
                font.bold: true
                Layout.fillWidth: true
            }

            Rectangle {
                width: 10
                height: 10
                radius: 5
                color: card.isUp ? ThemeManager.success : (ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted)
            }
        }

        Text {
            text: "IPv4: " + (card.ipv4 || "N/A")
            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
            font.pixelSize: 10
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        Text {
            visible: card.ipv6 !== ""
            text: "IPv6: " + card.ipv6
            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
            font.pixelSize: 10
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        Text {
            text: "MAC: " + (card.mac || "N/A")
            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
            font.pixelSize: 10
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
}
