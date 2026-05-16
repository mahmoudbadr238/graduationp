import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "pages"
import "ui"
import "components"

ApplicationWindow {
    id: window
    visible: true
    width: 1400
    height: 900
    minimumWidth: 1000
    minimumHeight: 600
    title: "Sentinel Endpoint Security"

    color: ThemeManager.background()
    
    // Update theme when ThemeManager changes
    Connections {
        target: ThemeManager
        function onThemeModeChanged() {
            window.color = ThemeManager.background()
        }
        function onFontSizeChanged() {
            window.color = ThemeManager.background()
        }
    }

    // ===== TOAST → NOTIFICATION CENTER =====
    // All toast messages are now redirected to the notification center
    Connections {
        target: Backend || null
        enabled: target !== null
        function onToast(message, type) {
            // Redirect toast to notification center
            if (NotificationService) {
                var title = "Notification"
                if (type === "success") title = "Success"
                else if (type === "error") title = "Error"
                else if (type === "warning") title = "Warning"
                else if (type === "info") title = "Info"
                
                NotificationService.push(title, message, type || "info")
            }
        }
        
        // Handle navigation requests from backend
        function onNavigateTo(route) {
            loadRoute(route)
        }
    }

    // ===== NAVIGATION STATE =====
    property string currentRoute: "home"
    property string historyRequestedTab: "scan"

    // Shared AI report text — set by ScanCenter, consumed by AiReport.
    // Tracked here so both Loaders can stay lazy and independent.
    property string _scanAiBriefText: ""
    property string _scanAiDetailedText: ""

    function routeTitle(routeId) {
        switch (routeId) {
        case "event-viewer":
            return "Event Viewer"
        case "history":
            return "History"
        case "snapshot":
            return "System Snapshot"
        case "system-monitor":
            return "System Monitor"
        case "net-scan":
            return "Network Scan"
        case "nmap-result":
            return "Network Scan Results"
        case "scan-tool":
            return "Scan Center"
        case "ai-report":
            return "AI Report"
        case "file-function":
            return "File Function"
        case "sandbox-lab":
            return "Sandbox"
        case "ai-assistant":
            return "Security Assistant"
        case "settings":
            return "Settings"
        default:
            return "Home"
        }
    }

    function routeSubtitle(routeId) {
        if (routeId === "history") {
            switch (historyRequestedTab) {
            case "incidents":
                return "Scan records, incident evidence, and quarantine activity."
            case "quarantine":
                return "Active and historical quarantine records with restore and delete workflow."
            case "url":
                return "URL scan outcomes and analyst review trail."
            default:
                return "Unified audit trail for scans, incidents, quarantine, and URL scan history."
            }
        }

        switch (routeId) {
        case "event-viewer":
            return "Platform event log from Windows Event Log or systemd journal, with AI-assisted explanation."
        case "snapshot":
            return "System inventory and security posture with truthful capability reporting."
        case "system-monitor":
            return "Live telemetry and real-time protection state with process-scanner activity."
        case "net-scan":
            return "Host discovery, service exposure, and network investigation."
        case "nmap-result":
            return "Detailed network findings for the last discovery or service scan."
        case "scan-tool":
            return "File and URL analysis with normalized verdicts, actions, and history."
        case "ai-report":
            return "AI-assisted explanation of the current scan, when configured."
        case "file-function":
            return "Secure deletion and recovery workflows with platform-aware limits."
        case "sandbox-lab":
            return "Isolated detonation and behavioral observation for supported Windows hosts."
        case "ai-assistant":
            return "Interactive security guidance backed by Groq when configured."
        case "settings":
            return "Local preferences, startup behavior, and capability-aware controls."
        default:
            return "Security overview, posture summary, and quick actions."
        }
    }

    function loadRoute(routeId) {
        // "events" and "history-events" both now open the top-level Event Viewer page
        if (routeId === "events" || routeId === "history-events" || routeId === "event-viewer") {
            currentRoute = "event-viewer"
            return
        }
        if (routeId === "history-scan") {
            historyRequestedTab = "scan"
            currentRoute = "history"
            return
        }
        if (routeId === "history-incidents") {
            historyRequestedTab = "incidents"
            currentRoute = "history"
            return
        }
        if (routeId === "history-quarantine") {
            historyRequestedTab = "quarantine"
            currentRoute = "history"
            return
        }
        if (routeId === "history-url") {
            historyRequestedTab = "url"
            currentRoute = "history"
            return
        }
        if (routeId === "history") {
            historyRequestedTab = "scan"
            currentRoute = "history"
            return
        }
        currentRoute = routeId
    }

    // ===== MAIN LAYOUT =====
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ===== SIDEBAR =====
        Rectangle {
            id: sidebar
            property bool sidebarExpanded: false
            readonly property int collapsedWidth: 74
            readonly property int expandedWidth: 218

            Layout.preferredWidth: sidebar.sidebarExpanded ? sidebar.expandedWidth : sidebar.collapsedWidth
            Layout.fillHeight: true
            color: ThemeManager.panel()

            Behavior on Layout.preferredWidth {
                NumberAnimation {
                    duration: 190
                    easing.type: Easing.OutCubic
                }
            }

            HoverHandler {
                id: sidebarHover
                onHoveredChanged: {
                    if (hovered) {
                        collapseSidebarTimer.stop()
                        sidebar.sidebarExpanded = true
                    } else {
                        collapseSidebarTimer.restart()
                    }
                }
            }

            Timer {
                id: collapseSidebarTimer
                interval: 170
                repeat: false
                onTriggered: sidebar.sidebarExpanded = false
            }

            Rectangle {
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.right: parent.right
                width: 1
                color: Qt.rgba(ThemeManager.border().r, ThemeManager.border().g, ThemeManager.border().b, 0.5)
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: sidebar.sidebarExpanded ? 16 : 10
                spacing: sidebar.sidebarExpanded ? 8 : 6

                Behavior on anchors.margins {
                    NumberAnimation {
                        duration: 180
                        easing.type: Easing.OutCubic
                    }
                }

                Behavior on spacing {
                    NumberAnimation {
                        duration: 180
                        easing.type: Easing.OutCubic
                    }
                }

                // Logo - clickable to go home
                Rectangle {
                    Layout.fillWidth: true
                    height: 52
                    color: "transparent"
                    Layout.topMargin: 8
                    Layout.bottomMargin: 16

                    RowLayout {
                        anchors.fill: parent
                        spacing: 10

                        Rectangle {
                            Layout.preferredWidth: 36
                            Layout.preferredHeight: 36
                            Layout.alignment: sidebar.sidebarExpanded ? Qt.AlignLeft : Qt.AlignHCenter
                            radius: 10
                            color: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.16)
                            border.color: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.32)
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: "S"
                                color: ThemeManager.accent
                                font.pixelSize: ThemeManager.fontSize_h3
                                font.bold: true
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: sidebar.sidebarExpanded ? brandColumn.implicitWidth : 0
                            implicitHeight: brandColumn.implicitHeight
                            clip: true
                            opacity: sidebar.sidebarExpanded ? 1 : 0

                            Behavior on Layout.preferredWidth {
                                NumberAnimation {
                                    duration: 180
                                    easing.type: Easing.OutCubic
                                }
                            }

                            Behavior on opacity {
                                NumberAnimation {
                                    duration: 120
                                    easing.type: Easing.OutQuad
                                }
                            }

                            ColumnLayout {
                                id: brandColumn
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 0

                                Text {
                                    text: "Sentinel"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_h3
                                    font.bold: true
                                }

                                Text {
                                    text: "Endpoint Security"
                                    color: ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_caption
                                }
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: loadRoute("home")
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: sidebar.sidebarExpanded ? 22 : 0
                    opacity: sidebar.sidebarExpanded ? 1 : 0
                    clip: true

                    Behavior on Layout.preferredHeight {
                        NumberAnimation {
                            duration: 180
                            easing.type: Easing.OutCubic
                        }
                    }

                    Behavior on opacity {
                        NumberAnimation {
                            duration: 120
                            easing.type: Easing.OutQuad
                        }
                    }

                    Text {
                        text: "Navigation"
                        color: ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_caption
                        font.bold: true
                        anchors.left: parent.left
                        anchors.leftMargin: 6
                        anchors.bottom: parent.bottom
                    }
                }

                // Navigation Items using SidebarItem
                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "home"
                    label: "Home"
                    isActive: currentRoute === "home"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("home")
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "snapshot"
                    label: "System Snapshot"
                    isActive: currentRoute === "snapshot"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("snapshot")
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "monitor"
                    label: "System Monitor"
                    isActive: currentRoute === "system-monitor"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("system-monitor")
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "events"
                    label: "Event Viewer"
                    isActive: currentRoute === "event-viewer"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("event-viewer")
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "network"
                    label: "Network Scan"
                    isActive: currentRoute === "net-scan" || currentRoute === "nmap-result"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("net-scan")
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "scan"
                    label: "Scan Center"
                    isActive: currentRoute === "scan-tool"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("scan-tool")
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "file"
                    label: "File Function"
                    isActive: currentRoute === "file-function"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("file-function")
                }

                // Separator before secondary tools section
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    Layout.topMargin: sidebar.sidebarExpanded ? 10 : 8
                    Layout.bottomMargin: sidebar.sidebarExpanded ? 10 : 8
                    color: ThemeManager.border()
                    opacity: sidebar.sidebarExpanded ? 0.42 : 0.24
                }

                Item {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: sidebar.sidebarExpanded ? 22 : 0
                    opacity: sidebar.sidebarExpanded ? 1 : 0
                    clip: true

                    Behavior on Layout.preferredHeight {
                        NumberAnimation {
                            duration: 180
                            easing.type: Easing.OutCubic
                        }
                    }

                    Behavior on opacity {
                        NumberAnimation {
                            duration: 120
                            easing.type: Easing.OutQuad
                        }
                    }

                    Text {
                        text: "Tools"
                        color: ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_caption
                        font.bold: true
                        anchors.left: parent.left
                        anchors.leftMargin: 6
                        anchors.bottom: parent.bottom
                    }
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "assistant"
                    label: "Security Assistant"
                    isActive: currentRoute === "ai-assistant"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("ai-assistant")
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "sandbox"
                    label: "Sandbox"
                    isActive: currentRoute === "sandbox-lab"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("sandbox-lab")
                    visible: Backend ? !Backend.isLinux : true
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "history"
                    label: "History"
                    isActive: currentRoute === "history"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("history")
                }

                SidebarItem {
                    Layout.fillWidth: true
                    iconName: "settings"
                    label: "Settings"
                    isActive: currentRoute === "settings"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("settings")
                }

                Item { Layout.fillHeight: true }
            }
        }

        // ===== MAIN CONTENT =====
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: ThemeManager.background()

            // Top bar with page context and alerts
            Rectangle {
                id: topBar
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 58
                color: ThemeManager.panel()
                border.color: ThemeManager.border()
                border.width: 1
                z: 10

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    spacing: 12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        Text {
                            text: routeTitle(currentRoute)
                            color: ThemeManager.foreground()
                            font.pixelSize: ThemeManager.fontSize_h3
                            font.bold: true
                        }

                        Text {
                            text: routeSubtitle(currentRoute)
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    Rectangle {
                        id: alertsBtn
                        width: Math.max(104, alertsRow.implicitWidth + 28)
                        height: 38
                        radius: 8
                        color: bellMouse.containsMouse ? ThemeManager.elevated() : ThemeManager.background()
                        border.color: ThemeManager.border()
                        border.width: 1

                        RowLayout {
                            id: alertsRow
                            anchors.centerIn: parent
                            spacing: 8

                            SidebarIcon {
                                width: 16
                                height: 16
                                name: "bell"
                                iconColor: ThemeManager.foreground()
                            }

                            Text {
                                text: "Alerts"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_small
                                font.bold: true
                            }
                        }

                        Rectangle {
                            visible: NotificationService ? NotificationService.unreadCount > 0 : false
                            anchors.top: parent.top
                            anchors.right: parent.right
                            anchors.topMargin: -6
                            anchors.rightMargin: -6
                            width: 20
                            height: 20
                            radius: 10
                            color: ThemeManager.danger
                            border.color: ThemeManager.panel()
                            border.width: 2

                            Text {
                                anchors.centerIn: parent
                                text: NotificationService ? Math.min(NotificationService.unreadCount, 99) : ""
                                color: "white"
                                font.pixelSize: ThemeManager.fontSize_caption
                                font.bold: true
                            }
                        }

                        MouseArea {
                            id: bellMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: notificationCenter.toggle()
                        }
                    }
                }
            }

            // Page content area (below top bar)
            // Each page is created only on first navigation (lazy Loader) and
            // kept alive afterwards. Pages that are never visited are never created.
            Item {
                anchors.top: topBar.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom

                // ── HomePage ─────────────────────────────────────
                // Loaded immediately — it is the startup landing page.
                Loader {
                    id: homeLoader
                    anchors.fill: parent
                    source: "pages/HomePage.qml"
                    active: true
                    visible: currentRoute === "home"
                }

                // ── HistoryPage ───────────────────────────────────
                Loader {
                    id: historyLoader
                    anchors.fill: parent
                    source: "pages/HistoryPage.qml"
                    active: _wasLoaded || currentRoute === "history"
                    visible: currentRoute === "history"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                    onLoaded: item.requestedTab = Qt.binding(
                        function() { return window.historyRequestedTab })
                }
                Connections {
                    target: historyLoader.item
                    function onRequestRoute(route) { loadRoute(route) }
                }

                // ── EventViewer ───────────────────────────────────
                Loader {
                    id: eventViewerLoader
                    anchors.fill: parent
                    source: "pages/EventViewer.qml"
                    active: _wasLoaded || currentRoute === "event-viewer"
                    visible: currentRoute === "event-viewer"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }

                // ── SystemSnapshot ────────────────────────────────
                Loader {
                    id: snapshotLoader
                    anchors.fill: parent
                    source: "pages/SystemSnapshot.qml"
                    active: _wasLoaded || currentRoute === "snapshot"
                    visible: currentRoute === "snapshot"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }

                // ── SystemMonitor ─────────────────────────────────
                Loader {
                    id: systemMonitorLoader
                    anchors.fill: parent
                    source: "pages/SystemMonitor.qml"
                    active: _wasLoaded || currentRoute === "system-monitor"
                    visible: currentRoute === "system-monitor"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }

                // ── NetworkScan ───────────────────────────────────
                Loader {
                    id: networkScanLoader
                    anchors.fill: parent
                    source: "pages/NetworkScan.qml"
                    active: _wasLoaded || currentRoute === "net-scan"
                    visible: currentRoute === "net-scan"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }

                // ── NmapScanResultPage ────────────────────────────
                Loader {
                    id: nmapResultLoader
                    anchors.fill: parent
                    source: "pages/NmapScanResultPage.qml"
                    active: _wasLoaded || currentRoute === "nmap-result"
                    visible: currentRoute === "nmap-result"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }

                // ── ScanCenter ────────────────────────────────────
                Loader {
                    id: scanCenterLoader
                    anchors.fill: parent
                    source: "pages/ScanCenter.qml"
                    active: _wasLoaded || currentRoute === "scan-tool"
                    visible: currentRoute === "scan-tool"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }
                Connections {
                    target: scanCenterLoader.item
                    function onRequestRoute(route) { loadRoute(route) }
                    function onAiBriefTextChanged() {
                        window._scanAiBriefText = scanCenterLoader.item.aiBriefText
                    }
                    function onAiDetailedTextChanged() {
                        window._scanAiDetailedText = scanCenterLoader.item.aiDetailedText
                    }
                }

                // ── AiReport ──────────────────────────────────────
                Loader {
                    id: aiReportLoader
                    anchors.fill: parent
                    source: "pages/AiReport.qml"
                    active: _wasLoaded || currentRoute === "ai-report"
                    visible: currentRoute === "ai-report"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                    onLoaded: {
                        item.briefText = Qt.binding(
                            function() { return window._scanAiBriefText })
                        item.detailedText = Qt.binding(
                            function() { return window._scanAiDetailedText })
                    }
                }

                // ── FileFunction ──────────────────────────────────
                Loader {
                    id: fileFunctionLoader
                    anchors.fill: parent
                    source: "pages/FileFunction.qml"
                    active: _wasLoaded || currentRoute === "file-function"
                    visible: currentRoute === "file-function"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }

                // ── SandboxLabPage ────────────────────────────────
                Loader {
                    id: sandboxLoader
                    anchors.fill: parent
                    source: "pages/SandboxLabPage.qml"
                    active: _wasLoaded || currentRoute === "sandbox-lab"
                    visible: currentRoute === "sandbox-lab"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }

                // ── SecurityAssistant ─────────────────────────────
                Loader {
                    id: securityAssistantLoader
                    anchors.fill: parent
                    source: "pages/SecurityAssistant.qml"
                    active: _wasLoaded || currentRoute === "ai-assistant"
                    visible: currentRoute === "ai-assistant"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }

                // ── SettingsPage ──────────────────────────────────
                Loader {
                    id: settingsLoader
                    anchors.fill: parent
                    source: "pages/SettingsPage.qml"
                    active: _wasLoaded || currentRoute === "settings"
                    visible: currentRoute === "settings"
                    property bool _wasLoaded: false
                    onStatusChanged: if (status === Loader.Ready) _wasLoaded = true
                }
            }
        }
    }
    
    // ===== NOTIFICATION CENTER (overlay on top of everything) =====
    NotificationCenter {
        id: notificationCenter
        anchors.fill: parent
        z: 1000
    }
}
