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
    title: "Sentinel - Endpoint Security Suite v1.0.0"

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
    }

    // ===== NAVIGATION STATE =====
    property string currentRoute: "home"

    function loadRoute(routeId) {
        console.log("[NAV] Loading route:", routeId)
        currentRoute = routeId
        console.log("[NAV] Route loaded:", routeId)
    }

    // ===== MAIN LAYOUT =====
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ===== COLLAPSIBLE SIDEBAR =====
        Rectangle {
            id: sidebar
            Layout.preferredWidth: sidebarExpanded ? 230 : 70
            Layout.fillHeight: true
            color: ThemeManager.panel()
            
            property bool sidebarExpanded: false
            
            // Smooth width animation
            Behavior on Layout.preferredWidth {
                NumberAnimation { 
                    duration: 200
                    easing.type: Easing.InOutQuad 
                }
            }
            
            // Hover detection using HoverHandler (doesn't block child events)
            HoverHandler {
                id: sidebarHover
                onHoveredChanged: {
                    sidebar.sidebarExpanded = hovered
                }
            }
            
            // Update when font size changes
            property int fontTrigger: ThemeManager.fontSizeUpdateTrigger

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: sidebar.sidebarExpanded ? 16 : 8
                spacing: 8
                
                Behavior on anchors.margins {
                    NumberAnimation { duration: 200 }
                }

                // Logo - clickable to go home
                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    color: "transparent"
                    Layout.topMargin: 8
                    Layout.bottomMargin: 16
                    
                    RowLayout {
                        anchors.fill: parent
                        spacing: 8
                        
                        Text {
                            text: "🛡️"
                            font.pixelSize: 22
                            Layout.alignment: sidebar.sidebarExpanded ? Qt.AlignLeft : Qt.AlignHCenter
                            Layout.fillWidth: !sidebar.sidebarExpanded
                        }
                        
                        Text {
                            text: "SENTINEL"
                            color: ThemeManager.accent
                            font.pixelSize: ThemeManager.fontSize_h3()
                            font.bold: true
                            visible: sidebar.sidebarExpanded
                            opacity: sidebar.sidebarExpanded ? 1 : 0
                            
                            Behavior on opacity {
                                NumberAnimation { duration: 150 }
                            }
                        }
                    }
                    
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: loadRoute("home")
                    }
                }
                
                // Navigation Items using SidebarItem
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "🏠"
                    label: "Home"
                    isActive: currentRoute === "home"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("home")
                }
                
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "📋"
                    label: "Event Viewer"
                    isActive: currentRoute === "events"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("events")
                }
                
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "📊"
                    label: "System Snapshot"
                    isActive: currentRoute === "snapshot"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("snapshot")
                }
                
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "📜"
                    label: "Scan History"
                    isActive: currentRoute === "history"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("history")
                }
                
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "🌐"
                    label: "Network Scan"
                    isActive: currentRoute === "net-scan" || currentRoute === "nmap-result"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("net-scan")
                }
                
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "🔍"
                    label: "Scan Tool"
                    isActive: currentRoute === "scan-tool"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("scan-tool")
                }
                
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "🛡️"
                    label: "Data Loss Prevention"
                    isActive: currentRoute === "dlp"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("dlp")
                }
                
                // Separator before AI section
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    Layout.topMargin: 8
                    Layout.bottomMargin: 8
                    color: ThemeManager.border()
                    opacity: 0.5
                }
                
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "🤖"
                    label: "AI Assistant"
                    isActive: currentRoute === "ai-assistant"
                    expanded: sidebar.sidebarExpanded
                    onClicked: loadRoute("ai-assistant")
                }
                
                SidebarItem {
                    Layout.fillWidth: true
                    icon: "⚙️"
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
            
            // Top bar with notification bell
            Rectangle {
                id: topBar
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 50
                color: ThemeManager.panel()
                z: 10
                
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    spacing: 12
                    
                    Item { Layout.fillWidth: true }
                    
                    // Notification bell
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 8
                        color: bellMouse.containsMouse ? ThemeManager.elevated() : "transparent"
                        
                        Text {
                            anchors.centerIn: parent
                            text: "🔔"
                            font.pixelSize: 18
                        }
                        
                        // Unread badge
                        Rectangle {
                            visible: NotificationService ? NotificationService.unreadCount > 0 : false
                            anchors.top: parent.top
                            anchors.right: parent.right
                            anchors.topMargin: 4
                            anchors.rightMargin: 4
                            width: 18
                            height: 18
                            radius: 9
                            color: "#EF4444"
                            
                            Text {
                                anchors.centerIn: parent
                                text: NotificationService ? Math.min(NotificationService.unreadCount, 99) : ""
                                color: "white"
                                font.pixelSize: 10
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
            Item {
                anchors.top: topBar.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom

                // Simple page switching - show/hide based on currentRoute
                HomePage {
                    anchors.fill: parent
                    visible: currentRoute === "home"
                }
                
                EventViewer {
                    anchors.fill: parent
                    visible: currentRoute === "events"
                }
                
                SystemSnapshot {
                    anchors.fill: parent
                    visible: currentRoute === "snapshot"
                }
                
                ScanHistory {
                    anchors.fill: parent
                    visible: currentRoute === "history"
                }
                
                NetworkScan {
                    anchors.fill: parent
                    visible: currentRoute === "net-scan"
                }
                
                NmapScanResultPage {
                    id: nmapResultPage
                    anchors.fill: parent
                    visible: currentRoute === "nmap-result"
                }
                
                ScanTool {
                    anchors.fill: parent
                    visible: currentRoute === "scan-tool"
                }
                
                DataLossPrevention {
                    anchors.fill: parent
                    visible: currentRoute === "dlp"
                }
                
                SecurityAssistant {
                    anchors.fill: parent
                    visible: currentRoute === "ai-assistant"
                }
                
                SettingsPage {
                    anchors.fill: parent
                    visible: currentRoute === "settings"
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