import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"


Item {
    id: topbar
    height: 56
    width: parent.width
    Rectangle {
        anchors.fill: parent
        color: Theme.panel
        radius: Theme.radii_sm
        
        Behavior on color {
            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
        }
    }
    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.gap
        spacing: Theme.gap
        // TODO: Add status pill, title, and actions
    }
}