import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../ui"
import "../components"

Item {
    id: root
    anchors.fill: parent
    
    // ============================================
    // STATE PROPERTIES
    // ============================================
    property int currentTab: 0  // 0 = File Scan, 1 = URL Check
    
    // File scan state
    property bool fileScanningInProgress: false
    property string fileScanStage: ""
    property var fileScanResult: null
    property string selectedFilePath: ""
    property bool useSandbox: true  // Default to true for integrated sandbox
    property bool blockNetwork: true  // Block network in sandbox
    property int sandboxTimeout: 30  // Seconds
    
    // URL check state (VirusTotal-like)
    property bool urlCheckingInProgress: false
    property string urlScanStage: ""
    property int urlScanProgressValue: 0
    property var urlCheckResult: null
    property bool useUrlSandbox: false  // Run sandbox detonation
    property bool blockDownloads: true  // Block downloads in sandbox
    property bool blockPrivateIPs: true // Block private IP URLs
    
    // URL sandbox availability
    property bool urlSandboxAvailable: false
    property string urlSandboxStatus: ""
    
    // Sandbox availability (integrated sandbox)
    property bool integratedSandboxAvailable: false
    property string integratedSandboxStatus: ""
    
    // Legacy sandbox (VirtualBox - deprecated)
    property bool sandboxAvailable: false
    property var sandboxMethods: []
    
    // ============================================
    // LIFECYCLE
    // ============================================
    Component.onCompleted: {
        // Check integrated sandbox availability (bundled with app)
        if (typeof Backend !== "undefined") {
            integratedSandboxAvailable = Backend.integratedSandboxAvailable()
            integratedSandboxStatus = Backend.integratedSandboxStatus()
            
            // URL sandbox availability (WebView2)
            urlSandboxAvailable = Backend.urlSandboxAvailable()
            urlSandboxStatus = Backend.urlSandboxStatus()
            
            // Legacy sandbox check (VirtualBox)
            sandboxAvailable = Backend.sandboxAvailable()
            sandboxMethods = Backend.sandboxMethods()
        }
    }
    
    // ============================================
    // FILE DIALOG
    // ============================================
    FileDialog {
        id: fileDialog
        title: "Select file to scan"
        nameFilters: ["All files (*)"]
        onAccepted: {
            var path = selectedFile.toString()
            // Remove file:/// prefix
            if (path.startsWith("file:///")) {
                path = path.substring(8)
            }
            // Handle Windows paths
            if (Qt.platform.os === "windows" && path.charAt(0) === '/') {
                path = path.substring(1)
            }
            selectedFilePath = path
            filePathInput.text = path
        }
    }
    
    // ============================================
    // BACKEND CONNECTIONS
    // ============================================
    Connections {
        target: Backend || null
        enabled: target !== null
        
        // Legacy local scan signals
        function onLocalScanStarted() {
            fileScanningInProgress = true
            fileScanResult = null
        }
        
        function onLocalScanProgress(stage) {
            fileScanStage = stage
        }
        
        function onLocalScanFinished(result) {
            fileScanningInProgress = false
            fileScanStage = ""
            fileScanResult = result
        }
        
        // Integrated sandbox signals (new)
        function onIntegratedSandboxStarted() {
            fileScanningInProgress = true
            fileScanResult = null
        }
        
        function onIntegratedSandboxProgress(stage) {
            fileScanStage = stage
        }
        
        function onIntegratedSandboxFinished(result) {
            fileScanningInProgress = false
            fileScanStage = ""
            fileScanResult = result
        }
        
        // URL scan signals (VirusTotal-like)
        function onUrlScanStarted() {
            urlCheckingInProgress = true
            urlCheckResult = null
            urlScanStage = ""
            urlScanProgressValue = 0
        }
        
        function onUrlScanProgress(stage, progress) {
            urlScanStage = stage
            urlScanProgressValue = progress
        }
        
        function onUrlScanFinished(result) {
            urlCheckingInProgress = false
            urlScanStage = ""
            urlScanProgressValue = 100
            urlCheckResult = result
        }
        
        function onLocalUrlCheckFinished(result) {
            urlCheckingInProgress = false
            urlCheckResult = result
        }
    }
    
    // ============================================
    // HELPER FUNCTIONS
    // ============================================
    function getVerdictColor(verdict) {
        if (!verdict) return ThemeManager.muted()
        switch(verdict.toLowerCase()) {
            case "malicious": return ThemeManager.danger
            case "likely_malicious": return ThemeManager.danger
            case "suspicious": return ThemeManager.warning
            case "safe": return ThemeManager.success
            default: return ThemeManager.foreground()
        }
    }
    
    function getVerdictIcon(verdict) {
        if (!verdict) return "❓"
        switch(verdict.toLowerCase()) {
            case "malicious": return "⛔"
            case "likely_malicious": return "🚨"
            case "suspicious": return "⚠️"
            case "safe": return "✅"
            default: return "❓"
        }
    }
    
    function getVerdictLabel(verdict) {
        if (!verdict) return "Unknown"
        switch(verdict.toLowerCase()) {
            case "malicious": return "MALICIOUS"
            case "likely_malicious": return "Likely Malicious"
            case "suspicious": return "Suspicious"
            case "safe": return "Safe"
            default: return verdict
        }
    }
    
    function getScoreColor(score) {
        if (score >= 80) return ThemeManager.danger
        if (score >= 50) return "#ff6b35"  // Orange-red
        if (score >= 20) return ThemeManager.warning
        return ThemeManager.success
    }
    
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + " B"
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB"
        return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB"
    }
    
    function startFileScan() {
        if (!selectedFilePath || selectedFilePath.length === 0) {
            if (Backend) Backend.toast("warning", "Please select a file first")
            return
        }
        
        fileScanResult = null
        if (Backend) {
            // Use integrated sandbox (bundled, no VirtualBox needed)
            Backend.runIntegratedScan(selectedFilePath, useSandbox, blockNetwork, sandboxTimeout)
        }
    }
    
    function startUrlCheck() {
        var url = urlInput.text.trim()
        if (!url || url.length === 0) {
            if (Backend) Backend.toast("warning", "Please enter a URL first")
            return
        }
        
        urlCheckResult = null
        urlCheckingInProgress = true
        urlScanStage = "Initializing..."
        urlScanProgressValue = 0
        
        if (Backend) {
            if (useUrlSandbox && urlSandboxAvailable) {
                // Run full sandbox scan
                Backend.scanUrlSandbox(url, blockDownloads, blockPrivateIPs, true, 30)
            } else {
                // Run static scan only
                Backend.scanUrlStatic(url, blockPrivateIPs, true, 30)
            }
        }
    }
    
    function cancelUrlCheck() {
        if (Backend) {
            Backend.cancelUrlScan()
        }
        urlCheckingInProgress = false
        urlScanStage = ""
        urlScanProgressValue = 0
    }
    
    function getSeverityColor(severity) {
        switch(severity) {
            case "critical": return ThemeManager.danger
            case "high": return "#ff4444"
            case "medium": return ThemeManager.warning
            case "low": return ThemeManager.info
            default: return ThemeManager.muted()
        }
    }
    
    function openReport(path) {
        if (Backend && path) {
            Backend.openReportFolder(path)
        }
    }
    
    // ============================================
    // MAIN LAYOUT
    // ============================================
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_lg
        spacing: Theme.spacing_lg
        
        // Page Title
        Text {
            text: "🔍 Local Scan Tool"
            font.pixelSize: 28
            font.bold: true
            color: ThemeManager.foreground()
        }
        
        Text {
            text: "100% Offline Security Analysis - No Network Required"
            font.pixelSize: 13
            color: ThemeManager.muted()
            Layout.bottomMargin: Theme.spacing_sm
        }
        
        // Tab Bar
        RowLayout {
            Layout.fillWidth: true
            spacing: 0
            
            // File Scan Tab
            Rectangle {
                Layout.preferredWidth: 150
                height: 44
                color: currentTab === 0 ? ThemeManager.primary : ThemeManager.surface()
                radius: 8
                
                Rectangle {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 8
                    color: parent.color
                }
                
                RowLayout {
                    anchors.centerIn: parent
                    spacing: 8
                    
                    Text {
                        text: "📁"
                        font.pixelSize: 16
                    }
                    
                    Text {
                        text: "File Scan"
                        color: currentTab === 0 ? "#FFFFFF" : ThemeManager.foreground()
                        font.pixelSize: 14
                        font.bold: currentTab === 0
                    }
                }
                
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: currentTab = 0
                }
            }
            
            // URL Check Tab
            Rectangle {
                Layout.preferredWidth: 150
                height: 44
                color: currentTab === 1 ? ThemeManager.primary : ThemeManager.surface()
                radius: 8
                
                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 8
                    color: parent.color
                }
                
                RowLayout {
                    anchors.centerIn: parent
                    spacing: 8
                    
                    Text {
                        text: "🌐"
                        font.pixelSize: 16
                    }
                    
                    Text {
                        text: "URL Check"
                        color: currentTab === 1 ? "#FFFFFF" : ThemeManager.foreground()
                        font.pixelSize: 14
                        font.bold: currentTab === 1
                    }
                }
                
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: currentTab = 1
                }
            }
            
            Item { Layout.fillWidth: true }
        }
        
        // Content Area
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: currentTab
            
            // ========================================
            // FILE SCAN TAB
            // ========================================
            Item {
                id: fileScanTab
                
                ScrollView {
                    anchors.fill: parent
                    clip: true
                    
                    ColumnLayout {
                        width: fileScanTab.width
                        spacing: Theme.spacing_md
                        
                        // File Selection Card
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: fileSelectColumn.implicitHeight + 40
                            color: ThemeManager.panel()
                            radius: 12
                            border.color: ThemeManager.border()
                            border.width: 1
                            
                            ColumnLayout {
                                id: fileSelectColumn
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 16
                                
                                Text {
                                    text: "Select File to Scan"
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: ThemeManager.foreground()
                                }
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 44
                                    spacing: 12
                                    
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        color: "#1a1a2e"
                                        radius: 8
                                        border.color: filePathInput.activeFocus ? ThemeManager.primary : ThemeManager.border()
                                        border.width: 1
                                        
                                        TextField {
                                            id: filePathInput
                                            anchors.fill: parent
                                            anchors.margins: 2
                                            placeholderText: "Enter file path or click Browse..."
                                            text: selectedFilePath
                                            maximumLength: 2048
                                            color: ThemeManager.foreground()
                                            placeholderTextColor: ThemeManager.muted()
                                            font.pixelSize: 13
                                            verticalAlignment: Text.AlignVCenter
                                            leftPadding: 12
                                            
                                            onTextChanged: {
                                                selectedFilePath = text
                                            }
                                            
                                            background: Rectangle {
                                                color: "transparent"
                                            }
                                        }
                                    }
                                    
                                    Button {
                                        text: "📂 Browse"
                                        Layout.preferredWidth: 110
                                        Layout.preferredHeight: 40
                                        
                                        onClicked: fileDialog.open()
                                        
                                        background: Rectangle {
                                            color: parent.hovered ? Qt.lighter(ThemeManager.accent, 1.1) : ThemeManager.accent
                                            radius: 8
                                        }
                                        
                                        contentItem: Text {
                                            text: parent.text
                                            color: "#FFFFFF"
                                            font.pixelSize: 13
                                            font.bold: true
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                                
                                // Options Row
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 24
                                    
                                    // Sandbox toggle with custom switch
                                    RowLayout {
                                        spacing: 10
                                        
                                        Rectangle {
                                            id: fileSandboxToggleBg
                                            width: 44
                                            height: 24
                                            radius: 12
                                            color: useSandbox ? ThemeManager.primary : ThemeManager.surface()
                                            border.color: ThemeManager.border()
                                            opacity: integratedSandboxAvailable ? 1.0 : 0.5
                                            
                                            Rectangle {
                                                x: useSandbox ? parent.width - width - 3 : 3
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 18
                                                height: 18
                                                radius: 9
                                                color: "#FFFFFF"
                                                
                                                Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                                            }
                                            
                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: integratedSandboxAvailable
                                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onClicked: useSandbox = !useSandbox
                                            }
                                        }
                                        
                                        Text {
                                            text: "Run in Sandbox"
                                            color: integratedSandboxAvailable ? ThemeManager.foreground() : ThemeManager.muted()
                                            font.pixelSize: 13
                                        }
                                    }
                                    
                                    // Block network toggle (visible when sandbox enabled)
                                    RowLayout {
                                        spacing: 10
                                        visible: useSandbox
                                        
                                        Rectangle {
                                            id: blockNetworkToggleBg
                                            width: 44
                                            height: 24
                                            radius: 12
                                            color: blockNetwork ? ThemeManager.accent : ThemeManager.surface()
                                            border.color: ThemeManager.border()
                                            opacity: integratedSandboxAvailable && useSandbox ? 1.0 : 0.5
                                            
                                            Rectangle {
                                                x: blockNetwork ? parent.width - width - 3 : 3
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 18
                                                height: 18
                                                radius: 9
                                                color: "#FFFFFF"
                                                
                                                Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                                            }
                                            
                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: integratedSandboxAvailable && useSandbox
                                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onClicked: blockNetwork = !blockNetwork
                                            }
                                        }
                                        
                                        Text {
                                            text: "Block Network"
                                            color: (integratedSandboxAvailable && useSandbox) ? ThemeManager.foreground() : ThemeManager.muted()
                                            font.pixelSize: 13
                                        }
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    Text {
                                        text: integratedSandboxAvailable 
                                            ? "✓ " + integratedSandboxStatus
                                            : "ℹ️ " + integratedSandboxStatus
                                        font.pixelSize: 11
                                        color: integratedSandboxAvailable ? ThemeManager.success : ThemeManager.muted()
                                    }
                                    
                                    Button {
                                        text: fileScanningInProgress ? "⏳ " + fileScanStage : "🔬 Scan File"
                                        Layout.preferredWidth: 150
                                        Layout.preferredHeight: 44
                                        enabled: !fileScanningInProgress && selectedFilePath.length > 0
                                        
                                        onClicked: startFileScan()
                                        
                                        background: Rectangle {
                                            color: parent.enabled 
                                                ? (parent.hovered ? Qt.lighter(ThemeManager.primary, 1.1) : ThemeManager.primary)
                                                : ThemeManager.muted()
                                            radius: 8
                                        }
                                        
                                        contentItem: Text {
                                            text: parent.text
                                            color: "#FFFFFF"
                                            font.pixelSize: 14
                                            font.bold: true
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Progress Indicator (while scanning)
                        Rectangle {
                            Layout.fillWidth: true
                            height: 60
                            color: ThemeManager.panel()
                            radius: 12
                            visible: fileScanningInProgress
                            
                            RowLayout {
                                anchors.centerIn: parent
                                spacing: 16
                                
                                BusyIndicator {
                                    running: fileScanningInProgress
                                    Layout.preferredWidth: 32
                                    Layout.preferredHeight: 32
                                }
                                
                                Text {
                                    text: "Scanning: " + fileScanStage
                                    font.pixelSize: 14
                                    color: ThemeManager.foreground()
                                }
                            }
                        }
                        
                        // Results Card
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: resultColumn.implicitHeight + 40
                            color: ThemeManager.panel()
                            radius: 12
                            border.color: fileScanResult && fileScanResult.verdict === "Malicious" 
                                ? ThemeManager.danger 
                                : (fileScanResult && fileScanResult.verdict === "Suspicious" 
                                    ? ThemeManager.warning 
                                    : ThemeManager.border())
                            border.width: fileScanResult ? 2 : 1
                            visible: fileScanResult !== null
                            
                            ColumnLayout {
                                id: resultColumn
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 16
                                
                                // Header with verdict
                                RowLayout {
                                    Layout.fillWidth: true
                                    
                                    Text {
                                        text: fileScanResult ? (
                                            fileScanResult.verdict === "Malicious" ? "⛔ " :
                                            fileScanResult.verdict === "Suspicious" ? "⚠️ " : "✅ "
                                        ) + fileScanResult.verdict : ""
                                        font.pixelSize: 24
                                        font.bold: true
                                        color: fileScanResult ? getVerdictColor(fileScanResult.verdict) : ThemeManager.foreground()
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    // Score badge
                                    Rectangle {
                                        Layout.preferredWidth: 80
                                        Layout.preferredHeight: 40
                                        color: fileScanResult ? getScoreColor(fileScanResult.score) : ThemeManager.muted()
                                        radius: 8
                                        
                                        Text {
                                            anchors.centerIn: parent
                                            text: fileScanResult ? fileScanResult.score + "/100" : ""
                                            font.pixelSize: 16
                                            font.bold: true
                                            color: "#FFFFFF"
                                        }
                                    }
                                }
                                
                                // Summary
                                Text {
                                    text: fileScanResult ? fileScanResult.summary : ""
                                    font.pixelSize: 13
                                    color: ThemeManager.foreground()
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                                
                                // File info grid
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    columnSpacing: 20
                                    rowSpacing: 8
                                    
                                    Text { text: "File:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { 
                                        text: fileScanResult ? fileScanResult.file_name : ""
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 12
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                    
                                    Text { text: "Size:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { 
                                        text: fileScanResult ? formatFileSize(fileScanResult.file_size) : ""
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 12
                                    }
                                    
                                    Text { text: "SHA256:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { 
                                        text: fileScanResult && fileScanResult.sha256 ? fileScanResult.sha256.substring(0, 32) + "..." : ""
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 12
                                        font.family: "Consolas, monospace"
                                    }
                                    
                                    Text { text: "MIME:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { 
                                        text: fileScanResult ? fileScanResult.mime_type : ""
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 12
                                    }
                                }
                                
                                // Statistics row
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 16
                                    
                                    // YARA matches
                                    Rectangle {
                                        Layout.preferredWidth: 100
                                        Layout.preferredHeight: 50
                                        color: ThemeManager.surface()
                                        radius: 8
                                        
                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 2
                                            
                                            Text {
                                                text: fileScanResult ? fileScanResult.yara_matches_count : "0"
                                                font.pixelSize: 20
                                                font.bold: true
                                                color: fileScanResult && fileScanResult.yara_matches_count > 0 
                                                    ? ThemeManager.danger : ThemeManager.foreground()
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                            Text {
                                                text: "YARA"
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                        }
                                    }
                                    
                                    // IOCs found
                                    Rectangle {
                                        Layout.preferredWidth: 100
                                        Layout.preferredHeight: 50
                                        color: ThemeManager.surface()
                                        radius: 8
                                        
                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 2
                                            
                                            Text {
                                                text: fileScanResult && fileScanResult.iocs_found ? "⚠️" : "✓"
                                                font.pixelSize: 18
                                                color: fileScanResult && fileScanResult.iocs_found 
                                                    ? ThemeManager.warning : ThemeManager.success
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                            Text {
                                                text: "IOCs"
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                        }
                                    }
                                    
                                    // PE Analysis
                                    Rectangle {
                                        Layout.preferredWidth: 100
                                        Layout.preferredHeight: 50
                                        color: ThemeManager.surface()
                                        radius: 8
                                        
                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 2
                                            
                                            Text {
                                                text: fileScanResult && fileScanResult.pe_analyzed ? "🔍" : "—"
                                                font.pixelSize: 18
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                            Text {
                                                text: "PE"
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                        }
                                    }
                                    
                                    // Sandbox status
                                    Rectangle {
                                        Layout.preferredWidth: 100
                                        Layout.preferredHeight: 50
                                        color: ThemeManager.surface()
                                        radius: 8
                                        
                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 2
                                            
                                            Text {
                                                text: fileScanResult && fileScanResult.has_sandbox ? "🔬" 
                                                    : (fileScanResult && fileScanResult.sandbox_error ? "❌" : "—")
                                                font.pixelSize: 18
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                            Text {
                                                text: fileScanResult && fileScanResult.has_sandbox 
                                                    ? (fileScanResult.sandbox_duration.toFixed(1) + "s")
                                                    : "Sandbox"
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                        }
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                }
                                
                                // Report button
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12
                                    
                                    Button {
                                        text: "📄 Open Report"
                                        Layout.preferredHeight: 36
                                        
                                        onClicked: {
                                            if (fileScanResult && fileScanResult.report_path) {
                                                openReport(fileScanResult.report_path)
                                            }
                                        }
                                        
                                        background: Rectangle {
                                            color: parent.hovered ? Qt.lighter(ThemeManager.accent, 1.1) : ThemeManager.accent
                                            radius: 6
                                        }
                                        
                                        contentItem: Text {
                                            text: parent.text
                                            color: "#FFFFFF"
                                            font.pixelSize: 12
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                    
                                    Text {
                                        text: fileScanResult && fileScanResult.report_path 
                                            ? "Saved: " + fileScanResult.report_path 
                                            : ""
                                        font.pixelSize: 11
                                        color: ThemeManager.muted()
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                        }
                        
                        // Analysis Features Info
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: infoColumn.implicitHeight + 40
                            color: ThemeManager.surface()
                            radius: 12
                            visible: !fileScanningInProgress && !fileScanResult
                            
                            ColumnLayout {
                                id: infoColumn
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 12
                                
                                Text {
                                    text: "📊 Analysis Features (100% Offline)"
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: ThemeManager.foreground()
                                }
                                
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    columnSpacing: 30
                                    rowSpacing: 8
                                    
                                    Text { text: "✓ SHA256 Hash Computation"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ PE Header Analysis"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ Entropy Calculation"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ YARA Rule Matching"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ IOC Extraction (IPs, URLs, Domains)"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ Suspicious Import Detection"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                }
                                
                                Text {
                                    text: "🔬 Integrated Sandbox (" + (integratedSandboxAvailable ? "Available" : "Not Available") + ")"
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: integratedSandboxAvailable ? ThemeManager.foreground() : ThemeManager.muted()
                                    Layout.topMargin: 8
                                }
                                
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    columnSpacing: 30
                                    rowSpacing: 8
                                    
                                    Text { 
                                        text: integratedSandboxAvailable ? "✓ Process Isolation (Job Objects)" : "○ Process Isolation"
                                        color: integratedSandboxAvailable ? ThemeManager.muted() : ThemeManager.border()
                                        font.pixelSize: 12 
                                    }
                                    Text { 
                                        text: integratedSandboxAvailable ? "✓ Resource Monitoring" : "○ Resource Monitoring"
                                        color: integratedSandboxAvailable ? ThemeManager.muted() : ThemeManager.border()
                                        font.pixelSize: 12 
                                    }
                                    Text { 
                                        text: integratedSandboxAvailable ? "✓ Network Blocking (Firewall)" : "○ Network Blocking"
                                        color: integratedSandboxAvailable ? ThemeManager.muted() : ThemeManager.border()
                                        font.pixelSize: 12 
                                    }
                                    Text { 
                                        text: integratedSandboxAvailable ? "✓ File System Activity Tracking" : "○ File System Activity"
                                        color: integratedSandboxAvailable ? ThemeManager.muted() : ThemeManager.border()
                                        font.pixelSize: 12 
                                    }
                                }
                                
                                Text {
                                    text: integratedSandboxStatus
                                    font.pixelSize: 11
                                    color: ThemeManager.muted()
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                    visible: integratedSandboxStatus.length > 0
                                }
                            }
                        }
                        
                        Item { Layout.fillHeight: true }
                    }
                }
            }
            
            // ========================================
            // URL CHECK TAB (VirusTotal-like)
            // ========================================
            Item {
                id: urlCheckTab
                
                ScrollView {
                    anchors.fill: parent
                    clip: true
                    
                    ColumnLayout {
                        width: urlCheckTab.width
                        spacing: Theme.spacing_md
                        
                        // URL Input Card
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: urlInputColumn.implicitHeight + 40
                            color: ThemeManager.panel()
                            radius: 12
                            border.color: ThemeManager.border()
                            border.width: 1
                            
                            ColumnLayout {
                                id: urlInputColumn
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 16
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    
                                    Text {
                                        text: "🌐 URL Scanner"
                                        font.pixelSize: 18
                                        font.bold: true
                                        color: ThemeManager.foreground()
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    // Sandbox status badge
                                    Rectangle {
                                        Layout.preferredHeight: 24
                                        Layout.preferredWidth: statusText.implicitWidth + 16
                                        color: urlSandboxAvailable ? Qt.rgba(0, 0.8, 0.4, 0.2) : Qt.rgba(1, 0.8, 0, 0.2)
                                        radius: 12
                                        
                                        Text {
                                            id: statusText
                                            anchors.centerIn: parent
                                            text: urlSandboxAvailable ? "✓ Sandbox Ready" : "Static Only"
                                            font.pixelSize: 11
                                            color: urlSandboxAvailable ? ThemeManager.success : ThemeManager.warning
                                        }
                                    }
                                }
                                
                                // URL Input row
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 48
                                    spacing: 12
                                    
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        color: "#1a1a2e"
                                        radius: 8
                                        border.color: urlInput.activeFocus ? ThemeManager.primary : ThemeManager.border()
                                        border.width: 1
                                        
                                        TextField {
                                            id: urlInput
                                            anchors.fill: parent
                                            anchors.margins: 2
                                            placeholderText: "Enter URL to analyze (e.g., https://example.com)"
                                            maximumLength: 2048
                                            color: ThemeManager.foreground()
                                            placeholderTextColor: ThemeManager.muted()
                                            font.pixelSize: 14
                                            verticalAlignment: Text.AlignVCenter
                                            leftPadding: 16
                                            
                                            background: Rectangle {
                                                color: "transparent"
                                            }
                                            
                                            Keys.onReturnPressed: startUrlCheck()
                                            Keys.onEnterPressed: startUrlCheck()
                                        }
                                    }
                                    
                                    Button {
                                        text: urlCheckingInProgress ? "⏳ Scanning..." : "🔍 Scan URL"
                                        Layout.preferredWidth: 140
                                        Layout.preferredHeight: 48
                                        enabled: !urlCheckingInProgress && urlInput.text.trim().length > 0
                                        
                                        onClicked: startUrlCheck()
                                        
                                        background: Rectangle {
                                            color: parent.enabled 
                                                ? (parent.hovered ? Qt.lighter(ThemeManager.primary, 1.1) : ThemeManager.primary)
                                                : ThemeManager.muted()
                                            radius: 8
                                        }
                                        
                                        contentItem: Text {
                                            text: parent.text
                                            color: "#FFFFFF"
                                            font.pixelSize: 14
                                            font.bold: true
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                                
                                // Options row
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 32
                                    
                                    // Sandbox toggle with custom switch
                                    RowLayout {
                                        spacing: 10
                                        
                                        Rectangle {
                                            id: sandboxToggleBg
                                            width: 44
                                            height: 24
                                            radius: 12
                                            color: useUrlSandbox ? ThemeManager.primary : ThemeManager.surface()
                                            border.color: ThemeManager.border()
                                            opacity: urlSandboxAvailable ? 1.0 : 0.5
                                            
                                            Rectangle {
                                                x: useUrlSandbox ? parent.width - width - 3 : 3
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 18
                                                height: 18
                                                radius: 9
                                                color: "#FFFFFF"
                                                
                                                Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                                            }
                                            
                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: urlSandboxAvailable && !urlCheckingInProgress
                                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onClicked: useUrlSandbox = !useUrlSandbox
                                            }
                                        }
                                        
                                        Text {
                                            text: "Sandbox Detonation"
                                            color: urlSandboxAvailable ? ThemeManager.foreground() : ThemeManager.muted()
                                            font.pixelSize: 13
                                        }
                                    }
                                    
                                    // Block private IPs toggle
                                    RowLayout {
                                        spacing: 10
                                        
                                        Rectangle {
                                            id: blockPrivateToggleBg
                                            width: 44
                                            height: 24
                                            radius: 12
                                            color: blockPrivateIPs ? ThemeManager.accent : ThemeManager.surface()
                                            border.color: ThemeManager.border()
                                            
                                            Rectangle {
                                                x: blockPrivateIPs ? parent.width - width - 3 : 3
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 18
                                                height: 18
                                                radius: 9
                                                color: "#FFFFFF"
                                                
                                                Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                                            }
                                            
                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: !urlCheckingInProgress
                                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onClicked: blockPrivateIPs = !blockPrivateIPs
                                            }
                                        }
                                        
                                        Text {
                                            text: "Block Private IPs"
                                            color: ThemeManager.foreground()
                                            font.pixelSize: 13
                                        }
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }
                        
                        // Progress Card
                        Rectangle {
                            Layout.fillWidth: true
                            height: 80
                            color: ThemeManager.panel()
                            radius: 12
                            visible: urlCheckingInProgress
                            
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 8
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    
                                    BusyIndicator {
                                        running: urlCheckingInProgress
                                        Layout.preferredWidth: 24
                                        Layout.preferredHeight: 24
                                    }
                                    
                                    Text {
                                        text: urlScanStage || "Analyzing..."
                                        font.pixelSize: 14
                                        color: ThemeManager.foreground()
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    Text {
                                        text: urlScanProgressValue + "%"
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: ThemeManager.primary
                                    }
                                    
                                    Button {
                                        text: "Cancel"
                                        Layout.preferredWidth: 80
                                        Layout.preferredHeight: 28
                                        onClicked: cancelUrlCheck()
                                        
                                        background: Rectangle {
                                            color: parent.hovered ? ThemeManager.danger : ThemeManager.surface()
                                            radius: 6
                                            border.color: ThemeManager.danger
                                            border.width: 1
                                        }
                                        
                                        contentItem: Text {
                                            text: parent.text
                                            color: parent.hovered ? "#FFFFFF" : ThemeManager.danger
                                            font.pixelSize: 12
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                                
                                // Progress bar
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 6
                                    color: ThemeManager.surface()
                                    radius: 3
                                    
                                    Rectangle {
                                        width: parent.width * (urlScanProgressValue / 100)
                                        height: parent.height
                                        color: ThemeManager.primary
                                        radius: 3
                                        
                                        Behavior on width { NumberAnimation { duration: 200 } }
                                    }
                                }
                            }
                        }
                        
                        // Results Card
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: urlResultColumn.implicitHeight + 40
                            color: ThemeManager.panel()
                            radius: 12
                            border.color: {
                                if (!urlCheckResult) return ThemeManager.border()
                                var verdict = urlCheckResult.verdict || ""
                                if (verdict === "malicious" || verdict === "likely_malicious") return ThemeManager.danger
                                if (verdict === "suspicious") return ThemeManager.warning
                                return ThemeManager.success
                            }
                            border.width: urlCheckResult ? 2 : 1
                            visible: urlCheckResult !== null && urlCheckResult.success !== false
                            
                            ColumnLayout {
                                id: urlResultColumn
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 20
                                
                                // Verdict Header
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 16
                                    
                                    // Verdict icon and text
                                    RowLayout {
                                        spacing: 12
                                        
                                        Text {
                                            text: getVerdictIcon(urlCheckResult ? urlCheckResult.verdict : "")
                                            font.pixelSize: 32
                                        }
                                        
                                        ColumnLayout {
                                            spacing: 2
                                            
                                            Text {
                                                text: getVerdictLabel(urlCheckResult ? urlCheckResult.verdict : "")
                                                font.pixelSize: 24
                                                font.bold: true
                                                color: getVerdictColor(urlCheckResult ? urlCheckResult.verdict : "")
                                            }
                                            
                                            Text {
                                                text: urlCheckResult && urlCheckResult.explanation 
                                                    ? urlCheckResult.explanation.confidence + " confidence"
                                                    : ""
                                                font.pixelSize: 12
                                                color: ThemeManager.muted()
                                            }
                                        }
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    // Score circle
                                    Rectangle {
                                        Layout.preferredWidth: 80
                                        Layout.preferredHeight: 80
                                        color: "transparent"
                                        
                                        Rectangle {
                                            anchors.fill: parent
                                            radius: 40
                                            color: "transparent"
                                            border.color: getScoreColor(urlCheckResult ? urlCheckResult.score : 0)
                                            border.width: 6
                                        }
                                        
                                        ColumnLayout {
                                            anchors.centerIn: parent
                                            spacing: 0
                                            
                                            Text {
                                                text: urlCheckResult ? urlCheckResult.score : 0
                                                font.pixelSize: 24
                                                font.bold: true
                                                color: getScoreColor(urlCheckResult ? urlCheckResult.score : 0)
                                                Layout.alignment: Qt.AlignHCenter
                                            }
                                            
                                            Text {
                                                text: "/100"
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                                Layout.alignment: Qt.AlignHCenter
                                            }
                                        }
                                    }
                                }
                                
                                // Explanation box
                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: explainColumn.implicitHeight + 24
                                    color: ThemeManager.surface()
                                    radius: 8
                                    visible: urlCheckResult && urlCheckResult.explanation
                                    
                                    ColumnLayout {
                                        id: explainColumn
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 12
                                        
                                        // What it is
                                        ColumnLayout {
                                            spacing: 4
                                            
                                            Text {
                                                text: "What It Is"
                                                font.pixelSize: 12
                                                font.bold: true
                                                color: ThemeManager.primary
                                            }
                                            
                                            Text {
                                                text: urlCheckResult && urlCheckResult.explanation 
                                                    ? urlCheckResult.explanation.what_it_is : ""
                                                font.pixelSize: 13
                                                color: ThemeManager.foreground()
                                                wrapMode: Text.Wrap
                                                Layout.fillWidth: true
                                            }
                                        }
                                        
                                        // Why risky
                                        ColumnLayout {
                                            spacing: 4
                                            
                                            Text {
                                                text: "Risk Assessment"
                                                font.pixelSize: 12
                                                font.bold: true
                                                color: ThemeManager.warning
                                            }
                                            
                                            Text {
                                                text: urlCheckResult && urlCheckResult.explanation 
                                                    ? urlCheckResult.explanation.why_risky : ""
                                                font.pixelSize: 13
                                                color: ThemeManager.foreground()
                                                wrapMode: Text.Wrap
                                                Layout.fillWidth: true
                                            }
                                        }
                                        
                                        // What to do
                                        ColumnLayout {
                                            spacing: 4
                                            
                                            Text {
                                                text: "Recommendation"
                                                font.pixelSize: 12
                                                font.bold: true
                                                color: ThemeManager.success
                                            }
                                            
                                            Text {
                                                text: urlCheckResult && urlCheckResult.explanation 
                                                    ? urlCheckResult.explanation.what_to_do : ""
                                                font.pixelSize: 13
                                                color: ThemeManager.foreground()
                                                wrapMode: Text.Wrap
                                                Layout.fillWidth: true
                                            }
                                        }
                                    }
                                }
                                
                                // URL Info
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    columnSpacing: 20
                                    rowSpacing: 8
                                    
                                    Text { text: "Original URL:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { 
                                        text: urlCheckResult ? urlCheckResult.url : ""
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 12
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                    
                                    Text { text: "Final URL:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { 
                                        text: urlCheckResult ? urlCheckResult.final_url : ""
                                        color: urlCheckResult && urlCheckResult.url !== urlCheckResult.final_url 
                                            ? ThemeManager.warning : ThemeManager.foreground()
                                        font.pixelSize: 12
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                    
                                    Text { text: "HTTP Status:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { 
                                        text: urlCheckResult && urlCheckResult.http_status 
                                            ? urlCheckResult.http_status.toString() : "N/A"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 12
                                    }
                                    
                                    Text { text: "Redirects:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { 
                                        text: urlCheckResult ? (urlCheckResult.redirect_count || 0).toString() : "0"
                                        color: urlCheckResult && urlCheckResult.redirect_count > 2 
                                            ? ThemeManager.warning : ThemeManager.foreground()
                                        font.pixelSize: 12
                                    }
                                }
                                
                                // Redirect chain (if any)
                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: redirectColumn.implicitHeight + 20
                                    color: ThemeManager.surface()
                                    radius: 8
                                    visible: urlCheckResult && urlCheckResult.redirects && urlCheckResult.redirects.length > 1
                                    
                                    ColumnLayout {
                                        id: redirectColumn
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        spacing: 6
                                        
                                        Text {
                                            text: "🔗 Redirect Chain"
                                            font.pixelSize: 12
                                            font.bold: true
                                            color: ThemeManager.foreground()
                                        }
                                        
                                        Repeater {
                                            model: urlCheckResult && urlCheckResult.redirects ? urlCheckResult.redirects : []
                                            
                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 8
                                                
                                                Text {
                                                    text: (index + 1) + "."
                                                    font.pixelSize: 11
                                                    color: ThemeManager.muted()
                                                    Layout.preferredWidth: 20
                                                }
                                                
                                                Text {
                                                    text: modelData
                                                    font.pixelSize: 11
                                                    color: ThemeManager.foreground()
                                                    elide: Text.ElideMiddle
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                // Evidence list
                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: evidenceColumn.implicitHeight + 20
                                    color: ThemeManager.surface()
                                    radius: 8
                                    visible: urlCheckResult && urlCheckResult.evidence && urlCheckResult.evidence.length > 0
                                    
                                    ColumnLayout {
                                        id: evidenceColumn
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        spacing: 8
                                        
                                        Text {
                                            text: "📋 Evidence (" + (urlCheckResult ? urlCheckResult.evidence_count : 0) + " findings)"
                                            font.pixelSize: 12
                                            font.bold: true
                                            color: ThemeManager.foreground()
                                        }
                                        
                                        Repeater {
                                            model: urlCheckResult && urlCheckResult.evidence ? urlCheckResult.evidence : []
                                            
                                            Rectangle {
                                                Layout.fillWidth: true
                                                implicitHeight: evidenceRow.implicitHeight + 16
                                                color: Qt.rgba(getSeverityColor(modelData.severity).r, 
                                                              getSeverityColor(modelData.severity).g,
                                                              getSeverityColor(modelData.severity).b, 0.1)
                                                radius: 6
                                                border.color: getSeverityColor(modelData.severity)
                                                border.width: 1
                                                
                                                RowLayout {
                                                    id: evidenceRow
                                                    anchors.fill: parent
                                                    anchors.margins: 8
                                                    spacing: 12
                                                    
                                                    // Severity badge
                                                    Rectangle {
                                                        Layout.preferredWidth: 60
                                                        Layout.preferredHeight: 22
                                                        color: getSeverityColor(modelData.severity)
                                                        radius: 4
                                                        
                                                        Text {
                                                            anchors.centerIn: parent
                                                            text: modelData.severity ? modelData.severity.toUpperCase() : "INFO"
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                            color: "#FFFFFF"
                                                        }
                                                    }
                                                    
                                                    ColumnLayout {
                                                        Layout.fillWidth: true
                                                        spacing: 2
                                                        
                                                        Text {
                                                            text: modelData.title || ""
                                                            font.pixelSize: 12
                                                            font.bold: true
                                                            color: ThemeManager.foreground()
                                                        }
                                                        
                                                        Text {
                                                            text: modelData.detail || ""
                                                            font.pixelSize: 11
                                                            color: ThemeManager.muted()
                                                            wrapMode: Text.Wrap
                                                            Layout.fillWidth: true
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                // IOCs section
                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: iocColumn.implicitHeight + 20
                                    color: ThemeManager.surface()
                                    radius: 8
                                    visible: urlCheckResult && urlCheckResult.has_iocs
                                    
                                    ColumnLayout {
                                        id: iocColumn
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        spacing: 8
                                        
                                        Text {
                                            text: "🔍 Indicators of Compromise"
                                            font.pixelSize: 12
                                            font.bold: true
                                            color: ThemeManager.foreground()
                                        }
                                        
                                        // Domains
                                        ColumnLayout {
                                            visible: urlCheckResult && urlCheckResult.iocs && 
                                                     urlCheckResult.iocs.domains && urlCheckResult.iocs.domains.length > 0
                                            spacing: 4
                                            
                                            Text {
                                                text: "Linked Domains:"
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                            }
                                            
                                            Flow {
                                                Layout.fillWidth: true
                                                spacing: 6
                                                
                                                Repeater {
                                                    model: urlCheckResult && urlCheckResult.iocs && urlCheckResult.iocs.domains 
                                                        ? urlCheckResult.iocs.domains.slice(0, 10) : []
                                                    
                                                    Rectangle {
                                                        width: domainText.implicitWidth + 12
                                                        height: 22
                                                        color: ThemeManager.panel()
                                                        radius: 4
                                                        
                                                        Text {
                                                            id: domainText
                                                            anchors.centerIn: parent
                                                            text: modelData
                                                            font.pixelSize: 10
                                                            color: ThemeManager.foreground()
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        
                                        // IPs
                                        ColumnLayout {
                                            visible: urlCheckResult && urlCheckResult.iocs && 
                                                     urlCheckResult.iocs.ips && urlCheckResult.iocs.ips.length > 0
                                            spacing: 4
                                            
                                            Text {
                                                text: "IP Addresses:"
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                            }
                                            
                                            Flow {
                                                Layout.fillWidth: true
                                                spacing: 6
                                                
                                                Repeater {
                                                    model: urlCheckResult && urlCheckResult.iocs && urlCheckResult.iocs.ips 
                                                        ? urlCheckResult.iocs.ips.slice(0, 10) : []
                                                    
                                                    Rectangle {
                                                        width: ipText.implicitWidth + 12
                                                        height: 22
                                                        color: ThemeManager.panel()
                                                        radius: 4
                                                        
                                                        Text {
                                                            id: ipText
                                                            anchors.centerIn: parent
                                                            text: modelData
                                                            font.pixelSize: 10
                                                            font.family: "Consolas"
                                                            color: ThemeManager.foreground()
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                // Technical summary and report button
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 16
                                    
                                    Text {
                                        text: urlCheckResult && urlCheckResult.explanation 
                                            ? "📊 " + urlCheckResult.explanation.technical_summary : ""
                                        font.pixelSize: 11
                                        color: ThemeManager.muted()
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                    
                                    Button {
                                        text: "📄 Open Report"
                                        Layout.preferredHeight: 36
                                        Layout.preferredWidth: 120
                                        visible: urlCheckResult && urlCheckResult.report_path
                                        
                                        onClicked: {
                                            if (urlCheckResult && urlCheckResult.report_path) {
                                                openReport(urlCheckResult.report_path)
                                            }
                                        }
                                        
                                        background: Rectangle {
                                            color: parent.hovered ? Qt.lighter(ThemeManager.accent, 1.1) : ThemeManager.accent
                                            radius: 6
                                        }
                                        
                                        contentItem: Text {
                                            text: parent.text
                                            color: "#FFFFFF"
                                            font.pixelSize: 12
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Error Card
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 100
                            color: Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.1)
                            radius: 12
                            border.color: ThemeManager.danger
                            border.width: 1
                            visible: urlCheckResult !== null && urlCheckResult.success === false
                            
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 16
                                
                                Text {
                                    text: "❌"
                                    font.pixelSize: 32
                                }
                                
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    
                                    Text {
                                        text: "Scan Failed"
                                        font.pixelSize: 16
                                        font.bold: true
                                        color: ThemeManager.danger
                                    }
                                    
                                    Text {
                                        text: urlCheckResult ? urlCheckResult.error : "Unknown error"
                                        font.pixelSize: 13
                                        color: ThemeManager.foreground()
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                        }
                        
                        // Features Info (when no results)
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: urlInfoColumn.implicitHeight + 40
                            color: ThemeManager.surface()
                            radius: 12
                            visible: !urlCheckingInProgress && !urlCheckResult
                            
                            ColumnLayout {
                                id: urlInfoColumn
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 16
                                
                                Text {
                                    text: "🔬 VirusTotal-like URL Analysis"
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: ThemeManager.foreground()
                                }
                                
                                Text {
                                    text: "100% local analysis - No data sent to external servers"
                                    font.pixelSize: 13
                                    color: ThemeManager.muted()
                                }
                                
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    columnSpacing: 40
                                    rowSpacing: 10
                                    
                                    Text { text: "✓ URL normalization & validation"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ Suspicious TLD detection"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ Punycode/homograph detection"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ Redirect chain tracking"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ Content analysis & forms"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ JavaScript obfuscation check"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ IOC extraction (IPs, domains)"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ YARA rule matching"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ Evidence-based scoring"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: "✓ AI-powered explanations"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                }
                                
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 1
                                    color: ThemeManager.border()
                                }
                                
                                RowLayout {
                                    spacing: 8
                                    
                                    Text {
                                        text: urlSandboxAvailable ? "🔬" : "ℹ️"
                                        font.pixelSize: 14
                                    }
                                    
                                    Text {
                                        text: urlSandboxAvailable 
                                            ? "Sandbox detonation available (WebView2)"
                                            : "Static analysis only (WebView2 not available for sandbox)"
                                        font.pixelSize: 12
                                        color: urlSandboxAvailable ? ThemeManager.success : ThemeManager.muted()
                                    }
                                }
                            }
                        }
                        
                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }
}
