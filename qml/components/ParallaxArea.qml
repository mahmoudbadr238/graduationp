import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15


Item {
    id: parallax
    property real maxOffset: 8
    property alias contentItem: content
    width: 1; height: 1
    Item {
        id: content
        anchors.fill: parent
    }
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onPositionChanged: {
            var dx = (mouse.x / width - 0.5) * 2 * maxOffset;
            var dy = (mouse.y / height - 0.5) * 2 * maxOffset;
            content.x = dx;
            content.y = dy;
        }
        onExited: {
            content.x = 0;
            content.y = 0;
        }
    }
}
