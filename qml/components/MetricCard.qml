import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: metricCard
    
    property string title: ""
    property string value: "0"
    property string unit: ""
    property string icon: "📊"
    property string subtitle: ""
    property string statusText: ""
    property color statusColor: Theme.primary
    
    color: Qt.rgba(1, 1, 1, 0.03)
    radius: 8
    border.color: Qt.rgba(1, 1, 1, 0.05)
    border.width: 1
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_sm
        spacing: Theme.spacing_xs
        
        // Icon and Title
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing_xs
            
            Label {
                text: metricCard.icon
                font.pixelSize: 16
            }
            
            Label {
                text: metricCard.title
                font.pixelSize: Theme.typography.body.size - 1
                color: Theme.textSecondary
                Layout.fillWidth: true
            }
            
            Label {
                text: metricCard.statusText
                font.pixelSize: Theme.typography.body.size - 2
                font.weight: Font.DemiBold
                color: metricCard.statusColor
                visible: metricCard.statusText !== ""
            }
        }
        
        Item { Layout.fillHeight: true }
        
        // Value
        RowLayout {
            Layout.fillWidth: true
            spacing: 4
            
            Label {
                text: metricCard.value !== undefined && metricCard.value !== null ? metricCard.value : "N/A"
                font.pixelSize: Theme.typography.h2.size
                font.weight: Font.Bold
                color: metricCard.statusColor
            }
            
            Label {
                text: metricCard.unit
                font.pixelSize: Theme.typography.h3.size
                color: Theme.textSecondary
                Layout.alignment: Qt.AlignBottom
                visible: metricCard.unit !== ""
            }
        }
        
        // Subtitle
        Label {
            text: metricCard.subtitle
            font.pixelSize: Theme.typography.body.size - 2
            color: Theme.textSecondary
            visible: metricCard.subtitle !== ""
        }
    }
}
