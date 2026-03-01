import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"
import "../components"

/**
 * ResolutionReport - View AI resolution sessions and action audit trail
 * 
 * Shows:
 * - List of resolution sessions
 * - Actions performed in each session
 * - Outcomes and timing
 * - Export capability
 */
Item {
    id: root
    anchors.fill: parent

    // State
    property var sessions: []
    property var selectedSession: null
    property bool isLoading: false
    property int themeUpdateTrigger: 0

    // Listen to theme changes
    Connections {
        target: ThemeManager
        function onThemeModeChanged() {
            themeUpdateTrigger++
        }
    }

    // Backend connections
    Connections {
        target: Backend || null
        enabled: target !== null

        function onResolutionSessionsLoaded(sessionsJson) {
            try {
                sessions = JSON.parse(sessionsJson)
                isLoading = false
            } catch (e) {
                console.log("[ResolutionReport] Failed to parse sessions:", e)
                sessions = []
                isLoading = false
            }
        }
    }

    // Load sessions on startup
    Component.onCompleted: {
        loadSessions()
    }

    function loadSessions() {
        isLoading = true
        if (typeof Backend !== "undefined" && Backend.getResolutionSessions) {
            Backend.getResolutionSessions()
        } else {
            isLoading = false
        }
    }

    function formatTimestamp(ts) {
        if (!ts) return ""
        try {
            var date = new Date(ts)
            return date.toLocaleString()
        } catch (e) {
            return ts
        }
    }

    function outcomeColor(outcome) {
        switch(outcome) {
            case "success": return ThemeManager.success
            case "partial": return ThemeManager.warning
            case "failed": return ThemeManager.danger
            case "skipped": return ThemeManager.muted()
            default: return ThemeManager.info
        }
    }

    function actionIcon(actionType) {
        switch(actionType) {
            case "explain": return "📖"
            case "scan": return "🔍"
            case "check_status": return "✓"
            case "analyze": return "🔬"
            case "recommend": return "💡"
            case "resolve": return "🔧"
            default: return "ℹ️"
        }
    }

    // Background
    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 20

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Text {
                text: "📋"
                font.pixelSize: 32
            }

            Column {
                spacing: 4

                Text {
                    text: "Resolution Reports"
                    font.pixelSize: 24
                    font.weight: Font.Bold
                    color: ThemeManager.foreground()
                }

                Text {
                    text: "View what the AI assistant did during help sessions"
                    font.pixelSize: 14
                    color: ThemeManager.muted()
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "↻ Refresh"
                implicitHeight: 36
                
                background: Rectangle {
                    color: parent.hovered ? ThemeManager.elevated() : ThemeManager.panel()
                    radius: 6
                    border.color: ThemeManager.border()
                    border.width: 1
                }
                
                contentItem: Text {
                    text: parent.text
                    color: ThemeManager.foreground()
                    font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                
                onClicked: loadSessions()
            }
        }

        // Main content
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // Sessions list (left panel)
            Rectangle {
                Layout.preferredWidth: 350
                Layout.fillHeight: true
                color: ThemeManager.panel()
                radius: 8
                
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12
                    
                    Text {
                        text: "Sessions (" + sessions.length + ")"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: ThemeManager.foreground()
                    }
                    
                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: ThemeManager.border()
                    }
                    
                    // Loading state
                    BusyIndicator {
                        Layout.alignment: Qt.AlignHCenter
                        running: isLoading
                        visible: isLoading
                    }
                    
                    // Empty state
                    Text {
                        visible: !isLoading && sessions.length === 0
                        text: "No resolution sessions yet.\n\nWhen you ask the chatbot to help resolve an event, the session will appear here."
                        font.pixelSize: 14
                        color: ThemeManager.muted()
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    
                    // Sessions list
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 8
                        visible: !isLoading && sessions.length > 0
                        
                        model: sessions
                        
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: sessionContent.implicitHeight + 16
                            color: selectedSession && selectedSession.session_id === modelData.session_id 
                                   ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.2) 
                                   : (sessionMouse.containsMouse ? ThemeManager.elevated() : "transparent")
                            radius: 6
                            border.color: selectedSession && selectedSession.session_id === modelData.session_id 
                                          ? ThemeManager.accent : "transparent"
                            border.width: 1
                            
                            ColumnLayout {
                                id: sessionContent
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 4
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    
                                    Rectangle {
                                        width: 8
                                        height: 8
                                        radius: 4
                                        color: modelData.status === "completed" ? ThemeManager.success : ThemeManager.warning
                                    }
                                    
                                    Text {
                                        text: modelData.event_source ? 
                                              (modelData.event_source + " #" + (modelData.event_id || "?")) : 
                                              "Session " + modelData.session_id.substring(0, 6)
                                        font.pixelSize: 14
                                        font.weight: Font.Medium
                                        color: ThemeManager.foreground()
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                }
                                
                                Text {
                                    text: modelData.event_summary || "No summary"
                                    font.pixelSize: 12
                                    color: ThemeManager.muted()
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    maximumLineCount: 2
                                    wrapMode: Text.Wrap
                                }
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    
                                    Text {
                                        text: formatTimestamp(modelData.started_at)
                                        font.pixelSize: 11
                                        color: ThemeManager.muted()
                                    }
                                    
                                    Text {
                                        text: "•"
                                        font.pixelSize: 11
                                        color: ThemeManager.muted()
                                    }
                                    
                                    Text {
                                        text: (modelData.actions ? modelData.actions.length : 0) + " actions"
                                        font.pixelSize: 11
                                        color: ThemeManager.muted()
                                    }
                                }
                            }
                            
                            MouseArea {
                                id: sessionMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: selectedSession = modelData
                            }
                        }
                    }
                }
            }

            // Session details (right panel)
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: ThemeManager.panel()
                radius: 8
                
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12
                    
                    // No session selected
                    ColumnLayout {
                        visible: !selectedSession
                        Layout.alignment: Qt.AlignCenter
                        spacing: 12
                        
                        Text {
                            text: "📋"
                            font.pixelSize: 48
                            Layout.alignment: Qt.AlignHCenter
                        }
                        
                        Text {
                            text: "Select a session to view details"
                            font.pixelSize: 16
                            color: ThemeManager.muted()
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }
                    
                    // Session details
                    ColumnLayout {
                        visible: selectedSession !== null
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 12
                        
                        // Header
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                
                                Text {
                                    text: selectedSession ? (selectedSession.event_source || "Session") + 
                                          (selectedSession.event_id ? " Event #" + selectedSession.event_id : "") : ""
                                    font.pixelSize: 18
                                    font.weight: Font.Bold
                                    color: ThemeManager.foreground()
                                }
                                
                                Text {
                                    text: selectedSession ? (selectedSession.event_summary || "No summary") : ""
                                    font.pixelSize: 14
                                    color: ThemeManager.muted()
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                            
                            Rectangle {
                                implicitWidth: statusText.implicitWidth + 16
                                implicitHeight: statusText.implicitHeight + 8
                                radius: height / 2
                                color: selectedSession && selectedSession.status === "completed" ? 
                                       ThemeManager.success : ThemeManager.warning
                                
                                Text {
                                    id: statusText
                                    anchors.centerIn: parent
                                    text: selectedSession ? selectedSession.status : ""
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    color: "#FFFFFF"
                                }
                            }
                        }
                        
                        // Session info
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 16
                            
                            Text {
                                text: "⏱ Started: " + (selectedSession ? formatTimestamp(selectedSession.started_at) : "")
                                font.pixelSize: 12
                                color: ThemeManager.muted()
                            }
                            
                            Text {
                                visible: selectedSession && selectedSession.ended_at
                                text: "✓ Ended: " + (selectedSession ? formatTimestamp(selectedSession.ended_at) : "")
                                font.pixelSize: 12
                                color: ThemeManager.muted()
                            }
                        }
                        
                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: ThemeManager.border()
                        }
                        
                        // Actions header
                        Text {
                            text: "Actions Performed"
                            font.pixelSize: 14
                            font.weight: Font.Bold
                            color: ThemeManager.foreground()
                        }
                        
                        // Actions list
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 8
                            
                            model: selectedSession ? selectedSession.actions : []
                            
                            delegate: Rectangle {
                                width: ListView.view.width
                                height: actionContent.implicitHeight + 16
                                color: ThemeManager.elevated()
                                radius: 6
                                
                                RowLayout {
                                    id: actionContent
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 12
                                    
                                    // Action icon
                                    Text {
                                        text: actionIcon(modelData.action_type)
                                        font.pixelSize: 20
                                    }
                                    
                                    // Action details
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8
                                            
                                            Text {
                                                text: modelData.description || modelData.action_type
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: ThemeManager.foreground()
                                                Layout.fillWidth: true
                                                elide: Text.ElideRight
                                            }
                                            
                                            Rectangle {
                                                implicitWidth: outcomeText.implicitWidth + 12
                                                implicitHeight: outcomeText.implicitHeight + 4
                                                radius: height / 2
                                                color: outcomeColor(modelData.outcome)
                                                
                                                Text {
                                                    id: outcomeText
                                                    anchors.centerIn: parent
                                                    text: modelData.outcome
                                                    font.pixelSize: 10
                                                    font.weight: Font.Medium
                                                    color: "#FFFFFF"
                                                }
                                            }
                                        }
                                        
                                        RowLayout {
                                            spacing: 12
                                            
                                            Text {
                                                text: formatTimestamp(modelData.timestamp)
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                            }
                                            
                                            Text {
                                                visible: modelData.duration_ms > 0
                                                text: modelData.duration_ms + "ms"
                                                font.pixelSize: 11
                                                color: ThemeManager.muted()
                                            }
                                        }
                                        
                                        // Error message if failed
                                        Text {
                                            visible: modelData.error && modelData.error.length > 0
                                            text: "⚠ " + (modelData.error || "")
                                            font.pixelSize: 12
                                            color: ThemeManager.danger
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }
                                    }
                                }
                            }
                            
                            // Empty actions
                            Text {
                                anchors.centerIn: parent
                                visible: parent.count === 0
                                text: "No actions recorded"
                                font.pixelSize: 14
                                color: ThemeManager.muted()
                            }
                        }
                        
                        // Summary
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: summaryContent.implicitHeight + 16
                            color: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.1)
                            radius: 6
                            visible: selectedSession && selectedSession.summary && selectedSession.summary.length > 0
                            
                            ColumnLayout {
                                id: summaryContent
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 4
                                
                                Text {
                                    text: "📝 Summary"
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    color: ThemeManager.accent
                                }
                                
                                Text {
                                    text: selectedSession ? selectedSession.summary : ""
                                    font.pixelSize: 14
                                    color: ThemeManager.foreground()
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
