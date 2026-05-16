import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import "../components"
import "../ui"

Item {
    id: root
    objectName: "systemSnapshotRoot"
    anchors.fill: parent
    
    // Track current tab index
    property int currentTabIndex: 0
    
    // Check if GPUService is available
    property bool gpuServiceAvailable: typeof GPUService !== 'undefined' && GPUService !== null
    
    // Platform detection for hiding Windows-only UI elements
    readonly property bool isLinux: (typeof Backend !== 'undefined' && Backend) ? Backend.isLinux : false
    
    // Start GPU service when switching to GPU tab (index 1)
    onCurrentTabIndexChanged: {
        if (currentTabIndex === 1 && gpuServiceAvailable && !GPUService.isRunning()) {
            GPUService.start(1000)
        }
    }

    // If GPUService registers after the GPU tab is already open, start it now.
    onGpuServiceAvailableChanged: {
        if (gpuServiceAvailable && currentTabIndex === 1 && !GPUService.isRunning()) {
            GPUService.start(1000)
        }
    }

    Component.onCompleted: {
        if (currentTabIndex === 1 && gpuServiceAvailable && !GPUService.isRunning()) {
            GPUService.start(1000)
        }
    }
    
    // Helper function to create a transparent version of a color
    function transparentColor(baseColor, alpha) {
        return Qt.rgba(baseColor.r, baseColor.g, baseColor.b, alpha)
    }
    
    // Status color helper - returns appropriate themed color based on status
    function statusColor(isGood, isWarning) {
        if (isGood) return ThemeManager.success
        if (isWarning) return ThemeManager.warning
        return ThemeManager.danger
    }
    
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

    RiskConfirmDialog {
        id: riskDialog

        onAcceptedFeature: function(featureId, newState) {
            if (typeof SecurityController !== "undefined" && SecurityController) {
                SecurityController.toggle_security_feature(featureId, newState)
            } else {
                console.warn("[Security] SecurityController not available")
            }
        }
    }

    function refreshSecuritySnapshot() {
        if (typeof SnapshotService !== "undefined" && SnapshotService) {
            SnapshotService.refreshSecurityInfo()
        }
    }

    Connections {
        target: (typeof SecurityController !== "undefined" && SecurityController) ? SecurityController : null

        function onFeature_state_updated(featureId, state) {
            if (featureId === "firewall") {
                securityColumn.firewallOverride = state
            } else if (featureId === "rdp") {
                securityColumn.rdpOverride = state
            } else if (featureId === "uac") {
                securityColumn.uacOverride = state
            }
        }

        function onFeatureToggled(_featureId, _enabled, _message) {
            refreshSecuritySnapshot()
            securityRefreshTimer.restart()
        }

        function onFeatureError(featureId, message) {
            console.warn("[Security] Toggle failed:", featureId, message)
        }
    }

    Timer {
        id: securityRefreshTimer
        interval: 1500
        repeat: false

        onTriggered: {
            refreshSecuritySnapshot()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 0
            spacing: 0

            // ===== HEADER =====
            Rectangle {
                Layout.fillWidth: true
                Layout.minimumHeight: 80
                implicitHeight: headerRow.implicitHeight + 48
                color: ThemeManager.panel()
                border.color: ThemeManager.border()
                border.width: 1

                RowLayout {
                    id: headerRow
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 12

                    Column {
                        spacing: 4

                        Text {
                            text: "System Snapshot"
                            color: ThemeManager.foreground()
                            font.pixelSize: ThemeManager.fontSize_h1
                            font.bold: true
                        }

                        Text {
                            text: "Real-time system metrics and device status"
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
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
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            font.weight: Font.Medium
                        }
                    }
                }
            }

            // ===== TAB BAR =====
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                color: ThemeManager.panel()
                border.color: ThemeManager.border()
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
                        border.color: root.currentTabIndex === 0 ? ThemeManager.accent : (ThemeManager.border())
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "System Overview"
                            color: root.currentTabIndex === 0 ? "#050814" : (ThemeManager.foreground())
                            font.pixelSize: ThemeManager.fontSize_small
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
                        border.color: root.currentTabIndex === 1 ? ThemeManager.accent : (ThemeManager.border())
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "GPU"
                            color: root.currentTabIndex === 1 ? "#050814" : (ThemeManager.foreground())
                            font.pixelSize: ThemeManager.fontSize_small
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
                        border.color: root.currentTabIndex === 2 ? ThemeManager.accent : (ThemeManager.border())
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Network"
                            color: root.currentTabIndex === 2 ? "#050814" : (ThemeManager.foreground())
                            font.pixelSize: ThemeManager.fontSize_small
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
                        border.color: root.currentTabIndex === 3 ? ThemeManager.accent : (ThemeManager.border())
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Security"
                            color: root.currentTabIndex === 3 ? "#050814" : (ThemeManager.foreground())
                            font.pixelSize: ThemeManager.fontSize_small
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
                color: ThemeManager.background()

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
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_h4
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
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_h4
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
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_h4
                                    font.bold: true
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    Text {
                                        text: "Focused volumes only"
                                        color: ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_small
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: SnapshotService && SnapshotService.hiddenDiskPartitions
                                              ? (SnapshotService.hiddenDiskPartitions.length + " hidden system mounts")
                                              : ""
                                        color: ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_caption
                                        visible: root.isLinux && SnapshotService && SnapshotService.hiddenDiskPartitions && SnapshotService.hiddenDiskPartitions.length > 0
                                    }

                                    StyledSwitch {
                                        visible: root.isLinux && SnapshotService
                                        checked: SnapshotService ? SnapshotService.showHiddenMounts : false
                                        text: "Show debug mounts"
                                        onToggled: {
                                            if (SnapshotService) {
                                                SnapshotService.showHiddenMounts = checked
                                            }
                                        }
                                    }
                                }

                                Repeater {
                                    model: SnapshotService ? SnapshotService.diskPartitions : []
                                    delegate: StorageCard {
                                        Layout.fillWidth: true
                                        driveName: modelData.displayName || modelData.device
                                        driveLetter: modelData.displayMount || modelData.mountpoint || "/"
                                        mountLabel: modelData.displayMount || modelData.mountpoint || "/"
                                        detail: modelData.detail || ""
                                        category: modelData.category || ""
                                        readOnly: modelData.isReadOnly || false
                                        usageAvailable: modelData.usageAvailable !== false
                                        total: modelData.total / (1024*1024*1024)
                                        used: modelData.used / (1024*1024*1024)
                                        percent: modelData.percent !== undefined && modelData.percent !== null ? modelData.percent : 0
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true; Layout.preferredHeight: 24 }
                        }
                    }

                    // ===== TAB 1: GPU MONITOR =====
                    GPUMonitor {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
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
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_h4
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
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_h4
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
                                    color: ThemeManager.panel()
                                    radius: 12
                                    border.color: ThemeManager.border()
                                    border.width: 1
                                    visible: !SnapshotService || SnapshotService.networkInterfaces.length === 0

                                    Text {
                                        anchors.centerIn: parent
                                        text: "No network adapters detected"
                                        color: ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_small
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
                            objectName: "securityColumn"
                            width: securityFlickable.width
                            anchors.margins: 24
                            spacing: 20

                            // Helper properties for security info access with null-safe chaining
                            property var secInfo: (SnapshotService && SnapshotService.securityInfo) ? SnapshotService.securityInfo : {}
                            property var simplified: (secInfo && secInfo.simplified) ? secInfo.simplified : {}
                            property var overall: (simplified && simplified.overall) ? simplified.overall : {status: "Loading...", detail: "Analyzing security...", isGood: false, isWarning: true}
                            property var internet: (simplified && simplified.internetProtection) ? simplified.internetProtection : {status: "Checking", isGood: false, isWarning: true}
                            property var updates: (simplified && simplified.updates) ? simplified.updates : {status: "Checking", isGood: false, isWarning: true}
                            property var device: (simplified && simplified.deviceProtection) ? simplified.deviceProtection : {status: "Checking", isGood: false, isWarning: true}
                            property var remote: (simplified && simplified.remoteAndApps) ? simplified.remoteAndApps : {status: "Checking", isGood: false, isWarning: true}
                            property var raw: (simplified && simplified.raw) ? simplified.raw : {}
                            property var capabilities: (raw && raw.capabilities) ? raw.capabilities : {}
                            property var providers: (secInfo && secInfo.providers) ? secInfo.providers : []
                            property var tpmData: (simplified && simplified.tpm) ? simplified.tpm : {}
                            readonly property bool securityControllerAvailable: (typeof SecurityController !== 'undefined') && SecurityController !== null

                            function supports(featureName) {
                                return capabilities && capabilities[featureName] === true
                            }

                            function canToggle(featureName) {
                                if (!securityControllerAvailable)
                                    return false
                                if (root.isLinux)
                                    return featureName === "firewall"
                                return featureName === "firewall" || featureName === "rdp" || featureName === "uac"
                            }

                            function cleanSecurityText(value) {
                                return (value || "").toString().replace(/\s+/g, " ").trim()
                            }

                            function primarySecurityText(value, fallback) {
                                var text = cleanSecurityText(value)
                                var marker = "Additional checks unavailable:"
                                var idx = text.indexOf(marker)
                                if (idx >= 0)
                                    text = text.substring(0, idx).trim()
                                text = text.replace(/[;,\.\s]+$/, "")
                                return text.length > 0 ? text : (fallback || "")
                            }

                            function secondarySecurityNote(value) {
                                var text = cleanSecurityText(value)
                                var marker = "Additional checks unavailable:"
                                var idx = text.indexOf(marker)
                                return idx >= 0 ? text.substring(idx).trim() : ""
                            }

                            readonly property string advancedCoverageNote: root.isLinux
                                ? "Showing verifiable Linux security controls."
                                : "Showing verifiable Windows security controls. Some advanced guards (Tamper, Credential, Device) are omitted."

                            // Backend-confirmed local overrides. These let the control cards
                            // reflect the successful toggle immediately, before the refreshed
                            // SnapshotService payload arrives.
                            // null = no override (use raw backend value)
                            property var firewallOverride: null
                            property var rdpOverride: null
                            property var uacOverride: null

                            // Effective state helpers that prefer override > backend
                            readonly property bool effectiveFirewall: firewallOverride !== null
                                ? firewallOverride
                                : (raw.firewallEnabled === true)
                            readonly property bool effectiveRdp: rdpOverride !== null
                                ? rdpOverride
                                : (raw.remoteDesktopEnabled === true)
                            readonly property bool effectiveUacOn: uacOverride !== null
                                ? uacOverride
                                : (raw.uacLevel === "High" || raw.uacLevel === "Medium" || raw.uacLevel === "Low")
                            readonly property string effectiveFirewallStatus: firewallOverride !== null
                                ? (firewallOverride ? "Enabled" : "Disabled")
                                : (raw.firewallStatus || "Unknown")
                            readonly property string effectiveRdpStatus: !root.isLinux && rdpOverride !== null
                                ? (rdpOverride ? "Enabled" : "Disabled")
                                : (raw.remoteDesktopStatus || "Unknown")
                            readonly property string effectiveUacLevel: {
                                if (uacOverride === false)
                                    return "Disabled"
                                if (uacOverride === true) {
                                    var currentLevel = raw.uacLevel || ""
                                    if (currentLevel === "High" || currentLevel === "Medium" || currentLevel === "Low")
                                        return currentLevel
                                    return "Enabled"
                                }
                                return raw.uacLevel || "Unknown"
                            }

                            // Clear overrides when SnapshotService delivers a fresh payload
                            // so the UI falls back to the real queried state.
                            onRawChanged: {
                                firewallOverride = null
                                rdpOverride = null
                                uacOverride = null
                            }

                            // ===== A. OVERALL SECURITY STATUS CARD =====
                            // Only show prominent banner for errors, subtle for warnings/good
                            Rectangle {
                                id: overallCard
                                Layout.fillWidth: true
                                Layout.preferredHeight: Math.max(securityColumn.overall.isGood ? 72 : 92, overallCardRow.implicitHeight + 32)
                                radius: 16
                                // More subtle appearance - no colored background for warnings (notification center handles alerts)
                                color: {
                                    if (!securityColumn.overall.isGood && !securityColumn.overall.isWarning) {
                                        // Error state - keep prominent red
                                        return root.transparentColor(root.statusColor(false, false), 0.13)
                                    }
                                    // Good or Warning - subtle panel color (notifications handle warnings)
                                    return ThemeManager.panel()
                                }
                                border.color: {
                                    if (!securityColumn.overall.isGood && !securityColumn.overall.isWarning) {
                                        return root.statusColor(false, false)  // Red for errors
                                    }
                                    if (securityColumn.overall.isGood) {
                                        return root.statusColor(true, false)  // Green for good
                                    }
                                    return ThemeManager.border()
                                }
                                border.width: securityColumn.overall.isGood ? 1 : 2

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        advancedSection.expanded = !advancedSection.expanded
                                    }
                                }

                                Row {
                                    id: overallCardRow
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 16

                                    // Status icon
                                    Rectangle {
                                        width: 48
                                        height: 48
                                        radius: 24
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: root.statusColor(securityColumn.overall.isGood, securityColumn.overall.isWarning)

                                        Text {
                                            anchors.centerIn: parent
                                            text: {
                                                if (securityColumn.overall.isGood) return "OK"
                                                if (securityColumn.overall.isWarning) return "!"
                                                return "X"
                                            }
                                            color: "white"
                                            font.pixelSize: ThemeManager.fontSize_h3
                                            font.bold: true
                                        }
                                    }

                                    Column {
                                        width: overallCard.width - 120
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 2

                                        Text {
                                            text: root.isLinux ? "Security posture" : "Security status"
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                        }

                                        Text {
                                            text: securityColumn.overall.status || "Checking..."
                                            color: root.statusColor(securityColumn.overall.isGood, securityColumn.overall.isWarning)
                                            font.pixelSize: ThemeManager.fontSize_h2
                                            font.bold: true
                                        }

                                        Text {
                                            text: securityColumn.overall.detail || "Analyzing your security..."
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            width: parent.width
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Item { width: 1; Layout.fillWidth: true }

                                    // Expand hint
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: advancedSection.expanded ? "^" : "v"
                                        color: ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_h4
                                    }
                                }
                            }

                            // ===== ADMIN PRIVILEGE INDICATOR =====
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: adminBannerRow.implicitHeight + 16
                                radius: 12
                                color: SnapshotService && SnapshotService.isAdmin 
                                       ? Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.12)
                                       : Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.12)
                                border.color: SnapshotService && SnapshotService.isAdmin ? ThemeManager.success : ThemeManager.warning
                                border.width: 1

                                RowLayout {
                                    id: adminBannerRow
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 12

                                    Rectangle {
                                        width: 24
                                        height: 24
                                        radius: 12
                                        color: SnapshotService && SnapshotService.isAdmin ? ThemeManager.success : ThemeManager.warning

                                        Text {
                                            anchors.centerIn: parent
                                            text: SnapshotService && SnapshotService.isAdmin ? "OK" : "!"
                                            color: "#FFFFFF"
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.bold: true
                                        }
                                    }

                                    Column {
                                        spacing: 2
                                        Layout.fillWidth: true

                                        Text {
                                            text: SnapshotService && SnapshotService.isAdmin 
                                                  ? (root.isLinux ? "Root Privileges Active" : "Admin Privileges Active")
                                                  : "Limited Privileges"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.bold: true
                                        }

                                        Text {
                                            text: SnapshotService && SnapshotService.isAdmin 
                                                  ? "Full visibility enabled. Some controls may be restricted by device policy."
                                                  : (root.isLinux ? "Run as root to enable all security checks and controls." : "Run as administrator to enable all security checks and controls.")
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            width: parent.width
                                            wrapMode: Text.WordWrap
                                        }
                                    }
                                }
                            }

                            // ===== B. FOUR MAIN PROTECTION CARDS =====
                            Text {
                                text: root.isLinux ? "Linux protection overview" : "Protection overview"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
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
                                    var minWidth = 192
                                    var maxWidth = 236
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
                                    id: internetSummaryCard
                                    width: mainCardsFlow.cardWidth
                                    height: Math.max(138, internetSummaryColumn.implicitHeight + 32)
                                    radius: 12
                                    color: ThemeManager.panel()
                                    border.color: ThemeManager.border()

                                    ColumnLayout {
                                        id: internetSummaryColumn
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 8

                                        Rectangle {
                                            Layout.alignment: Qt.AlignLeft
                                            implicitWidth: internetSummaryLabel.implicitWidth + 18
                                            implicitHeight: 24
                                            radius: 12
                                            color: root.transparentColor(root.statusColor(securityColumn.internet.isGood, securityColumn.internet.isWarning), 0.12)

                                            Text {
                                                id: internetSummaryLabel
                                                anchors.centerIn: parent
                                                text: "Internet protection"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_caption
                                                font.weight: Font.DemiBold
                                            }
                                        }

                                        Text {
                                            text: securityColumn.internet.status || "Checking"
                                            color: root.statusColor(securityColumn.internet.isGood, securityColumn.internet.isWarning)
                                            font.pixelSize: ThemeManager.fontSize_h2
                                            font.bold: true
                                            Layout.fillWidth: true
                                            maximumLineCount: 1
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: securityColumn.primarySecurityText(securityColumn.internet.detail, "Sentinel is still verifying internet-facing protections.")
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_caption
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: securityColumn.secondarySecurityNote(securityColumn.internet.detail)
                                            visible: text.length > 0
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                            opacity: 0.72
                                        }
                                    }

                                    // Status dot
                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 12
                                        color: root.statusColor(securityColumn.internet.isGood, securityColumn.internet.isWarning)
                                    }
                                }

                                // Card 2: Updates
                                Rectangle {
                                    id: updatesSummaryCard
                                    width: mainCardsFlow.cardWidth
                                    height: Math.max(138, updatesSummaryColumn.implicitHeight + 32)
                                    radius: 12
                                    color: ThemeManager.panel()
                                    border.color: ThemeManager.border()

                                    ColumnLayout {
                                        id: updatesSummaryColumn
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 8

                                        Rectangle {
                                            Layout.alignment: Qt.AlignLeft
                                            implicitWidth: updatesSummaryLabel.implicitWidth + 18
                                            implicitHeight: 24
                                            radius: 12
                                            color: root.transparentColor(root.statusColor(securityColumn.updates.isGood, securityColumn.updates.isWarning), 0.12)

                                            Text {
                                                id: updatesSummaryLabel
                                                anchors.centerIn: parent
                                                text: "Updates"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_caption
                                                font.weight: Font.DemiBold
                                            }
                                        }

                                        Text {
                                            text: securityColumn.updates.status || "Checking"
                                            color: root.statusColor(securityColumn.updates.isGood, securityColumn.updates.isWarning)
                                            font.pixelSize: ThemeManager.fontSize_h2
                                            font.bold: true
                                            Layout.fillWidth: true
                                            maximumLineCount: 1
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: securityColumn.primarySecurityText(securityColumn.updates.detail, "Update verification is still running.")
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_caption
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: securityColumn.secondarySecurityNote(securityColumn.updates.detail)
                                            visible: text.length > 0
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                            opacity: 0.72
                                        }
                                    }

                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 12
                                        color: root.statusColor(securityColumn.updates.isGood, securityColumn.updates.isWarning)
                                    }
                                }

                                // Card 3: Device Protection
                                Rectangle {
                                    id: deviceSummaryCard
                                    width: mainCardsFlow.cardWidth
                                    height: Math.max(138, deviceSummaryColumn.implicitHeight + 32)
                                    radius: 12
                                    color: ThemeManager.panel()
                                    border.color: ThemeManager.border()

                                    ColumnLayout {
                                        id: deviceSummaryColumn
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 8

                                        Rectangle {
                                            Layout.alignment: Qt.AlignLeft
                                            implicitWidth: deviceSummaryLabel.implicitWidth + 18
                                            implicitHeight: 24
                                            radius: 12
                                            color: root.transparentColor(root.statusColor(securityColumn.device.isGood, securityColumn.device.isWarning), 0.12)

                                            Text {
                                                id: deviceSummaryLabel
                                                anchors.centerIn: parent
                                                text: "Device protection"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_caption
                                                font.weight: Font.DemiBold
                                            }
                                        }

                                        Text {
                                            text: securityColumn.device.status || "Checking"
                                            color: root.statusColor(securityColumn.device.isGood, securityColumn.device.isWarning)
                                            font.pixelSize: ThemeManager.fontSize_h2
                                            font.bold: true
                                            Layout.fillWidth: true
                                            maximumLineCount: 1
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: securityColumn.primarySecurityText(securityColumn.device.detail, "Device-hardening checks are still being verified.")
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_caption
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: securityColumn.secondarySecurityNote(securityColumn.device.detail)
                                            visible: text.length > 0
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                            opacity: 0.72
                                        }
                                    }

                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 12
                                        color: root.statusColor(securityColumn.device.isGood, securityColumn.device.isWarning)
                                    }
                                }

                                // Card 4: Remote & Apps
                                Rectangle {
                                    id: remoteSummaryCard
                                    width: mainCardsFlow.cardWidth
                                    height: Math.max(138, remoteSummaryColumn.implicitHeight + 32)
                                    radius: 12
                                    color: ThemeManager.panel()
                                    border.color: ThemeManager.border()

                                    ColumnLayout {
                                        id: remoteSummaryColumn
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 8

                                        Rectangle {
                                            Layout.alignment: Qt.AlignLeft
                                            implicitWidth: remoteSummaryLabel.implicitWidth + 18
                                            implicitHeight: 24
                                            radius: 12
                                            color: root.transparentColor(root.statusColor(securityColumn.remote.isGood, securityColumn.remote.isWarning), 0.12)

                                            Text {
                                                id: remoteSummaryLabel
                                                anchors.centerIn: parent
                                                text: "Remote & apps"
                                                color: ThemeManager.muted()
                                                font.pixelSize: ThemeManager.fontSize_caption
                                                font.weight: Font.DemiBold
                                            }
                                        }

                                        Text {
                                            text: securityColumn.remote.status || "Checking"
                                            color: root.statusColor(securityColumn.remote.isGood, securityColumn.remote.isWarning)
                                            font.pixelSize: ThemeManager.fontSize_h2
                                            font.bold: true
                                            Layout.fillWidth: true
                                            maximumLineCount: 1
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: securityColumn.primarySecurityText(securityColumn.remote.detail, "Remote exposure and app-hardening checks are still loading.")
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_caption
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: securityColumn.secondarySecurityNote(securityColumn.remote.detail)
                                            visible: text.length > 0
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                            opacity: 0.72
                                        }
                                    }

                                    Rectangle {
                                        width: 8; height: 8; radius: 4
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 12
                                        color: root.statusColor(securityColumn.remote.isGood, securityColumn.remote.isWarning)
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
                                    color: ThemeManager.panel()
                                    border.color: ThemeManager.border()

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
                                            text: advancedSection.expanded ? "v" : ">"
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: "Advanced details"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            font.weight: Font.Medium
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Item { width: 1; Layout.fillWidth: true }

                                        Text {
                                            text: root.isLinux ? "Verified controls" : "Verified Windows controls"
                                            color: ThemeManager.muted()
                                            font.pixelSize: ThemeManager.fontSize_small
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }

                                Rectangle {
                                    width: parent.width
                                    visible: advancedSection.expanded
                                    implicitHeight: advancedCoverageText.implicitHeight + 16
                                    radius: 8
                                    color: "transparent"
                                    border.color: ThemeManager.border()
                                    border.width: 1

                                    Text {
                                        id: advancedCoverageText
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        text: securityColumn.advancedCoverageNote
                                        color: ThemeManager.muted()
                                        font.pixelSize: ThemeManager.fontSize_small
                                        wrapMode: Text.WordWrap
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
                                        var minCardWidth = 184
                                        var maxCardWidth = 220
                                        var cardsPerRow = Math.max(1, Math.floor(availableWidth / (minCardWidth + spacing)))
                                        var calculatedWidth = (availableWidth - (cardsPerRow - 1) * spacing) / cardsPerRow
                                        return Math.min(maxCardWidth, Math.max(minCardWidth, calculatedWidth))
                                    }

                                    // Firewall (toggleable)
                                    SecurityCard {
                                        objectName: "firewallSecurityCard"
                                        width: advancedCardsFlow.cardWidth
                                        title: "Firewall"
                                        value: {
                                            var status = securityColumn.effectiveFirewallStatus
                                            if (status === "Enabled") return "On"
                                            if (status === "Disabled") return "Off"
                                            if (status === "Requires Admin") return "Admin required"
                                            return status
                                        }
                                        subtitle: securityColumn.raw.firewallName || securityColumn.internet.detail || ""
                                        isGood: securityColumn.effectiveFirewallStatus === "Enabled"
                                        isWarning: securityColumn.effectiveFirewallStatus === "Disabled"
                                        isNeutral: securityColumn.effectiveFirewallStatus === "Requires Admin" || securityColumn.effectiveFirewallStatus === "Unknown"
                                        toggleable: securityColumn.canToggle("firewall")
                                                    && (securityColumn.effectiveFirewallStatus === "Enabled" || securityColumn.effectiveFirewallStatus === "Disabled")
                                        toggleChecked: securityColumn.effectiveFirewall
                                        onToggleRequested: function(newState) {
                                            riskDialog.show("firewall", newState)
                                        }
                                    }

                                    // Antivirus
                                    SecurityCard {
                                        width: advancedCardsFlow.cardWidth
                                        title: root.isLinux ? "Endpoint Scanner" : "Antivirus"
                                        value: {
                                            var status = securityColumn.raw.antivirusStatus || ""
                                            if (root.isLinux) {
                                                if (status) return status
                                                if (securityColumn.raw.antivirusRealtime === true) return "Realtime active"
                                                if (securityColumn.raw.antivirusEnabled === true) return "Scanner only"
                                                return "Unknown"
                                            }
                                            if (status === "On" || status === "Off") return status
                                            if (status === "Admin required") return "Admin required"
                                            return status || "Unknown"
                                        }
                                        subtitle: {
                                            var name = securityColumn.raw.antivirusName || "Unknown"
                                            return name
                                        }
                                        note: {
                                            if (securityColumn.raw.antivirusDetail)
                                                return securityColumn.raw.antivirusDetail
                                            if (securityColumn.raw.antivirusRealtime === true)
                                                return "Real-time protection active"
                                            if (!root.isLinux && securityColumn.raw.antivirusRealtime === false)
                                                return "Real-time protection is off"
                                            return ""
                                        }
                                        isGood: root.isLinux
                                                ? (securityColumn.raw.antivirusStatus === "Realtime active")
                                                : (securityColumn.raw.antivirusStatus === "On")
                                        isWarning: root.isLinux
                                                   ? (securityColumn.raw.antivirusStatus === "Scanner only")
                                                   : (securityColumn.raw.antivirusStatus === "Off"
                                                      || (securityColumn.raw.antivirusStatus === "On" && securityColumn.raw.antivirusRealtime === false))
                                        isNeutral: securityColumn.raw.antivirusStatus === "Unknown" || securityColumn.raw.antivirusStatus === "Admin required"
                                    }

                                    // Secure Boot
                                    SecurityCard {
                                        visible: securityColumn.supports("secureBoot")
                                        width: advancedCardsFlow.cardWidth
                                        title: "Secure Boot"
                                        value: securityColumn.raw.secureBoot || "Unknown"
                                        isGood: securityColumn.raw.secureBoot === "Enabled"
                                        isWarning: root.isLinux && securityColumn.raw.secureBoot === "Disabled"
                                        isNeutral: securityColumn.raw.secureBoot === "N/A" || securityColumn.raw.secureBoot === "Unknown"
                                    }

                                    // TPM (Windows-only)
                                    SecurityCard {
                                        visible: !root.isLinux && securityColumn.supports("tpm")
                                        width: advancedCardsFlow.cardWidth
                                        title: "TPM"
                                        value: {
                                            if (securityColumn.tpmData.present === true) {
                                                var ver = securityColumn.tpmData.version || ""
                                                if (securityColumn.tpmData.enabled) {
                                                    return "Present" + (ver && ver !== "Unknown" ? " (" + ver + ")" : "")
                                                } else {
                                                    return "Disabled"
                                                }
                                            }
                                            if (securityColumn.tpmData.present === false)
                                                return "Not found"
                                            return securityColumn.tpmData.status || "Unknown"
                                        }
                                        subtitle: securityColumn.tpmData.detail || ""
                                        isGood: (securityColumn.tpmData.present === true) && (securityColumn.tpmData.enabled === true)
                                        isWarning: (securityColumn.tpmData.present === true) && (securityColumn.tpmData.enabled !== true)
                                        isNeutral: securityColumn.tpmData.present !== true && securityColumn.tpmData.present !== false
                                    }

                                    // Disk Encryption (hidden on Linux - unreliable)
                                    SecurityCard {
                                        visible: securityColumn.supports("diskEncryption")
                                        width: advancedCardsFlow.cardWidth
                                        title: "Disk Encryption"
                                        value: securityColumn.raw.diskEncryption || "Unknown"
                                        subtitle: securityColumn.raw.diskEncryptionDetail || ""
                                        isGood: securityColumn.raw.diskEncryption === "Enabled"
                                        isWarning: securityColumn.raw.diskEncryption === "Not detected" || securityColumn.raw.diskEncryption === "Not Encrypted"
                                        isNeutral: securityColumn.raw.diskEncryption === "NotAvailable" || securityColumn.raw.diskEncryption === "Unknown"
                                    }

                                    // Windows Update (Windows-only)
                                    SecurityCard {
                                        visible: true
                                        width: advancedCardsFlow.cardWidth
                                        title: root.isLinux ? "Package Updates" : "Windows Update"
                                        value: {
                                            var status = securityColumn.raw.windowsUpdateStatus || "Unknown"
                                            if (status === "UpToDate") return "Up to date"
                                            if (status === "PendingUpdates") return "Pending"
                                            if (status === "RestartRequired") return "Restart needed"
                                            if (root.isLinux && status === "Unknown") return "Unavailable"
                                            return status
                                        }
                                        subtitle: {
                                            if (root.isLinux) {
                                                var manager = securityColumn.raw.linuxUpdateManager || ""
                                                var count = securityColumn.raw.linuxUpdatePendingCount
                                                if (manager && count !== undefined && count !== null && count >= 0) {
                                                    return manager + (count > 0 ? (" | " + count + " pending") : " | no pending packages")
                                                }
                                                if (manager) return manager
                                            }
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
                                        note: securityColumn.raw.windowsUpdateDetail || ""
                                        isGood: securityColumn.raw.windowsUpdateStatus === "UpToDate"
                                        isWarning: securityColumn.raw.windowsUpdateStatus === "PendingUpdates" || 
                                                   securityColumn.raw.windowsUpdateStatus === "RestartRequired"
                                    }

                                    // Remote Desktop (toggleable, Windows-only)
                                    SecurityCard {
                                        objectName: "rdpSecurityCard"
                                        visible: true
                                        width: advancedCardsFlow.cardWidth
                                        title: root.isLinux ? "Remote Access" : "Remote Desktop"
                                        value: root.isLinux
                                               ? (securityColumn.raw.remoteDesktopStatus || "Unknown")
                                               : (function() {
                                                     var status = securityColumn.effectiveRdpStatus
                                                     if (status === "Enabled") return "On"
                                                     if (status === "Disabled") return "Off"
                                                     return status
                                                 })()
                                        subtitle: root.isLinux
                                                  ? (securityColumn.raw.remoteDesktopDetail || securityColumn.remote.detail || "")
                                                  : (securityColumn.raw.remoteDesktopDetail
                                                     || (securityColumn.effectiveRdpStatus === "Enabled"
                                                        ? ((securityColumn.raw.remoteDesktopNla === true) ? "NLA enabled" : (securityColumn.raw.remoteDesktopNla === false ? "NLA off" : ""))
                                                        : ""))
                                        isGood: root.isLinux ? securityColumn.raw.remoteDesktopStatus === "Minimized" : securityColumn.effectiveRdpStatus === "Disabled"
                                        isWarning: root.isLinux ? securityColumn.raw.remoteDesktopStatus === "Exposed" : securityColumn.effectiveRdpStatus === "Enabled"
                                        isNeutral: securityColumn.effectiveRdpStatus === "Unknown"
                                        toggleable: !root.isLinux
                                                    && securityColumn.canToggle("rdp")
                                                    && (securityColumn.effectiveRdpStatus === "Enabled" || securityColumn.effectiveRdpStatus === "Disabled")
                                        toggleChecked: !root.isLinux ? securityColumn.effectiveRdp : false
                                        onToggleRequested: function(newState) {
                                            riskDialog.show("rdp", newState)
                                        }
                                    }

                                    // Local Admins (hidden on Linux - unreliable)
                                    SecurityCard {
                                        visible: root.isLinux
                                                 && securityColumn.supports("mandatoryAccessControl")
                                        width: advancedCardsFlow.cardWidth
                                        title: "MAC Enforcement"
                                        value: securityColumn.raw.linuxMandatoryAccessControl || "Unknown"
                                        subtitle: {
                                            var appArmor = securityColumn.raw.linuxAppArmor || "Unknown"
                                            var selinux = securityColumn.raw.linuxSELinux || "Unknown"
                                            return "AppArmor: " + appArmor + " | SELinux: " + selinux
                                        }
                                        isGood: securityColumn.raw.linuxMandatoryAccessControl === "Active"
                                        isWarning: securityColumn.raw.linuxMandatoryAccessControl === "Inactive"
                                        isNeutral: securityColumn.raw.linuxMandatoryAccessControl === undefined
                                    }

                                    SecurityCard {
                                        visible: !root.isLinux && securityColumn.supports("localAdmins")
                                        width: advancedCardsFlow.cardWidth
                                        title: "Local Admins"
                                        value: (securityColumn.raw.adminAccountCount === null || securityColumn.raw.adminAccountCount === undefined)
                                               ? "Unknown"
                                               : (securityColumn.raw.adminAccountCount + " accounts")
                                        subtitle: securityColumn.raw.adminAccountDetail || ""
                                        isGood: securityColumn.raw.adminAccountCount !== null
                                                && securityColumn.raw.adminAccountCount !== undefined
                                                && securityColumn.raw.adminAccountCount <= 2
                                        isWarning: securityColumn.raw.adminAccountCount === 3
                                        isNeutral: securityColumn.raw.adminAccountCount === null || securityColumn.raw.adminAccountCount === undefined
                                    }

                                    // UAC (toggleable, Windows-only)
                                    SecurityCard {
                                        objectName: "uacSecurityCard"
                                        visible: !root.isLinux && securityColumn.supports("uac")
                                        width: advancedCardsFlow.cardWidth
                                        title: "UAC Level"
                                        value: securityColumn.effectiveUacLevel
                                        subtitle: securityColumn.raw.uacDetail || ""
                                        isGood: securityColumn.effectiveUacLevel === "High" || securityColumn.effectiveUacLevel === "Medium" || securityColumn.effectiveUacLevel === "Enabled"
                                        isWarning: securityColumn.effectiveUacLevel === "Low" || securityColumn.effectiveUacLevel === "Disabled"
                                        isNeutral: securityColumn.effectiveUacLevel === "Unknown"
                                        toggleable: securityColumn.canToggle("uac")
                                                    && (securityColumn.effectiveUacLevel === "High"
                                                    || securityColumn.effectiveUacLevel === "Medium"
                                                    || securityColumn.effectiveUacLevel === "Low"
                                                    || securityColumn.effectiveUacLevel === "Disabled"
                                                    || securityColumn.effectiveUacLevel === "Enabled")
                                        toggleChecked: securityColumn.effectiveUacOn
                                        onToggleRequested: function(newState) {
                                            riskDialog.show("uac", newState)
                                        }
                                    }

                                    // SmartScreen (Windows-only)
                                    SecurityCard {
                                        visible: !root.isLinux && securityColumn.supports("smartScreen")
                                        width: advancedCardsFlow.cardWidth
                                        title: "SmartScreen"
                                        value: securityColumn.raw.smartScreenStatus || "Unknown"
                                        subtitle: securityColumn.raw.smartScreenDetail || ""
                                        isGood: securityColumn.raw.smartScreenStatus === "Enabled"
                                        isWarning: securityColumn.raw.smartScreenStatus === "Disabled"
                                        isNeutral: securityColumn.raw.smartScreenStatus === "Unknown"
                                    }

                                    // Memory Integrity (Windows-only)
                                    SecurityCard {
                                        visible: !root.isLinux && securityColumn.supports("memoryIntegrity")
                                        width: advancedCardsFlow.cardWidth
                                        title: "Memory Integrity"
                                        value: securityColumn.raw.memoryIntegrityStatus || "Unknown"
                                        subtitle: securityColumn.raw.memoryIntegrityDetail || ""
                                        isGood: securityColumn.raw.memoryIntegrityStatus === "Enabled"
                                        isWarning: securityColumn.raw.memoryIntegrityStatus === "Disabled" || securityColumn.raw.memoryIntegrityStatus === "Partial"
                                        isNeutral: securityColumn.raw.memoryIntegrityStatus === "Unknown"
                                    }
                                }

                                Column {
                                    width: parent.width
                                    spacing: 8
                                    visible: advancedSection.expanded && root.isLinux && securityColumn.providers.length > 0

                                    Text {
                                        text: "Provider diagnostics"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_small
                                        font.bold: true
                                    }

                                    Repeater {
                                        model: securityColumn.providers

                                        Rectangle {
                                            width: parent.width
                                            height: providerRow.implicitHeight + 16
                                            radius: 10
                                            color: ThemeManager.panel()
                                            border.color: ThemeManager.border()

                                            RowLayout {
                                                id: providerRow
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                spacing: 10

                                                Rectangle {
                                                    width: 8
                                                    height: 8
                                                    radius: 4
                                                    color: {
                                                        if (modelData.status === "ok") return ThemeManager.success
                                                        if (modelData.status === "warning") return ThemeManager.warning
                                                        if (modelData.status === "error") return ThemeManager.danger
                                                        return ThemeManager.muted()
                                                    }
                                                }

                                                Text {
                                                    text: modelData.name || "provider"
                                                    color: ThemeManager.foreground()
                                                    font.pixelSize: ThemeManager.fontSize_small
                                                    font.bold: true
                                                }

                                                Text {
                                                    text: modelData.detail || ""
                                                    color: ThemeManager.muted()
                                                    font.pixelSize: ThemeManager.fontSize_caption
                                                    Layout.fillWidth: true
                                                    wrapMode: Text.WordWrap
                                                }
                                            }
                                        }
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
}
