import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    height: 60
    color: Theme.panel
    
    Behavior on color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    
    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        spacing: Theme.spacing_md
        
        Text {
            text: "Sentinel  Endpoint Security Suite"
            color: Theme.text
            font.pixelSize: Theme.typography.h2.size
            font.weight: Theme.typography.h2.weight
            
            Behavior on color {
                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
            }
        }
        
        Item { Layout.fillWidth: true }
        
        Rectangle {
            Layout.preferredWidth: 12
            Layout.preferredHeight: 12
            radius: 6
            color: Theme.success
            
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.3; duration: 1000 }
                NumberAnimation { from: 0.3; to: 1.0; duration: 1000 }
            }
        }
        
        Text {
            text: "System Protected"
            color: Theme.success
            font.pixelSize: Theme.typography.body.size
            
            Behavior on color {
                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
            }
        }
    }
}
