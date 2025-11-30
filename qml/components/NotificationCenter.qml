import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

/**
 * NotificationCenter - Sliding panel for application notifications
 * 
 * Opens from the right side when triggered by the bell icon.
 * Shows a list of notifications with dismiss functionality.
 */
Item {
    id: root
    anchors.fill: parent
    
    // Public properties
    property bool isOpen: false
    
    // Notification model
    ListModel {
        id: notificationModel
    }
    
    // Connect to NotificationService
    Connections {
        target: NotificationService || null
        enabled: target !== null
        
        function onNotificationListUpdated() {
            refreshNotifications()
        }
        
        function onNotificationReceived(id, title, message, type) {
            // Could show a mini popup here if desired
        }
    }
    
    // Refresh notifications from backend
    function refreshNotifications() {
        if (!NotificationService) return
        
        notificationModel.clear()
        var notifications = NotificationService.getNotifications()
        for (var i = 0; i < notifications.length; i++) {
            notificationModel.append(notifications[i])
        }
    }
    
    // Open/close functions
    function open() {
        isOpen = true
        refreshNotifications()
        if (NotificationService) {
            NotificationService.markAllRead()
        }
    }
    
    function close() {
        isOpen = false
    }
    
    function toggle() {
        if (isOpen) close()
        else open()
    }
    
    // Dim overlay
    Rectangle {
        id: dimOverlay
        anchors.fill: parent
        color: "#000000"
        opacity: isOpen ? 0.4 : 0
        visible: opacity > 0
        z: 998
        
        Behavior on opacity {
            NumberAnimation { duration: 250; easing.type: Easing.InOutQuad }
        }
        
        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }
    
    // Notification panel
    Rectangle {
        id: panel
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: isOpen ? 380 : 0
        color: ThemeManager.panel()
        z: 999
        clip: true
        
        Behavior on width {
            NumberAnimation { duration: 250; easing.type: Easing.InOutQuad }
        }
        
        // Left border accent
        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 1
            color: ThemeManager.border()
        }
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 0
            spacing: 0
            visible: panel.width > 50
            opacity: panel.width > 200 ? 1 : 0
            
            Behavior on opacity {
                NumberAnimation { duration: 150 }
            }
            
            // Header
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 60
                color: ThemeManager.elevated()
                
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    spacing: 12
                    
                    Text {
                        text: "🔔"
                        font.pixelSize: 20
                    }
                    
                    Text {
                        text: "Notifications"
                        color: ThemeManager.foreground()
                        font.pixelSize: 18
                        font.bold: true
                        Layout.fillWidth: true
                    }
                    
                    // Clear all button
                    Rectangle {
                        width: clearAllText.implicitWidth + 16
                        height: 28
                        radius: 6
                        color: clearAllMouse.containsMouse ? ThemeManager.surface() : "transparent"
                        visible: notificationModel.count > 0
                        
                        Text {
                            id: clearAllText
                            anchors.centerIn: parent
                            text: "Clear All"
                            color: ThemeManager.muted()
                            font.pixelSize: 12
                        }
                        
                        MouseArea {
                            id: clearAllMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (NotificationService) {
                                    NotificationService.clearAll()
                                }
                            }
                        }
                    }
                    
                    // Close button
                    Rectangle {
                        width: 32
                        height: 32
                        radius: 6
                        color: closeButtonMouse.containsMouse ? ThemeManager.surface() : "transparent"
                        
                        Text {
                            anchors.centerIn: parent
                            text: "✕"
                            color: ThemeManager.muted()
                            font.pixelSize: 16
                        }
                        
                        MouseArea {
                            id: closeButtonMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.close()
                        }
                    }
                }
            }
            
            // Divider
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: ThemeManager.border()
            }
            
            // Notification list
            ListView {
                id: notificationList
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: notificationModel
                clip: true
                spacing: 0
                
                // Empty state
                Text {
                    anchors.centerIn: parent
                    text: "No notifications"
                    color: ThemeManager.muted()
                    font.pixelSize: 14
                    visible: notificationModel.count === 0
                }
                
                delegate: Rectangle {
                    width: notificationList.width
                    height: notificationContent.implicitHeight + 24
                    color: delegateMouse.containsMouse ? ThemeManager.elevated() : "transparent"
                    
                    // Left colored border based on type
                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 4
                        color: {
                            if (model.type === "error") return "#EF4444"
                            if (model.type === "warning") return "#F59E0B"
                            if (model.type === "success") return "#22C55E"
                            return ThemeManager.accent  // info
                        }
                    }
                    
                    ColumnLayout {
                        id: notificationContent
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        spacing: 4
                        
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            
                            // Type icon
                            Text {
                                text: {
                                    if (model.type === "error") return "❌"
                                    if (model.type === "warning") return "⚠️"
                                    if (model.type === "success") return "✅"
                                    return "ℹ️"
                                }
                                font.pixelSize: 14
                            }
                            
                            // Title
                            Text {
                                text: model.title || ""
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            
                            // Time
                            Text {
                                text: model.time || ""
                                color: ThemeManager.muted()
                                font.pixelSize: 11
                            }
                            
                            // Dismiss button
                            Rectangle {
                                width: 24
                                height: 24
                                radius: 12
                                color: dismissMouse.containsMouse ? ThemeManager.surface() : "transparent"
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "✕"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 12
                                }
                                
                                MouseArea {
                                    id: dismissMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (NotificationService) {
                                            NotificationService.clearNotification(model.id)
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Message
                        Text {
                            text: model.message || ""
                            color: ThemeManager.muted()
                            font.pixelSize: 13
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            Layout.leftMargin: 22
                        }
                    }
                    
                    // Bottom divider
                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        height: 1
                        color: ThemeManager.border()
                        opacity: 0.5
                    }
                    
                    MouseArea {
                        id: delegateMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        // Don't block clicks to child elements
                        propagateComposedEvents: true
                        onClicked: mouse.accepted = false
                        onPressed: mouse.accepted = false
                        onReleased: mouse.accepted = false
                    }
                }
                
                ScrollBar.vertical: ScrollBar {
                    active: true
                    policy: ScrollBar.AsNeeded
                }
            }
        }
    }
    
    // Initialize on completion
    Component.onCompleted: {
        refreshNotifications()
    }
}
