import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: smallCard
    
    property string title: ""
    property string value: "0"
    property string unit: ""
    property string icon: ""
    
    implicitHeight: 60
    color: Qt.rgba(1, 1, 1, 0.03)
    radius: 6
    border.color: Qt.rgba(1, 1, 1, 0.05)
    border.width: 1
    
    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_sm
        spacing: Theme.spacing_sm
        
        Label {
            text: smallCard.icon
            font.pixelSize: 20
            visible: smallCard.icon !== ""
        }
        
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            
            Label {
                text: smallCard.title
                font.pixelSize: Theme.typography.body.size - 2
                color: Theme.textSecondary
            }
            
            RowLayout {
                spacing: 4
                
                Label {
                    text: smallCard.value !== undefined && smallCard.value !== null ? smallCard.value.toString() : "N/A"
                    font.pixelSize: Theme.typography.h3.size
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                
                Label {
                    text: smallCard.unit
                    font.pixelSize: Theme.typography.body.size
                    color: Theme.textSecondary
                    visible: smallCard.unit !== ""
                }
            }
        }
    }
}
