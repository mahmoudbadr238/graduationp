import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"
import "../components"

/**
 * SecurityAssistant - Smart Local AI Security Chatbot Page
 * 
 * Provides a conversational interface for security assistance with:
 * - Conversation memory and context
 * - Intent-based routing
 * - Structured responses with sources and confidence
 * - Technical details collapsible
 * 
 * 100% local - no network calls, all AI runs on the user's machine.
 */
Item {
    id: root
    anchors.fill: parent

    // State
    property bool isThinking: false
    property int themeUpdateTrigger: 0
    property var lastStructuredResponse: null  // Store last smart response for details

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

        function onChatMessageAdded(role, content) {
            // Add message to list
            chatModel.append({
                "role": role,
                "content": content,
                "timestamp": new Date().toLocaleTimeString(Qt.locale(), "hh:mm"),
                "hasStructuredData": false,
                "structuredData": ""
            })

            // Stop thinking indicator when assistant responds
            // Use Qt.callLater to defer this to avoid binding loops
            if (role === "assistant") {
                Qt.callLater(function() { isThinking = false })
            }

            // Scroll is handled by ListView.onCountChanged, no need to call here
        }
        
        function onSmartAssistantResponse(responseJson) {
            // Parse JSON string response
            try {
                var response = JSON.parse(responseJson)
                // Store structured response for last message
                lastStructuredResponse = response
                
                // Update the last assistant message with structured data
                if (chatModel.count > 0) {
                    var lastIndex = chatModel.count - 1
                    if (chatModel.get(lastIndex).role === "assistant") {
                        chatModel.setProperty(lastIndex, "hasStructuredData", true)
                        chatModel.setProperty(lastIndex, "structuredData", responseJson)
                    }
                }
            } catch (e) {
                console.log("[SecurityAssistant] Failed to parse response:", e)
            }
        }
        
        function onSmartAssistantError(errorMsg) {
            console.log("[SecurityAssistant] Smart assistant error:", errorMsg)
            isThinking = false
        }
    }

    // Chat message model
    ListModel {
        id: chatModel
    }

    // Initial welcome message - Sentinel tone
    Component.onCompleted: {
        chatModel.append({
            "role": "assistant",
            "content": "**Hello! I'm Sentinel, your local security assistant.** 🛡️\n\nThink of me as a junior security analyst sitting on your machine. I can:\n\n• **Check your security status** - Defender, Firewall, real-time protection\n• **Explain Windows events** - What happened, why, and should you worry\n• **Answer security questions** - Best practices, threats, how to stay safe\n• **Guide you through the app** - How to use any Sentinel feature\n\nI remember our conversation, so ask follow-up questions anytime.\n\n*Everything I do is 100% local - I never connect to the internet.*",
            "timestamp": new Date().toLocaleTimeString(Qt.locale(), "hh:mm"),
            "hasStructuredData": false,
            "structuredData": ""
        })
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
                text: "🧠"
                font.pixelSize: 32
            }

            Column {
                spacing: 4

                Text {
                    text: "Smart Security Assistant"
                    font.pixelSize: 28
                    font.bold: true
                    color: ThemeManager.foreground()
                }

                Text {
                    text: "Context-Aware • Memory • Local-Only"
                    font.pixelSize: 12
                    color: ThemeManager.muted()
                }
            }

            Item { Layout.fillWidth: true }

            // AI Mode indicator
            Rectangle {
                width: aiModeLabel.implicitWidth + 20
                height: 28
                radius: 14
                color: Backend && Backend.aiAvailable() ? 
                       ThemeManager.accent : 
                       ThemeManager.surface()
                opacity: 0.8

                Text {
                    id: aiModeLabel
                    anchors.centerIn: parent
                    text: Backend ? (Backend.aiAvailable() ? "AI Ready" : "AI Unavailable") : "Loading..."
                    color: Backend && Backend.aiAvailable() ? 
                           "white" : 
                           ThemeManager.muted()
                    font.pixelSize: 11
                    font.bold: true
                }
            }
            
            // Explain Recent Events button
            Rectangle {
                width: explainEventsLabel.implicitWidth + 24
                height: 32
                radius: 8
                color: explainMouse.containsMouse ? ThemeManager.accent : ThemeManager.elevated()
                
                Text {
                    id: explainEventsLabel
                    anchors.centerIn: parent
                    text: "📋 Explain Events"
                    color: explainMouse.containsMouse ? "white" : ThemeManager.foreground()
                    font.pixelSize: 12
                }
                
                MouseArea {
                    id: explainMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (Backend && !isThinking) {
                            Backend.explainRecentEvents("5")
                            isThinking = true
                        }
                    }
                }
                
                ToolTip.visible: explainMouse.containsMouse
                ToolTip.text: "Ask assistant to explain recent events"
                ToolTip.delay: 500
            }

            // Clear chat button
            Rectangle {
                width: 36
                height: 36
                radius: 8
                color: clearMouse.containsMouse ? ThemeManager.elevated() : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "🗑️"
                    font.pixelSize: 16
                }

                MouseArea {
                    id: clearMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        chatModel.clear()
                        if (Backend) Backend.clearChatHistory()
                        lastStructuredResponse = null
                        // Re-add welcome message
                        chatModel.append({
                            "role": "assistant",
                            "content": "Chat cleared. How can I help you with security?",
                            "timestamp": new Date().toLocaleTimeString(Qt.locale(), "hh:mm"),
                            "hasStructuredData": false,
                            "structuredData": ""
                        })
                    }
                }

                ToolTip.visible: clearMouse.containsMouse
                ToolTip.text: "Clear chat history"
                ToolTip.delay: 500
            }
        }

        // Chat area
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: ThemeManager.panel()
            radius: 16
            border.color: ThemeManager.border()
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 0

                // Messages list
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    ListView {
                        id: chatListView
                        width: parent.width
                        model: chatModel
                        spacing: 12

                        delegate: Item {
                            id: delegateItem
                            width: chatListView.width
                            height: messageBubble.height + 8

                            // SIMPLIFIED DELEGATE FOR DEBUGGING
                            // Remove all structured data parsing - just show messages

                            // Message bubble
                            Rectangle {
                                id: messageBubble
                                width: Math.min(messageColumn.implicitWidth + 32, parent.width * 0.85)
                                height: messageColumn.implicitHeight + 24
                                radius: 16

                                // Position based on role
                                anchors.right: model.role === "user" ? parent.right : undefined
                                anchors.left: model.role === "assistant" ? parent.left : undefined

                                // Colors based on role
                                color: model.role === "user" ? 
                                       ThemeManager.accent : 
                                       ThemeManager.surface()

                                Column {
                                    id: messageColumn
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 8

                                    // Main message text - PLAIN TEXT ONLY
                                    Text {
                                        id: messageText
                                        width: parent.width
                                        text: model.content
                                        color: model.role === "user" ? 
                                               "white" : 
                                               ThemeManager.foreground()
                                        font.pixelSize: 14
                                        wrapMode: Text.Wrap
                                        lineHeight: 1.4
                                        textFormat: Text.PlainText
                                    }

                                    // Timestamp
                                    Text {
                                        text: model.timestamp
                                        color: model.role === "user" ? 
                                               Qt.rgba(1, 1, 1, 0.7) : 
                                               ThemeManager.muted()
                                        font.pixelSize: 10
                                        anchors.right: model.role === "user" ? parent.right : undefined
                                    }
                                }
                            }
                        }

                        // Auto-scroll to bottom
                        onCountChanged: {
                            Qt.callLater(function() {
                                chatListView.positionViewAtEnd()
                            })
                        }
                    }
                }

                // Thinking indicator
                Rectangle {
                    Layout.fillWidth: true
                    height: isThinking ? 40 : 0
                    color: "transparent"
                    visible: isThinking
                    clip: true

                    Behavior on height {
                        NumberAnimation { duration: 200 }
                    }

                    RowLayout {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        spacing: 8

                        // Animated dots
                        Row {
                            spacing: 4

                            Repeater {
                                model: 3

                                Rectangle {
                                    width: 8
                                    height: 8
                                    radius: 4
                                    color: ThemeManager.accent

                                    SequentialAnimation on opacity {
                                        running: isThinking
                                        loops: Animation.Infinite
                                        NumberAnimation { 
                                            to: 0.3
                                            duration: 300
                                            easing.type: Easing.InOutQuad
                                        }
                                        PauseAnimation { duration: index * 150 }
                                        NumberAnimation { 
                                            to: 1.0
                                            duration: 300
                                            easing.type: Easing.InOutQuad
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            text: "Thinking locally..."
                            color: ThemeManager.muted()
                            font.pixelSize: 12
                            font.italic: true
                        }
                    }
                }

                // Divider
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: ThemeManager.border()
                    Layout.topMargin: 12
                }

                // Input area
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    spacing: 12

                    Rectangle {
                        Layout.fillWidth: true
                        height: Math.min(100, Math.max(44, inputField.implicitHeight + 16))
                        color: ThemeManager.surface()
                        radius: 12
                        border.color: inputField.activeFocus ? ThemeManager.accent : ThemeManager.border()
                        border.width: inputField.activeFocus ? 2 : 1

                        Behavior on border.color {
                            ColorAnimation { duration: 150 }
                        }

                        ScrollView {
                            anchors.fill: parent
                            anchors.margins: 8

                            TextArea {
                                id: inputField
                                placeholderText: "Ask about security, events, or system status..."
                                placeholderTextColor: ThemeManager.muted()
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                wrapMode: TextArea.Wrap
                                background: Rectangle { color: "transparent" }

                                Keys.onReturnPressed: function(event) {
                                    if (!(event.modifiers & Qt.ShiftModifier)) {
                                        sendMessage()
                                        event.accepted = true
                                    }
                                }
                            }
                        }
                    }

                    // Send button
                    Rectangle {
                        width: 48
                        height: 48
                        radius: 12
                        color: sendMouse.containsMouse && !isThinking ? 
                               Qt.darker(ThemeManager.accent, 1.1) : 
                               ThemeManager.accent
                        opacity: isThinking ? 0.5 : 1.0

                        Text {
                            anchors.centerIn: parent
                            text: "➤"
                            color: "white"
                            font.pixelSize: 20
                            font.bold: true
                        }

                        MouseArea {
                            id: sendMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: isThinking ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                            onClicked: {
                                if (!isThinking) {
                                    sendMessage()
                                }
                            }
                        }
                    }
                }

                // Quick suggestions
                Flow {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    spacing: 8

                    Repeater {
                        model: [
                            "What's my security status?",
                            "Explain recent events",
                            "Is my firewall enabled?",
                            "Any security concerns?"
                        ]

                        Rectangle {
                            width: suggestionText.implicitWidth + 20
                            height: 32
                            radius: 16
                            color: suggestionMouse.containsMouse ? 
                                   ThemeManager.elevated() : 
                                   ThemeManager.surface()
                            border.color: ThemeManager.border()
                            border.width: 1

                            Text {
                                id: suggestionText
                                anchors.centerIn: parent
                                text: modelData
                                color: ThemeManager.muted()
                                font.pixelSize: 12
                            }

                            MouseArea {
                                id: suggestionMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    inputField.text = modelData
                                    sendMessage()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Send message function
    function sendMessage() {
        var text = inputField.text.trim()
        if (text.length === 0 || isThinking) return

        inputField.text = ""
        isThinking = true

        if (Backend) {
            // Use smart assistant for intelligent responses
            Backend.sendSmartMessage(text)
        } else {
            // Fallback if backend not available
            chatModel.append({
                "role": "user",
                "content": text,
                "timestamp": new Date().toLocaleTimeString(Qt.locale(), "hh:mm"),
                "hasStructuredData": false,
                "structuredData": ""
            })
            chatModel.append({
                "role": "assistant",
                "content": "Backend not available. Please restart the application.",
                "timestamp": new Date().toLocaleTimeString(Qt.locale(), "hh:mm"),
                "hasStructuredData": false,
                "structuredData": ""
            })
            isThinking = false
        }
    }
}
