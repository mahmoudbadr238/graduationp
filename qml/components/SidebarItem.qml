import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    property string text: ""
    property bool selected: false
    signal clicked()

    height: 44
    width: parent ? parent.width : 240

    Theme { id: theme }

    Rectangle {
        anchors.fill: parent
        radius: theme.radiusMedium
        color: root.selected ? theme.colorAccentSoft : "transparent"

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.clicked()
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: theme.paddingM
            text: root.text
            color: root.selected ? theme.colorAccent : theme.colorTextSecondary
            font.pixelSize: 14
            font.weight: root.selected ? Font.DemiBold : Font.Normal
        }
    }
}
