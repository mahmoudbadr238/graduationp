import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"

/**
 * AppSurface: Properly sized page wrapper for StackView
 * Ensures pages fill available space without extra insets
 */
Item {
    id: surface
    
    // CRITICAL: Must fill parent (StackView provides the geometry)
    anchors.fill: parent
    
    // Allow child items to be placed directly
    default property alias children: container.children
    
    focus: true
    Accessible.role: Accessible.Application
    
    // Background color
    Rectangle {
        anchors.fill: parent
        color: Theme.bg
        
        Behavior on color {
            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
        }
    }
    
    // Container for all children - fills parent, NO insets
    Item {
        id: container
        anchors.fill: parent
    }
    
    // Fade+slide enter animation
    states: [
        State {
            name: "entered"
            PropertyChanges { target: surface; opacity: 1; y: 0 }
        }
    ]
    
    transitions: [
        Transition {
            from: ""; to: "entered"
            NumberAnimation { properties: "opacity,y"; duration: Theme.duration_fast; easing.type: Easing.OutCubic }
        }
    ]
    
    opacity: 0
    y: 32
    
    Component.onCompleted: {
        surface.state = "entered"
        console.log("[DEBUG] AppSurface instantiated (", surface.width, "x", surface.height, ")")
    }
}
