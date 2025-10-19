import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"

Column {
    id: root
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24

    // This property will be set by SystemSnapshot.qml Loader
    property var snapshotData: ({
        "cpu": {"usage": 0, "freq_current": 0, "core_count": 0},
        "mem": {"used": 0, "total": 0, "percent": 0},
        "gpu": {"available": false, "usage": 0},
        "net": {"send_rate_mbps": 0, "recv_rate_mbps": 0, "adapters": []},
        "disk": [{"used": 0, "total": 0, "percent": 0}]
    })

    PageHeader {
        title: "System Overview"
        subtitle: "Quick health check and key metrics"
    }

    Flow {
        width: parent.width
        spacing: 18

        LiveMetricTile {
            label: "CPU"
            valueText: root.snapshotData.cpu ? root.snapshotData.cpu.usage.toFixed(1) + "%" : "N/A"
            hint: root.snapshotData.cpu ? root.snapshotData.cpu.core_count + " cores @ " + (root.snapshotData.cpu.freq_current / 1000).toFixed(2) + " GHz" : ""
            positive: root.snapshotData.cpu ? root.snapshotData.cpu.usage < 80 : true
        }

        LiveMetricTile {
            label: "Memory"
            valueText: root.snapshotData.mem ? root.snapshotData.mem.percent.toFixed(1) + "%" : "N/A"
            hint: root.snapshotData.mem ? (root.snapshotData.mem.used / (1024**3)).toFixed(1) + " GB / " + (root.snapshotData.mem.total / (1024**3)).toFixed(1) + " GB" : ""
            positive: root.snapshotData.mem ? root.snapshotData.mem.percent < 80 : true
        }
        
        LiveMetricTile {
            label: "Disk"
            valueText: root.snapshotData.disk && root.snapshotData.disk.length > 0 ? root.snapshotData.disk[0].percent.toFixed(1) + "%" : "N/A"
            hint: root.snapshotData.disk && root.snapshotData.disk.length > 0 ? 
                  (root.snapshotData.disk[0].used / (1024**3)).toFixed(0) + " GB / " + (root.snapshotData.disk[0].total / (1024**3)).toFixed(0) + " GB" : ""
            positive: root.snapshotData.disk && root.snapshotData.disk.length > 0 ? root.snapshotData.disk[0].percent < 80 : true
        }

        LiveMetricTile {
            label: "Network"
            valueText: root.snapshotData.net ? "↓ " + (root.snapshotData.net.recv_rate_mbps || 0).toFixed(2) + " Mbps ↑ " + (root.snapshotData.net.send_rate_mbps || 0).toFixed(2) + " Mbps" : "N/A"
            hint: root.snapshotData.net && root.snapshotData.net.adapters ? root.snapshotData.net.adapters.length + " adapters" : ""
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
