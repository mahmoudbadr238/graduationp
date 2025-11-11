import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../theme"

Item {
    id: panel
    default property alias children: content.children
    property int padding: Theme.spacing_lg
    property bool hoverable: false
    property bool elevated: false
    property bool glassmorphic: false

    // Let parent layout control size - NO hardcoded dimensions
    Layout.fillWidth: true
    implicitHeight: content.implicitHeight + padding * 2

    Accessible.role: Accessible.Grouping

    Rectangle {
        id: bg
        anchors.fill: parent
        color: glassmorphic ? Theme.glass.panel : Theme.panel
        radius: Theme.radii_lg
        border.color: glassmorphic ? Theme.glass.border : Theme.border
        border.width: 1
        
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowBlur: elevated ? 12 : 8
            shadowColor: elevated ? Theme.neon.purpleGlow : Theme.shadow.color
            shadowVerticalOffset: Theme.shadow.md
            shadowHorizontalOffset: 0
        }
        
        Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
        
        scale: mouseArea.containsMouse && hoverable ? 1.02 : 1.0
        Behavior on scale { NumberAnimation { duration: Theme.duration_fast } }

        // Neon gradient overlay for glassmorphic panels
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: glassmorphic
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.glass.gradientStart }
                GradientStop { position: 1.0; color: Theme.glass.gradientEnd }
            }
        }
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