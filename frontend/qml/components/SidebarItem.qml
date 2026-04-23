import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

/**
 * SidebarItem - Reusable sidebar navigation item
 * 
 * Supports collapsed (icon only) and expanded (icon + text) states
 * with smooth animations.
 */
Rectangle {
    id: root
    
    // Required properties
    property string iconName: "home"
    property string label: ""
    property bool isActive: false
    property bool expanded: true
    readonly property color accentWash: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.11)
    readonly property color accentBorder: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.34)
    readonly property color hoverWash: Qt.rgba(ThemeManager.elevated().r, ThemeManager.elevated().g, ThemeManager.elevated().b, 0.58)
    readonly property color idlePlate: Qt.rgba(ThemeManager.panel().r, ThemeManager.panel().g, ThemeManager.panel().b, 0.74)
    readonly property color hoverPlate: Qt.rgba(ThemeManager.elevated().r, ThemeManager.elevated().g, ThemeManager.elevated().b, 0.74)
    readonly property color mutedForeground: Qt.rgba(ThemeManager.foreground().r, ThemeManager.foreground().g, ThemeManager.foreground().b, 0.74)
    readonly property color softMutedForeground: Qt.rgba(ThemeManager.foreground().r, ThemeManager.foreground().g, ThemeManager.foreground().b, 0.88)
    
    // Signals
    signal clicked()
    
    // Layout
    height: 44
    radius: 8
    color: isActive
           ? accentWash
           : (mouseArea.containsMouse
              ? hoverWash
              : "transparent")
    border.color: isActive
                  ? accentBorder
                  : "transparent"
    border.width: isActive ? 1 : 0
    
    Behavior on color {
        ColorAnimation { duration: 150 }
    }
    
    Rectangle {
        width: 3
        height: expanded ? 22 : 18
        radius: 2
        color: ThemeManager.accent
        anchors.left: parent.left
        anchors.leftMargin: 6
        anchors.verticalCenter: parent.verticalCenter
        opacity: isActive ? 1 : 0

        Behavior on opacity {
            NumberAnimation { duration: 140 }
        }
    }

    Item {
        anchors.fill: parent

        Rectangle {
            id: iconContainer
            width: 36
            height: 36
            radius: 10
            color: "transparent"
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: expanded ? 16 : (root.width - width) / 2

            Behavior on anchors.leftMargin {
                NumberAnimation { duration: 170; easing.type: Easing.OutCubic }
            }

            SidebarIcon {
                anchors.centerIn: parent
                width: 20
                height: 20
                name: root.iconName
                iconColor: isActive
                           ? ThemeManager.accent
                           : (mouseArea.containsMouse ? ThemeManager.foreground() : softMutedForeground)
            }
        }

        Item {
            anchors.left: iconContainer.right
            anchors.leftMargin: expanded ? 12 : 0
            anchors.right: parent.right
            anchors.rightMargin: expanded ? 14 : 0
            anchors.verticalCenter: parent.verticalCenter
            height: labelText.implicitHeight
            clip: true
            opacity: expanded ? 1 : 0

            Behavior on opacity {
                NumberAnimation { duration: 120 }
            }
            
            Behavior on anchors.leftMargin {
                NumberAnimation { duration: 170; easing.type: Easing.OutCubic }
            }

            Text {
                id: labelText
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: root.label
                color: isActive ? ThemeManager.foreground() : (mouseArea.containsMouse ? softMutedForeground : ThemeManager.muted())
                font.pixelSize: ThemeManager.fontSize_body
                font.weight: isActive ? Font.DemiBold : Font.Normal
                elide: Text.ElideRight

                Behavior on color {
                    ColorAnimation { duration: 150 }
                }
            }
        }
    }
    
    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
    
    // Tooltip when collapsed
    ToolTip {
        visible: !expanded && mouseArea.containsMouse
        text: root.label
        delay: 500
        
        background: Rectangle {
            color: ThemeManager.panel()
            border.color: ThemeManager.border()
            radius: 4
        }
        
        contentItem: Text {
            text: root.label
            color: ThemeManager.foreground()
            font.pixelSize: ThemeManager.fontSize_small
        }
    }
}
