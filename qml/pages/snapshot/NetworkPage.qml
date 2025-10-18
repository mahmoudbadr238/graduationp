import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"

Column {
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24
    
    PageHeader {
        title: "Network Usage"
        subtitle: "Live throughput & adapter details"
    }
    
    Row {
        spacing: 18
        width: parent.width
        
        AnimatedCard {
            width: (parent.width - 18) / 2
            implicitHeight: 340
            
            Column {
                spacing: 10
                width: parent.width
                
                Text {
                    text: "Upload (Mbps)"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
                
                LineChartLive {
                    id: upChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#6ee7a8"
                }
                
                LiveMetricTile {
                    label: "Up"
                    valueText: upMbps.toFixed(2) + " Mbps"
                    positive: true
                    width: parent.width - 40
                }
            }
        }
        
        AnimatedCard {
            width: (parent.width - 18) / 2
            implicitHeight: 340
            
            Column {
                spacing: 10
                width: parent.width
                
                Text {
                    text: "Download (Mbps)"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
                
                LineChartLive {
                    id: downChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#a66bff"
                }
                
                LiveMetricTile {
                    label: "Down"
                    valueText: downMbps.toFixed(2) + " Mbps"
                    positive: true
                    width: parent.width - 40
                }
            }
        }
    }
    
    AnimatedCard {
        width: parent.width - 48
        implicitHeight: 120
        
        Column {
            spacing: 10
            width: parent.width
            
            Text {
                text: "Adapter Details"
                color: Theme.text
                font.pixelSize: 16
                font.bold: true
                
                Behavior on color {
                    ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                }
            }
            
            Text {
                text: "Realtek PCIe GbE — 192.168.1.50 — Gateway 192.168.1.1"
                color: Theme.muted
                wrapMode: Text.Wrap
                width: parent.width - 40
                font.pixelSize: 14
                
                Behavior on color {
                    ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                }
            }
        }
    }
    
    // Stubbed generator; replace with real data
    property real upMbps: 1.4
    property real downMbps: 9.2
    
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            upMbps = Math.max(0, upMbps + (Math.random() - 0.5) * 3);
            downMbps = Math.max(0, downMbps + (Math.random() - 0.5) * 10);
            upChart.pushValue(Math.min(1, upMbps / 50));
            downChart.pushValue(Math.min(1, downMbps / 200));
        }
    }
}
