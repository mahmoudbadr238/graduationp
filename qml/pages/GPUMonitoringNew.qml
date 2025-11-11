import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

/**
 * GPU Monitoring Page - Subprocess-based telemetry
 * Only loads when page is active, stops worker when deactivated
 */
PageWrapper {
    id: root
    
    sourceComponent: Component {
        Item {
            id: pageItem
            
            // Helper functions (accessible to all children)
            function getStatusText() {
                if (typeof GPUService === 'undefined') return "Service unavailable"
                var count = GPUService.gpuCount
                var interval = GPUService.updateInterval / 1000.0
                return count + " GPU(s) detected • Updates every " + interval.toFixed(1) + "s"
            }
            
            function getStatusLabel() {
                if (typeof GPUService === 'undefined') return "UNAVAILABLE"
                var status = GPUService.status
                if (status === 'running') return "ACTIVE"
                if (status === 'stopped') return "STOPPED"
                if (status === 'starting') return "STARTING"
                if (status === 'degraded') return "DEGRADED"
                if (status === 'breaker-open') return "DISABLED"
                return status.toUpperCase()
            }
            
            function getStatusColor() {
                if (typeof GPUService === 'undefined') return Qt.rgba(0.5, 0.5, 0.5, 0.2)
                var status = GPUService.status
                if (status === 'running') return Qt.rgba(0.3, 0.8, 0.4, 0.2)
                if (status === 'breaker-open' || status === 'degraded') return Qt.rgba(0.8, 0.3, 0.2, 0.2)
                return Qt.rgba(0.8, 0.6, 0.2, 0.2)
            }
            
            function getEmptyStateTitle() {
                if (typeof GPUService === 'undefined') return "GPU Service Unavailable"
                var status = GPUService.status
                if (status === 'stopped') return "Monitoring Paused"
                if (status === 'breaker-open') return "Service Disabled"
                return "No Compatible GPUs Found"
            }
            
            function getEmptyStateMessage() {
                if (typeof GPUService === 'undefined') return "GPU service failed to initialize"
                var status = GPUService.status
                if (status === 'breaker-open') return "Too many failures - restart app to retry"
                if (status === 'stopped') return "Monitoring will start when page is active"
                return "No compatible GPUs found on this system"
            }
            
            function getVendorColor(vendor) {
                if (vendor === "NVIDIA") return "#76b900"
                if (vendor === "AMD") return "#ed1c24"
                if (vendor === "Intel") return "#0071c5"
                return Theme.primary
            }
            
            function getVendorIcon(vendor) {
                if (vendor === "NVIDIA") return "🟢"
                if (vendor === "AMD") return "🔴"
                if (vendor === "Intel") return "🔵"
                return "🎮"
            }
            
            // Update metrics when service emits
            Connections {
                target: typeof GPUService !== 'undefined' ? GPUService : null
                
                function onMetricsUpdated() {
                    // Trigger UI refresh
                    gpuRepeater.model = 0
                    gpuRepeater.model = GPUService.gpuCount
                }
                
                function onError(title, message) {
                    console.error("GPU Service Error:", title, message)
                }
            }
            
            AppSurface {
                id: content
                anchors.fill: parent
                
                // Background
                Rectangle {
                    anchors.fill: parent
                    color: Theme.bg
                }
            
            ScrollView {
                anchors.fill: parent
                anchors.margins: Theme.spacing_m
                contentWidth: availableWidth
                clip: true
                
                ColumnLayout {
                    width: Math.min(parent.width, 1200)
                    spacing: Theme.spacing_lg
                    
                    // Page Header
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing_md
                        
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            
                            Label {
                                text: "GPU Monitoring"
                                font.pixelSize: Theme.typography.h1.size
                                font.weight: Theme.typography.h1.weight
                                color: Theme.text
                            }
                            
                            Label {
                                text: getStatusText()
                                font.pixelSize: Theme.typography.body.size
                                color: Theme.textSecondary
                            }
                        }
                        
                        // Status Badge
                        Rectangle {
                            Layout.preferredWidth: statusLabel.implicitWidth + Theme.spacing_md
                            Layout.preferredHeight: 28
                            radius: 14
                            color: getStatusColor()
                            border.color: Qt.lighter(getStatusColor(), 1.2)
                            border.width: 1
                            
                            Label {
                                id: statusLabel
                                anchors.centerIn: parent
                                text: getStatusLabel()
                                font.pixelSize: Theme.typography.body.size - 2
                                font.weight: Font.DemiBold
                                color: Theme.text
                            }
                        }
                    }
                    
                    // GPU Cards
                    Repeater {
                        id: gpuRepeater
                        model: typeof GPUService !== 'undefined' ? GPUService.gpuCount : 0
                        
                        delegate: Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: cardContent.implicitHeight + Theme.spacing_lg * 2
                            color: Theme.panel
                            radius: Theme.radii_lg
                            border.color: Theme.border
                            border.width: 1
                            
                            property var metrics: typeof GPUService !== 'undefined' ? GPUService.getGPUMetrics(index) : null
                            
                            ColumnLayout {
                                id: cardContent
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_lg
                                spacing: Theme.spacing_md
                                
                                // GPU Header
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Theme.spacing_md
                                    
                                    // Vendor Icon
                                    Rectangle {
                                        Layout.preferredWidth: 48
                                        Layout.preferredHeight: 48
                                        radius: 8
                                        color: getVendorColor(metrics ? metrics.vendor : "Unknown")
                                        
                                        Label {
                                            anchors.centerIn: parent
                                            text: getVendorIcon(metrics ? metrics.vendor : "Unknown")
                                            font.pixelSize: 24
                                        }
                                    }
                                    
                                    // GPU Info
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        
                                        Label {
                                            text: metrics ? metrics.name : "GPU " + index
                                            font.pixelSize: Theme.typography.h3.size
                                            font.weight: Font.DemiBold
                                            color: Theme.text
                                        }
                                        
                                        Label {
                                            text: metrics ? metrics.vendor : "Unknown"
                                            font.pixelSize: Theme.typography.body.size
                                            color: Theme.textSecondary
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
                                        value: metrics ? metrics.usage.toFixed(1) : "0.0"
                                        unit: "%"
                                        icon: "📊"
                                        statusColor: metrics && metrics.usage > 80 ? "#fbbf24" : Theme.primary
                                    }
                                    
                                    // Temperature
                                    MetricCard {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 100
                                        title: "Temperature"
                                        value: metrics && metrics.tempC > 0 ? metrics.tempC.toString() : "N/A"
                                        unit: metrics && metrics.tempC > 0 ? "°C" : ""
                                        icon: "🌡️"
                                        statusColor: metrics && metrics.tempC > 75 ? "#ff6b6b" : 
                                                    metrics && metrics.tempC > 60 ? "#fbbf24" : Theme.textSecondary
                                    }
                                    
                                    // VRAM Usage
                                    MetricCard {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 100
                                        title: "VRAM Usage"
                                        value: metrics ? metrics.memPercent.toFixed(1) : "0.0"
                                        unit: "%"
                                        icon: "💾"
                                        subtitle: metrics ? metrics.memUsedMB + " / " + metrics.memTotalMB + " MB" : "0 / 0 MB"
                                    }
                                    
                                    // Power Usage
                                    MetricCard {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 100
                                        title: "Power Usage"
                                        value: metrics && metrics.powerW > 0 ? metrics.powerW.toFixed(1) : "N/A"
                                        unit: metrics && metrics.powerW > 0 ? "W" : ""
                                        icon: "⚡"
                                        subtitle: metrics && metrics.powerLimitW > 0 ? "Limit: " + metrics.powerLimitW.toFixed(0) + "W" : ""
                                    }
                                }
                            }
                        }
                    }
                    
                    // Empty State
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 200
                        visible: (typeof GPUService === 'undefined') || GPUService.gpuCount === 0
                        color: "transparent"
                        
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: Theme.spacing_md
                            
                            Label {
                                text: "🎮"
                                font.pixelSize: 48
                                Layout.alignment: Qt.AlignHCenter
                            }
                            
                            Label {
                                text: getEmptyStateTitle()
                                font.pixelSize: Theme.typography.h2.size
                                font.weight: Font.DemiBold
                                color: Theme.text
                                Layout.alignment: Qt.AlignHCenter
                            }
                            
                            Label {
                                text: getEmptyStateMessage()
                                font.pixelSize: Theme.typography.body.size
                                color: Theme.textSecondary
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }
            }
            }  // Close AppSurface
        }  // Close Item wrapper
    }
}
