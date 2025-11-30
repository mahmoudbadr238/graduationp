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
    property string icon: ""
    property string label: ""
    property bool isActive: false
    property bool expanded: true
    
    // Signals
    signal clicked()
    
    // Layout
    height: 44
    radius: 8
    color: isActive ? ThemeManager.elevated() : (mouseArea.containsMouse ? Qt.rgba(ThemeManager.elevated().r, ThemeManager.elevated().g, ThemeManager.elevated().b, 0.5) : "transparent")
    
    Behavior on color {
        ColorAnimation { duration: 150 }
    }
    
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: expanded ? 16 : 0
        anchors.rightMargin: expanded ? 16 : 0
        spacing: expanded ? 12 : 0
        
        // Icon
        Text {
            id: iconText
            text: root.icon
            color: isActive ? ThemeManager.accent : ThemeManager.muted()
            font.pixelSize: 18
            Layout.preferredWidth: expanded ? 24 : parent.width
            horizontalAlignment: expanded ? Text.AlignLeft : Text.AlignHCenter
            
            Behavior on color {
                ColorAnimation { duration: 150 }
            }
        }
        
        // Label - only visible when expanded
        Text {
            id: labelText
            text: root.label
            color: isActive ? ThemeManager.accent : ThemeManager.muted()
            font.pixelSize: ThemeManager.fontSize_body()
            font.weight: isActive ? Font.Bold : Font.Normal
            Layout.fillWidth: true
            visible: expanded
            opacity: expanded ? 1 : 0
            elide: Text.ElideRight
            
            Behavior on opacity {
                NumberAnimation { duration: 150 }
            }
            
            Behavior on color {
                ColorAnimation { duration: 150 }
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
            font.pixelSize: 12
        }
    }
}
