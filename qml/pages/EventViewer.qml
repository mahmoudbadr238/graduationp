import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"
import "../ui"

Item {
    id: root
    anchors.fill: parent
    
    // ===========================================
    // STATE PROPERTIES
    // ===========================================
    property var selectedEvent: null
    property int selectedEventIndex: -1  // Index in eventModel (not filteredModel)
    property var eventModel: []
    property var filteredModel: []
    property bool isLoading: false
    property string errorMessage: ""
    property string searchText: ""
    property string levelFilter: "All"
    
    // AI State
    property bool aiBusy: false
    property var aiData: null
    property string aiError: ""
    
    // ===========================================
    // HELPER FUNCTIONS
    // ===========================================
    
    function filterEvents() {
        var result = []
        for (var i = 0; i < eventModel.length; i++) {
            var event = eventModel[i]
            
            // Level filter - backend uses uppercase: INFO, WARNING, ERROR, SUCCESS, FAILURE
            if (levelFilter !== "All") {
                var eventLevel = (event.level || "").toUpperCase()
                var filterLevel = levelFilter.toUpperCase()
                // Handle aliases
                if (filterLevel === "INFORMATION") filterLevel = "INFO"
                if (eventLevel !== filterLevel) continue
            }
            
            // Search filter
            if (searchText.length > 0) {
                var searchLower = searchText.toLowerCase()
                var source = (event.source || event.provider || "").toLowerCase()
                var message = (event.message || "").toLowerCase()
                var eventId = String(event.event_id || "")
                
                if (!source.includes(searchLower) && 
                    !message.includes(searchLower) && 
                    !eventId.includes(searchLower)) {
                    continue
                }
            }
            
            result.push(event)
        }
        filteredModel = result
    }
    
    function getLevelColor(level) {
        if (!level) return ThemeManager.muted()
        var l = level.toLowerCase()
        if (l === "error" || l === "critical") return ThemeManager.danger
        if (l === "warning") return ThemeManager.warning
        return ThemeManager.info  // INFO and others
    }
    
    function severityColor(severity) {
        switch(severity) {
            case "Safe": return ThemeManager.success
            case "Minor": return ThemeManager.info
            case "Warning": return ThemeManager.warning
            case "Critical": return ThemeManager.danger
            default: return ThemeManager.foreground()
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
    
    function requestExplanation() {
        if (!selectedEvent || selectedEventIndex < 0) {
            if (typeof Backend !== "undefined" && Backend.toast) {
                Backend.toast("warning", "Please select an event first.")
            }
            return
        }
        
        // Cancel any previous request by resetting state
        aiData = null
        aiError = ""
        aiBusy = true
        
        // Use the stored original index
        if (typeof Backend !== "undefined" && Backend.requestEventExplanation) {
            Backend.requestEventExplanation(selectedEventIndex)
        } else {
            aiBusy = false
            aiError = "Backend not available"
        }
    }
    
    // ===========================================
    // BACKEND CONNECTIONS
    // ===========================================
    
    Connections {
        target: typeof Backend !== "undefined" ? Backend : null
        
        function onEventsLoaded(events) {
            eventModel = events || []
            filterEvents()
            isLoading = false
            errorMessage = ""
        }
        
        function onEventExplanationReady(eventId, explanation) {
            console.log("[EventViewer] AI explanation received for event", eventId)
            aiBusy = false
            aiError = ""
            
            try {
                if (typeof explanation === "string") {
                    aiData = JSON.parse(explanation)
                    console.log("[EventViewer] Parsed AI data:", JSON.stringify(aiData))
                } else {
                    aiData = explanation
                }
            } catch (e) {
                console.log("[EventViewer] JSON parse error, using fallback:", e)
                aiData = {
                    severity: "Safe",
                    title: "Event Analysis",
                    short_title: "Event Analysis",
                    explanation: String(explanation),
                    recommendation: "No action needed."
                }
            }
        }
        
        function onEventExplanationFailed(eventId, errorMsg) {
            console.log("[EventViewer] AI explanation failed for event", eventId, ":", errorMsg)
            aiBusy = false
            aiData = null
            aiError = errorMsg || "Analysis failed"
        }
    }
    
    Component.onCompleted: {
        if (typeof Backend !== "undefined" && Backend.loadRecentEvents) {
            isLoading = true
            Backend.loadRecentEvents()
        }
    }
    
    // Watch for filter changes
    onSearchTextChanged: filterEvents()
    onLevelFilterChanged: filterEvents()
    onEventModelChanged: filterEvents()
    
    // ===========================================
    // MAIN LAYOUT
    // ===========================================
    
    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()
    }
    
    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        spacing: Theme.spacing_md
        
        // ===========================================
        // LEFT: Table View Area
        // ===========================================
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacing_sm
            
            // -----------------------------------------
            // TOP TOOLBAR
            // -----------------------------------------
            Rectangle {
                Layout.fillWidth: true
                height: 48
                color: ThemeManager.panel()
                radius: Theme.radii_sm
                
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacing_md
                    anchors.rightMargin: Theme.spacing_md
                    spacing: Theme.spacing_md
                    
                    // Level Filter Dropdown
                    RowLayout {
                        spacing: Theme.spacing_xs
                        
                        Text {
                            text: "Level:"
                            font.pixelSize: Theme.typography.body.size
                            color: ThemeManager.foreground()
                        }
                        
                        ComboBox {
                            id: levelCombo
                            model: ["All", "INFO", "WARNING", "ERROR"]
                            currentIndex: 0
                            implicitWidth: 130
                            implicitHeight: 32
                            
                            onCurrentTextChanged: {
                                levelFilter = currentText
                            }
                            
                            background: Rectangle {
                                color: ThemeManager.elevated()
                                radius: Theme.radii_xs
                                border.color: levelCombo.pressed ? ThemeManager.accent : ThemeManager.border()
                                border.width: 1
                            }
                            
                            contentItem: Text {
                                text: levelCombo.displayText
                                color: ThemeManager.foreground()
                                font.pixelSize: Theme.typography.body.size
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: Theme.spacing_sm
                                rightPadding: Theme.spacing_lg
                            }
                            
                            indicator: Text {
                                x: levelCombo.width - width - Theme.spacing_sm
                                y: (levelCombo.height - height) / 2
                                text: "▼"
                                font.pixelSize: 10
                                color: ThemeManager.muted()
                            }
                            
                            delegate: ItemDelegate {
                                width: levelCombo.width
                                height: 32
                                
                                contentItem: Text {
                                    text: modelData
                                    color: ThemeManager.foreground()
                                    font.pixelSize: Theme.typography.body.size
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: Theme.spacing_sm
                                }
                                
                                background: Rectangle {
                                    color: highlighted ? ThemeManager.accent : ThemeManager.elevated()
                                }
                                
                                highlighted: levelCombo.highlightedIndex === index
                            }
                            
                            popup: Popup {
                                y: levelCombo.height
                                width: levelCombo.width
                                implicitHeight: contentItem.implicitHeight + 2
                                padding: 1
                                
                                contentItem: ListView {
                                    clip: true
                                    implicitHeight: contentHeight
                                    model: levelCombo.popup.visible ? levelCombo.delegateModel : null
                                    currentIndex: levelCombo.highlightedIndex
                                    ScrollIndicator.vertical: ScrollIndicator { }
                                }
                                
                                background: Rectangle {
                                    color: ThemeManager.panel()
                                    border.color: ThemeManager.border()
                                    border.width: 1
                                    radius: Theme.radii_xs
                                }
                            }
                        }
                    }
                    
                    // Search Box
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.maximumWidth: 300
                        height: 32
                        color: ThemeManager.elevated()
                        radius: Theme.radii_xs
                        border.color: searchInput.activeFocus ? ThemeManager.accent : ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacing_sm
                            anchors.rightMargin: Theme.spacing_sm
                            spacing: Theme.spacing_xs
                            
                            Text {
                                text: "🔍"
                                font.pixelSize: 14
                                color: ThemeManager.muted()
                            }
                            
                            TextInput {
                                id: searchInput
                                Layout.fillWidth: true
                                font.pixelSize: Theme.typography.body.size
                                color: ThemeManager.foreground()
                                clip: true
                                
                                Text {
                                    anchors.fill: parent
                                    text: "Search events..."
                                    color: ThemeManager.muted()
                                    font.pixelSize: Theme.typography.body.size
                                    visible: !searchInput.text && !searchInput.activeFocus
                                }
                                
                                onTextChanged: {
                                    searchText = text
                                }
                            }
                        }
                    }
                    
                    Item { Layout.fillWidth: true }
                    
                    // Explain Event Button
                    Button {
                        id: explainBtn
                        text: "Explain Event"
                        enabled: selectedEvent !== null && !aiBusy
                        implicitWidth: 120
                        implicitHeight: 32
                        
                        background: Rectangle {
                            color: explainBtn.enabled ? 
                                   (explainBtn.down ? Qt.darker(ThemeManager.accent, 1.2) : 
                                    explainBtn.hovered ? Qt.lighter(ThemeManager.accent, 1.2) : ThemeManager.accent) :
                                   ThemeManager.muted()
                            radius: Theme.radii_xs
                            opacity: explainBtn.enabled ? 1.0 : 0.5
                        }
                        
                        contentItem: Text {
                            text: explainBtn.text
                            color: "#FFFFFF"
                            font.pixelSize: Theme.typography.body.size
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        
                        onClicked: {
                            console.log("[EventViewer] Explain button clicked, selectedEventIndex:", selectedEventIndex)
                            requestExplanation()
                        }
                    }
                    
                    // Refresh Button
                    Button {
                        id: refreshBtn
                        text: isLoading ? "Loading..." : "Refresh"
                        enabled: !isLoading
                        implicitWidth: 100
                        implicitHeight: 32
                        
                        background: Rectangle {
                            color: refreshBtn.enabled ?
                                   (refreshBtn.down ? Qt.darker(Theme.primary, 1.2) :
                                    refreshBtn.hovered ? Qt.lighter(Theme.primary, 1.2) : Theme.primary) :
                                   ThemeManager.muted()
                            radius: Theme.radii_xs
                            opacity: refreshBtn.enabled ? 1.0 : 0.5
                        }
                        
                        contentItem: Text {
                            text: refreshBtn.text
                            color: "#FFFFFF"
                            font.pixelSize: Theme.typography.body.size
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        
                        onClicked: {
                            console.log("[EventViewer] Refresh button clicked")
                            if (typeof Backend !== "undefined" && Backend.loadRecentEvents) {
                                isLoading = true
                                selectedEvent = null
                                selectedEventIndex = -1
                                aiData = null
                                aiError = ""
                                Backend.loadRecentEvents()
                            } else {
                                console.log("[EventViewer] Backend not available!")
                            }
                        }
                    }
                }
            }
            
            // -----------------------------------------
            // TABLE HEADER
            // -----------------------------------------
            Rectangle {
                Layout.fillWidth: true
                height: 40
                color: ThemeManager.elevated()
                radius: Theme.radii_xs
                
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacing_md
                    anchors.rightMargin: Theme.spacing_md
                    spacing: 0
                    
                    // Timestamp column header
                    Text {
                        Layout.preferredWidth: 160
                        text: "Timestamp"
                        font.pixelSize: Theme.typography.body.size
                        font.weight: Font.Bold
                        color: ThemeManager.foreground()
                    }
                    
                    // Event ID column header
                    Text {
                        Layout.preferredWidth: 70
                        text: "ID"
                        font.pixelSize: Theme.typography.body.size
                        font.weight: Font.Bold
                        color: ThemeManager.foreground()
                    }
                    
                    // Level column header
                    Text {
                        Layout.preferredWidth: 90
                        text: "Level"
                        font.pixelSize: Theme.typography.body.size
                        font.weight: Font.Bold
                        color: ThemeManager.foreground()
                    }
                    
                    // Source column header
                    Text {
                        Layout.preferredWidth: 140
                        text: "Source"
                        font.pixelSize: Theme.typography.body.size
                        font.weight: Font.Bold
                        color: ThemeManager.foreground()
                    }
                    
                    // Message column header
                    Text {
                        Layout.fillWidth: true
                        text: "Summary"
                        font.pixelSize: Theme.typography.body.size
                        font.weight: Font.Bold
                        color: ThemeManager.foreground()
                    }
                }
            }
            
            // -----------------------------------------
            // TABLE BODY (ListView)
            // -----------------------------------------
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: ThemeManager.panel()
                radius: Theme.radii_sm
                clip: true
                
                ListView {
                    id: eventListView
                    anchors.fill: parent
                    anchors.margins: 2
                    clip: true
                    
                    model: filteredModel
                    
                    delegate: Rectangle {
                        width: eventListView.width
                        height: 44
                        
                        // Alternating row colors
                        color: {
                            if (selectedEvent === modelData) {
                                return Qt.lighter(ThemeManager.accent, 1.6)
                            }
                            return index % 2 === 0 ? ThemeManager.panel() : ThemeManager.elevated()
                        }
                        
                        // Hover effect
                        Rectangle {
                            anchors.fill: parent
                            color: ThemeManager.accent
                            opacity: rowMouseArea.containsMouse && selectedEvent !== modelData ? 0.1 : 0
                        }
                        
                        MouseArea {
                            id: rowMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            
                            onClicked: {
                                selectedEvent = modelData
                                // Find index in original eventModel
                                for (var i = 0; i < eventModel.length; i++) {
                                    var evt = eventModel[i]
                                    if (evt.timestamp === modelData.timestamp && 
                                        evt.source === modelData.source && 
                                        evt.message === modelData.message) {
                                        selectedEventIndex = i
                                        break
                                    }
                                }
                                // Clear previous AI data when selecting new event
                                aiData = null
                                aiError = ""
                            }
                        }
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacing_md
                            anchors.rightMargin: Theme.spacing_md
                            spacing: 0
                            
                            // Timestamp
                            Text {
                                Layout.preferredWidth: 160
                                text: formatTimestamp(modelData.time_created || modelData.timestamp)
                                font.pixelSize: Theme.typography.caption.size
                                color: ThemeManager.foreground()
                                elide: Text.ElideRight
                            }
                            
                            // Event ID
                            Text {
                                Layout.preferredWidth: 70
                                text: modelData.event_id || "-"
                                font.pixelSize: Theme.typography.caption.size
                                font.family: "Consolas, monospace"
                                color: ThemeManager.muted()
                                elide: Text.ElideRight
                            }
                            
                            // Level (colored)
                            Rectangle {
                                Layout.preferredWidth: 90
                                height: 24
                                color: "transparent"
                                
                                Rectangle {
                                    anchors.left: parent.left
                                    width: levelText.implicitWidth + Theme.spacing_sm * 2
                                    height: 22
                                    radius: 4
                                    color: getLevelColor(modelData.level)
                                    opacity: 0.2
                                    
                                    Text {
                                        id: levelText
                                        anchors.centerIn: parent
                                        text: modelData.level || "Info"
                                        font.pixelSize: Theme.typography.caption.size
                                        font.weight: Font.Medium
                                        color: getLevelColor(modelData.level)
                                    }
                                }
                            }
                            
                            // Source
                            Text {
                                Layout.preferredWidth: 140
                                text: modelData.source || modelData.provider || "Unknown"
                                font.pixelSize: Theme.typography.caption.size
                                color: ThemeManager.foreground()
                                elide: Text.ElideRight
                            }
                            
                            // Friendly Message (use friendly_message, fall back to message)
                            Text {
                                Layout.fillWidth: true
                                text: modelData.friendly_message || modelData.message || ""
                                font.pixelSize: Theme.typography.caption.size
                                color: ThemeManager.muted()
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }
                    }
                    
                    // Empty state
                    Text {
                        anchors.centerIn: parent
                        text: isLoading ? "Loading events..." : (filteredModel.length === 0 ? "No events found" : "")
                        font.pixelSize: Theme.typography.body.size
                        color: ThemeManager.muted()
                        visible: filteredModel.length === 0
                    }
                }
            }
            
            // -----------------------------------------
            // FOOTER: Total count
            // -----------------------------------------
            Rectangle {
                Layout.fillWidth: true
                height: 32
                color: ThemeManager.panel()
                radius: Theme.radii_xs
                
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: Theme.spacing_md
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Total: " + filteredModel.length
                    font.pixelSize: Theme.typography.body.size
                    color: ThemeManager.muted()
                }
            }
        }
        
        // ===========================================
        // RIGHT: AI Explanation Panel
        // ===========================================
        Rectangle {
            Layout.preferredWidth: 320
            Layout.fillHeight: true
            color: ThemeManager.panel()
            radius: Theme.radii_sm
            visible: selectedEvent !== null || aiBusy || aiData !== null || aiError !== ""
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacing_md
                spacing: Theme.spacing_md
                
                // Panel Header
                Text {
                    text: "Event Explanation"
                    font.pixelSize: Theme.typography.h3.size
                    font.weight: Font.Bold
                    color: ThemeManager.foreground()
                }
                
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: ThemeManager.border()
                }
                
                // Loading state
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing_sm
                    visible: aiBusy
                    
                    BusyIndicator {
                        Layout.alignment: Qt.AlignHCenter
                        running: aiBusy
                        implicitWidth: 40
                        implicitHeight: 40
                    }
                    
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Analyzing this event in simple English…"
                        font.pixelSize: Theme.typography.body.size
                        color: ThemeManager.muted()
                    }
                }
                
                // Error state
                Rectangle {
                    Layout.fillWidth: true
                    height: errorContent.implicitHeight + Theme.spacing_md * 2
                    color: "#7F1D1D"
                    radius: Theme.radii_xs
                    visible: aiError !== "" && !aiBusy
                    
                    ColumnLayout {
                        id: errorContent
                        anchors.fill: parent
                        anchors.margins: Theme.spacing_md
                        spacing: Theme.spacing_xs
                        
                        Text {
                            text: "Analysis failed"
                            font.pixelSize: Theme.typography.body.size
                            font.weight: Font.Medium
                            color: "#FCA5A5"
                        }
                        
                        Text {
                            text: aiError
                            font.pixelSize: Theme.typography.caption.size
                            color: "#FECACA"
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                        
                        Button {
                            text: "Try again"
                            implicitHeight: 28
                            
                            background: Rectangle {
                                color: parent.hovered ? "#DC2626" : "#B91C1C"
                                radius: Theme.radii_xs
                            }
                            
                            contentItem: Text {
                                text: parent.text
                                color: "#FFFFFF"
                                font.pixelSize: Theme.typography.caption.size
                                horizontalAlignment: Text.AlignHCenter
                            }
                            
                            onClicked: requestExplanation()
                        }
                    }
                }
                
                // AI Result display - wrapped in Flickable for scrolling
                Flickable {
                    id: aiResultFlickable
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: aiData !== null && !aiBusy && aiError === ""
                    clip: true
                    
                    contentWidth: width
                    contentHeight: aiResultContent.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    
                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                    }
                    
                    ColumnLayout {
                        id: aiResultContent
                        // Account for scrollbar width (typically 10-12px)
                        width: aiResultFlickable.width - 12
                        spacing: Theme.spacing_md
                    
                        // Title
                        Text {
                            text: aiData ? (aiData.title || aiData.short_title || "Event Analysis") : ""
                            font.pixelSize: Theme.typography.h4 ? Theme.typography.h4.size : 18
                            font.weight: Font.Bold
                            color: ThemeManager.foreground()
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                        
                        // Severity Badge
                        Rectangle {
                            implicitWidth: severityBadgeText.implicitWidth + Theme.spacing_md * 2
                            implicitHeight: severityBadgeText.implicitHeight + Theme.spacing_xs * 2
                            radius: height / 2
                            color: aiData ? severityColor(aiData.severity_label || aiData.severity) : ThemeManager.muted()
                            
                            Text {
                                id: severityBadgeText
                                anchors.centerIn: parent
                                text: "Severity: " + (aiData ? (aiData.severity_label || aiData.severity || "Unknown") : "Unknown")
                                font.pixelSize: Theme.typography.caption.size
                                font.weight: Font.Medium
                                color: "#FFFFFF"
                            }
                        }
                        
                        // What happened section
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            
                            Text {
                                text: "📋 What happened:"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                color: ThemeManager.accent
                            }
                            
                            Text {
                                text: aiData ? (aiData.what_happened || aiData.explanation || "") : ""
                                font.pixelSize: Theme.typography.body.size
                                color: ThemeManager.foreground()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.4
                            }
                        }
                        
                        // Why this usually happens section
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: aiData && aiData.why_it_happens && aiData.why_it_happens.length > 0
                            
                            Text {
                                text: "🔍 Why this usually happens:"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                color: ThemeManager.info
                            }
                            
                            Text {
                                text: aiData ? (aiData.why_it_happens || "") : ""
                                font.pixelSize: Theme.typography.body.size
                                color: ThemeManager.foreground()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.4
                            }
                        }
                        
                        // What you should do section (now includes "when to worry")
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: aiData && (aiData.what_to_do || aiData.what_you_can_do || aiData.recommendation)
                            
                            Text {
                                text: "✅ What you should do:"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                color: ThemeManager.success
                            }
                            
                            Text {
                                text: aiData ? (aiData.what_to_do || aiData.what_you_can_do || aiData.recommendation || "") : ""
                                font.pixelSize: Theme.typography.body.size
                                color: ThemeManager.foreground()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.4
                            }
                        }
                        
                        // Tech notes (optional, subtle)
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: aiData && aiData.tech_notes && aiData.tech_notes.length > 0
                            
                            Text {
                                text: "🔧 Technical notes:"
                                font.pixelSize: Theme.typography.caption.size
                                font.weight: Font.Medium
                                color: ThemeManager.muted()
                            }
                            
                            Text {
                                text: aiData ? (aiData.tech_notes || "") : ""
                                font.pixelSize: Theme.typography.caption.size
                                font.italic: true
                                color: ThemeManager.muted()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                opacity: 0.8
                            }
                        }
                        
                        // Knowledge base indicator
                        Text {
                            visible: aiData && (aiData.used_knowledge_base || false) === true
                            text: "ℹ Based on known Windows event documentation."
                            font.pixelSize: Theme.typography.caption.size
                            color: ThemeManager.info
                            opacity: 0.8
                            Layout.fillWidth: true
                        }
                        
                        // Bottom spacing
                        Item {
                            Layout.fillWidth: true
                            height: Theme.spacing_md
                        }
                    }
                }
                
                // No event selected prompt
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Theme.spacing_sm
                    visible: selectedEvent !== null && aiData === null && !aiBusy && aiError === ""
                    
                    Item { Layout.fillHeight: true }
                    
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Click 'Explain Event' to analyze"
                        font.pixelSize: Theme.typography.body.size
                        color: ThemeManager.muted()
                    }
                    
                    Item { Layout.fillHeight: true }
                }
                
                // Selected event info
                Rectangle {
                    Layout.fillWidth: true
                    height: selectedInfoCol.implicitHeight + Theme.spacing_sm * 2
                    color: ThemeManager.elevated()
                    radius: Theme.radii_xs
                    visible: selectedEvent !== null
                    
                    ColumnLayout {
                        id: selectedInfoCol
                        anchors.fill: parent
                        anchors.margins: Theme.spacing_sm
                        spacing: 2
                        
                        Text {
                            text: "Selected Event"
                            font.pixelSize: Theme.typography.caption.size
                            font.weight: Font.Medium
                            color: ThemeManager.muted()
                        }
                        
                        Text {
                            text: selectedEvent ? (selectedEvent.source || selectedEvent.provider || "Unknown") : ""
                            font.pixelSize: Theme.typography.caption.size
                            color: ThemeManager.foreground()
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        
                        Text {
                            text: selectedEvent ? ("ID: " + (selectedEvent.event_id || "N/A")) : ""
                            font.pixelSize: Theme.typography.caption.size
                            color: ThemeManager.muted()
                        }
                    }
                }
            }
        }
    }
}
