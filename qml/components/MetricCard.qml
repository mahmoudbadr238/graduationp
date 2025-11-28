import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: card
    property string title: ""
    property string value: ""
    property string subtitle: ""
    property color accentColor: theme.colorAccent

    Theme { id: theme }

    color: theme.colorSurface
    radius: theme.radiusLarge
    border.color: theme.colorBorderSubtle
    border.width: 1
    implicitWidth: 280
    implicitHeight: 160

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.paddingM
        spacing: theme.gapSmall
        
        Text {
            text: card.title
            color: theme.colorTextSecondary
            font.pixelSize: 12
            font.capitalization: Font.AllUppercase
        }

        Text {
            text: card.value
            color: accentColor
            font.pixelSize: 36
            font.bold: true
        }

        Text {
            visible: card.subtitle !== ""
            text: card.subtitle
            color: theme.colorTextMuted
            font.pixelSize: 11
            wrapMode: Text.Wrap
        }

        Item { Layout.fillHeight: true }
    }
}
