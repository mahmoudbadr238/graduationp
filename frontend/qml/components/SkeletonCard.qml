import QtQuick 2.15
import "../ui"
import "../theme"

Rectangle {
    id: skeleton
    
    implicitWidth: 200
    implicitHeight: 100
    radius: 8
    color: ThemeManager.panel()
    border.width: 1
    border.color: ThemeManager.border()
    
    Rectangle {
        id: shimmer
        anchors.fill: parent
        radius: parent.radius
        
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: ThemeManager.isDark() ? "#ffffff15" : "#00000010" }
            GradientStop { position: 1.0; color: "transparent" }
        }
        
        SequentialAnimation on x {
            running: true
            loops: Animation.Infinite
            
            NumberAnimation {
                from: -skeleton.width
                to: skeleton.width
                duration: 1500
                easing.type: Easing.InOutQuad
            }
        }
    }
    
    Column {
        anchors.centerIn: parent
        spacing: 8
        width: parent.width * 0.8
        
        Rectangle {
            width: parent.width * 0.6
            height: 16
            radius: 4
            color: ThemeManager.isDark() ? "#ffffff20" : "#00000020"
        }
        
        Rectangle {
            width: parent.width * 0.9
            height: 12
            radius: 4
            color: ThemeManager.isDark() ? "#ffffff15" : "#00000015"
        }
        
        Rectangle {
            width: parent.width * 0.7
            height: 12
            radius: 4
            color: ThemeManager.isDark() ? "#ffffff15" : "#00000015"
        }
    }
}
