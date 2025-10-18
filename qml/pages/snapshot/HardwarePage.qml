import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"

Column {
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24
    
    PageHeader {
        title: "Hardware Usage"
        subtitle: "Live system performance"
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
                    text: "CPU Usage"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
                
                LineChartLive {
                    id: cpuChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#6ee7a8"
                }
                
                LiveMetricTile {
                    label: "CPU"
                    valueText: (cpuPct * 100).toFixed(0) + "%"
                    hint: "avg last 10s"
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
                    text: "Memory Usage"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
                
                LineChartLive {
                    id: memChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#a66bff"
                }
                
                LiveMetricTile {
                    label: "RAM"
                    valueText: (memPct * 100).toFixed(0) + "%"
                    hint: "in use"
                    positive: false
                    width: parent.width - 40
                }
            }
        }
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
                    text: "GPU Usage"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
                
                LineChartLive {
                    id: gpuChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#66c7ff"
                }
                
                LiveMetricTile {
                    label: "GPU"
                    valueText: (gpuPct * 100).toFixed(0) + "%"
                    hint: "compute / 3D"
                    positive: true
                    width: parent.width - 40
                }
            }
        }
        
        AnimatedCard {
            width: (parent.width - 18) / 2
            implicitHeight: 340
            
            Column {
                spacing: 16
                width: parent.width
                
                Text {
                    text: "Storage"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
                
                Text {
                    text: storageSummary
                    color: Theme.muted
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    width: parent.width - 40
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
                
                Rectangle {
                    width: parent.width - 40
                    height: 24
                    radius: 12
                    color: Theme.surface
                    border.color: Theme.border
                    border.width: 1
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                    Behavior on border.color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                    
                    Rectangle {
                        width: parent.width * 0.6
                        height: parent.height
                        radius: 12
                        color: "#a66bff"
                        
                        Behavior on width {
                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                        }
                    }
                }
                
                Text {
                    text: "612 GB used / 1 TB total"
                    color: Theme.muted
                    font.pixelSize: 13
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
            }
        }
    }
    
    // Stubbed timers; replace data sources later
    property real cpuPct: 0.22
    property real memPct: 0.41
    property real gpuPct: 0.15
    property string storageSummary: "NVMe 1TB — 612 GB used (60%)"
    
    Timer {
        id: updateTimer
        interval: 1000
        running: Qt.application.state === Qt.ApplicationActive && parent.visible
        repeat: true
        onTriggered: {
            cpuPct = Math.min(0.98, Math.max(0.02, cpuPct + (Math.random() - 0.5) * 0.12));
            memPct = Math.min(0.98, Math.max(0.02, memPct + (Math.random() - 0.5) * 0.04));
            gpuPct = Math.min(0.98, Math.max(0.02, gpuPct + (Math.random() - 0.5) * 0.10));
            cpuChart.pushValue(cpuPct);
            memChart.pushValue(memPct);
            gpuChart.pushValue(gpuPct);
        }
    }
}
