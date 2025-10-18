import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Rectangle {
    id: root
    
    property string title: ""
    property bool hoverable: true
    default property alias children: contentContainer.children
    // Internal padding for content
    property int padding: Theme.spacing_md
    property int spacing: Theme.spacing_md
    // Let layouts compute size from content
    implicitWidth: Math.max(titleLabel.implicitWidth, contentContainer.implicitWidth) + padding * 2
    implicitHeight: (title !== "" ? titleLabel.implicitHeight + spacing : 0) + contentContainer.implicitHeight + padding * 2
    
    Accessible.role: Accessible.Grouping
    Accessible.name: title !== "" ? title : "Card"
    
    color: Theme.elevatedPanel
    radius: Theme.radii_md
    
    // Smooth color transitions
    Behavior on color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    
    states: [
        State {
            name: "hovered"
            when: hoverable && hoverArea.containsMouse
            PropertyChanges { target: root; scale: 1.02 }
            PropertyChanges { target: shadowEffect; shadowBlur: 24 }
        }
    ]
    
    transitions: Transition {
        NumberAnimation { properties: "scale,shadowBlur"; duration: Theme.duration_fast; easing.type: Easing.OutCubic }
    }
    
    MultiEffect {
        id: shadowEffect
        source: root
        anchors.fill: root
        shadowEnabled: true
        shadowColor: root.hoverable ? Theme.primary : Theme.border
        shadowHorizontalOffset: 0
        shadowVerticalOffset: 4
        shadowBlur: 12
    }
    
    ColumnLayout {
        // Use padding instead of anchors to allow implicit size calculation
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: root.padding
        spacing: root.spacing
        
        Text {
            visible: title !== ""
            id: titleLabel
            text: title
            color: Theme.text
            
            Behavior on color {
                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
            }
            font.pixelSize: Theme.typography.h2.size
            font.weight: Theme.typography.h2.weight
            Layout.fillWidth: true
        }
        
        ColumnLayout {
            id: contentContainer
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacing_md
        }
    }
    
    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: hoverable
        acceptedButtons: Qt.NoButton
    }
}
