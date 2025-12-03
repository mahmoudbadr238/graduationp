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
    property int themeUpdateTrigger: 0
    property int selectedEventIndex: -1
    property var aiExplanation: null
    property bool isExplaining: false
    property bool technicalDetailsExpanded: false
    
    // ============================================================
    // HELPER FUNCTIONS for user-friendly text
    // ============================================================
    
    function getSelectedEvent() {
        if (selectedEventIndex >= 0 && eventModel.get(selectedEventIndex)) {
            return eventModel.get(selectedEventIndex)
        }
        return null
    }
    
    // SUMMARY: What happened?
    function getFriendlySummary() {
        if (aiExplanation && aiExplanation.short_summary) {
            return aiExplanation.short_summary
        }
        // Fallback based on event level
        var evt = getSelectedEvent()
        if (!evt) return ""
        var level = evt.level || "Information"
        var source = evt.source || "Windows"
        if (source.length > 25) source = source.substring(0, 22) + "..."
        
        if (level === "Critical") {
            return "Something serious happened with " + source + "."
        } else if (level === "Error") {
            return "Something went wrong with " + source + "."
        } else if (level === "Warning") {
            return "Windows noticed something unusual from " + source + "."
        }
        return "Windows recorded a normal message from " + source + "."
    }
    
    // SEVERITY INFO: Is this a problem?
    function getSeverityInfo() {
        // Returns: { label, color, description }
        if (aiExplanation && aiExplanation.severity_label) {
            var label = aiExplanation.severity_label
            var meaning = aiExplanation.what_it_means || ""
            
            if (label === "Critical") {
                return { 
                    label: "Critical", 
                    color: "#DC2626", 
                    description: meaning || "Yes, this needs immediate attention."
                }
            } else if (label === "High") {
                return { 
                    label: "High", 
                    color: "#EA580C", 
                    description: meaning || "Yes, this could affect your computer."
                }
            } else if (label === "Medium") {
                return { 
                    label: "Medium", 
                    color: "#CA8A04", 
                    description: meaning || "This might cause small issues. Keep using your PC, but watch for problems."
                }
            } else if (label === "Low") {
                return { 
                    label: "Low", 
                    color: "#2563EB", 
                    description: meaning || "This is minor. You can safely ignore it unless it happens often."
                }
            }
            return { 
                label: "Info", 
                color: "#22C55E", 
                description: meaning || "No, this is just a normal system message."
            }
        }
        
        // Fallback based on event level
        var evt = getSelectedEvent()
        if (!evt) return { label: "Unknown", color: ThemeManager.muted(), description: "" }
        var level = evt.level || "Information"
        
        if (level === "Critical") {
            return { label: "Critical", color: "#DC2626", description: "This is a serious issue that needs attention." }
        } else if (level === "Error") {
            return { label: "Medium", color: "#EA580C", description: "Something went wrong, but your PC should still work." }
        } else if (level === "Warning") {
            return { label: "Low", color: "#CA8A04", description: "Windows noticed something, but it's probably fine." }
        }
        return { label: "Info", color: "#22C55E", description: "This is just a normal system message." }
    }
    
    // CAUSE: Possible cause
    function getLikelyCause() {
        if (aiExplanation && aiExplanation.likely_cause) {
            var cause = aiExplanation.likely_cause
            if (cause.toLowerCase() === "unknown" || cause.toLowerCase() === "unknown.") {
                return "The exact cause is not clear from this message."
            }
            return cause
        }
        return "The exact cause is not clear from this message."
    }
    
    // ACTIONS: What should I do?
    function getRecommendedActions() {
        if (aiExplanation && aiExplanation.recommended_actions && aiExplanation.recommended_actions.length > 0) {
            return aiExplanation.recommended_actions
        }
        // Fallback based on event level
        var evt = getSelectedEvent()
        if (!evt) return ["No action needed."]
        var level = evt.level || "Information"
        
        if (level === "Critical" || level === "Error") {
            return [
                "If this keeps happening, restart your computer.",
                "If the problem continues, contact a technician."
            ]
        } else if (level === "Warning") {
            return ["Keep an eye on this. If it happens often, restart your PC."]
        }
        return ["No action needed."]
    }
    
    // ============================================================
    // CONNECTIONS
    // ============================================================
    
    Connections {
        target: ThemeManager
        function onThemeModeChanged() {
            themeUpdateTrigger++
        }
    }
    
    Connections {
        target: Backend || null
        enabled: target !== null
        
        function onEventsLoaded(events) {
            eventsList = events
            eventModel.clear()
            selectedEventIndex = -1
            aiExplanation = null
            technicalDetailsExpanded = false
            
            for (var i = 0; i < events.length; i++) {
                var evt = events[i]
                var eventLevel = evt.level ? evt.level.toUpperCase() : ""
                var filterLevelUpper = filterLevel.toUpperCase()
                
                if ((filterLevel === "All" || eventLevel === filterLevelUpper) &&
                    (searchText === "" || 
                     (evt.message && evt.message.indexOf(searchText) >= 0) || 
                     (evt.source && evt.source.indexOf(searchText) >= 0))) {
                    eventModel.append(evt)
                }
            }
        }
        
        function onEventExplanationReady(eventId, explanationJson) {
            isExplaining = false
            try {
                var explanation = JSON.parse(explanationJson)
                // Only apply if still viewing the same event
                if (parseInt(eventId) === selectedEventIndex) {
                    aiExplanation = explanation
                }
            } catch (e) {
                console.error("Failed to parse AI explanation:", e)
                // Set a safe fallback
                if (parseInt(eventId) === selectedEventIndex) {
                    aiExplanation = {
                        short_summary: "Windows recorded a system event.",
                        what_it_means: "This is not usually serious unless it keeps happening.",
                        likely_cause: "Unknown.",
                        recommended_actions: ["If this message repeats many times, restart your PC."],
                        severity_score: 0,
                        severity_label: "Info"
                    }
                }
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
        for (var i = 0; i < eventsList.length; i++) {
            var evt = eventsList[i]
            var eventLevel = evt.level ? evt.level.toUpperCase() : ""
            var filterLevelUpper = filterLevel.toUpperCase()
            var levelMatch = (filterLevel === "All" || eventLevel === filterLevelUpper)
            var searchMatch = (searchText === "" || 
                              (evt.message && evt.message.indexOf(searchText) >= 0) || 
                              (evt.source && evt.source.indexOf(searchText) >= 0))
            if (levelMatch && searchMatch) {
                eventModel.append(evt)
            }
        }
    }

    // ============================================================
    // MAIN LAYOUT
    // ============================================================
    
    RowLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        // LEFT SIDE: Event list
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: selectedEventIndex >= 0 ? parent.width * 0.55 : parent.width
            spacing: 16

            Text {
                text: "Event Viewer"
                font.pixelSize: 28
                font.bold: true
                color: ThemeManager.foreground()
            }

            // Filter controls
            Rectangle {
                Layout.fillWidth: true
                height: 56
                color: ThemeManager.panel()
                radius: 12
                border.color: ThemeManager.border()
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    Text {
                        text: "Filter:"
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
                        height: 36
                        color: ThemeManager.surface()
                        radius: 6
                        border.color: ThemeManager.border()
                        border.width: 1

                        TextField {
                            id: searchField
                            anchors.fill: parent
                            anchors.margins: 6
                            color: ThemeManager.foreground()
                            placeholderText: "Search events..."
                            placeholderTextColor: ThemeManager.muted()
                            background: Rectangle { color: "transparent" }
                            onTextChanged: searchDebounceTimer.restart()
                        }
                        
                        Timer {
                            id: searchDebounceTimer
                            interval: 200
                            onTriggered: {
                                searchText = searchField.text
                                root.applyFilters()
                            }
                        }
                    }

                    Rectangle {
                        width: 80
                        height: 36
                        radius: 6
                        color: refreshMouse.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                        
                        Text {
                            anchors.centerIn: parent
                            text: "Refresh"
                            color: "white"
                            font.pixelSize: 11
                            font.bold: true
                        }
                        
                        MouseArea {
                            id: refreshMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (Backend) Backend.loadRecentEvents()
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

                    // Header row
                    Rectangle {
                        Layout.fillWidth: true
                        height: 36
                        color: ThemeManager.surface()
                        radius: 6

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 12

                            Text { text: "Time"; color: ThemeManager.muted(); font.pixelSize: 10; font.bold: true; Layout.preferredWidth: 80 }
                            Text { text: "Type"; color: ThemeManager.muted(); font.pixelSize: 10; font.bold: true; Layout.preferredWidth: 70 }
                            Text { text: "Source"; color: ThemeManager.muted(); font.pixelSize: 10; font.bold: true; Layout.preferredWidth: 100 }
                            Text { text: "Description"; color: ThemeManager.muted(); font.pixelSize: 10; font.bold: true; Layout.fillWidth: true }
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
                                height: 44
                                color: {
                                    if (index === selectedEventIndex) {
                                        return ThemeManager.accent + "30"
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
                                        technicalDetailsExpanded = false
                                        // Auto-request AI explanation
                                        if (Backend && !isExplaining) {
                                            isExplaining = true
                                            Backend.requestEventExplanation(index)
                                        }
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
                                        Layout.preferredWidth: 80
                                    }

                                    // Friendly level badge
                                    Rectangle {
                                        width: 60
                                        height: 20
                                        radius: 10
                                        color: {
                                            var lvl = model.level || "Info"
                                            if (lvl === "Critical") return "#DC2626"
                                            if (lvl === "Error") return "#EA580C"
                                            if (lvl === "Warning") return "#CA8A04"
                                            return "#6B7280"
                                        }
                                        Layout.preferredWidth: 70
                                        
                                        Text {
                                            anchors.centerIn: parent
                                            text: {
                                                var lvl = model.level || "Info"
                                                if (lvl === "Critical") return "⚠️ Bad"
                                                if (lvl === "Error") return "❌ Issue"
                                                if (lvl === "Warning") return "⚡ Notice"
                                                return "ℹ️ Info"
                                            }
                                            color: "white"
                                            font.pixelSize: 9
                                            font.bold: true
                                        }
                                    }

                                    Text {
                                        text: model.source || "--"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 10
                                        Layout.preferredWidth: 100
                                        elide: Text.ElideRight
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
                        text: eventModel.count === 0 ? "No events found" : eventModel.count + " events"
                        color: ThemeManager.muted()
                        font.pixelSize: 10
                        Layout.alignment: Qt.AlignRight
                        Layout.topMargin: 8
                    }
                }
            }
        }

        // ============================================================
        // RIGHT SIDE: Event explanation panel
        // ============================================================
        
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: selectedEventIndex >= 0 ? parent.width * 0.4 : 0
            visible: selectedEventIndex >= 0
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1
            clip: true
            
            Behavior on Layout.preferredWidth {
                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
            }

            ScrollView {
                anchors.fill: parent
                anchors.margins: 20
                clip: true
                
                ColumnLayout {
                    width: parent.width - 8
                    spacing: 16

                    // Header with close button
                    RowLayout {
                        Layout.fillWidth: true
                        
                        Text {
                            text: "📋 Event Explanation"
                            color: ThemeManager.foreground()
                            font.pixelSize: 16
                            font.bold: true
                        }
                        
                        Item { Layout.fillWidth: true }
                        
                        Rectangle {
                            width: 28
                            height: 28
                            radius: 14
                            color: closeDetailsMouse.containsMouse ? ThemeManager.surface() : "transparent"
                            
                            Text {
                                anchors.centerIn: parent
                                text: "✕"
                                color: ThemeManager.muted()
                                font.pixelSize: 14
                            }
                            
                            MouseArea {
                                id: closeDetailsMouse
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

                    // Loading indicator
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 8
                        color: ThemeManager.surface()
                        visible: isExplaining
                        
                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 12
                            
                            Text {
                                text: "🔍"
                                font.pixelSize: 20
                                
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite
                                    running: isExplaining
                                    NumberAnimation { to: 0.3; duration: 500 }
                                    NumberAnimation { to: 1.0; duration: 500 }
                                }
                            }
                            
                            Text {
                                text: "Analyzing this event..."
                                color: ThemeManager.muted()
                                font.pixelSize: 12
                            }
                        }
                    }

                    // SECTION 1: What happened?
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: whatHappenedContent.implicitHeight + 24
                        radius: 10
                        color: ThemeManager.surface()
                        visible: !isExplaining
                        
                        ColumnLayout {
                            id: whatHappenedContent
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 8
                            
                            Text {
                                text: "💬 What happened?"
                                color: ThemeManager.foreground()
                                font.pixelSize: 13
                                font.bold: true
                            }
                            
                            Text {
                                text: getFriendlySummary()
                                color: ThemeManager.foreground()
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.3
                            }
                        }
                    }

                    // SECTION 2: Is this a problem?
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: problemContent.implicitHeight + 24
                        radius: 10
                        color: ThemeManager.surface()
                        visible: !isExplaining
                        
                        ColumnLayout {
                            id: problemContent
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 10
                            
                            Text {
                                text: "🔍 Is this a problem?"
                                color: ThemeManager.foreground()
                                font.pixelSize: 13
                                font.bold: true
                            }
                            
                            // Severity badge
                            Rectangle {
                                width: severityLabel.implicitWidth + 20
                                height: 26
                                radius: 13
                                color: getSeverityInfo().color
                                
                                Text {
                                    id: severityLabel
                                    anchors.centerIn: parent
                                    text: getSeverityInfo().label
                                    color: "white"
                                    font.pixelSize: 11
                                    font.bold: true
                                }
                            }
                            
                            Text {
                                text: getSeverityInfo().description
                                color: ThemeManager.muted()
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.3
                            }
                        }
                    }

                    // SECTION 3: Possible cause
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: causeContent.implicitHeight + 24
                        radius: 10
                        color: ThemeManager.surface()
                        visible: !isExplaining
                        
                        ColumnLayout {
                            id: causeContent
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 8
                            
                            Text {
                                text: "🔎 Possible cause"
                                color: ThemeManager.foreground()
                                font.pixelSize: 13
                                font.bold: true
                            }
                            
                            Text {
                                text: getLikelyCause()
                                color: ThemeManager.muted()
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.3
                            }
                        }
                    }

                    // SECTION 4: What should I do?
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: actionsContent.implicitHeight + 24
                        radius: 10
                        color: ThemeManager.surface()
                        visible: !isExplaining
                        
                        ColumnLayout {
                            id: actionsContent
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 8
                            
                            Text {
                                text: "✅ What should I do?"
                                color: ThemeManager.foreground()
                                font.pixelSize: 13
                                font.bold: true
                            }
                            
                            Repeater {
                                model: getRecommendedActions()
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    
                                    Rectangle {
                                        width: 6
                                        height: 6
                                        radius: 3
                                        color: ThemeManager.accent
                                        Layout.alignment: Qt.AlignTop
                                        Layout.topMargin: 5
                                    }
                                    
                                    Text {
                                        text: modelData
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 11
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                        lineHeight: 1.3
                                    }
                                }
                            }
                        }
                    }

                    // SECTION 5: Technical details (collapsible)
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: technicalHeader.implicitHeight + (technicalDetailsExpanded ? technicalContent.implicitHeight + 12 : 0) + 24
                        radius: 10
                        color: ThemeManager.surface()
                        visible: !isExplaining
                        clip: true
                        
                        Behavior on implicitHeight {
                            NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                        }
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12
                            
                            // Collapsible header
                            Item {
                                id: technicalHeader
                                Layout.fillWidth: true
                                implicitHeight: technicalHeaderRow.implicitHeight
                                
                                RowLayout {
                                    id: technicalHeaderRow
                                    anchors.fill: parent
                                    
                                    Text {
                                        text: technicalDetailsExpanded ? "🔧 Technical details" : "🔧 Show technical details"
                                        color: ThemeManager.muted()
                                        font.pixelSize: 12
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    Text {
                                        text: technicalDetailsExpanded ? "▲" : "▼"
                                        color: ThemeManager.muted()
                                        font.pixelSize: 10
                                    }
                                }
                                
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: technicalDetailsExpanded = !technicalDetailsExpanded
                                }
                            }
                            
                            // Technical content
                            ColumnLayout {
                                id: technicalContent
                                Layout.fillWidth: true
                                spacing: 6
                                visible: technicalDetailsExpanded
                                opacity: technicalDetailsExpanded ? 1 : 0
                                
                                Behavior on opacity {
                                    NumberAnimation { duration: 150 }
                                }
                                
                                // Event ID
                                RowLayout {
                                    spacing: 8
                                    Text { text: "Event ID:"; color: ThemeManager.muted(); font.pixelSize: 10; Layout.preferredWidth: 80 }
                                    Text { 
                                        text: getSelectedEvent() ? (getSelectedEvent().event_id || "--") : "--"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 10
                                        font.family: "Consolas"
                                    }
                                }
                                
                                // Level
                                RowLayout {
                                    spacing: 8
                                    Text { text: "Level:"; color: ThemeManager.muted(); font.pixelSize: 10; Layout.preferredWidth: 80 }
                                    Text { 
                                        text: getSelectedEvent() ? (getSelectedEvent().level || "--") : "--"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 10
                                        font.family: "Consolas"
                                    }
                                }
                                
                                // Source
                                RowLayout {
                                    spacing: 8
                                    Text { text: "Source:"; color: ThemeManager.muted(); font.pixelSize: 10; Layout.preferredWidth: 80 }
                                    Text { 
                                        text: getSelectedEvent() ? (getSelectedEvent().source || "--") : "--"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 10
                                        font.family: "Consolas"
                                    }
                                }
                                
                                // Log name
                                RowLayout {
                                    spacing: 8
                                    Text { text: "Log:"; color: ThemeManager.muted(); font.pixelSize: 10; Layout.preferredWidth: 80 }
                                    Text { 
                                        text: getSelectedEvent() ? (getSelectedEvent().log_name || "--") : "--"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 10
                                        font.family: "Consolas"
                                    }
                                }
                                
                                // Time
                                RowLayout {
                                    spacing: 8
                                    Text { text: "Time:"; color: ThemeManager.muted(); font.pixelSize: 10; Layout.preferredWidth: 80 }
                                    Text { 
                                        text: getSelectedEvent() ? (getSelectedEvent().timestamp || "--") : "--"
                                        color: ThemeManager.foreground()
                                        font.pixelSize: 10
                                        font.family: "Consolas"
                                    }
                                }
                                
                                // Full message
                                Text { 
                                    text: "Full message:"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 10
                                    Layout.topMargin: 4
                                }
                                
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: Math.min(fullMessageText.implicitHeight + 16, 120)
                                    color: ThemeManager.panel()
                                    radius: 6
                                    
                                    ScrollView {
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        clip: true
                                        
                                        Text {
                                            id: fullMessageText
                                            text: getSelectedEvent() ? (getSelectedEvent().message || "No message") : ""
                                            color: ThemeManager.foreground()
                                            font.pixelSize: 10
                                            font.family: "Consolas"
                                            wrapMode: Text.Wrap
                                            width: parent.width - 16
                                        }
                                    }
                                }
                            }
                        }
                    }
                    
                    // Spacer
                    Item { Layout.fillHeight: true }
                }
            }
        }
    }

    // Data model
    ListModel {
        id: eventModel
    }
}
