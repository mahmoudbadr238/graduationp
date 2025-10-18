import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15


Item {
    id: surface
    // Expose a default slot so page children are placed into the inset container
    default property alias content: contentInset.children
    // Keep a named alias for explicit usage
    property alias contentItem: contentInset
    property bool isWideScreen: width >= 1200
    // Do not set anchors here; StackView controls geometry of its pages.
    focus: true
    Accessible.role: Accessible.Application
    Rectangle {
        anchors.fill: parent
        color: Theme.bg
        
        Behavior on color {
            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
        }
    }
    // Inset content to avoid overlapping rounded sidebar/topbar visuals
    Item {
        id: contentInset
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
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
    Component.onCompleted: surface.state = "entered"
}
