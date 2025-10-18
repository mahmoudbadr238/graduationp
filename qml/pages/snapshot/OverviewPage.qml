import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"

Column {
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24
    
    PageHeader {
        title: "System Overview"
        subtitle: "Quick health check and key metrics"
    }
    
    Flow {
        width: parent.width
        spacing: 18
        
        LiveMetricTile {
            label: "CPU"
            valueText: "23%"
            hint: "avg load"
            positive: true
        }
        
        LiveMetricTile {
            label: "Memory"
            valueText: "41%"
            hint: "16.4 GB / 40 GB"
            positive: true
        }
        
        LiveMetricTile {
            label: "Disk"
            valueText: "60%"
            hint: "612 GB / 1 TB"
            positive: false
        }
        
        LiveMetricTile {
            label: "Network"
            valueText: "Active"
            hint: "192.168.1.50"
            positive: true
        }
    }
    
    AnimatedCard {
        width: parent.width - 48
        implicitHeight: 140
        
        Column {
            spacing: 12
            
            Text {
                text: "Security Status"
                font.pixelSize: 18
                font.bold: true
                color: Theme.text
                
                Behavior on color {
                    ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                }
            }
            
            Flow {
                width: parent.width - 40
                spacing: 12
                
                Rectangle {
                    width: 180
                    height: 32
                    radius: 8
                    color: Theme.isDark ? "#1a2f2a" : "#e8f5e9"
                    border.color: Theme.success
                    border.width: 1
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                    
                    Text {
                        anchors.centerIn: parent
                        text: "✓ Windows Defender"
                        color: Theme.success
                        font.pixelSize: 13
                    }
                }
                
                Rectangle {
                    width: 140
                    height: 32
                    radius: 8
                    color: Theme.isDark ? "#1a2f2a" : "#e8f5e9"
                    border.color: Theme.success
                    border.width: 1
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                    
                    Text {
                        anchors.centerIn: parent
                        text: "✓ Firewall"
                        color: Theme.success
                        font.pixelSize: 13
                    }
                }
                
                Rectangle {
                    width: 150
                    height: 32
                    radius: 8
                    color: Theme.isDark ? "#1a2f2a" : "#e8f5e9"
                    border.color: Theme.success
                    border.width: 1
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                    
                    Text {
                        anchors.centerIn: parent
                        text: "✓ Secure Boot"
                        color: Theme.success
                        font.pixelSize: 13
                    }
                }
            }
        }
    }
}
