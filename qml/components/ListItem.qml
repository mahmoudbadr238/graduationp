import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15


Item {
    id: listItem
    property string icon: ""
    property string title: ""
    property string meta: ""
    width: 1; height: 48
    RowLayout {
        anchors.fill: parent
        spacing: Theme.gap
        Image {
            source: listItem.icon
            width: 24; height: 24
            fillMode: Image.PreserveAspectFit
        }
        Text {
            text: listItem.title
            color: Theme.text
            font.pixelSize: Theme.typography.body.size
            font.weight: Theme.typography.body.weight
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        Text {
            text: listItem.meta
            color: Theme.muted
            font.pixelSize: Theme.typography.mono.size
            font.family: "monospace"
            elide: Text.ElideRight
            visible: listItem.meta !== ""
        }
    }
}