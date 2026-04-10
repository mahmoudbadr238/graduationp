import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"


Rectangle {
    id: skeleton
    color: Theme.surface
    radius: Theme.radii_sm
    height: 32
    width: parent ? parent.width : 120
    SequentialAnimation on opacity {
        loops: Animation.Infinite
        NumberAnimation { from: 0.5; to: 1; duration: 600 }
        NumberAnimation { from: 1; to: 0.5; duration: 600 }
    }
    Rectangle {
        anchors.fill: parent
        color: Theme.muted
        opacity: 0.18
        radius: Theme.radii_sm
    }
}