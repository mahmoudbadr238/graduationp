import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root
    
    property int gpuId: 0
    property var gpuMetrics: GPUBackend ? GPUBackend.getGPUMetrics(gpuId) : null
    
    implicitHeight: mainLayout.implicitHeight + Theme.spacing_lg * 2
    color: Theme.panel
    radius: 12
    border.color: Qt.rgba(1, 1, 1, 0.05)
    border.width: 1
    
    // Gradient background based on vendor
    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        opacity: 0.05
        
        gradient: Gradient {
            GradientStop {
                position: 0
                color: gpuMetrics && gpuMetrics.vendor === "NVIDIA" ? "#76b900" : 
                       gpuMetrics && gpuMetrics.vendor === "AMD" ? "#ed1c24" :
                       gpuMetrics && gpuMetrics.vendor === "Intel" ? "#0071c5" : Theme.primary
            }
            GradientStop {
                position: 1
                color: "transparent"
            }
        }
    }
    
    ColumnLayout {
        id: mainLayout
        anchors.fill: parent
        anchors.margins: Theme.spacing_lg
        spacing: Theme.spacing_md
        
        // Header Row
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing_md
            
            // Vendor Logo/Icon
            Rectangle {
                Layout.preferredWidth: 48
                Layout.preferredHeight: 48
                radius: 8
                color: gpuMetrics && gpuMetrics.vendor === "NVIDIA" ? "#76b900" : 
                       gpuMetrics && gpuMetrics.vendor === "AMD" ? "#ed1c24" :
                       gpuMetrics && gpuMetrics.vendor === "Intel" ? "#0071c5" : Theme.primary
                
                Label {
                    anchors.centerIn: parent
                    text: gpuMetrics && gpuMetrics.vendor === "NVIDIA" ? "🟢" : 
                          gpuMetrics && gpuMetrics.vendor === "AMD" ? "🔴" :
                          gpuMetrics && gpuMetrics.vendor === "Intel" ? "🔵" : "🎮"
                    font.pixelSize: 24
                }
            }
            
            // GPU Name and Info
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                
                Label {
                    text: gpuMetrics ? gpuMetrics.name : "GPU " + gpuId
                    font.pixelSize: Theme.typography.h3.size
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                
                RowLayout {
                    spacing: Theme.spacing_sm
                    
                    Label {
                        text: gpuMetrics ? gpuMetrics.vendor : "Unknown"
                        font.pixelSize: Theme.typography.body.size
                        color: Theme.textSecondary
                    }
                    
                    Rectangle {
                        width: 4
                        height: 4
                        radius: 2
                        color: Theme.textSecondary
                    }
                    
                    Label {
                        text: gpuMetrics ? "Driver: " + gpuMetrics.driver : ""
                        font.pixelSize: Theme.typography.body.size
                        color: Theme.textSecondary
                    }
                    
                    Rectangle {
                        width: 4
                        height: 4
                        radius: 2
                        color: Theme.textSecondary
                        visible: gpuMetrics && gpuMetrics.pciBus !== ""
                    }
                    
                    Label {
                        text: gpuMetrics && gpuMetrics.pciBus ? gpuMetrics.pciBus : ""
                        font.pixelSize: Theme.typography.body.size
                        color: Theme.textSecondary
                        visible: gpuMetrics && gpuMetrics.pciBus !== ""
                    }
                }
            }
            
            // Status Badge
            Rectangle {
                Layout.preferredWidth: statusLabel.implicitWidth + Theme.spacing_sm * 2
                Layout.preferredHeight: 24
                radius: 12
                color: gpuMetrics && gpuMetrics.status === "active" ? Qt.rgba(0.3, 0.8, 0.4, 0.2) :
                       gpuMetrics && gpuMetrics.status === "idle" ? Qt.rgba(0.5, 0.5, 0.5, 0.2) :
                       Qt.rgba(0.8, 0.6, 0.2, 0.2)
                border.color: gpuMetrics && gpuMetrics.status === "active" ? Qt.rgba(0.3, 0.8, 0.4, 0.5) :
                             gpuMetrics && gpuMetrics.status === "idle" ? Qt.rgba(0.5, 0.5, 0.5, 0.5) :
                             Qt.rgba(0.8, 0.6, 0.2, 0.5)
                border.width: 1
                
                Label {
                    id: statusLabel
                    anchors.centerIn: parent
                    text: gpuMetrics ? gpuMetrics.status.toUpperCase() : "UNKNOWN"
                    font.pixelSize: Theme.typography.body.size - 2
                    font.weight: Font.DemiBold
                    color: gpuMetrics && gpuMetrics.status === "active" ? "#4ade80" :
                           gpuMetrics && gpuMetrics.status === "idle" ? Theme.textSecondary :
                           "#fbbf24"
                }
            }
        }
        
        // Metrics Grid
        GridLayout {
            Layout.fillWidth: true
            columns: 4
            rowSpacing: Theme.spacing_md
            columnSpacing: Theme.spacing_md
            
            // GPU Usage
            MetricCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 100
                title: "GPU Usage"
                value: gpuMetrics ? gpuMetrics.usage.toFixed(1) : "0.0"
                unit: "%"
                icon: "📊"
                statusColor: gpuMetrics && gpuMetrics.usage > 80 ? "#fbbf24" : Theme.primary
            }
            
            // Temperature
            MetricCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 100
                title: "Temperature"
                value: gpuMetrics && gpuMetrics.temperature > 0 ? gpuMetrics.temperature.toString() : "N/A"
                unit: gpuMetrics && gpuMetrics.temperature > 0 ? "°C" : ""
                icon: "🌡️"
                statusColor: gpuMetrics && gpuMetrics.tempStatus === "critical" ? "#ff6b6b" :
                            gpuMetrics && gpuMetrics.tempStatus === "hot" ? "#fbbf24" :
                            gpuMetrics && gpuMetrics.tempStatus === "warm" ? "#4ade80" :
                            Theme.textSecondary
                statusText: gpuMetrics && gpuMetrics.temperature > 0 ? gpuMetrics.tempStatus : "Not Available"
            }
            
            // VRAM Usage
            MetricCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 100
                title: "VRAM Usage"
                value: gpuMetrics ? gpuMetrics.memoryPercent.toFixed(1) : "0.0"
                unit: "%"
                icon: "💾"
                statusColor: gpuMetrics && gpuMetrics.vramStatus === "critical" ? "#ff6b6b" :
                            gpuMetrics && gpuMetrics.vramStatus === "high" ? "#fbbf24" :
                            Theme.primary
                subtitle: gpuMetrics ? gpuMetrics.memoryUsed + " / " + gpuMetrics.memoryTotal + " MB" : "0 / 0 MB"
            }
            
            // Power Usage
            MetricCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 100
                title: "Power Usage"
                value: gpuMetrics && gpuMetrics.powerUsage > 0 ? gpuMetrics.powerUsage.toFixed(1) : "N/A"
                unit: gpuMetrics && gpuMetrics.powerUsage > 0 ? "W" : ""
                icon: "⚡"
                statusColor: Theme.primary
                subtitle: gpuMetrics && gpuMetrics.powerLimit > 0 ? "Limit: " + gpuMetrics.powerLimit.toFixed(0) + "W" : "Not Available"
            }
        }
        
        // Additional Metrics Row
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing_md
            visible: gpuMetrics && (gpuMetrics.clockGraphics > 0 || gpuMetrics.fanSpeedPercent > 0)
            
            // Clock Speed
            SmallMetricCard {
                Layout.fillWidth: true
                title: "GPU Clock"
                value: gpuMetrics && gpuMetrics.clockGraphics > 0 ? gpuMetrics.clockGraphics : "N/A"
                unit: gpuMetrics && gpuMetrics.clockGraphics > 0 ? "MHz" : ""
                icon: "⚙️"
            }
            
            // Memory Clock
            SmallMetricCard {
                Layout.fillWidth: true
                title: "Memory Clock"
                value: gpuMetrics && gpuMetrics.clockMemory > 0 ? gpuMetrics.clockMemory : "N/A"
                unit: gpuMetrics && gpuMetrics.clockMemory > 0 ? "MHz" : ""
                icon: "🔄"
            }
            
            // Fan Speed
            SmallMetricCard {
                Layout.fillWidth: true
                title: "Fan Speed"
                value: gpuMetrics && gpuMetrics.fanSpeedPercent > 0 ? gpuMetrics.fanSpeedPercent : "N/A"
                unit: gpuMetrics && gpuMetrics.fanSpeedPercent > 0 ? "%" : ""
                icon: "🌀"
            }
            
            // Fan RPM
            SmallMetricCard {
                Layout.fillWidth: true
                title: "Fan RPM"
                value: gpuMetrics && gpuMetrics.fanSpeedRPM > 0 ? gpuMetrics.fanSpeedRPM : "N/A"
                unit: gpuMetrics && gpuMetrics.fanSpeedRPM > 0 ? "RPM" : ""
                icon: "💨"
            }
        }
    }
    
    // Update when backend signals change (no per-card timer needed)
    Component.onCompleted: {
        root.gpuMetrics = GPUBackend ? GPUBackend.getGPUMetrics(root.gpuId) : null
    }
}
