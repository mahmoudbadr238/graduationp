import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Item {
    id: root
    anchors.fill: parent
    
    // State
    property var eventsList: []
    property string filterLevel: "All"
    property string searchText: ""
    property int themeUpdateTrigger: 0  // Dummy property to trigger redraws
    property int selectedEventIndex: -1  // Selected event for AI explanation
    property var aiExplanation: null  // Current AI explanation
    property bool isExplaining: false  // AI is processing
    
    // Listen to theme changes to trigger UI updates
    Connections {
        target: ThemeManager
        function onThemeModeChanged() {
            themeUpdateTrigger++  // This forces QML to re-evaluate bindings
        }
    }
    
    // Backend connections
    Connections {
        target: Backend || null
        enabled: target !== null
        function onEventsLoaded(events) {
            eventsList = events
            eventModel.clear()
            selectedEventIndex = -1
            aiExplanation = null
            // Apply filters and populate model
            for (var i = 0; i < events.length; i++) {
                var evt = events[i]
                // Normalize level comparison (events have uppercase, filter options are title case)
                var eventLevel = evt.level ? evt.level.toUpperCase() : ""
                var filterLevelUpper = filterLevel.toUpperCase()
                if ((filterLevel === "All" || eventLevel === filterLevelUpper) &&
                    (searchText === "" || (evt.message && evt.message.indexOf(searchText) >= 0) || (evt.source && evt.source.indexOf(searchText) >= 0))) {
                    eventModel.append(evt)
                }
            }
        }
        
        function onEventExplanationReady(eventId, explanationJson) {
            isExplaining = false
            try {
                var explanation = JSON.parse(explanationJson)
                if (parseInt(eventId) === selectedEventIndex) {
                    aiExplanation = explanation
                }
            } catch (e) {
                console.error("Failed to parse AI explanation:", e)
            }
        }
    }
    
    Component.onCompleted: {
        if (typeof Backend !== 'undefined' && Backend !== null) {
            Backend.loadRecentEvents()
        }
    }
    
    function applyFilters() {
        eventModel.clear()
        var matchedCount = 0
        for (var i = 0; i < eventsList.length; i++) {
            var evt = eventsList[i]
            // Normalize level comparison (events have uppercase, filter options are title case)
            var eventLevel = evt.level ? evt.level.toUpperCase() : ""
            var filterLevelUpper = filterLevel.toUpperCase()
            var levelMatch = (filterLevel === "All" || eventLevel === filterLevelUpper)
            var searchMatch = (searchText === "" || (evt.message && evt.message.indexOf(searchText) >= 0) || (evt.source && evt.source.indexOf(searchText) >= 0))
            
            if (levelMatch && searchMatch) {
                eventModel.append(evt)
                matchedCount++
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        Text {
            text: "Event Viewer"
            font.pixelSize: 28
            font.bold: true
            color: ThemeManager.foreground()
        }

        // Filter controls
        Rectangle {
            Layout.fillWidth: true
            height: 60
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12

                Text {
                    text: "Level:"
                    color: ThemeManager.foreground()
                    font.pixelSize: 12
                }

                ComboBox {
                    id: levelFilterCombo
                    model: ["All", "Info", "Warning", "Error", "Critical"]
                    currentIndex: 0
                    onCurrentIndexChanged: {
                        if (currentIndex >= 0) {
                            filterLevel = model[currentIndex]
                            root.applyFilters()
                        }
                    }
                    background: Rectangle {
                        color: ThemeManager.surface()
                        radius: 6
                        border.color: ThemeManager.border()
                        border.width: 1
                    }
                    contentItem: Text {
                        text: parent.currentText
                        color: ThemeManager.foreground()
                        font.pixelSize: 12
                        leftPadding: 8
                        verticalAlignment: Text.AlignVCenter
                    }
                    delegate: ItemDelegate {
                        width: parent ? parent.width : 150
                        text: modelData
                        background: Rectangle {
                            color: parent.highlighted ? ThemeManager.elevated() : ThemeManager.surface()
                        }
                        contentItem: Text {
                            text: modelData
                            color: ThemeManager.foreground()
                            font.pixelSize: 12
                            leftPadding: 8
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 40
                    color: ThemeManager.surface()
                    radius: 6
                    border.color: ThemeManager.border()
                    border.width: 1

                    TextField {
                        id: searchField
                        anchors.fill: parent
                        anchors.margins: 8
                        color: ThemeManager.foreground()
                        placeholderText: "Search events..."
                        placeholderTextColor: ThemeManager.muted()
                        background: Rectangle { color: "transparent" }
                        onTextChanged: {
                            searchDebounceTimer.restart()
                        }
                    }
                    
                    // Debounce timer to avoid filtering on every keystroke
                    Timer {
                        id: searchDebounceTimer
                        interval: 200
                        onTriggered: {
                            searchText = searchField.text
                            root.applyFilters()
                        }
                    }
                }

                Button {
                    text: "Refresh"
                    onClicked: if (Backend) Backend.loadRecentEvents()
                    background: Rectangle {
                        color: ThemeManager.accent
                        radius: 6
                    }
                    contentItem: Text {
                        text: parent.text
                        color: ThemeManager.foreground()
                        font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }

        // Events table
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 0

                // Header
                Rectangle {
                    Layout.fillWidth: true
                    height: 40
                    color: ThemeManager.surface()
                    radius: 6

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 12

                        Text {
                            text: "Timestamp"
                            color: ThemeManager.muted()
                            font.pixelSize: 11
                            font.bold: true
                            Layout.preferredWidth: 100
                        }

                        Text {
                            text: "Level"
                            color: ThemeManager.muted()
                            font.pixelSize: 11
                            font.bold: true
                            Layout.preferredWidth: 80
                        }

                        Text {
                            text: "Source"
                            color: ThemeManager.muted()
                            font.pixelSize: 11
                            font.bold: true
                            Layout.preferredWidth: 120
                        }

                        Text {
                            text: "Message"
                            color: ThemeManager.muted()
                            font.pixelSize: 11
                            font.bold: true
                            Layout.fillWidth: true
                        }
                    }
                }

                // Events list
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    
                    ListView {
                        id: eventListView
                        width: parent.width
                        model: eventModel
                        spacing: 2
                        currentIndex: selectedEventIndex

                        delegate: Rectangle {
                            width: ListView.view ? ListView.view.width : 500
                            height: 50
                            color: {
                                if (index === selectedEventIndex) {
                                    return ThemeManager.accent + "30"  // Selected highlight
                                }
                                var isDark = ThemeManager ? ThemeManager.isDark() : true
                                return isDark ? 
                                       (index % 2 === 0 ? "#0B1020" : "#050814") : 
                                       (index % 2 === 0 ? "#F3F4F6" : "#FFFFFF")
                            }
                            border.color: index === selectedEventIndex ? ThemeManager.accent : "transparent"
                            border.width: index === selectedEventIndex ? 1 : 0
                            radius: 4

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    selectedEventIndex = index
                                    aiExplanation = null
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 12

                                Text {
                                    text: model.timestamp ? model.timestamp.substr(11, 8) : "--"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 10
                                    Layout.preferredWidth: 100
                                }

                                Text {
                                    text: model.level || "--"
                                    color: model.level === "Error" || model.level === "Critical" ? "#FF6B6B" : 
                                           model.level === "Warning" ? "#FFD93D" : "#7C3AED"
                                    font.pixelSize: 10
                                    font.bold: true
                                    Layout.preferredWidth: 80
                                }

                                Text {
                                    text: model.source || "--"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: 10
                                    Layout.preferredWidth: 120
                                }

                                Text {
                                    text: model.message || "--"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }

                Text {
                    text: eventModel.count === 0 ? "No events" : "Total: " + eventModel.count + (selectedEventIndex >= 0 ? " • Selected: " + (selectedEventIndex + 1) : "")
                    color: ThemeManager.muted()
                    font.pixelSize: 10
                    Layout.alignment: Qt.AlignRight
                    Layout.rightMargin: 8
                    Layout.topMargin: 8
                }
            }
        }
        
        // AI Explanation Panel (shown when event is selected)
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: selectedEventIndex >= 0 ? 280 : 0
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1
            visible: selectedEventIndex >= 0
            clip: true
            
            Behavior on Layout.preferredHeight {
                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
            }
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12
                
                // Header with AI button
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    
                    Text {
                        text: "🔍 Event Details"
                        color: ThemeManager.foreground()
                        font.pixelSize: 14
                        font.bold: true
                    }
                    
                    Item { Layout.fillWidth: true }
                    
                    // AI Explain button
                    Rectangle {
                        width: explainButtonContent.implicitWidth + 24
                        height: 32
                        radius: 8
                        color: explainMouse.containsMouse && !isExplaining ? 
                               Qt.darker(ThemeManager.accent, 1.1) : 
                               ThemeManager.accent
                        opacity: isExplaining ? 0.6 : 1.0
                        
                        Row {
                            id: explainButtonContent
                            anchors.centerIn: parent
                            spacing: 6
                            
                            Text {
                                text: isExplaining ? "⏳" : "🤖"
                                font.pixelSize: 12
                            }
                            
                            Text {
                                text: isExplaining ? "Analyzing..." : "Explain with AI"
                                color: "white"
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                        
                        MouseArea {
                            id: explainMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: isExplaining ? Qt.WaitCursor : Qt.PointingHandCursor
                            onClicked: {
                                if (!isExplaining && Backend && selectedEventIndex >= 0) {
                                    isExplaining = true
                                    aiExplanation = null
                                    Backend.requestEventExplanation(selectedEventIndex)
                                }
                            }
                        }
                    }
                    
                    // Close button
                    Rectangle {
                        width: 28
                        height: 28
                        radius: 6
                        color: closeMouse.containsMouse ? ThemeManager.surface() : "transparent"
                        
                        Text {
                            anchors.centerIn: parent
                            text: "✕"
                            color: ThemeManager.muted()
                            font.pixelSize: 12
                        }
                        
                        MouseArea {
                            id: closeMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                selectedEventIndex = -1
                                aiExplanation = null
                            }
                        }
                    }
                }
                
                // Content area
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    
                    ColumnLayout {
                        width: parent.width
                        spacing: 12
                        
                        // Event info
                        Rectangle {
                            Layout.fillWidth: true
                            height: eventInfoCol.implicitHeight + 16
                            color: ThemeManager.surface()
                            radius: 8
                            
                            Column {
                                id: eventInfoCol
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 4
                                
                                Text {
                                    text: selectedEventIndex >= 0 && eventModel.get(selectedEventIndex) ? 
                                          eventModel.get(selectedEventIndex).message || "No message" : ""
                                    color: ThemeManager.foreground()
                                    font.pixelSize: 11
                                    wrapMode: Text.Wrap
                                    width: parent.width
                                }
                            }
                        }
                        
                        // AI Explanation (if available)
                        Rectangle {
                            Layout.fillWidth: true
                            visible: aiExplanation !== null
                            height: visible ? aiExplanationCol.implicitHeight + 20 : 0
                            color: ThemeManager.accent + "15"
                            radius: 8
                            border.color: ThemeManager.accent + "40"
                            border.width: 1
                            
                            Column {
                                id: aiExplanationCol
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 8
                                
                                // Summary
                                Row {
                                    spacing: 8
                                    Text {
                                        text: "🤖"
                                        font.pixelSize: 14
                                    }
                                    Text {
                                        text: aiExplanation ? aiExplanation.short_summary || "" : ""
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 12
                                        font.bold: true
                                        wrapMode: Text.Wrap
                                        width: parent.parent.width - 30
                                    }
                                }
                                
                                // Severity badge
                                Rectangle {
                                    width: severityText.implicitWidth + 16
                                    height: 22
                                    radius: 11
                                    color: {
                                        if (!aiExplanation) return ThemeManager.surface()
                                        var label = aiExplanation.severity_label || "Info"
                                        if (label === "Critical") return "#DC2626"
                                        if (label === "High") return "#EA580C"
                                        if (label === "Medium") return "#CA8A04"
                                        if (label === "Low") return "#2563EB"
                                        return "#6B7280"
                                    }
                                    
                                    Text {
                                        id: severityText
                                        anchors.centerIn: parent
                                        text: aiExplanation ? 
                                              (aiExplanation.severity_label || "Info") + " (" + (aiExplanation.severity_score || 0) + "/10)" : ""
                                        color: "white"
                                        font.pixelSize: 10
                                        font.bold: true
                                    }
                                }
                                
                                // What it means
                                Text {
                                    text: aiExplanation ? ("💡 " + (aiExplanation.what_it_means || "")) : ""
                                    color: ThemeManager.foreground()
                                    font.pixelSize: 11
                                    wrapMode: Text.Wrap
                                    width: parent.width
                                    visible: aiExplanation && aiExplanation.what_it_means
                                }
                                
                                // Recommended actions
                                Column {
                                    width: parent.width
                                    spacing: 4
                                    visible: aiExplanation && aiExplanation.recommended_actions && aiExplanation.recommended_actions.length > 0
                                    
                                    Text {
                                        text: "📋 Recommended Actions:"
                                        color: ThemeManager.muted()
                                        font.pixelSize: 10
                                        font.bold: true
                                    }
                                    
                                    Repeater {
                                        model: aiExplanation ? aiExplanation.recommended_actions || [] : []
                                        
                                        Text {
                                            text: "• " + modelData
                                            color: ThemeManager.foreground()
                                            font.pixelSize: 10
                                            wrapMode: Text.Wrap
                                            width: parent.width
                                            leftPadding: 8
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Prompt to use AI
                        Text {
                            visible: aiExplanation === null && !isExplaining
                            text: "💡 Click 'Explain with AI' to get a detailed analysis of this event"
                            color: ThemeManager.muted()
                            font.pixelSize: 11
                            font.italic: true
                        }
                    }
                }
            }
        }

    // Data model
    ListModel {
        id: eventModel
    }
}
