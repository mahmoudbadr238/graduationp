import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Item {
    id: topbar

    property string title: ""
    property alias actions: actionsSlot.data

    height: 56
    width: parent ? parent.width : 0

    Rectangle {
        anchors.fill: parent
        color: Theme.panel
        border.color: Theme.border
        border.width: 1

        Behavior on color {
            ColorAnimation { duration: Theme.duration_fast; easing.type: Easing.InOutQuad }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing_lg
        anchors.rightMargin: Theme.spacing_lg
        spacing: Theme.spacing_md

        Text {
            text: topbar.title
            color: Theme.text
            font.pixelSize: Theme.typography.h4.size
            font.weight: Theme.typography.h4.weight
            elide: Text.ElideRight
            Layout.fillWidth: true
            visible: topbar.title !== ""
        }

        Item {
            id: actionsSlot
            Layout.fillWidth: topbar.title === ""
            implicitWidth: childrenRect.width
            implicitHeight: childrenRect.height
        }
    }
}
