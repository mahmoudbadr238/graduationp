import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../ui"

Item {
    id: root
    anchors.fill: parent
    
    // Currently selected GPU index
    property int selectedGpuIndex: 0
    
    // Check if GPUService is available
    property bool gpuServiceAvailable: typeof GPUService !== 'undefined' && GPUService !== null
    
    // Start GPU monitoring when page becomes visible (not on Component.onCompleted)
    onVisibleChanged: {
        if (visible && gpuServiceAvailable && !GPUService.isRunning()) {
            console.log("[GPUMonitor] Starting GPU monitoring (page visible)")
            GPUService.start(5000)  // 5 second interval for efficiency
        }
    }
    
    // Don't stop on destruction - keep running for quick return to page
    // The service will be cleaned up when the app exits
    
    // Get current GPU data
    property var currentGpu: gpuServiceAvailable && GPUService.metrics && GPUService.metrics.length > selectedGpuIndex ? 
                             GPUService.metrics[selectedGpuIndex] : null
    
    // History data
    property var usageHistory: gpuServiceAvailable ? GPUService.getHistory(selectedGpuIndex, "usage") : []
    property var tempHistory: gpuServiceAvailable ? GPUService.getHistory(selectedGpuIndex, "temperature") : []
    property var powerHistory: gpuServiceAvailable ? GPUService.getHistory(selectedGpuIndex, "power") : []
    property var memHistory: gpuServiceAvailable ? GPUService.getHistory(selectedGpuIndex, "memUsage") : []
    property var clockCoreHistory: gpuServiceAvailable ? GPUService.getHistory(selectedGpuIndex, "clockCore") : []
    property var clockMemHistory: gpuServiceAvailable ? GPUService.getHistory(selectedGpuIndex, "clockMem") : []
    property var fanHistory: gpuServiceAvailable ? GPUService.getHistory(selectedGpuIndex, "fanSpeed") : []
    
    // Refresh history when metrics update
    Connections {
        target: gpuServiceAvailable ? GPUService : null
        enabled: gpuServiceAvailable
        function onMetricsChanged() {
            if (gpuServiceAvailable) {
                root.usageHistory = GPUService.getHistory(selectedGpuIndex, "usage")
                root.tempHistory = GPUService.getHistory(selectedGpuIndex, "temperature")
                root.powerHistory = GPUService.getHistory(selectedGpuIndex, "power")
                root.memHistory = GPUService.getHistory(selectedGpuIndex, "memUsage")
                root.clockCoreHistory = GPUService.getHistory(selectedGpuIndex, "clockCore")
                root.clockMemHistory = GPUService.getHistory(selectedGpuIndex, "clockMem")
                root.fanHistory = GPUService.getHistory(selectedGpuIndex, "fanSpeed")
            }
        }
    }
    
    Rectangle {
        anchors.fill: parent
        color: ThemeManager.isDark() ? ThemeManager.darkBg : ThemeManager.lightBg
        
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            
            // ===== HEADER =====
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 70
                color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 24
                    anchors.rightMargin: 24
                    spacing: 16
                    
                    Column {
                        spacing: 4
                        
                        Text {
                            text: "GPU Monitor"
                            color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                            font.pixelSize: 24
                            font.bold: true
                        }
                        
                        Text {
                            text: "Real-time GPU monitoring like MSI Afterburner"
                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                            font.pixelSize: 11
                        }
                    }
                    
                    Item { Layout.fillWidth: true }
                    
                    // GPU selector
                    Rectangle {
                        width: 300
                        height: 36
                        radius: 6
                        color: ThemeManager.isDark() ? ThemeManager.darkElevated : ThemeManager.lightElevated
                        border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                        visible: gpuServiceAvailable && GPUService.gpuCount > 0
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 8
                            
                            Text {
                                text: currentGpu ? ("GPU " + selectedGpuIndex + ": " + currentGpu.name) : "No GPU"
                                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            
                            // Nav buttons for multiple GPUs
                            Row {
                                spacing: 4
                                visible: gpuServiceAvailable && GPUService.gpuCount > 1
                                
                                Rectangle {
                                    width: 24
                                    height: 24
                                    radius: 4
                                    color: selectedGpuIndex > 0 ? ThemeManager.accent : "transparent"
                                    opacity: selectedGpuIndex > 0 ? 1 : 0.3
                                    
                                    Text {
                                        anchors.centerIn: parent
                                        text: "◀"
                                        color: "white"
                                        font.pixelSize: 10
                                    }
                                    
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: selectedGpuIndex > 0
                                        onClicked: selectedGpuIndex--
                                    }
                                }
                                
                                Rectangle {
                                    width: 24
                                    height: 24
                                    radius: 4
                                    color: gpuServiceAvailable && selectedGpuIndex < GPUService.gpuCount - 1 ? ThemeManager.accent : "transparent"
                                    opacity: gpuServiceAvailable && selectedGpuIndex < GPUService.gpuCount - 1 ? 1 : 0.3
                                    
                                    Text {
                                        anchors.centerIn: parent
                                        text: "▶"
                                        color: "white"
                                        font.pixelSize: 10
                                    }
                                    
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: gpuServiceAvailable && selectedGpuIndex < GPUService.gpuCount - 1
                                        onClicked: selectedGpuIndex++
                                    }
                                }
                            }
                        }
                    }
                    
                    // Status
                    Row {
                        spacing: 6
                        
                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            anchors.verticalCenter: parent.verticalCenter
                            color: gpuServiceAvailable && GPUService.status === "running" ? ThemeManager.success : ThemeManager.warning
                        }
                        
                        Text {
                            text: gpuServiceAvailable ? GPUService.status : "init"
                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
            
            // ===== SCROLLABLE CONTENT =====
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth  // Prevents horizontal scroll
                
                Flickable {
                    contentWidth: width
                    contentHeight: contentColumn.height + 40
                    
                    ColumnLayout {
                        id: contentColumn
                        width: parent.width - 48
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: 20
                        spacing: 16
                        
                        // ===== GPU INFO CARD =====
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 90
                            color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                            radius: 10
                            border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                            
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 20
                                
                                // GPU Icon
                                Rectangle {
                                    width: 56
                                    height: 56
                                    radius: 10
                                    color: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.15)
                                    
                                    Text {
                                        anchors.centerIn: parent
                                        text: "🎮"
                                        font.pixelSize: 26
                                    }
                                }
                                
                                // GPU Info
                                Column {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    
                                    Text {
                                        text: currentGpu ? currentGpu.name : "No GPU Detected"
                                        color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                        font.pixelSize: 16
                                        font.bold: true
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }
                                    
                                    Text {
                                        text: currentGpu ? (currentGpu.vendor + " | Driver: " + (currentGpu.driverVersion || "N/A")) : ""
                                        color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                        font.pixelSize: 11
                                    }
                                    
                                    Text {
                                        text: currentGpu && currentGpu.vendor === "NVIDIA" && currentGpu.cudaVersion ? 
                                              ("CUDA " + currentGpu.cudaVersion + " | " + (currentGpu.perfState || "")) : ""
                                        color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                        font.pixelSize: 10
                                        visible: text !== ""
                                    }
                                }
                                
                                // Quick Stats
                                Row {
                                    spacing: 24
                                    
                                    Column {
                                        spacing: 2
                                        Text {
                                            text: "GPU"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                        }
                                        Text {
                                            text: currentGpu ? Math.round(currentGpu.usage) + "%" : "N/A"
                                            color: ThemeManager.accent
                                            font.pixelSize: 18
                                            font.bold: true
                                        }
                                    }
                                    
                                    Column {
                                        spacing: 2
                                        Text {
                                            text: "Temp"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                        }
                                        Text {
                                            text: currentGpu && currentGpu.tempC > 0 ? currentGpu.tempC + "°C" : "N/A"
                                            color: currentGpu && currentGpu.tempC > 80 ? ThemeManager.danger :
                                                   currentGpu && currentGpu.tempC > 60 ? ThemeManager.warning : ThemeManager.success
                                            font.pixelSize: 18
                                            font.bold: true
                                        }
                                    }
                                    
                                    Column {
                                        spacing: 2
                                        Text {
                                            text: "Power"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                        }
                                        Text {
                                            text: currentGpu && currentGpu.powerW > 0 ? Math.round(currentGpu.powerW) + "W" : "N/A"
                                            color: ThemeManager.warning
                                            font.pixelSize: 18
                                            font.bold: true
                                        }
                                    }
                                    
                                    Column {
                                        spacing: 2
                                        Text {
                                            text: "VRAM"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                        }
                                        Text {
                                            text: currentGpu ? (currentGpu.memUsedMB / 1024).toFixed(1) + " GB" : "N/A"
                                            color: ThemeManager.success
                                            font.pixelSize: 18
                                            font.bold: true
                                        }
                                    }
                                }
                            }
                        }
                        
                        // ===== METRICS GRID =====
                        Text {
                            text: "Detailed Metrics"
                            color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                            font.pixelSize: 14
                            font.bold: true
                            Layout.topMargin: 8
                        }
                        
                        // Row 1: Utilization
                        Row {
                            Layout.fillWidth: true
                            spacing: 12
                            
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "GPU Usage"
                                value: currentGpu ? currentGpu.usage.toFixed(1) + "%" : "N/A"
                                barValue: currentGpu ? currentGpu.usage / 100 : 0
                                accentColor: ThemeManager.accent
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Memory Ctrl"
                                value: currentGpu ? (currentGpu.memControllerUtil || 0).toFixed(1) + "%" : "N/A"
                                barValue: currentGpu ? (currentGpu.memControllerUtil || 0) / 100 : 0
                                accentColor: "#6366F1"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Video Encode"
                                value: currentGpu ? (currentGpu.encoderUtil || 0) + "%" : "N/A"
                                barValue: currentGpu ? (currentGpu.encoderUtil || 0) / 100 : 0
                                accentColor: "#8B5CF6"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Video Decode"
                                value: currentGpu ? (currentGpu.decoderUtil || 0) + "%" : "N/A"
                                barValue: currentGpu ? (currentGpu.decoderUtil || 0) / 100 : 0
                                accentColor: "#A78BFA"
                            }
                        }
                        
                        // Row 2: Clocks & Temps
                        Row {
                            Layout.fillWidth: true
                            spacing: 12
                            
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Core Clock"
                                value: currentGpu && currentGpu.clockMHz > 0 ? currentGpu.clockMHz + " MHz" : "N/A"
                                barValue: currentGpu && currentGpu.maxClockMHz > 0 ? currentGpu.clockMHz / currentGpu.maxClockMHz : 0
                                accentColor: "#F59E0B"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Memory Clock"
                                value: currentGpu && currentGpu.clockMemMHz > 0 ? currentGpu.clockMemMHz + " MHz" : "N/A"
                                barValue: currentGpu && currentGpu.maxClockMemMHz > 0 ? currentGpu.clockMemMHz / currentGpu.maxClockMemMHz : 0
                                accentColor: "#EAB308"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "GPU Temp"
                                value: currentGpu && currentGpu.tempC > 0 ? currentGpu.tempC + "°C" : "N/A"
                                barValue: currentGpu && currentGpu.tempC > 0 ? currentGpu.tempC / 100 : 0
                                accentColor: currentGpu && currentGpu.tempC > 80 ? ThemeManager.danger :
                                            currentGpu && currentGpu.tempC > 60 ? ThemeManager.warning : ThemeManager.success
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Hotspot"
                                value: currentGpu && currentGpu.tempHotspot > 0 ? currentGpu.tempHotspot + "°C" : "N/A"
                                barValue: currentGpu && currentGpu.tempHotspot > 0 ? currentGpu.tempHotspot / 110 : 0
                                accentColor: currentGpu && currentGpu.tempHotspot > 90 ? ThemeManager.danger :
                                            currentGpu && currentGpu.tempHotspot > 70 ? ThemeManager.warning : ThemeManager.success
                            }
                        }
                        
                        // Row 3: Power & Fan
                        Row {
                            Layout.fillWidth: true
                            spacing: 12
                            
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Power Draw"
                                value: currentGpu && currentGpu.powerW > 0 ? currentGpu.powerW.toFixed(0) + " W" : "N/A"
                                barValue: currentGpu && currentGpu.powerLimitW > 0 ? currentGpu.powerW / currentGpu.powerLimitW : 0
                                accentColor: "#EF4444"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "TDP %"
                                value: currentGpu && currentGpu.powerPercent > 0 ? currentGpu.powerPercent.toFixed(0) + "%" : "N/A"
                                barValue: currentGpu && currentGpu.powerPercent > 0 ? currentGpu.powerPercent / 120 : 0
                                accentColor: "#F87171"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Fan Speed"
                                value: currentGpu ? currentGpu.fanPercent + "%" : "N/A"
                                barValue: currentGpu ? currentGpu.fanPercent / 100 : 0
                                accentColor: "#06B6D4"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "Fan RPM"
                                value: currentGpu && currentGpu.fanRPM > 0 ? currentGpu.fanRPM + " RPM" : "N/A"
                                barValue: currentGpu && currentGpu.fanRPM > 0 ? currentGpu.fanRPM / 4000 : 0
                                accentColor: "#22D3EE"
                            }
                        }
                        
                        // Row 4: Memory & PCIe
                        Row {
                            Layout.fillWidth: true
                            spacing: 12
                            
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "VRAM Used"
                                value: currentGpu ? (currentGpu.memUsedMB / 1024).toFixed(2) + " GB" : "N/A"
                                barValue: currentGpu && currentGpu.memTotalMB > 0 ? currentGpu.memUsedMB / currentGpu.memTotalMB : 0
                                accentColor: "#10B981"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "VRAM Total"
                                value: currentGpu ? (currentGpu.memTotalMB / 1024).toFixed(0) + " GB" : "N/A"
                                barValue: 1
                                accentColor: "#34D399"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "VRAM %"
                                value: currentGpu ? currentGpu.memPercent.toFixed(1) + "%" : "N/A"
                                barValue: currentGpu ? currentGpu.memPercent / 100 : 0
                                accentColor: currentGpu && currentGpu.memPercent > 90 ? ThemeManager.danger :
                                            currentGpu && currentGpu.memPercent > 70 ? ThemeManager.warning : "#10B981"
                            }
                            MetricTile { 
                                width: (parent.width - 36) / 4
                                title: "PCIe"
                                value: currentGpu && currentGpu.pcieGen > 0 ? "Gen" + currentGpu.pcieGen + " x" + currentGpu.pcieWidth : "N/A"
                                barValue: 0
                                showBar: false
                                accentColor: "#94A3B8"
                            }
                        }
                        
                        // ===== CHARTS SECTION =====
                        Text {
                            text: "Real-Time Charts"
                            color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                            font.pixelSize: 14
                            font.bold: true
                            Layout.topMargin: 16
                        }
                        
                        // GPU Usage Chart
                        ChartCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            title: "GPU Usage"
                            currentValue: currentGpu ? currentGpu.usage.toFixed(1) + "%" : "N/A"
                            historyData: root.usageHistory
                            maxValue: 100
                            lineColor: ThemeManager.accent
                        }
                        
                        // Temperature Chart
                        ChartCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            title: "Temperature"
                            currentValue: currentGpu && currentGpu.tempC > 0 ? currentGpu.tempC + "°C" : "N/A"
                            historyData: root.tempHistory
                            maxValue: 100
                            lineColor: currentGpu && currentGpu.tempC > 75 ? ThemeManager.danger : ThemeManager.warning
                        }
                        
                        // Power Chart
                        ChartCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            title: "Power Draw"
                            currentValue: currentGpu && currentGpu.powerW > 0 ? currentGpu.powerW.toFixed(0) + "W" : "N/A"
                            historyData: root.powerHistory
                            maxValue: currentGpu && currentGpu.powerLimitW > 0 ? currentGpu.powerLimitW : 350
                            lineColor: "#EF4444"
                        }
                        
                        // Clock Speeds Chart
                        DualChartCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 200
                            title: "Clock Speeds"
                            label1: "Core"
                            label2: "Memory"
                            value1: currentGpu ? currentGpu.clockMHz + " MHz" : "N/A"
                            value2: currentGpu ? (currentGpu.clockMemMHz || 0) + " MHz" : "N/A"
                            historyData1: root.clockCoreHistory
                            historyData2: root.clockMemHistory
                            maxValue: Math.max(3000, currentGpu ? Math.max(currentGpu.maxClockMHz || 0, currentGpu.maxClockMemMHz || 0) : 3000)
                            lineColor1: "#F59E0B"
                            lineColor2: "#22C55E"
                        }
                        
                        // VRAM Usage Chart
                        ChartCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            title: "VRAM Usage"
                            currentValue: currentGpu ? currentGpu.memPercent.toFixed(1) + "%" : "N/A"
                            historyData: root.memHistory
                            maxValue: 100
                            lineColor: "#10B981"
                        }
                        
                        // Fan Speed Chart
                        ChartCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            title: "Fan Speed"
                            currentValue: currentGpu ? currentGpu.fanPercent + "%" : "N/A"
                            historyData: root.fanHistory
                            maxValue: 100
                            lineColor: "#06B6D4"
                        }
                        
                        Item { Layout.preferredHeight: 20 }
                    }
                }
            }
        }
    }
    
    // ===== METRIC TILE COMPONENT =====
    component MetricTile: Rectangle {
        id: tile
        height: 70
        color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
        radius: 8
        border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
        
        property string title: ""
        property string value: ""
        property real barValue: 0
        property color accentColor: ThemeManager.accent
        property bool showBar: true
        
        Column {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 6
            
            Text {
                text: tile.title
                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                font.pixelSize: 10
            }
            
            Text {
                text: tile.value
                color: tile.accentColor
                font.pixelSize: 16
                font.bold: true
            }
            
            Rectangle {
                width: parent.width
                height: 4
                radius: 2
                color: ThemeManager.isDark() ? "#1F2937" : "#E5E7EB"
                visible: tile.showBar
                
                Rectangle {
                    width: parent.width * Math.min(1, Math.max(0, tile.barValue))
                    height: parent.height
                    radius: 2
                    color: tile.accentColor
                    
                    Behavior on width { NumberAnimation { duration: 200 } }
                }
            }
        }
    }
    
    // ===== CHART CARD COMPONENT =====
    component ChartCard: Rectangle {
        id: chart
        color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
        radius: 10
        border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
        
        property string title: ""
        property string currentValue: ""
        property var historyData: []
        property real maxValue: 100
        property color lineColor: ThemeManager.accent
        
        Column {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 8
            
            Row {
                width: parent.width
                
                Text {
                    text: chart.title
                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                    font.pixelSize: 12
                    font.bold: true
                }
                
                Item { width: parent.width - parent.children[0].width - parent.children[2].width; height: 1 }
                
                Text {
                    text: chart.currentValue
                    color: chart.lineColor
                    font.pixelSize: 12
                    font.bold: true
                }
            }
            
            Canvas {
                id: chartCanvas
                width: parent.width
                height: parent.height - 30
                
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    
                    var data = chart.historyData
                    if (!data || data.length < 2) {
                        // Draw empty state
                        ctx.strokeStyle = ThemeManager.isDark() ? "#1F2937" : "#E5E7EB"
                        ctx.lineWidth = 1
                        for (var g = 0; g <= 4; g++) {
                            var gy = (height / 4) * g
                            ctx.beginPath()
                            ctx.moveTo(0, gy)
                            ctx.lineTo(width, gy)
                            ctx.stroke()
                        }
                        return
                    }
                    
                    // Draw grid
                    ctx.strokeStyle = ThemeManager.isDark() ? "#1F2937" : "#E5E7EB"
                    ctx.lineWidth = 1
                    for (var i = 0; i <= 4; i++) {
                        var y = (height / 4) * i
                        ctx.beginPath()
                        ctx.moveTo(0, y)
                        ctx.lineTo(width, y)
                        ctx.stroke()
                    }
                    
                    // Draw gradient fill
                    var gradient = ctx.createLinearGradient(0, 0, 0, height)
                    gradient.addColorStop(0, Qt.rgba(chart.lineColor.r, chart.lineColor.g, chart.lineColor.b, 0.3))
                    gradient.addColorStop(1, Qt.rgba(chart.lineColor.r, chart.lineColor.g, chart.lineColor.b, 0.0))
                    
                    ctx.fillStyle = gradient
                    ctx.beginPath()
                    ctx.moveTo(0, height)
                    
                    for (var j = 0; j < data.length; j++) {
                        var x = (width / Math.max(1, data.length - 1)) * j
                        var val = Math.min(data[j] || 0, chart.maxValue)
                        var yPos = height - (val / chart.maxValue) * height
                        ctx.lineTo(x, yPos)
                    }
                    ctx.lineTo(width, height)
                    ctx.closePath()
                    ctx.fill()
                    
                    // Draw line
                    ctx.strokeStyle = String(chart.lineColor)
                    ctx.lineWidth = 2
                    ctx.lineJoin = "round"
                    ctx.lineCap = "round"
                    ctx.beginPath()
                    
                    for (var k = 0; k < data.length; k++) {
                        var xk = (width / Math.max(1, data.length - 1)) * k
                        var valk = Math.min(data[k] || 0, chart.maxValue)
                        var yPosk = height - (valk / chart.maxValue) * height
                        
                        if (k === 0) ctx.moveTo(xk, yPosk)
                        else ctx.lineTo(xk, yPosk)
                    }
                    ctx.stroke()
                }
            }
        }
        
        Connections {
            target: chart
            function onHistoryDataChanged() { chartCanvas.requestPaint() }
        }
        
        Timer {
            interval: 500
            running: true
            repeat: true
            onTriggered: chartCanvas.requestPaint()
        }
    }
    
    // ===== DUAL CHART CARD COMPONENT =====
    component DualChartCard: Rectangle {
        id: dualChart
        color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
        radius: 10
        border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
        
        property string title: ""
        property string label1: ""
        property string label2: ""
        property string value1: ""
        property string value2: ""
        property var historyData1: []
        property var historyData2: []
        property real maxValue: 100
        property color lineColor1: "#F59E0B"
        property color lineColor2: "#22C55E"
        
        Column {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 8
            
            Row {
                width: parent.width
                spacing: 20
                
                Text {
                    text: dualChart.title
                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                    font.pixelSize: 12
                    font.bold: true
                }
                
                Item { width: 10; height: 1 }
                
                Row {
                    spacing: 6
                    Rectangle { width: 12; height: 3; radius: 1; color: dualChart.lineColor1; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: dualChart.label1 + ": " + dualChart.value1; color: dualChart.lineColor1; font.pixelSize: 10 }
                }
                
                Row {
                    spacing: 6
                    Rectangle { width: 12; height: 3; radius: 1; color: dualChart.lineColor2; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: dualChart.label2 + ": " + dualChart.value2; color: dualChart.lineColor2; font.pixelSize: 10 }
                }
            }
            
            Canvas {
                id: dualChartCanvas
                width: parent.width
                height: parent.height - 30
                
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    
                    // Draw grid
                    ctx.strokeStyle = ThemeManager.isDark() ? "#1F2937" : "#E5E7EB"
                    ctx.lineWidth = 1
                    for (var i = 0; i <= 4; i++) {
                        var y = (height / 4) * i
                        ctx.beginPath()
                        ctx.moveTo(0, y)
                        ctx.lineTo(width, y)
                        ctx.stroke()
                    }
                    
                    // Draw line 1
                    var data1 = dualChart.historyData1
                    if (data1 && data1.length >= 2) {
                        ctx.strokeStyle = String(dualChart.lineColor1)
                        ctx.lineWidth = 2
                        ctx.lineJoin = "round"
                        ctx.beginPath()
                        for (var j = 0; j < data1.length; j++) {
                            var x1 = (width / Math.max(1, data1.length - 1)) * j
                            var val1 = Math.min(data1[j] || 0, dualChart.maxValue)
                            var y1 = height - (val1 / dualChart.maxValue) * height
                            if (j === 0) ctx.moveTo(x1, y1)
                            else ctx.lineTo(x1, y1)
                        }
                        ctx.stroke()
                    }
                    
                    // Draw line 2
                    var data2 = dualChart.historyData2
                    if (data2 && data2.length >= 2) {
                        ctx.strokeStyle = String(dualChart.lineColor2)
                        ctx.lineWidth = 2
                        ctx.beginPath()
                        for (var k = 0; k < data2.length; k++) {
                            var x2 = (width / Math.max(1, data2.length - 1)) * k
                            var val2 = Math.min(data2[k] || 0, dualChart.maxValue)
                            var y2 = height - (val2 / dualChart.maxValue) * height
                            if (k === 0) ctx.moveTo(x2, y2)
                            else ctx.lineTo(x2, y2)
                        }
                        ctx.stroke()
                    }
                }
            }
        }
        
        Connections {
            target: dualChart
            function onHistoryData1Changed() { dualChartCanvas.requestPaint() }
            function onHistoryData2Changed() { dualChartCanvas.requestPaint() }
        }
        
        Timer {
            interval: 500
            running: true
            repeat: true
            onTriggered: dualChartCanvas.requestPaint()
        }
    }
}
