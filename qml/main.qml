import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "pages"
import "ui"

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

    // ===== TOAST NOTIFICATION SYSTEM =====
    property string toastMessage: ""
    property string toastType: "info"
    
    Connections {
        target: Backend || null
        enabled: target !== null
        function onToast(message, type) {
            toastMessage = message
            toastType = type || "info"
            toastTimer.restart()
            toastNotification.visible = true
        }
    }
    
    Timer {
        id: toastTimer
        interval: 3000
        onTriggered: toastNotification.visible = false
    }

    // ===== NAVIGATION STATE =====
    property string currentRoute: "home"

    function loadRoute(routeId) {
        console.log("[NAV] Loading route:", routeId)
        currentRoute = routeId
        console.log("[NAV] Route loaded:", routeId)
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ===== SIDEBAR =====
        Rectangle {
            Layout.preferredWidth: 240
            Layout.fillHeight: true
            color: ThemeManager.panel()
            
            // Update when font size changes
            property int fontTrigger: ThemeManager.fontSizeUpdateTrigger

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 8

                // Logo - clickable to go home
                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    color: "transparent"
                    Layout.topMargin: 8
                    Layout.bottomMargin: 16
                    
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "SENTINEL"
                        color: ThemeManager.accent
                        font.pixelSize: ThemeManager.fontSize_h3()
                        font.bold: true
                    }
                    
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: loadRoute("home")
                    }
                }
                
                // Home Navigation Item
                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: 8
                    color: currentRoute === "home" ? ThemeManager.elevated() : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: loadRoute("home")
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: "🏠  Home"
                        color: currentRoute === "home" ? ThemeManager.accent : ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body()
                        font.weight: currentRoute === "home" ? Font.Bold : Font.Normal
                    }
                }

                // Navigation Items
                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: 8
                    color: currentRoute === "events" ? ThemeManager.elevated() : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: loadRoute("events")
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: "Event Viewer"
                        color: currentRoute === "events" ? ThemeManager.accent : ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body()
                        font.weight: currentRoute === "events" ? Font.Bold : Font.Normal
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: 8
                    color: currentRoute === "snapshot" ? ThemeManager.elevated() : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: loadRoute("snapshot")
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: "System Snapshot"
                        color: currentRoute === "snapshot" ? ThemeManager.accent : ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body()
                        font.weight: currentRoute === "snapshot" ? Font.Bold : Font.Normal
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: 8
                    color: currentRoute === "history" ? ThemeManager.elevated() : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: loadRoute("history")
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: "Scan History"
                        color: currentRoute === "history" ? ThemeManager.accent : ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body()
                        font.weight: currentRoute === "history" ? Font.Bold : Font.Normal
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: 8
                    color: currentRoute === "net-scan" ? ThemeManager.elevated() : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: loadRoute("net-scan")
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: "Network Scan"
                        color: currentRoute === "net-scan" ? ThemeManager.accent : ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body()
                        font.weight: currentRoute === "net-scan" ? Font.Bold : Font.Normal
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: 8
                    color: currentRoute === "scan-tool" ? ThemeManager.elevated() : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: loadRoute("scan-tool")
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: "Scan Tool"
                        color: currentRoute === "scan-tool" ? ThemeManager.accent : ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body()
                        font.weight: currentRoute === "scan-tool" ? Font.Bold : Font.Normal
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: 8
                    color: currentRoute === "dlp" ? ThemeManager.elevated() : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: loadRoute("dlp")
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: "Data Loss Prevention"
                        color: currentRoute === "dlp" ? ThemeManager.accent : ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body()
                        font.weight: currentRoute === "dlp" ? Font.Bold : Font.Normal
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 44
                    radius: 8
                    color: currentRoute === "settings" ? ThemeManager.elevated() : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: loadRoute("settings")
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        text: "Settings"
                        color: currentRoute === "settings" ? ThemeManager.accent : ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body()
                        font.weight: currentRoute === "settings" ? Font.Bold : Font.Normal
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // ===== MAIN CONTENT =====
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: ThemeManager.background()

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
            
            ScanTool {
                anchors.fill: parent
                visible: currentRoute === "scan-tool"
            }
            
            DataLossPrevention {
                anchors.fill: parent
                visible: currentRoute === "dlp"
            }
            
            SettingsPage {
                anchors.fill: parent
                visible: currentRoute === "settings"
            }
            
            // Toast Notification Overlay
            Rectangle {
                id: toastNotification
                visible: false
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottomMargin: 20
                width: Math.min(400, parent.width - 40)
                height: 60
                radius: 8
                z: 100
                color: {
                    if (toastType === "success") return "#10B981"
                    else if (toastType === "error") return "#EF4444"
                    else return "#3B82F6"
                }
                
                Behavior on opacity {
                    NumberAnimation { duration: 200 }
                }
                
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12
                    
                    Text {
                        text: {
                            if (toastType === "success") return "✓"
                            else if (toastType === "error") return "✕"
                            else return "ℹ"
                        }
                        color: "white"
                        font.pixelSize: 18
                        font.bold: true
                    }
                    
                    Text {
                        text: toastMessage
                        color: "white"
                        font.pixelSize: 14
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                    
                    Item { Layout.fillWidth: true }
                }
            }
        }
    }
}

