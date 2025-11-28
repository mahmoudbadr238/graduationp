import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Rectangle {
    id: card
    
    property string title: ""
    property string value: ""
    property bool isGood: true

    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
    radius: 12
    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
    border.width: 1
    implicitWidth: 180
    implicitHeight: 100

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 8

        Text {
            text: card.title
            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
            font.pixelSize: 11
            font.weight: Font.Medium
        }

        Text {
            text: card.value
            color: card.isGood ? ThemeManager.success : ThemeManager.warning
            font.pixelSize: 20
            font.bold: true
            wrapMode: Text.Wrap
        }

        Item { Layout.fillHeight: true }
    }
}
