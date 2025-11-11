import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: listItem
    
    property string icon: ""
    property string title: ""
    property string meta: ""
    property bool hoverable: true
    
    implicitWidth: 400
    implicitHeight: 56
    color: hoverable && mouseArea.containsMouse ? Theme.hover : "transparent"
    radius: Theme.radii.md
    
    Behavior on color {
        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
    }
    
    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: hoverable
        cursorShape: Qt.PointingHandCursor
    }
    
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing.md
        anchors.rightMargin: Theme.spacing.md
        spacing: Theme.spacing.md
        
        Image {
            visible: listItem.icon !== ""
            source: listItem.icon
            Layout.preferredWidth: 24
            Layout.preferredHeight: 24
            fillMode: Image.PreserveAspectFit
        }
        
        Text {
            text: listItem.title
            color: Theme.text
            font.pixelSize: Theme.typography.body.size
            font.weight: Theme.typography.body.weight
            elide: Text.ElideRight
            Layout.fillWidth: true
            
            Behavior on color {
                ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
            }
        }
        
        Text {
            visible: listItem.meta !== ""
            text: listItem.meta
            color: Theme.textSecondary
            font.pixelSize: Theme.typography.mono.size
            font.family: Theme.typography.mono.family
            elide: Text.ElideRight
            
            Behavior on color {
                ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
            }
        }
    }
}
