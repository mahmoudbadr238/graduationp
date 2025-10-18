import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"

Column {
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24
    
    PageHeader {
        title: "Operating System"
        subtitle: "Version, build, and update information"
    }
    
    AnimatedCard {
        width: parent.width - 48
        implicitHeight: 280
        
        Grid {
            columns: 2
            columnSpacing: 40
            rowSpacing: 16
            
            Text { 
                text: "Operating System:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text { 
                text: "Windows 11 Pro"
                color: Theme.text
                font.pixelSize: 14
                font.bold: true
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            
            Text { 
                text: "Version:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text { 
                text: "22H2 (Build 22621.2861)"
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            
            Text { 
                text: "Architecture:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text { 
                text: "x64-based PC"
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            
            Text { 
                text: "Last Update:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text { 
                text: "2024-01-15"
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            
            Text { 
                text: "Uptime:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text { 
                text: "3 days, 14 hours"
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            
            Text { 
                text: "Installation Date:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text { 
                text: "2023-11-20"
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
        }
    }
}
