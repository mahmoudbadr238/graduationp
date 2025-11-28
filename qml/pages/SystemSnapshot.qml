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

                    // ===== TAB 1: GPU =====
                    Flickable {
                        id: gpuFlickable
                        clip: true
                        contentWidth: gpuColumn.implicitWidth
                        contentHeight: gpuColumn.implicitHeight
                        ScrollBar.vertical: ScrollBar { }

                        ColumnLayout {
                            id: gpuColumn
                            width: gpuFlickable.width
                            anchors.margins: 24
                            spacing: 24

                            Text {
                                text: "GPU Devices"
                                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                font.pixelSize: 16
                                font.bold: true
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: gpuRepeater.count > 0 ? gpuRepeater.height : 80
                                color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                                radius: 12
                                border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                                border.width: 1

                                ColumnLayout {
                                    width: parent.width
                                    anchors.margins: 14
                                    spacing: 12

                                    Repeater {
                                        id: gpuRepeater
                                        model: GPUService ? GPUService.metrics.length : 0

                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 120
                                            color: ThemeManager.isDark() ? ThemeManager.darkElevated : ThemeManager.lightElevated
                                            radius: 6
                                            border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                                            border.width: 1

                                            ColumnLayout {
                                                anchors.fill: parent
                                                anchors.margins: 14
                                                spacing: 8

                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 12

                                                    ColumnLayout {
                                                        Layout.fillWidth: true
                                                        spacing: 2

                                                        Text {
                                                            text: GPUService && index < GPUService.metrics.length ? 
                                                                  (GPUService.metrics[index].name || "GPU Device " + index) : "N/A"
                                                            color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                        }

                                                        Text {
                                                            text: "Active"
                                                            color: ThemeManager.success
                                                            font.pixelSize: 11
                                                        }
                                                    }

                                                    Rectangle {
                                                        width: 10
                                                        height: 10
                                                        radius: 5
                                                        color: ThemeManager.success
                                                    }
                                                }

                                                GridLayout {
                                                    Layout.fillWidth: true
                                                    columns: 3
                                                    columnSpacing: 12
                                                    rowSpacing: 4

                                                    Column {
                                                        Text {
                                                            text: "Usage"
                                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                            font.pixelSize: 10
                                                        }
                                                        Text {
                                                            text: GPUService && index < GPUService.metrics.length ? 
                                                                  Math.round(GPUService.metrics[index].usage || 0) + "%" : "N/A"
                                                            color: ThemeManager.accent
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                        }
                                                    }

                                                    Column {
                                                        Text {
                                                            text: "VRAM"
                                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                            font.pixelSize: 10
                                                        }
                                                        Text {
                                                            text: GPUService && index < GPUService.metrics.length ? 
                                                                  ((GPUService.metrics[index].memUsedMB || 0) / 1024).toFixed(1) + " GB" : "N/A"
                                                            color: ThemeManager.accent
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                        }
                                                    }

                                                    Column {
                                                        Text {
                                                            text: "Temp"
                                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                                            font.pixelSize: 10
                                                        }
                                                        Text {
                                                            text: GPUService && index < GPUService.metrics.length ? 
                                                                  (GPUService.metrics[index].tempC || 0) + "°C" : "N/A"
                                                            color: GPUService && GPUService.metrics[index] && 
                                                                   GPUService.metrics[index].tempC > 80 ? ThemeManager.danger :
                                                                   GPUService && GPUService.metrics[index] && 
                                                                   GPUService.metrics[index].tempC > 60 ? ThemeManager.warning :
                                                                   ThemeManager.success
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    Text {
                                        visible: gpuRepeater.count === 0
                                        text: "No GPU devices detected"
                                        color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                        font.pixelSize: 12
                                        Layout.alignment: Qt.AlignCenter
                                        Layout.topMargin: 20
                                        Layout.bottomMargin: 20
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true; Layout.preferredHeight: 24 }
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

                    // ===== TAB 3: SECURITY =====
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
                            spacing: 24

                            Text {
                                text: "Security Overview"
                                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                font.pixelSize: 16
                                font.bold: true
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 12
                                rowSpacing: 12

                                SecurityCard {
                                    Layout.fillWidth: true
                                    title: "Firewall Status"
                                    value: SnapshotService && SnapshotService.securityInfo ? 
                                           SnapshotService.securityInfo.firewallStatus || "Unknown" : "Unknown"
                                    isGood: SnapshotService && SnapshotService.securityInfo && 
                                           SnapshotService.securityInfo.firewallStatus === "Enabled"
                                }

                                SecurityCard {
                                    Layout.fillWidth: true
                                    title: "Antivirus Status"
                                    value: SnapshotService && SnapshotService.securityInfo ? 
                                           SnapshotService.securityInfo.antivirus || "Unknown" : "Unknown"
                                    isGood: true
                                }

                                SecurityCard {
                                    Layout.fillWidth: true
                                    title: "Secure Boot"
                                    value: SnapshotService && SnapshotService.securityInfo ? 
                                           SnapshotService.securityInfo.secureBoot || "Unknown" : "Unknown"
                                    isGood: SnapshotService && SnapshotService.securityInfo && 
                                           SnapshotService.securityInfo.secureBoot === "Enabled"
                                }

                                SecurityCard {
                                    Layout.fillWidth: true
                                    title: "TPM Status"
                                    value: SnapshotService && SnapshotService.securityInfo ? 
                                           SnapshotService.securityInfo.tpmPresent || "Unknown" : "Unknown"
                                    isGood: SnapshotService && SnapshotService.securityInfo && 
                                           SnapshotService.securityInfo.tpmPresent === "Present"
                                }
                            }

                            Item { Layout.fillHeight: true; Layout.preferredHeight: 24 }
                        }
                    }
                }
            }
        }
    }
}


