import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../ui"

/**
 * SandboxLiveView - Live sandbox visualization with video preview
 * 
 * Features:
 * - Live video-like preview of sandboxed window (5-10 FPS)
 * - Event timeline with expand/collapse details
 * - Filters: All/Process/File/Registry/Network/Suspicious
 * - Session stats and status
 * - Copy event details button
 * 
 * Safe numeric helper: use num(value, fallback) to avoid undefined->double errors
 */
Rectangle {
    id: root
    color: ThemeManager.background()
    
    // ═══════════════════════════════════════════════════════════════════
    // SAFE NUMERIC HELPER
    // ═══════════════════════════════════════════════════════════════════
    
    // Safe numeric conversion - prevents "Unable to assign [undefined] to double" errors.
    // Usage: num(value, fallback) where fallback defaults to 0
    function num(value, fallback) {
        if (fallback === undefined) fallback = 0
        if (value === undefined || value === null) return fallback
        var n = Number(value)
        return isNaN(n) ? fallback : n
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // PROPERTIES
    // ═══════════════════════════════════════════════════════════════════
    
    property bool isActive: false
    property string sessionId: ""
    property string status: "idle"
    property string targetFile: ""
    property int eventCount: 0
    property int suspiciousCount: 0
    property int processCount: 0
    property int fileCount: 0
    property int registryCount: 0
    property int networkCount: 0
    property bool previewAvailable: false
    property bool autopilotEnabled: false
    property int frameNumber: 0
    property string previewStatus: "Waiting for window..."
    
    // Current filter: "all", "process", "file", "registry", "network", "suspicious"
    property string currentFilter: "all"
    
    // Selected event for details panel
    property int selectedEventIndex: -1
    property var selectedEvent: null
    
    // Event list model
    property var events: []
    
    // Filtered events based on current filter
    property var filteredEvents: {
        if (currentFilter === "all") return events;
        return events.filter(function(evt) {
            if (currentFilter === "suspicious") return evt.suspicious === true;
            return evt.category === currentFilter;
        });
    }
    
    implicitWidth: 800
    implicitHeight: 600
    
    // ═══════════════════════════════════════════════════════════════════
    // SIGNALS
    // ═══════════════════════════════════════════════════════════════════
    
    signal stopRequested()
    signal cancelClicked()  // Alias for compatibility with ScanTool.qml
    signal copyEventDetails(string details)
    signal toggleAutopilot(bool enabled)
    signal exportSession()
    
    // ═══════════════════════════════════════════════════════════════════
    // COMPATIBILITY PROPERTIES (for ScanTool.qml)
    // ═══════════════════════════════════════════════════════════════════
    
    // Stats object for ScanTool.qml compatibility
    // Backend sends snake_case: processes_spawned, files_touched, is_running, etc.
    property var stats: null
    onStatsChanged: {
        if (stats) {
            // Support both snake_case (from backend) and camelCase (legacy)
            processCount = stats.processes_spawned || stats.processesSpawned || stats.process_count || 0
            fileCount = stats.files_touched || stats.filesTouched || stats.file_count || 0
            registryCount = stats.registry_changes || stats.registryChanges || stats.registry_count || 0
            networkCount = stats.network_attempts || stats.networkAttempts || stats.network_count || 0
            suspiciousCount = stats.suspicious_behaviors || stats.suspiciousBehaviors || stats.suspicious_count || 0
            
            // Update isActive - check is_running or infer from stats presence
            var running = stats.is_running || stats.isRunning || false
            if (!running && (processCount > 0 || fileCount > 0 || networkCount > 0)) {
                // Stats are being updated, so sandbox is active
                running = true
            }
            isActive = running
            status = isActive ? "running" : "idle"
            
            // Update preview status from stats if available
            if (stats.current_action && stats.current_action !== "Initializing") {
                previewStatus = stats.current_action
            }
        }
    }
    
    // When events array changes, update counts and activate if needed
    onEventsChanged: {
        if (events && events.length > 0) {
            eventCount = events.length
            // If we have events, sandbox is active
            if (!isActive) {
                isActive = true
                status = "running"
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════
    
    function addEvent(event) {
        // Event structure: { type, category, message, timestamp, suspicious, details }
        let newEvents = events.slice();
        newEvents.push(event);
        events = newEvents;
        eventCount = events.length;
        
        // Update category counts
        if (event.suspicious) suspiciousCount++;
        switch (event.category) {
            case "process": processCount++; break;
            case "file": fileCount++; break;
            case "registry": registryCount++; break;
            case "network": networkCount++; break;
        }
    }
    
    function clearEvents() {
        events = [];
        eventCount = 0;
        suspiciousCount = 0;
        processCount = 0;
        fileCount = 0;
        registryCount = 0;
        networkCount = 0;
        selectedEventIndex = -1;
        selectedEvent = null;
    }
    
    function updatePreview() {
        frameNumber++;
        previewImage.source = "";
        previewImage.source = "image://sandboxpreview/frame?" + frameNumber;
    }
    
    function formatTimestamp(ts) {
        if (!ts) return "";
        let d = new Date(ts);
        return d.toLocaleTimeString();
    }
    
    function getEventIcon(category, suspicious) {
        if (suspicious) return "⚠️";
        switch (category) {
            case "process": return "⚙️";
            case "file": return "📄";
            case "registry": return "🗝️";
            case "network": return "🌐";
            default: return "📌";
        }
    }
    
    function getEventColor(category, suspicious) {
        if (suspicious) return ThemeManager.danger;
        switch (category) {
            case "process": return ThemeManager.accent;
            case "file": return ThemeManager.info;
            case "registry": return ThemeManager.warning;
            case "network": return ThemeManager.info;
            default: return ThemeManager.muted();
        }
    }
    
    function copyToClipboard(text) {
        copyEventDetails(text);
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // MAIN LAYOUT
    // ═══════════════════════════════════════════════════════════════════
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16
        
        // ───────────────────────────────────────────────────────────────
        // HEADER ROW
        // ───────────────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            color: ThemeManager.panel()
            radius: 12
            
            RowLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 16
                
                // Status indicator
                Rectangle {
                    width: 12
                    height: 12
                    radius: 6
                    color: {
                        switch (root.status) {
                            case "running": return ThemeManager.success;
                            case "stopping": return ThemeManager.warning;
                            case "error": return ThemeManager.danger;
                            default: return ThemeManager.muted();
                        }
                    }
                    
                    SequentialAnimation on opacity {
                        running: root.status === "running"
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.4; duration: 600 }
                        NumberAnimation { to: 1.0; duration: 600 }
                    }
                }
                
                // Title and session info
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    
                    Text {
                        text: root.isActive ? "🔬 Live Sandbox Session" : "Sandbox Viewer"
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        color: ThemeManager.foreground()
                    }
                    
                    Text {
                        text: root.sessionId ? "Session: " + root.sessionId.substring(0, 8) + "..." : "No active session"
                        font.pixelSize: 12
                        color: ThemeManager.muted()
                        visible: root.sessionId !== ""
                    }
                }
                
                // Autopilot toggle
                Rectangle {
                    Layout.preferredWidth: 140
                    Layout.preferredHeight: 32
                    color: root.autopilotEnabled ? Qt.rgba(0.133, 0.773, 0.369, 0.2) : ThemeManager.surface()
                    radius: 8
                    border.color: root.autopilotEnabled ? ThemeManager.success : ThemeManager.border()
                    border.width: 1
                    visible: root.isActive
                    
                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 6
                        
                        Text {
                            text: "🤖"
                            font.pixelSize: 14
                        }
                        
                        Text {
                            text: "Autopilot"
                            font.pixelSize: 14
                            color: root.autopilotEnabled ? ThemeManager.success : ThemeManager.muted()
                        }
                        
                        Switch {
                            id: autopilotSwitch
                            checked: root.autopilotEnabled
                            onCheckedChanged: {
                                if (checked !== root.autopilotEnabled) {
                                    root.toggleAutopilot(checked);
                                }
                            }
                        }
                    }
                }
                
                // Stop button
                Rectangle {
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 36
                    color: stopButtonArea.containsMouse ? Qt.darker(ThemeManager.danger, 1.1) : ThemeManager.danger
                    radius: 8
                    visible: root.isActive
                    
                    Text {
                        anchors.centerIn: parent
                        text: "⏹ Stop"
                        font.pixelSize: 14
                        font.weight: Font.Medium
                        color: "#FFFFFF"
                    }
                    
                    MouseArea {
                        id: stopButtonArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.stopRequested()
                            root.cancelClicked()
                        }
                    }
                }
            }
        }
        
        // ───────────────────────────────────────────────────────────────
        // STATS BAR
        // ───────────────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            color: ThemeManager.panel()
            radius: 12
            
            RowLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 24
                
                // Event count
                StatBadge {
                    label: "Events"
                    value: root.eventCount
                    icon: "📊"
                }
                
                StatBadge {
                    label: "Processes"
                    value: root.processCount
                    icon: "⚙️"
                    valueColor: ThemeManager.accent
                }
                
                StatBadge {
                    label: "Files"
                    value: root.fileCount
                    icon: "📄"
                    valueColor: ThemeManager.info
                }
                
                StatBadge {
                    label: "Registry"
                    value: root.registryCount
                    icon: "🗝️"
                    valueColor: ThemeManager.warning
                }
                
                StatBadge {
                    label: "Network"
                    value: root.networkCount
                    icon: "🌐"
                    valueColor: ThemeManager.info
                }
                
                StatBadge {
                    label: "Suspicious"
                    value: root.suspiciousCount
                    icon: "⚠️"
                    valueColor: ThemeManager.danger
                    highlight: root.suspiciousCount > 0
                }
                
                Item { Layout.fillWidth: true }
            }
        }
        
        // ───────────────────────────────────────────────────────────────
        // MAIN CONTENT AREA
        // ───────────────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16
            
            // ═══════════════════════════════════════════════════════════
            // LEFT: VIDEO PREVIEW PANEL
            // ═══════════════════════════════════════════════════════════
            Rectangle {
                Layout.preferredWidth: 380
                Layout.fillHeight: true
                color: ThemeManager.panel()
                radius: 12
                
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10
                    
                    // Preview header with LIVE badge
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        
                        Text {
                            text: "📺 Live Preview"
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: ThemeManager.foreground()
                        }
                        
                        // LIVE badge
                        Rectangle {
                            width: 48
                            height: 20
                            radius: 4
                            color: root.previewAvailable && root.isActive ? ThemeManager.danger : ThemeManager.surface()
                            visible: root.isActive
                            
                            Text {
                                anchors.centerIn: parent
                                text: "LIVE"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: root.previewAvailable ? "#FFFFFF" : ThemeManager.muted()
                            }
                            
                            SequentialAnimation on opacity {
                                running: root.previewAvailable && root.isActive
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.6; duration: 500 }
                                NumberAnimation { to: 1.0; duration: 500 }
                            }
                        }
                        
                        Item { Layout.fillWidth: true }
                        
                        Text {
                            text: "Frame: " + root.num(root.frameNumber, 0)
                            font.pixelSize: 12
                            color: ThemeManager.muted()
                            visible: root.previewAvailable
                        }
                    }
                    
                    // Preview container
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: root.previewAvailable ? "#000000" : ThemeManager.surface()
                        radius: 8
                        clip: true
                        
                        // Preview image - uses timestamp for cache-busting
                        Image {
                            id: previewImage
                            anchors.fill: parent
                            anchors.margins: 2
                            fillMode: Image.PreserveAspectFit
                            cache: false
                            asynchronous: true
                            source: root.previewAvailable ? "image://sandboxpreview/frame?t=" + root.num(root.frameNumber, 0) : ""
                            visible: root.previewAvailable
                        }
                        
                        // Placeholder when no preview - shows helpful status messages
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 12
                            visible: !root.previewAvailable
                            
                            // Status icon - changes based on state
                            Text {
                                text: {
                                    if (!root.isActive) return "🖥️";
                                    if (root.status === "launching") return "🚀";
                                    if (root.previewStatus.indexOf("console") >= 0) return "⌨️";
                                    return "🔍";
                                }
                                font.pixelSize: 48
                                Layout.alignment: Qt.AlignHCenter
                                opacity: root.isActive ? 0.8 : 0.4
                            }
                            
                            // Primary status message
                            Text {
                                text: {
                                    if (!root.isActive) {
                                        return "Session Inactive";
                                    }
                                    return root.previewStatus || "Waiting for window...";
                                }
                                font.pixelSize: 15
                                font.weight: Font.Medium
                                color: ThemeManager.foreground()
                                Layout.alignment: Qt.AlignHCenter
                                opacity: root.isActive ? 1.0 : 0.6
                            }
                            
                            // Secondary explanation
                            Text {
                                text: {
                                    if (!root.isActive) {
                                        return "Start a sandbox scan to see live preview";
                                    }
                                    if (root.previewStatus.indexOf("console") >= 0 || root.previewStatus.indexOf("background") >= 0) {
                                        return "Live metrics are still being collected below ↓";
                                    }
                                    if (root.status === "launching") {
                                        return "Please wait while the sandbox initializes...";
                                    }
                                    return "Looking for sandbox window...";
                                }
                                font.pixelSize: 12
                                color: ThemeManager.muted()
                                Layout.alignment: Qt.AlignHCenter
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                Layout.maximumWidth: 280
                            }
                            
                            // Loading spinner - only when actively looking for window
                            Rectangle {
                                Layout.preferredWidth: 32
                                Layout.preferredHeight: 32
                                Layout.alignment: Qt.AlignHCenter
                                color: "transparent"
                                visible: root.isActive && !root.previewAvailable && root.previewStatus.indexOf("console") < 0
                                
                                Rectangle {
                                    width: 24
                                    height: 24
                                    anchors.centerIn: parent
                                    radius: 12
                                    color: "transparent"
                                    border.width: 3
                                    border.color: ThemeManager.accent
                                    opacity: 0.3
                                }
                                
                                Rectangle {
                                    width: 24
                                    height: 24
                                    anchors.centerIn: parent
                                    radius: 12
                                    color: "transparent"
                                    border.width: 3
                                    border.color: ThemeManager.accent
                                    
                                    // Arc effect
                                    Rectangle {
                                        width: parent.width
                                        height: parent.height / 2
                                        color: ThemeManager.panel()
                                        anchors.bottom: parent.bottom
                                    }
                                    
                                    RotationAnimation on rotation {
                                        from: 0
                                        to: 360
                                        duration: 1000
                                        loops: Animation.Infinite
                                        running: root.isActive && !root.previewAvailable
                                    }
                                }
                            }
                        }
                    }
                    
                    // Target file info
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 40
                        color: ThemeManager.surface()
                        radius: 8
                        visible: root.targetFile !== ""
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 6
                            
                            Text {
                                text: "📦"
                                font.pixelSize: 14
                            }
                            
                            Text {
                                text: {
                                    let parts = root.targetFile.split(/[/\\]/);
                                    return parts[parts.length - 1] || root.targetFile;
                                }
                                font.pixelSize: 14
                                color: ThemeManager.foreground()
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
            
            // ═══════════════════════════════════════════════════════════
            // RIGHT: EVENT TIMELINE
            // ═══════════════════════════════════════════════════════════
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: ThemeManager.panel()
                radius: 12
                
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10
                    
                    // Event timeline header with filters
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        
                        Text {
                            text: "📋 Event Timeline"
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: ThemeManager.foreground()
                        }
                        
                        Item { Layout.fillWidth: true }
                        
                        // Filter buttons
                        Row {
                            spacing: 4
                            
                            Repeater {
                                model: [
                                    { key: "all", label: "All", icon: "📊" },
                                    { key: "process", label: "Process", icon: "⚙️" },
                                    { key: "file", label: "File", icon: "📄" },
                                    { key: "registry", label: "Registry", icon: "🗝️" },
                                    { key: "network", label: "Network", icon: "🌐" },
                                    { key: "suspicious", label: "⚠️", icon: "" }
                                ]
                                
                                Rectangle {
                                    width: modelData.key === "suspicious" ? 32 : 70
                                    height: 26
                                    radius: 4
                                    color: root.currentFilter === modelData.key ? ThemeManager.accent : ThemeManager.surface()
                                    border.color: root.currentFilter === modelData.key ? ThemeManager.accent : ThemeManager.border()
                                    border.width: 1
                                    
                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.key === "suspicious" ? modelData.label : modelData.label
                                        font.pixelSize: 11
                                        color: root.currentFilter === modelData.key ? "#FFFFFF" : ThemeManager.muted()
                                    }
                                    
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.currentFilter = modelData.key
                                    }
                                }
                            }
                        }
                    }
                    
                    // Event list
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        
                        ScrollBar.vertical.policy: ScrollBar.AsNeeded
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        
                        ListView {
                            id: eventListView
                            model: root.filteredEvents
                            spacing: 4
                            
                            // Empty state
                            Text {
                                anchors.centerIn: parent
                                text: root.events.length === 0 ? "No events yet...\nWaiting for sandbox activity" : "No events match filter"
                                font.pixelSize: 14
                                color: ThemeManager.muted()
                                horizontalAlignment: Text.AlignHCenter
                                visible: root.filteredEvents.length === 0
                                opacity: 0.6
                            }
                            
                            delegate: Rectangle {
                                id: eventDelegate
                                width: eventListView.width - 8
                                height: expandedContent.visible ? expandedContent.height + compactRow.height + 10 : compactRow.height
                                color: root.selectedEventIndex === index ? Qt.rgba(0.486, 0.227, 0.929, 0.15) : 
                                       (eventHover.containsMouse ? ThemeManager.surface() : "transparent")
                                radius: 8
                                border.color: root.selectedEventIndex === index ? ThemeManager.accent : "transparent"
                                border.width: 1
                                
                                property bool isExpanded: false
                                property var eventData: modelData
                                
                                Behavior on height {
                                    NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
                                }
                                
                                MouseArea {
                                    id: eventHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: {
                                        root.selectedEventIndex = index;
                                        root.selectedEvent = eventData;
                                        eventDelegate.isExpanded = !eventDelegate.isExpanded;
                                    }
                                }
                                
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 4
                                    
                                    // Compact row (always visible)
                                    RowLayout {
                                        id: compactRow
                                        Layout.fillWidth: true
                                        spacing: 10
                                        
                                        // Category icon
                                        Text {
                                            text: root.getEventIcon(eventData.category, eventData.suspicious)
                                            font.pixelSize: 14
                                        }
                                        
                                        // Timestamp
                                        Text {
                                            text: root.formatTimestamp(eventData.timestamp)
                                            font.pixelSize: 12
                                            font.family: "Consolas"
                                            color: ThemeManager.muted()
                                            Layout.preferredWidth: 70
                                        }
                                        
                                        // Message (truncated)
                                        Text {
                                            text: eventData.message || ""
                                            font.pixelSize: 14
                                            color: root.getEventColor(eventData.category, eventData.suspicious)
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                        
                                        // Expand indicator
                                        Text {
                                            text: eventDelegate.isExpanded ? "▼" : "▶"
                                            font.pixelSize: 10
                                            color: ThemeManager.muted()
                                            visible: eventData.details !== undefined
                                        }
                                    }
                                    
                                    // Expanded details
                                    Rectangle {
                                        id: expandedContent
                                        Layout.fillWidth: true
                                        // Use num() to safely convert implicitHeight - prevents undefined->double crash
                                        Layout.preferredHeight: num(detailsColumn.implicitHeight, 60) + 20
                                    color: ThemeManager.surface()
                                    radius: 8
                                    visible: !!(eventDelegate.isExpanded && eventData.details)
                                        
                                        ColumnLayout {
                                            id: detailsColumn
                                            anchors.fill: parent
                                            anchors.margins: 10
                                            spacing: 4
                                            
                                            // Detail rows
                                            Repeater {
                                                model: {
                                                    if (!eventData.details) return [];
                                                    let items = [];
                                                    let d = eventData.details;
                                                    if (d.pid) items.push({ key: "PID", value: d.pid });
                                                    if (d.process_name) items.push({ key: "Process", value: d.process_name });
                                                    if (d.command_line) items.push({ key: "Command", value: d.command_line });
                                                    if (d.path) items.push({ key: "Path", value: d.path });
                                                    if (d.target_path) items.push({ key: "Target", value: d.target_path });
                                                    if (d.operation) items.push({ key: "Operation", value: d.operation });
                                                    if (d.key_path) items.push({ key: "Registry Key", value: d.key_path });
                                                    if (d.value_name) items.push({ key: "Value", value: d.value_name });
                                                    if (d.remote_ip) items.push({ key: "Remote IP", value: d.remote_ip });
                                                    if (d.remote_port) items.push({ key: "Remote Port", value: d.remote_port });
                                                    if (d.url) items.push({ key: "URL", value: d.url });
                                                    if (d.reason) items.push({ key: "Reason", value: d.reason });
                                                    return items;
                                                }
                                                
                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 10
                                                    
                                                    Text {
                                                        text: modelData.key + ":"
                                                        font.pixelSize: 12
                                                        font.weight: Font.Medium
                                                        color: ThemeManager.muted()
                                                        Layout.preferredWidth: 80
                                                    }
                                                    
                                                    Text {
                                                        text: String(modelData.value)
                                                        font.pixelSize: 12
                                                        font.family: "Consolas"
                                                        color: ThemeManager.foreground()
                                                        wrapMode: Text.WrapAnywhere
                                                        Layout.fillWidth: true
                                                    }
                                                }
                                            }
                                            
                                            // Copy button
                                            Rectangle {
                                                Layout.alignment: Qt.AlignRight
                                                Layout.preferredWidth: 70
                                                Layout.preferredHeight: 24
                                                color: copyBtnArea.containsMouse ? ThemeManager.accent : ThemeManager.surface()
                                                radius: 4
                                                border.color: ThemeManager.border()
                                                border.width: 1
                                                
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: "📋 Copy"
                                                    font.pixelSize: 11
                                                    color: copyBtnArea.containsMouse ? "#FFFFFF" : ThemeManager.muted()
                                                }
                                                
                                                MouseArea {
                                                    id: copyBtnArea
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        let text = JSON.stringify(eventData, null, 2);
                                                        root.copyToClipboard(text);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        // ───────────────────────────────────────────────────────────────
        // FOOTER: Selected event details / Actions
        // ───────────────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.selectedEvent ? 80 : 44
            color: ThemeManager.panel()
            radius: 12
            
            Behavior on Layout.preferredHeight {
                NumberAnimation { duration: 150 }
            }
            
            RowLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 16
                
                // Selected event summary
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    visible: root.selectedEvent !== null
                    
                    Text {
                        text: root.selectedEvent ? ("Selected: " + root.getEventIcon(root.selectedEvent.category, root.selectedEvent.suspicious) + " " + root.selectedEvent.message) : ""
                        font.pixelSize: 14
                        color: ThemeManager.foreground()
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    
                    Text {
                        text: root.selectedEvent && root.selectedEvent.details ? 
                              "PID: " + (root.selectedEvent.details.pid || "N/A") + " | " +
                              "Process: " + (root.selectedEvent.details.process_name || "N/A") : ""
                        font.pixelSize: 12
                        color: ThemeManager.muted()
                        visible: !!(root.selectedEvent && root.selectedEvent.details)
                    }
                }
                
                // No selection message
                Text {
                    text: root.isActive ? "Click an event to see details" : "Session inactive"
                    font.pixelSize: 14
                    color: ThemeManager.muted()
                    visible: root.selectedEvent === null
                    Layout.fillWidth: true
                }
                
                // Export button
                Rectangle {
                    Layout.preferredWidth: 110
                    Layout.preferredHeight: 32
                    color: exportBtnArea.containsMouse ? Qt.lighter(ThemeManager.info, 1.1) : ThemeManager.info
                    radius: 8
                    visible: root.eventCount > 0
                    
                    Text {
                        anchors.centerIn: parent
                        text: "📥 Export"
                        font.pixelSize: 14
                        color: "#FFFFFF"
                    }
                    
                    MouseArea {
                        id: exportBtnArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.exportSession()
                    }
                }
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // STAT BADGE COMPONENT - Responsive, safe numeric display
    // ═══════════════════════════════════════════════════════════════════
    component StatBadge: RowLayout {
        property string label: ""
        property var value: 0  // Use var to allow undefined, we'll safely convert
        property string icon: ""
        property color valueColor: ThemeManager.foreground()
        property bool highlight: false
        
        spacing: 6
        Layout.preferredWidth: 85
        
        Rectangle {
            width: 32
            height: 32
            radius: 8
            color: highlight ? Qt.rgba(0.937, 0.267, 0.267, 0.25) : ThemeManager.surface()
            border.width: highlight ? 1 : 0
            border.color: ThemeManager.danger
            
            Text {
                anchors.centerIn: parent
                text: icon
                font.pixelSize: 14
            }
        }
        
        ColumnLayout {
            spacing: 1
            Layout.fillWidth: true
            
            Text {
                // Safe numeric display - never undefined
                text: root.num(value, 0)
                font.pixelSize: 18
                font.weight: Font.Bold
                color: valueColor
            }
            
            Text {
                text: label
                font.pixelSize: 11
                color: ThemeManager.muted()
            }
        }
    }
}
