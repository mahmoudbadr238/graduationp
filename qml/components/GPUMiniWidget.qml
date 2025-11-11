import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../theme"

// GPU Mini Widget for System Snapshot - Glassmorphism Style
Rectangle {
    id: root
    
    implicitHeight: contentLayout.implicitHeight + Theme.spacing_lg * 2
    color: "transparent"
    
    // Glassmorphic background with blur
    Rectangle {
        id: glassBackground
        anchors.fill: parent
        radius: 16
        color: Qt.rgba(0.1, 0.1, 0.15, 0.4)
        border.color: Qt.rgba(0.5, 0.4, 1.0, 0.3)
        border.width: 1
        
        // Subtle gradient overlay
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            opacity: 0.1
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#7C5CFF" }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }
    
    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        anchors.margins: Theme.spacing_lg
        spacing: Theme.spacing_md
        
        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing_sm
            
            Label {
                text: "🎮"
                font.pixelSize: 20
            }
            
            Label {
                text: "GPU Status"
                font.pixelSize: Theme.typography.h3.size
                font.weight: Font.DemiBold
                color: Theme.text
            }
            
            Item { Layout.fillWidth: true }
            
            // GPU Count Badge
            Rectangle {
                Layout.preferredWidth: countLabel.implicitWidth + 16
                Layout.preferredHeight: 22
                radius: 11
                color: Qt.rgba(0.49, 0.36, 1.0, 0.2)
                border.color: "#7C5CFF"
                border.width: 1
                
                Label {
                    id: countLabel
                    anchors.centerIn: parent
                    text: (typeof GPUService !== 'undefined' && GPUService) ? GPUService.gpuCount + " GPU" + (GPUService.gpuCount > 1 ? "s" : "") : "Loading..."
                    font.pixelSize: Theme.typography.body.size - 2
                    font.weight: Font.DemiBold
                    color: "#7C5CFF"
                }
            }
        }
        
        // GPU Cards - Compact Version
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing_sm

            Repeater {
                id: gpuRepeater
                model: (typeof GPUService !== 'undefined' && GPUService) ? GPUService.gpuCount : 0

                onModelChanged: {
                    console.log("GPUMiniWidget: Repeater model changed to", model)
                }

                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    radius: 12
                    color: Qt.rgba(1, 1, 1, 0.03)
                    border.color: Qt.rgba(1, 1, 1, 0.08)
                    border.width: 1

                    property var metrics: (typeof GPUService !== 'undefined' && GPUService) ? GPUService.getGPUMetrics(index) : null

                    // Neon glow for active GPUs
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -1
                        radius: parent.radius + 1
                        color: "transparent"
                        border.color: metrics && metrics.usage > 50 ? "#7C5CFF" : "transparent"
                        border.width: 1
                        opacity: metrics ? metrics.usage / 100 : 0
                        
                        Behavior on opacity {
                            NumberAnimation { duration: Theme.duration_fast }
                        }
                    }
                    
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacing_md
                        spacing: Theme.spacing_md
                        
                        // Vendor Icon
                        Rectangle {
                            Layout.preferredWidth: 48
                            Layout.preferredHeight: 48
                            radius: 8
                            color: metrics && metrics.vendor === "NVIDIA" ? "#76b900" : 
                                   metrics && metrics.vendor === "AMD" ? "#ed1c24" :
                                   metrics && metrics.vendor === "Intel" ? "#0071c5" : Theme.primary
                            
                            Label {
                                anchors.centerIn: parent
                                text: metrics && metrics.vendor === "NVIDIA" ? "🟢" : 
                                      metrics && metrics.vendor === "AMD" ? "🔴" :
                                      metrics && metrics.vendor === "Intel" ? "🔵" : "🎮"
                                font.pixelSize: 20
                            }
                        }
                        
                        // GPU Info
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            
                            Label {
                                text: metrics ? metrics.name : "GPU " + index
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.DemiBold
                                color: Theme.text
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            
                            RowLayout {
                                spacing: Theme.spacing_sm
                                
                                // Usage
                                Label {
                                    text: "Usage: " + (metrics ? metrics.usage.toFixed(1) + "%" : "0%")
                                    font.pixelSize: Theme.typography.body.size - 2
                                    color: metrics && metrics.usage > 80 ? "#fbbf24" : Theme.textSecondary
                                }
                                
                                Rectangle {
                                    width: 3
                                    height: 3
                                    radius: 1.5
                                    color: Theme.textSecondary
                                }
                                
                                // Temperature
                                Label {
                                    text: "Temp: " + (metrics && metrics.temperature > 0 ? metrics.temperature + "°C" : "N/A")
                                    font.pixelSize: Theme.typography.body.size - 2
                                    color: metrics && metrics.temperature > 75 ? "#ff6b6b" : 
                                           metrics && metrics.temperature > 60 ? "#fbbf24" : Theme.textSecondary
                                }
                                
                                Rectangle {
                                    width: 3
                                    height: 3
                                    radius: 1.5
                                    color: Theme.textSecondary
                                    visible: metrics && metrics.memoryTotal > 0
                                }
                                
                                // VRAM
                                Label {
                                    text: "VRAM: " + (metrics && metrics.memoryTotal > 0 ? 
                                                     (metrics.memoryUsed / 1024).toFixed(1) + "GB" : "N/A")
                                    font.pixelSize: Theme.typography.body.size - 2
                                    color: Theme.textSecondary
                                    visible: metrics && metrics.memoryTotal > 0
                                }
                            }
                        }
                        
                        // Usage Bar
                        Rectangle {
                            Layout.preferredWidth: 60
                            Layout.preferredHeight: 48
                            radius: 6
                            color: Qt.rgba(1, 1, 1, 0.05)
                            
                            Rectangle {
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                height: metrics ? (parent.height * metrics.usage / 100) : 0
                                radius: parent.radius
                                color: "#7C5CFF"
                                opacity: 0.7
                                
                                Behavior on height {
                                    NumberAnimation { duration: Theme.duration_medium }
                                }
                            }
                            
                            Label {
                                anchors.centerIn: parent
                                text: metrics ? metrics.usage.toFixed(0) + "%" : "0%"
                                font.pixelSize: Theme.typography.body.size - 2
                                font.weight: Font.Bold
                                color: Theme.text
                            }
                        }
                    }
                    
                    Component.onCompleted: {
                        metrics = (typeof GPUService !== 'undefined' && GPUService) ? GPUService.getGPUMetrics(index) : null
                    }
                }
            }
        }
        
        // View All Button
        Button {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            text: "View All GPUs →"
            
            background: Rectangle {
                radius: 8
                color: parent.hovered ? Qt.rgba(0.49, 0.36, 1.0, 0.3) : Qt.rgba(0.49, 0.36, 1.0, 0.15)
                border.color: "#7C5CFF"
                border.width: 1
                
                Behavior on color {
                    ColorAnimation { duration: Theme.duration_fast }
                }
            }
            
            contentItem: Label {
                text: parent.text
                font.pixelSize: Theme.typography.body.size
                font.weight: Font.DemiBold
                color: "#7C5CFF"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            
        onClicked: {
            // Navigate to GPU Monitoring page (index 2)
            if (typeof window !== 'undefined' && typeof sidebar !== 'undefined') {
                sidebar.setCurrentIndex(2)
            }
        }
    }
}    // Update when backend signals change
    Connections {
        target: (typeof GPUService !== 'undefined') ? GPUService : null

        function onGpuCountChanged(count) {
            console.log("GPU count changed:", count)
        }

        function onMetricsUpdated() {
            for (var i = 0; i < gpuRepeater.count; i++) {
                var card = gpuRepeater.itemAt(i)
                if (card && GPUService) {
                    card.metrics = GPUService.getGPUMetrics(i)
                }
            }
        }

        function onStatusChanged(status) {
            console.log("GPU service status:", status)
        }
    }
}
