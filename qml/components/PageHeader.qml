import QtQuick 2.15
import QtQuick.Controls 2.15

Column {
    property string title: "Title"
    property string subtitle: ""
    spacing: 6
    
    Text {
        text: title
        font.pixelSize: 28
        font.bold: true
        color: Theme.text
        
        Behavior on color {
            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
        }
    }
    
    Text {
        visible: subtitle.length > 0
        text: subtitle
        font.pixelSize: 14
        color: Theme.muted
        
        Behavior on color {
            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
        }
    }
}
