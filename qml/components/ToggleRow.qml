import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: toggleRow
    
    property string title: ""
    property string description: ""
    property bool checked: false
    property bool enabled: true
    
    signal toggled(bool checked)
    
    implicitWidth: 400
    implicitHeight: descText.visible ? 72 : 56
    color: mouseArea.containsMouse ? Theme.hover : "transparent"
    radius: Theme.radii.md
    
    Behavior on color {
        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
    }
    
    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        enabled: toggleRow.enabled
        onClicked: {
            if (toggleRow.enabled) {
                toggleRow.checked = !toggleRow.checked
                toggleRow.toggled(toggleRow.checked)
            }
        }
    }
    
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing.md
        anchors.rightMargin: Theme.spacing.md
        spacing: Theme.spacing.md
        
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing.xs
            
            Text {
                text: toggleRow.title
                color: toggleRow.enabled ? Theme.text : Theme.textSecondary
                font.pixelSize: Theme.typography.body.size
                font.weight: Font.Medium
                elide: Text.ElideRight
                Layout.fillWidth: true
                
                Behavior on color {
                    ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                }
            }
            
            Text {
                id: descText
                visible: toggleRow.description !== ""
                text: toggleRow.description
                color: Theme.textSecondary
                font.pixelSize: Theme.typography.caption.size
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                maximumLineCount: 2
                Layout.fillWidth: true
                
                Behavior on color {
                    ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                }
            }
        }
        
        Switch {
            checked: toggleRow.checked
            enabled: toggleRow.enabled
            onToggled: {
                toggleRow.checked = checked
                toggleRow.toggled(checked)
            }
            
            indicator: Rectangle {
                width: 44
                height: 24
                radius: 12
                color: parent.checked ? Theme.primary : Theme.surface
                border.color: Theme.border
                border.width: parent.checked ? 0 : 1
                
                Behavior on color {
                    ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                }
                
                Rectangle {
                    x: parent.parent.checked ? parent.width - width - 3 : 3
                    y: 3
                    width: 18
                    height: 18
                    radius: 9
                    color: "#FFFFFF"
                    
                    Behavior on x {
                        NumberAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                    }
                }
            }
        }
    }
}
