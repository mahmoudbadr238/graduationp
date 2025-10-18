import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Effects


Item {
    id: panel
    default property alias children: content.children
    property int padding: Theme.spacing_md
    property bool hoverable: false
    property bool elevated: false
    
    // Let parent layout control size
    Layout.fillWidth: true
    implicitHeight: content.implicitHeight + padding * 2
    
    Accessible.role: Accessible.Grouping

    Rectangle {
        id: bg
        anchors.fill: parent
        color: Theme.panel
        radius: Theme.radius
        border.color: Theme.border
        border.width: 1
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowBlur: 0.25
            shadowColor: elevated ? Theme.primary : "#00000033"
            shadowVerticalOffset: 2
            shadowHorizontalOffset: 0
            shadowOpacity: 0.18
        }
        Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
        Behavior on radius { NumberAnimation { duration: Theme.duration_fast } }
        scale: mouseArea.containsMouse && hoverable ? 1.02 : 1.0
        Behavior on scale { NumberAnimation { duration: Theme.duration_fast } }
    }
    
    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: padding
        spacing: Theme.spacing_md
    }
    
    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: hoverable
        cursorShape: hoverable ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (hoverable) panel.forceActiveFocus()
        propagateComposedEvents: true
        z: -1
    }
}
