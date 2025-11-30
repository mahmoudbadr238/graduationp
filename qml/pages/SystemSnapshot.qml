import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import "../components"
import "../ui"

Item {
    id: root
    anchors.fill: parent
    
    // Track current tab index
    property int currentTabIndex: 0
    
    // Helper function to format network speed with BPS/KBPS/MBPS/GBPS scaling
    function formatNetworkSpeed(bps) {
        if (!bps || bps === 0) return "0 BPS"
        if (bps >= 1000000000) {  // >= 1 GBPS
            return (bps / 1000000000).toFixed(2) + " GBPS"
        } else if (bps >= 1000000) {  // >= 1 MBPS
            return (bps / 1000000).toFixed(2) + " MBPS"
        } else if (bps >= 1000) {  // >= 1 KBPS
            return (bps / 1000).toFixed(2) + " KBPS"
        } else {
            return bps.toFixed(0) + " BPS"
        }
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeManager.isDark() ? ThemeManager.darkBg : ThemeManager.lightBg

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 0
            spacing: 0

            // ===== HEADER =====
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 80
                color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 12

                    Column {
                        spacing: 4

                        Text {
                            text: "System Snapshot"
                            color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                            font.pixelSize: 26
                            font.bold: true
                        }

                        Text {
                            text: "Real-time system metrics and device status"
                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                            font.pixelSize: 12
                        }
                    }

                    Item { Layout.fillWidth: true }

                    RowLayout {
                        spacing: 8

                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            color: ThemeManager.success
                        }

                        Text {
                            text: "Live"
                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                            font.pixelSize: 12
                            font.weight: Font.Medium
                        }
                    }
                }
            }

            // ===== TAB BAR =====
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 24
                    anchors.rightMargin: 24
                    anchors.topMargin: 5
                    anchors.bottomMargin: 5
                    spacing: 12

                    Rectangle {
                        Layout.minimumWidth: 120
                        height: 44
                        radius: 8
                        color: root.currentTabIndex === 0 ? ThemeManager.accent : "transparent"
                        border.color: root.currentTabIndex === 0 ? ThemeManager.accent : (ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder)
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "System Overview"
                            color: root.currentTabIndex === 0 ? "#050814" : (ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText)
                            font.pixelSize: 12
                            font.bold: true
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.currentTabIndex = 0
                        }
                    }

                    Rectangle {
                        Layout.minimumWidth: 80
                        height: 44
                        radius: 8
                        color: root.currentTabIndex === 1 ? ThemeManager.accent : "transparent"
                        border.color: root.currentTabIndex === 1 ? ThemeManager.accent : (ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder)
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "GPU"
                            color: root.currentTabIndex === 1 ? "#050814" : (ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText)
                            font.pixelSize: 12
                            font.bold: true
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.currentTabIndex = 1
                        }
                    }

                    Rectangle {
                        Layout.minimumWidth: 100
                        height: 44
                        radius: 8
                        color: root.currentTabIndex === 2 ? ThemeManager.accent : "transparent"
                        border.color: root.currentTabIndex === 2 ? ThemeManager.accent : (ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder)
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Network"
                            color: root.currentTabIndex === 2 ? "#050814" : (ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText)
                            font.pixelSize: 12
                            font.bold: true
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.currentTabIndex = 2
                        }
                    }

                    Rectangle {
                        Layout.minimumWidth: 100
                        height: 44
                        radius: 8
                        color: root.currentTabIndex === 3 ? ThemeManager.accent : "transparent"
                        border.color: root.currentTabIndex === 3 ? ThemeManager.accent : (ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder)
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Security"
                            color: root.currentTabIndex === 3 ? "#050814" : (ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText)
                            font.pixelSize: 12
                            font.bold: true
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.currentTabIndex = 3
                        }
                    }

                    Item { Layout.fillWidth: true }
                }
            }

            // ===== CONTENT AREA =====
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: ThemeManager.isDark() ? ThemeManager.darkBg : ThemeManager.lightBg

                StackLayout {
                    id: tabBar
                    anchors.fill: parent
                    currentIndex: root.currentTabIndex

                    // ===== TAB 0: SYSTEM OVERVIEW =====
                    Flickable {
                        id: overviewFlickable
                        clip: true
                        contentWidth: overviewColumn.implicitWidth
                        contentHeight: overviewColumn.implicitHeight
                        ScrollBar.vertical: ScrollBar { }

                        ColumnLayout {
                            id: overviewColumn
                            width: overviewFlickable.width
                            anchors.margins: 24
                            spacing: 24

                            // CPU section
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: "CPU Metrics"
                                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                    font.pixelSize: 16
                                    font.bold: true
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    StatCard {
                                        Layout.fillWidth: true
                                        title: "Cores"
                                        value: SnapshotService ? SnapshotService.cpuCount : "N/A"
                                        subtitle: "physical cores"
                                    }

                                    StatCard {
                                        Layout.fillWidth: true
                                        title: "Threads"
                                        value: SnapshotService ? SnapshotService.cpuCountLogical : "N/A"
                                        subtitle: "logical threads"
                                    }

                                    StatCard {
                                        Layout.fillWidth: true
                                        title: "Frequency"
                                        value: SnapshotService ? (SnapshotService.cpuFrequency / 1000).toFixed(1) : "N/A"
                                        subtitle: "GHz base"
                                    }
                                }

                                StatCard {
                                    Layout.fillWidth: true
                                    title: "Processor Model"
                                    value: SnapshotService ? (SnapshotService.cpuName || "Unknown").substring(0, 40) : "N/A"
                                    subtitle: "CPU architecture"
                                    accentColor: ThemeManager.warning
                                }

                                // CPU History Chart with toggle
                                CPUDetailChartCard {
                                    Layout.fillWidth: true
                                    Layout.minimumHeight: 350
                                    title: "CPU Usage Over Time"
                                    historyData: SnapshotService ? SnapshotService.cpuChartData : []
                                    coreData: SnapshotService ? SnapshotService.cpuPerCore : []
                                    lineColor: ThemeManager.accent
                                }
                            }

                            // Memory section
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: "Memory Details"
                                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                    font.pixelSize: 16
                                    font.bold: true
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    StatCard {
                                        Layout.fillWidth: true
                                        title: "Total Memory"
                                        value: SnapshotService ? (SnapshotService.memoryTotal / (1024*1024*1024)).toFixed(1) : "N/A"
                                        subtitle: "GB"
                                    }

                                    StatCard {
                                        Layout.fillWidth: true
                                        title: "Used Memory"
                                        value: SnapshotService ? (SnapshotService.memoryUsed / (1024*1024*1024)).toFixed(1) : "N/A"
                                        subtitle: "GB in use"
                                        accentColor: ThemeManager.warning
                                    }

                                    StatCard {
                                        Layout.fillWidth: true
                                        title: "Available"
                                        value: SnapshotService ? (SnapshotService.memoryAvailable / (1024*1024*1024)).toFixed(1) : "N/A"
                                        subtitle: "GB free"
                                        accentColor: ThemeManager.success
                                    }

                                    StatCard {
                                        Layout.fillWidth: true
                                        title: "Usage %"
                                        value: SnapshotService ? Math.round(SnapshotService.memoryUsage) : "N/A"
                                        subtitle: "%"
                                        accentColor: SnapshotService && SnapshotService.memoryUsage > 80 ? ThemeManager.danger :
                                                   SnapshotService && SnapshotService.memoryUsage > 60 ? ThemeManager.warning :
                                                   ThemeManager.success
                                    }
                                }

                                // Memory History Chart
                                SimpleLineChartCard {
                                    Layout.fillWidth: true
                                    Layout.minimumHeight: 250
                                    title: "Memory Usage Over Time"
                                    historyData: SnapshotService ? SnapshotService.memoryChartData : []
                                    valueUnit: "%"
                                    lineColor: ThemeManager.warning
                                }
                            }

                            // Storage section
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: "Storage Details"
                                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                    font.pixelSize: 16
                                    font.bold: true
                                }

                                Repeater {
                                    model: SnapshotService ? SnapshotService.diskPartitions : []
                                    delegate: StorageCard {
                                        Layout.fillWidth: true
                                        driveName: modelData.displayName || modelData.device
                                        driveLetter: modelData.mountpoint || "/"
                                        total: modelData.total / (1024*1024*1024)
                                        used: modelData.used / (1024*1024*1024)
                                        percent: modelData.percent || 0
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true; Layout.preferredHeight: 24 }
                        }
                    }

                    // ===== TAB 1: GPU MONITOR (Full MSI Afterburner-style) =====
                    Item {
                        id: gpuMonitorTab
                        
                        // Currently selected GPU index
                        property int selectedGpuIndex: 0
                        
                        // Check if GPUService is available
                        property bool gpuServiceAvailable: typeof GPUService !== 'undefined' && GPUService !== null
                        
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
                            target: gpuMonitorTab.gpuServiceAvailable ? GPUService : null
                            enabled: gpuMonitorTab.gpuServiceAvailable
                            function onMetricsChanged() {
                                if (gpuMonitorTab.gpuServiceAvailable) {
                                    gpuMonitorTab.usageHistory = GPUService.getHistory(gpuMonitorTab.selectedGpuIndex, "usage")
                                    gpuMonitorTab.tempHistory = GPUService.getHistory(gpuMonitorTab.selectedGpuIndex, "temperature")
                                    gpuMonitorTab.powerHistory = GPUService.getHistory(gpuMonitorTab.selectedGpuIndex, "power")
                                    gpuMonitorTab.memHistory = GPUService.getHistory(gpuMonitorTab.selectedGpuIndex, "memUsage")
                                    gpuMonitorTab.clockCoreHistory = GPUService.getHistory(gpuMonitorTab.selectedGpuIndex, "clockCore")
                                    gpuMonitorTab.clockMemHistory = GPUService.getHistory(gpuMonitorTab.selectedGpuIndex, "clockMem")
                                    gpuMonitorTab.fanHistory = GPUService.getHistory(gpuMonitorTab.selectedGpuIndex, "fanSpeed")
                                }
                            }
                        }
                        
                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 0
                            
                            // GPU Header with selector
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 60
                                color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                                
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 16
                                    anchors.rightMargin: 16
                                    spacing: 16
                                    
                                    Column {
                                        spacing: 2
                                        Text {
                                            text: "GPU Monitor"
                                            color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                            font.pixelSize: 16
                                            font.bold: true
                                        }
                                        Text {
                                            text: "Real-time GPU monitoring"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                        }
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    // GPU selector
                                    Rectangle {
                                        width: 280
                                        height: 32
                                        radius: 6
                                        color: ThemeManager.isDark() ? ThemeManager.darkElevated : ThemeManager.lightElevated
                                        border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                                        visible: gpuMonitorTab.gpuServiceAvailable && GPUService.gpuCount > 0
                                        
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 10
                                            anchors.rightMargin: 10
                                            spacing: 6
                                            
                                            Text {
                                                text: "GPU:"
                                                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                font.pixelSize: 11
                                            }
                                            
                                            Text {
                                                Layout.fillWidth: true
                                                text: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.name : "No GPU"
                                                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                                font.pixelSize: 11
                                                font.bold: true
                                                elide: Text.ElideRight
                                            }
                                            
                                            Row {
                                                spacing: 4
                                                visible: gpuMonitorTab.gpuServiceAvailable && GPUService.gpuCount > 1
                                                
                                                Rectangle {
                                                    width: 22
                                                    height: 22
                                                    radius: 4
                                                    color: gpuMonitorTab.selectedGpuIndex > 0 ? ThemeManager.accent : (ThemeManager.isDark() ? "#374151" : "#D1D5DB")
                                                    
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "◀"
                                                        color: gpuMonitorTab.selectedGpuIndex > 0 ? "#050814" : (ThemeManager.isDark() ? "#6B7280" : "#9CA3AF")
                                                        font.pixelSize: 10
                                                    }
                                                    
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: if (gpuMonitorTab.selectedGpuIndex > 0) gpuMonitorTab.selectedGpuIndex--
                                                    }
                                                }
                                                
                                                Rectangle {
                                                    width: 22
                                                    height: 22
                                                    radius: 4
                                                    color: gpuMonitorTab.gpuServiceAvailable && gpuMonitorTab.selectedGpuIndex < GPUService.gpuCount - 1 ? ThemeManager.accent : (ThemeManager.isDark() ? "#374151" : "#D1D5DB")
                                                    
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "▶"
                                                        color: gpuMonitorTab.gpuServiceAvailable && gpuMonitorTab.selectedGpuIndex < GPUService.gpuCount - 1 ? "#050814" : (ThemeManager.isDark() ? "#6B7280" : "#9CA3AF")
                                                        font.pixelSize: 10
                                                    }
                                                    
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: if (gpuMonitorTab.gpuServiceAvailable && gpuMonitorTab.selectedGpuIndex < GPUService.gpuCount - 1) gpuMonitorTab.selectedGpuIndex++
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    
                                    // Status indicator
                                    Row {
                                        spacing: 6
                                        Rectangle {
                                            width: 8
                                            height: 8
                                            radius: 4
                                            color: gpuMonitorTab.gpuServiceAvailable && GPUService.status === "running" ? ThemeManager.success : ThemeManager.warning
                                        }
                                        Text {
                                            text: gpuMonitorTab.gpuServiceAvailable ? GPUService.status : "N/A"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                        }
                                    }
                                }
                            }
                            
                            // Scrollable content
                            Flickable {
                                id: gpuMonitorFlickable
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                contentWidth: gpuContentColumn.implicitWidth
                                contentHeight: gpuContentColumn.implicitHeight
                                ScrollBar.vertical: ScrollBar { }
                                
                                ColumnLayout {
                                    id: gpuContentColumn
                                    width: gpuMonitorFlickable.width
                                    spacing: 16
                                    
                                    Item { Layout.preferredHeight: 8 }
                                    
                                    // GPU Info Card
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        Layout.preferredHeight: 70
                                        radius: 10
                                        color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                        border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                                        
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 14
                                            spacing: 20
                                            
                                            Column {
                                                spacing: 2
                                                Text {
                                                    text: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.name : "No GPU detected"
                                                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                                    font.pixelSize: 14
                                                    font.bold: true
                                                }
                                                Text {
                                                    text: gpuMonitorTab.currentGpu ? "Driver: " + (gpuMonitorTab.currentGpu.driverVersion || "N/A") : ""
                                                    color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                    font.pixelSize: 10
                                                }
                                            }
                                            
                                            Item { Layout.fillWidth: true }
                                            
                                            Row {
                                                spacing: 24
                                                
                                                Column {
                                                    Text { text: "Usage"; color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted; font.pixelSize: 9 }
                                                    Text { text: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.usage.toFixed(1) + "%" : "N/A"; color: ThemeManager.accent; font.pixelSize: 16; font.bold: true }
                                                }
                                                Column {
                                                    Text { text: "Temp"; color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted; font.pixelSize: 9 }
                                                    Text { text: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempC > 0 ? gpuMonitorTab.currentGpu.tempC + "°C" : "N/A"; color: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempC > 75 ? ThemeManager.danger : ThemeManager.warning; font.pixelSize: 16; font.bold: true }
                                                }
                                                Column {
                                                    Text { text: "Power"; color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted; font.pixelSize: 9 }
                                                    Text { text: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.powerW > 0 ? gpuMonitorTab.currentGpu.powerW.toFixed(0) + "W" : "N/A"; color: "#EF4444"; font.pixelSize: 16; font.bold: true }
                                                }
                                                Column {
                                                    Text { text: "VRAM"; color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted; font.pixelSize: 9 }
                                                    Text { text: gpuMonitorTab.currentGpu ? (gpuMonitorTab.currentGpu.memUsedMB / 1024).toFixed(1) + " GB" : "N/A"; color: "#10B981"; font.pixelSize: 16; font.bold: true }
                                                }
                                            }
                                        }
                                    }
                                    
                                    // Metrics Section Header
                                    Text {
                                        text: "Real-Time Metrics"
                                        color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                        font.pixelSize: 13
                                        font.bold: true
                                        Layout.leftMargin: 16
                                    }
                                    
                                    // Metrics Grid - Row 1: Core Metrics
                                    Row {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        spacing: 10
                                        
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "GPU Usage"
                                            value: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.usage.toFixed(1) + "%" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.usage / 100 : 0
                                            accentColor: ThemeManager.accent
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "Core Clock"
                                            value: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.clockMHz + " MHz" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.maxClockMHz > 0 ? gpuMonitorTab.currentGpu.clockMHz / gpuMonitorTab.currentGpu.maxClockMHz : 0
                                            accentColor: "#F59E0B"
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "Memory Clock"
                                            value: gpuMonitorTab.currentGpu ? (gpuMonitorTab.currentGpu.clockMemMHz || 0) + " MHz" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.maxClockMemMHz > 0 ? (gpuMonitorTab.currentGpu.clockMemMHz || 0) / gpuMonitorTab.currentGpu.maxClockMemMHz : 0
                                            accentColor: "#22C55E"
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "SM Clock"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.clockSMMHz > 0 ? gpuMonitorTab.currentGpu.clockSMMHz + " MHz" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.maxClockMHz > 0 ? (gpuMonitorTab.currentGpu.clockSMMHz || 0) / gpuMonitorTab.currentGpu.maxClockMHz : 0
                                            accentColor: "#A855F7"
                                        }
                                    }
                                    
                                    // Row 2: Temperature
                                    Row {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        spacing: 10
                                        
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "GPU Temp"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempC > 0 ? gpuMonitorTab.currentGpu.tempC + "°C" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.tempC / 100 : 0
                                            accentColor: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempC > 80 ? ThemeManager.danger :
                                                        gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempC > 60 ? ThemeManager.warning : ThemeManager.success
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "Memory Temp"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempMemC > 0 ? gpuMonitorTab.currentGpu.tempMemC + "°C" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempMemC > 0 ? gpuMonitorTab.currentGpu.tempMemC / 100 : 0
                                            accentColor: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempMemC > 95 ? ThemeManager.danger :
                                                        gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempMemC > 80 ? ThemeManager.warning : ThemeManager.success
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "Hotspot"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempHotspot > 0 ? gpuMonitorTab.currentGpu.tempHotspot + "°C" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempHotspot > 0 ? gpuMonitorTab.currentGpu.tempHotspot / 100 : 0
                                            accentColor: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempHotspot > 90 ? ThemeManager.danger :
                                                        gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempHotspot > 70 ? ThemeManager.warning : ThemeManager.success
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "Voltage"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.voltageMV > 0 ? (gpuMonitorTab.currentGpu.voltageMV / 1000).toFixed(3) + " V" : "N/A"
                                            barValue: 0
                                            showBar: false
                                            accentColor: "#94A3B8"
                                        }
                                    }
                                    
                                    // Row 3: Power & Fan
                                    Row {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        spacing: 10
                                        
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "Power Draw"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.powerW > 0 ? gpuMonitorTab.currentGpu.powerW.toFixed(0) + " W" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.powerLimitW > 0 ? gpuMonitorTab.currentGpu.powerW / gpuMonitorTab.currentGpu.powerLimitW : 0
                                            accentColor: "#EF4444"
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "TDP %"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.powerPercent > 0 ? gpuMonitorTab.currentGpu.powerPercent.toFixed(0) + "%" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.powerPercent > 0 ? gpuMonitorTab.currentGpu.powerPercent / 120 : 0
                                            accentColor: "#F87171"
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "Fan Speed"
                                            value: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.fanPercent + "%" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.fanPercent / 100 : 0
                                            accentColor: "#06B6D4"
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "Fan RPM"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.fanRPM > 0 ? gpuMonitorTab.currentGpu.fanRPM + " RPM" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.fanRPM > 0 ? gpuMonitorTab.currentGpu.fanRPM / 4000 : 0
                                            accentColor: "#22D3EE"
                                        }
                                    }
                                    
                                    // Row 4: Memory & PCIe
                                    Row {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        spacing: 10
                                        
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "VRAM Used"
                                            value: gpuMonitorTab.currentGpu ? (gpuMonitorTab.currentGpu.memUsedMB / 1024).toFixed(2) + " GB" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.memTotalMB > 0 ? gpuMonitorTab.currentGpu.memUsedMB / gpuMonitorTab.currentGpu.memTotalMB : 0
                                            accentColor: "#10B981"
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "VRAM Total"
                                            value: gpuMonitorTab.currentGpu ? (gpuMonitorTab.currentGpu.memTotalMB / 1024).toFixed(0) + " GB" : "N/A"
                                            barValue: 1
                                            accentColor: "#34D399"
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "VRAM %"
                                            value: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.memPercent.toFixed(1) + "%" : "N/A"
                                            barValue: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.memPercent / 100 : 0
                                            accentColor: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.memPercent > 90 ? ThemeManager.danger :
                                                        gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.memPercent > 70 ? ThemeManager.warning : "#10B981"
                                        }
                                        GPUMetricTile { 
                                            width: (parent.width - 30) / 4
                                            title: "PCIe"
                                            value: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.pcieGen > 0 ? "Gen" + gpuMonitorTab.currentGpu.pcieGen + " x" + gpuMonitorTab.currentGpu.pcieWidth : "N/A"
                                            barValue: 0
                                            showBar: false
                                            accentColor: "#94A3B8"
                                        }
                                    }
                                    
                                    // Charts Section Header
                                    Text {
                                        text: "Real-Time Charts"
                                        color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                        font.pixelSize: 13
                                        font.bold: true
                                        Layout.leftMargin: 16
                                        Layout.topMargin: 8
                                    }
                                    
                                    // GPU Usage Chart
                                    GPUChartCard {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        Layout.preferredHeight: 160
                                        title: "GPU Usage"
                                        currentValue: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.usage.toFixed(1) + "%" : "N/A"
                                        historyData: gpuMonitorTab.usageHistory
                                        maxValue: 100
                                        lineColor: ThemeManager.accent
                                    }
                                    
                                    // Temperature Chart
                                    GPUChartCard {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        Layout.preferredHeight: 160
                                        title: "Temperature"
                                        currentValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempC > 0 ? gpuMonitorTab.currentGpu.tempC + "°C" : "N/A"
                                        historyData: gpuMonitorTab.tempHistory
                                        maxValue: 100
                                        lineColor: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.tempC > 75 ? ThemeManager.danger : ThemeManager.warning
                                    }
                                    
                                    // Power Chart
                                    GPUChartCard {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        Layout.preferredHeight: 160
                                        title: "Power Draw"
                                        currentValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.powerW > 0 ? gpuMonitorTab.currentGpu.powerW.toFixed(0) + "W" : "N/A"
                                        historyData: gpuMonitorTab.powerHistory
                                        maxValue: gpuMonitorTab.currentGpu && gpuMonitorTab.currentGpu.powerLimitW > 0 ? gpuMonitorTab.currentGpu.powerLimitW : 350
                                        lineColor: "#EF4444"
                                    }
                                    
                                    // Clock Speeds Chart (Dual)
                                    GPUDualChartCard {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        Layout.preferredHeight: 180
                                        title: "Clock Speeds"
                                        label1: "Core"
                                        label2: "Memory"
                                        value1: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.clockMHz + " MHz" : "N/A"
                                        value2: gpuMonitorTab.currentGpu ? (gpuMonitorTab.currentGpu.clockMemMHz || 0) + " MHz" : "N/A"
                                        historyData1: gpuMonitorTab.clockCoreHistory
                                        historyData2: gpuMonitorTab.clockMemHistory
                                        maxValue: Math.max(3000, gpuMonitorTab.currentGpu ? Math.max(gpuMonitorTab.currentGpu.maxClockMHz || 0, gpuMonitorTab.currentGpu.maxClockMemMHz || 0) : 3000)
                                        lineColor1: "#F59E0B"
                                        lineColor2: "#22C55E"
                                    }
                                    
                                    // VRAM Usage Chart
                                    GPUChartCard {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        Layout.preferredHeight: 160
                                        title: "VRAM Usage"
                                        currentValue: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.memPercent.toFixed(1) + "%" : "N/A"
                                        historyData: gpuMonitorTab.memHistory
                                        maxValue: 100
                                        lineColor: "#10B981"
                                    }
                                    
                                    // Fan Speed Chart
                                    GPUChartCard {
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 16
                                        Layout.rightMargin: 16
                                        Layout.preferredHeight: 160
                                        title: "Fan Speed"
                                        currentValue: gpuMonitorTab.currentGpu ? gpuMonitorTab.currentGpu.fanPercent + "%" : "N/A"
                                        historyData: gpuMonitorTab.fanHistory
                                        maxValue: 100
                                        lineColor: "#06B6D4"
                                    }
                                    
                                    Item { Layout.preferredHeight: 20 }
                                }
                            }
                        }
                    }

                    // ===== TAB 2: NETWORK =====
                    Flickable {
                        id: networkFlickable
                        clip: true
                        contentWidth: networkColumn.implicitWidth
                        contentHeight: networkColumn.implicitHeight
                        ScrollBar.vertical: ScrollBar { }

                        ColumnLayout {
                            id: networkColumn
                            width: networkFlickable.width
                            anchors.margins: 24
                            spacing: 24

                            Text {
                                text: "Network Throughput"
                                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                font.pixelSize: 16
                                font.bold: true
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                StatCard {
                                    Layout.fillWidth: true
                                    title: "Upload Speed"
                                    value: SnapshotService ? root.formatNetworkSpeed(SnapshotService.netUpBps) : "N/A"
                                    subtitle: ""
                                    accentColor: ThemeManager.success
                                }

                                StatCard {
                                    Layout.fillWidth: true
                                    title: "Download Speed"
                                    value: SnapshotService ? root.formatNetworkSpeed(SnapshotService.netDownBps) : "N/A"
                                    subtitle: ""
                                    accentColor: ThemeManager.warning
                                }
                            }

                            // Network History Chart
                            SimpleDualLineChartCard {
                                Layout.fillWidth: true
                                Layout.minimumHeight: 280
                                title: "Network Throughput Over Time"
                                // Keep data in BPS (bits per second) - formatValue will scale it
                                historyDataUp: {
                                    if (!SnapshotService || !SnapshotService.networkHistoryUp) return []
                                    return SnapshotService.networkHistoryUp
                                }
                                historyDataDown: {
                                    if (!SnapshotService || !SnapshotService.networkHistoryDown) return []
                                    return SnapshotService.networkHistoryDown
                                }
                                valueUnit: "BPS"
                                lineColorUp: ThemeManager.success
                                lineColorDown: ThemeManager.warning
                                labelUp: "Upload"
                                labelDown: "Download"
                            }

                            Text {
                                text: "Network Adapters"
                                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                font.pixelSize: 16
                                font.bold: true
                                Layout.topMargin: 12
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Repeater {
                                    model: SnapshotService ? SnapshotService.networkInterfaces : []

                                    NetworkAdapterCard {
                                        Layout.fillWidth: true
                                        adapterName: modelData.name || "Unknown"
                                        ipv4: modelData.ipv4 || "N/A"
                                        ipv6: modelData.ipv6 || ""
                                        mac: modelData.mac || "N/A"
                                        isUp: modelData.isUp ?? true
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 80
                                    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                    radius: 12
                                    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                                    border.width: 1
                                    visible: !SnapshotService || SnapshotService.networkInterfaces.length === 0

                                    Text {
                                        anchors.centerIn: parent
                                        text: "No network adapters detected"
                                        color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                        font.pixelSize: 12
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true; Layout.preferredHeight: 24 }
                        }
                    }

                    // ===== TAB 3: SECURITY (Simplified User-Friendly Design) =====
                    Flickable {
                        id: securityFlickable
                        clip: true
                        contentWidth: securityColumn.implicitWidth
                        contentHeight: securityColumn.implicitHeight
                        ScrollBar.vertical: ScrollBar { }

                        ColumnLayout {
                            id: securityColumn
                            width: securityFlickable.width
                            anchors.margins: 24
                            spacing: 20

                            // Helper properties for security info access
                            property var secInfo: SnapshotService && SnapshotService.securityInfo ? SnapshotService.securityInfo : ({})
                            property var simplified: secInfo.simplified || ({})
                            property var overall: simplified.overall || ({})
                            property var internet: simplified.internetProtection || ({})
                            property var updates: simplified.updates || ({})
                            property var device: simplified.deviceProtection || ({})
                            property var remote: simplified.remoteAndApps || ({})
                            property var raw: simplified.raw || ({})
                            property var tpmData: simplified.tpm || ({})

                            // ===== A. OVERALL SECURITY STATUS CARD =====
                            Rectangle {
                                id: overallCard
                                Layout.fillWidth: true
                                Layout.preferredHeight: 100
                                radius: 16
                                color: {
                                    if (securityColumn.overall.isGood) return "#10B98120"
                                    if (securityColumn.overall.isWarning) return "#F59E0B20"
                                    return "#EF444420"
                                }
                                border.color: {
                                    if (securityColumn.overall.isGood) return "#10B981"
                                    if (securityColumn.overall.isWarning) return "#F59E0B"
                                    return "#EF4444"
                                }
                                border.width: 2

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        advancedSection.expanded = !advancedSection.expanded
                                    }
                                }

                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    spacing: 16

                                    // Status icon
                                    Rectangle {
                                        width: 56
                                        height: 56
                                        radius: 28
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: {
                                            if (securityColumn.overall.isGood) return "#10B981"
                                            if (securityColumn.overall.isWarning) return "#F59E0B"
                                            return "#EF4444"
                                        }

                                        Text {
                                            anchors.centerIn: parent
                                            text: {
                                                if (securityColumn.overall.isGood) return "✓"
                                                if (securityColumn.overall.isWarning) return "!"
                                                return "✕"
                                            }
                                            color: "white"
                                            font.pixelSize: 28
                                            font.bold: true
                                        }
                                    }

                                    Column {
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 4

                                        Text {
                                            text: "Security status"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 12
                                        }

                                        Text {
                                            text: securityColumn.overall.status || "Checking..."
                                            color: {
                                                if (securityColumn.overall.isGood) return "#10B981"
                                                if (securityColumn.overall.isWarning) return "#F59E0B"
                                                return "#EF4444"
                                            }
                                            font.pixelSize: 24
                                            font.bold: true
                                        }

                                        Text {
                                            text: securityColumn.overall.detail || "Analyzing your security..."
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 12
                                        }
                                    }

                                    Item { width: 1; Layout.fillWidth: true }

                                    // Expand hint
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: advancedSection.expanded ? "▲" : "▼"
                                        color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                        font.pixelSize: 16
                                    }
                                }
                            }

                            // ===== B. FOUR MAIN PROTECTION CARDS =====
                            Text {
                                text: "Protection overview"
                                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                font.pixelSize: 14
                                font.bold: true
                                Layout.topMargin: 8
                            }

                            // Responsive grid for 4 cards
                            Flow {
                                id: mainCardsFlow
                                Layout.fillWidth: true
                                spacing: 12

                                property real cardWidth: {
                                    var availableWidth = securityColumn.width - 24
                                    var minWidth = 160
                                    var maxWidth = 200
                                    // Try to fit 4, then 2, then 1
                                    if (availableWidth >= (minWidth * 4 + spacing * 3)) {
                                        return (availableWidth - spacing * 3) / 4
                                    } else if (availableWidth >= (minWidth * 2 + spacing)) {
                                        return (availableWidth - spacing) / 2
                                    }
                                    return availableWidth
                                }

                                // Card 1: Internet Protection
                                Rectangle {
                                    width: mainCardsFlow.cardWidth
                                    height: 110
                                    radius: 12
                                    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 6

                                        Row {
                                            spacing: 8
                                            Text {
                                                text: "🛡️"
                                                font.pixelSize: 16
                                            }
                                            Text {
                                                text: "Internet protection"
                                                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                font.pixelSize: 11
                                                font.weight: Font.Medium
                                            }
                                        }

                                        Text {
                                            text: securityColumn.internet.status || "Checking"
                                            color: {
                                                if (securityColumn.internet.isGood) return "#10B981"
                                                if (securityColumn.internet.isWarning) return "#F59E0B"
                                                return "#EF4444"
                                            }
                                            font.pixelSize: 20
                                            font.bold: true
                                        }

                                        Text {
                                            text: securityColumn.internet.detail || ""
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                            width: parent.width
                                        }
                                    }

                                    // Status dot
                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 12
                                        color: {
                                            if (securityColumn.internet.isGood) return "#10B981"
                                            if (securityColumn.internet.isWarning) return "#F59E0B"
                                            return "#EF4444"
                                        }
                                    }
                                }

                                // Card 2: Updates
                                Rectangle {
                                    width: mainCardsFlow.cardWidth
                                    height: 110
                                    radius: 12
                                    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 6

                                        Row {
                                            spacing: 8
                                            Text {
                                                text: "🔄"
                                                font.pixelSize: 16
                                            }
                                            Text {
                                                text: "Updates"
                                                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                font.pixelSize: 11
                                                font.weight: Font.Medium
                                            }
                                        }

                                        Text {
                                            text: securityColumn.updates.status || "Checking"
                                            color: {
                                                if (securityColumn.updates.isGood) return "#10B981"
                                                if (securityColumn.updates.isWarning) return "#F59E0B"
                                                return "#EF4444"
                                            }
                                            font.pixelSize: 20
                                            font.bold: true
                                        }

                                        Text {
                                            text: securityColumn.updates.detail || ""
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                            width: parent.width
                                        }
                                    }

                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 12
                                        color: {
                                            if (securityColumn.updates.isGood) return "#10B981"
                                            if (securityColumn.updates.isWarning) return "#F59E0B"
                                            return "#EF4444"
                                        }
                                    }
                                }

                                // Card 3: Device Protection
                                Rectangle {
                                    width: mainCardsFlow.cardWidth
                                    height: 110
                                    radius: 12
                                    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 6

                                        Row {
                                            spacing: 8
                                            Text {
                                                text: "💻"
                                                font.pixelSize: 16
                                            }
                                            Text {
                                                text: "Device protection"
                                                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                font.pixelSize: 11
                                                font.weight: Font.Medium
                                            }
                                        }

                                        Text {
                                            text: securityColumn.device.status || "Checking"
                                            color: {
                                                if (securityColumn.device.isGood) return "#10B981"
                                                if (securityColumn.device.isWarning) return "#F59E0B"
                                                return "#EF4444"
                                            }
                                            font.pixelSize: 20
                                            font.bold: true
                                        }

                                        Text {
                                            text: securityColumn.device.detail || ""
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                            width: parent.width
                                        }
                                    }

                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 12
                                        color: {
                                            if (securityColumn.device.isGood) return "#10B981"
                                            if (securityColumn.device.isWarning) return "#F59E0B"
                                            return "#EF4444"
                                        }
                                    }
                                }

                                // Card 4: Remote & Apps
                                Rectangle {
                                    width: mainCardsFlow.cardWidth
                                    height: 110
                                    radius: 12
                                    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 6

                                        Row {
                                            spacing: 8
                                            Text {
                                                text: "🔒"
                                                font.pixelSize: 16
                                            }
                                            Text {
                                                text: "Remote & apps"
                                                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                font.pixelSize: 11
                                                font.weight: Font.Medium
                                            }
                                        }

                                        Text {
                                            text: securityColumn.remote.status || "Checking"
                                            color: {
                                                if (securityColumn.remote.isGood) return "#10B981"
                                                if (securityColumn.remote.isWarning) return "#F59E0B"
                                                return "#EF4444"
                                            }
                                            font.pixelSize: 20
                                            font.bold: true
                                        }

                                        Text {
                                            text: securityColumn.remote.detail || ""
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                            width: parent.width
                                        }
                                    }

                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 12
                                        color: {
                                            if (securityColumn.remote.isGood) return "#10B981"
                                            if (securityColumn.remote.isWarning) return "#F59E0B"
                                            return "#EF4444"
                                        }
                                    }
                                }
                            }

                            // ===== C. ADVANCED DETAILS (Collapsible) =====
                            Column {
                                id: advancedSection
                                Layout.fillWidth: true
                                spacing: 12
                                property bool expanded: false

                                // Header / Toggle
                                Rectangle {
                                    width: parent.width
                                    height: 44
                                    radius: 8
                                    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: advancedSection.expanded = !advancedSection.expanded
                                    }

                                    Row {
                                        anchors.fill: parent
                                        anchors.leftMargin: 16
                                        anchors.rightMargin: 16
                                        spacing: 8

                                        Text {
                                            text: advancedSection.expanded ? "▼" : "▶"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 12
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: "Advanced details"
                                            color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                            font.pixelSize: 13
                                            font.weight: Font.Medium
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Item { width: 1; Layout.fillWidth: true }

                                        Text {
                                            text: "For power users"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 11
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }

                                // Expandable content
                                Flow {
                                    id: advancedCardsFlow
                                    width: parent.width
                                    spacing: 12
                                    visible: advancedSection.expanded
                                    opacity: advancedSection.expanded ? 1 : 0

                                    Behavior on opacity { NumberAnimation { duration: 200 } }

                                    property real cardWidth: {
                                        var availableWidth = parent.width
                                        var minCardWidth = 170
                                        var maxCardWidth = 200
                                        var cardsPerRow = Math.max(1, Math.floor(availableWidth / (minCardWidth + spacing)))
                                        var calculatedWidth = (availableWidth - (cardsPerRow - 1) * spacing) / cardsPerRow
                                        return Math.min(maxCardWidth, Math.max(minCardWidth, calculatedWidth))
                                    }

                                    // Firewall
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "Firewall"
                                        value: securityColumn.raw.firewallEnabled ? "On" : "Off"
                                        isGood: securityColumn.raw.firewallEnabled === true
                                    }

                                    // Antivirus
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "Antivirus"
                                        value: securityColumn.raw.antivirusEnabled ? "On" : "Off"
                                        subtitle: securityColumn.raw.antivirusRealtime ? "Real-time active" : "Real-time off"
                                        isGood: securityColumn.raw.antivirusEnabled === true
                                        isWarning: securityColumn.raw.antivirusEnabled && !securityColumn.raw.antivirusRealtime
                                    }

                                    // Secure Boot
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "Secure Boot"
                                        value: securityColumn.raw.secureBoot || "N/A"
                                        isGood: securityColumn.raw.secureBoot === "Enabled"
                                        isNeutral: securityColumn.raw.secureBoot === "N/A"
                                    }

                                    // TPM - Fixed with proper detection
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "TPM"
                                        value: {
                                            if (securityColumn.tpmData.present) {
                                                var ver = securityColumn.tpmData.version || ""
                                                if (securityColumn.tpmData.enabled) {
                                                    return "Present" + (ver && ver !== "Unknown" ? " (" + ver + ")" : "")
                                                } else {
                                                    return "Disabled"
                                                }
                                            }
                                            return "Not found"
                                        }
                                        subtitle: securityColumn.tpmData.detail || ""
                                        isGood: securityColumn.tpmData.present && securityColumn.tpmData.enabled
                                        isWarning: securityColumn.tpmData.present && !securityColumn.tpmData.enabled
                                    }

                                    // Disk Encryption
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "Disk Encryption"
                                        value: securityColumn.raw.diskEncryption || "Unknown"
                                        subtitle: securityColumn.raw.diskEncryptionDetail || ""
                                        isGood: securityColumn.raw.diskEncryption === "Enabled"
                                        isNeutral: securityColumn.raw.diskEncryption === "NotAvailable"
                                    }

                                    // Windows Update
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "Windows Update"
                                        value: {
                                            var status = securityColumn.raw.windowsUpdateStatus || "Unknown"
                                            if (status === "UpToDate") return "Up to date"
                                            if (status === "PendingUpdates") return "Pending"
                                            if (status === "RestartRequired") return "Restart needed"
                                            return status
                                        }
                                        subtitle: {
                                            var lastInstall = securityColumn.raw.windowsUpdateLastInstall || ""
                                            if (lastInstall) {
                                                try {
                                                    var date = new Date(lastInstall)
                                                    return "Last: " + date.toLocaleDateString()
                                                } catch(e) {
                                                    return ""
                                                }
                                            }
                                            return ""
                                        }
                                        isGood: securityColumn.raw.windowsUpdateStatus === "UpToDate"
                                        isWarning: securityColumn.raw.windowsUpdateStatus === "PendingUpdates" || 
                                                   securityColumn.raw.windowsUpdateStatus === "RestartRequired"
                                    }

                                    // Remote Desktop
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "Remote Desktop"
                                        value: securityColumn.raw.remoteDesktopEnabled ? "On" : "Off"
                                        subtitle: securityColumn.raw.remoteDesktopEnabled ? 
                                                  (securityColumn.raw.remoteDesktopNla ? "NLA enabled" : "NLA off") : ""
                                        isGood: !securityColumn.raw.remoteDesktopEnabled
                                        isWarning: securityColumn.raw.remoteDesktopEnabled && securityColumn.raw.remoteDesktopNla
                                    }

                                    // Local Admins
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "Local Admins"
                                        value: (securityColumn.raw.adminAccountCount || 0) + " accounts"
                                        isGood: (securityColumn.raw.adminAccountCount || 0) <= 2
                                        isWarning: securityColumn.raw.adminAccountCount === 3
                                    }

                                    // UAC
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "UAC Level"
                                        value: securityColumn.raw.uacLevel || "Unknown"
                                        isGood: securityColumn.raw.uacLevel === "High" || securityColumn.raw.uacLevel === "Medium"
                                        isWarning: securityColumn.raw.uacLevel === "Low"
                                    }

                                    // SmartScreen
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "SmartScreen"
                                        value: securityColumn.raw.smartScreenEnabled ? "On" : "Off"
                                        isGood: securityColumn.raw.smartScreenEnabled === true
                                    }

                                    // Memory Integrity
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: "Memory Integrity"
                                        value: securityColumn.raw.memoryIntegrityEnabled ? "On" : "Off"
                                        isGood: securityColumn.raw.memoryIntegrityEnabled === true
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true; Layout.preferredHeight: 24 }
                        }
                    }
                }
            }
        }
    }
    
    // ===== GPU METRIC TILE COMPONENT =====
    component GPUMetricTile: Rectangle {
        id: tile
        height: 65
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
            anchors.margins: 8
            spacing: 4
            
            Text {
                text: tile.title
                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                font.pixelSize: 9
            }
            
            Text {
                text: tile.value
                color: tile.accentColor
                font.pixelSize: 14
                font.bold: true
            }
            
            Rectangle {
                width: parent.width
                height: 3
                radius: 1.5
                color: ThemeManager.isDark() ? "#1F2937" : "#E5E7EB"
                visible: tile.showBar
                
                Rectangle {
                    width: parent.width * Math.min(1, Math.max(0, tile.barValue))
                    height: parent.height
                    radius: 1.5
                    color: tile.accentColor
                    
                    Behavior on width { NumberAnimation { duration: 200 } }
                }
            }
        }
    }
    
    // ===== GPU CHART CARD COMPONENT =====
    component GPUChartCard: Rectangle {
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
            anchors.margins: 12
            spacing: 6
            
            Row {
                width: parent.width
                
                Text {
                    text: chart.title
                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                    font.pixelSize: 11
                    font.bold: true
                }
                
                Item { width: parent.width - parent.children[0].width - parent.children[2].width; height: 1 }
                
                Text {
                    text: chart.currentValue
                    color: chart.lineColor
                    font.pixelSize: 11
                    font.bold: true
                }
            }
            
            Canvas {
                id: chartCanvas
                width: parent.width
                height: parent.height - 24
                
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    
                    var data = chart.historyData
                    if (!data || data.length < 2) {
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
    
    // ===== GPU DUAL CHART CARD COMPONENT =====
    component GPUDualChartCard: Rectangle {
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
            anchors.margins: 12
            spacing: 6
            
            Row {
                width: parent.width
                spacing: 16
                
                Text {
                    text: dualChart.title
                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                    font.pixelSize: 11
                    font.bold: true
                }
                
                Item { width: 8; height: 1 }
                
                Row {
                    spacing: 4
                    Rectangle { width: 10; height: 2; radius: 1; color: dualChart.lineColor1; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: dualChart.label1 + ": " + dualChart.value1; color: dualChart.lineColor1; font.pixelSize: 9 }
                }
                
                Row {
                    spacing: 4
                    Rectangle { width: 10; height: 2; radius: 1; color: dualChart.lineColor2; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: dualChart.label2 + ": " + dualChart.value2; color: dualChart.lineColor2; font.pixelSize: 9 }
                }
            }
            
            Canvas {
                id: dualChartCanvas
                width: parent.width
                height: parent.height - 24
                
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
