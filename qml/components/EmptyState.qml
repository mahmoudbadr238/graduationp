import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Item {
    id: emptyState
    
    property string icon: "⚠"
    property string title: "No Data"
    property string message: "Nothing to display yet"
    property string actionText: ""
    signal actionClicked()
    
    implicitWidth: 300
    implicitHeight: column.implicitHeight
    
    ColumnLayout {
        id: column
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 400)
        spacing: Theme.spacing.md
        
        Text {
            text: emptyState.icon
            font.pixelSize: 48
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
            opacity: 0.5
        }
        
        Text {
            text: emptyState.title
            color: Theme.text
            font.pixelSize: Theme.typography.h3.size
            font.weight: Theme.typography.h3.weight
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            
            Behavior on color {
                ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
            }
        }
        
        Text {
            text: emptyState.message
            color: Theme.textSecondary
            font.pixelSize: Theme.typography.body.size
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            
            Behavior on color {
                ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
            }
        }
        
        Button {
            visible: emptyState.actionText !== ""
            text: emptyState.actionText
            Layout.alignment: Qt.AlignHCenter
            onClicked: emptyState.actionClicked()
            
            background: Rectangle {
                color: parent.down ? Theme.pressed : (parent.hovered ? Theme.hover : Theme.primary)
                radius: Theme.radii.md
                
                Behavior on color {
                    ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                }
            }
            
            contentItem: Text {
                text: parent.text
                color: "#FFFFFF"
                font.pixelSize: Theme.typography.body.size
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
