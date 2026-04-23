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

    color: ThemeManager.panel()
    radius: 12
    border.color: ThemeManager.border()
    border.width: 1
    implicitWidth: 280
    implicitHeight: 140

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 6

        Text {
            text: card.title
            color: ThemeManager.muted()
            font.pixelSize: ThemeManager.fontSize_small
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 0.8
        }

        Text {
            text: card.value
            color: accentColor
            font.pixelSize: ThemeManager.fontSize_h1
            font.bold: true
        }

        Text {
            visible: card.subtitle !== ""
            text: card.subtitle
            color: ThemeManager.muted()
            font.pixelSize: ThemeManager.fontSize_small
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }

        Item { Layout.fillHeight: true }
    }
}
