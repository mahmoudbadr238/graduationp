import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Rectangle {
    id: card
    
    property string title: ""
    property string value: ""
    property string subtitle: ""
    property color accentColor: ThemeManager.accent

    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
    radius: 12
    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
    border.width: 1
    implicitWidth: 200
    implicitHeight: 100

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 4

        Text {
            text: card.title
            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
            font.pixelSize: 11
            font.weight: Font.Medium
        }

        Text {
            text: card.value
            color: accentColor
            font.pixelSize: 22
            font.bold: true
        }

        Text {
            visible: card.subtitle !== ""
            text: card.subtitle
            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
            font.pixelSize: 10
            wrapMode: Text.Wrap
        }

        Item { Layout.fillHeight: true }
    }
}
