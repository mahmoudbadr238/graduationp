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
    
    // Explanation mode: "none" | "brief" | "detailed"
    property string explanationMode: "none"
    property var briefData: null
    
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
        explanationMode = "detailed"
        
        // Use the stored original index
        if (typeof Backend !== "undefined" && Backend.requestEventExplanation) {
            Backend.requestEventExplanation(selectedEventIndex)
        } else {
            aiBusy = false
            aiError = "Backend not available"
        }
    }
    
    function requestSimplifiedExplanation() {
        if (!selectedEvent || selectedEventIndex < 0) {
            if (typeof Backend !== "undefined" && Backend.toast) {
                Backend.toast("warning", "Please select an event first.")
            }
            return
        }
        
        // Request simplified explanation
        aiData = null
        aiError = ""
        aiBusy = true
        
        if (typeof Backend !== "undefined" && Backend.requestSimplifiedExplanation) {
            Backend.requestSimplifiedExplanation(selectedEventIndex)
        } else {
            aiBusy = false
            aiError = "Simplified explanation not available"
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
        
        function onEventPreviewReady(eventId, previewJson) {
            console.log("[EventViewer] Preview received for event", eventId)
            try {
                briefData = JSON.parse(previewJson)
            } catch (e) {
                briefData = { meaning: "Event recorded", risk: "Low", actions: ["No action needed"] }
            }
        }
        
        function onAgentStepsCleared() {
            // no-op: agent steps feature removed
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
                                // Reset to brief mode and request preview
                                explanationMode = "brief"
                                aiData = null
                                aiError = ""
                                aiBusy = false
                                briefData = null
                                if (typeof Backend !== "undefined" && Backend.previewEvent) {
                                    Backend.previewEvent(selectedEventIndex)
                                }
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
            visible: selectedEvent !== null
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacing_md
                spacing: Theme.spacing_md
                
                // Panel Header
                Text {
                    text: explanationMode === "detailed" ? "Detailed Analysis" : "Quick Summary"
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
                    color: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.15)
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
                            color: Theme.danger
                        }
                        
                        Text {
                            text: aiError
                            font.pixelSize: Theme.typography.caption.size
                            color: Theme.danger
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                        
                        Button {
                            text: "Try again"
                            implicitHeight: 28
                            
                            background: Rectangle {
                                color: parent.hovered ? Qt.lighter(Theme.danger, 1.2) : Theme.danger
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
                
                // =============================================
                // BRIEF SUMMARY (shown when explanationMode === "brief")
                // =============================================
                Flickable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: explanationMode === "brief" && !aiBusy
                    clip: true
                    contentWidth: width
                    contentHeight: briefContent.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    
                    ColumnLayout {
                        id: briefContent
                        width: parent.width - 12
                        spacing: Theme.spacing_md
                        
                        // Meaning
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: meaningCol.implicitHeight + Theme.spacing_md * 2
                            color: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.1)
                            radius: Theme.radii_sm
                            
                            ColumnLayout {
                                id: meaningCol
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_md
                                spacing: Theme.spacing_xs
                                
                                Text {
                                    text: "💡 What this means"
                                    font.pixelSize: Theme.typography.body.size
                                    font.weight: Font.Bold
                                    color: ThemeManager.accent
                                }
                                
                                Text {
                                    text: briefData ? (briefData.meaning || "") : "Loading..."
                                    font.pixelSize: Theme.typography.body.size + 1
                                    color: ThemeManager.foreground()
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                    lineHeight: 1.5
                                }
                            }
                        }
                        
                        // Risk Badge
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: riskRow.implicitHeight + Theme.spacing_sm * 2
                            radius: Theme.radii_sm
                            color: {
                                if (!briefData) return ThemeManager.elevated()
                                if (briefData.risk === "High") return "#7F1D1D"
                                if (briefData.risk === "Medium") return "#78350F"
                                return Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.15)
                            }
                            
                            RowLayout {
                                id: riskRow
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_sm
                                spacing: Theme.spacing_sm
                                
                                Text {
                                    text: {
                                        if (!briefData) return "⏳"
                                        if (briefData.risk === "High") return "🔴"
                                        if (briefData.risk === "Medium") return "🟡"
                                        return "🟢"
                                    }
                                    font.pixelSize: 18
                                }
                                
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    
                                    Text {
                                        text: "Risk: " + (briefData ? briefData.risk : "...")
                                        font.pixelSize: Theme.typography.body.size
                                        font.weight: Font.Bold
                                        color: {
                                            if (!briefData) return ThemeManager.muted()
                                            if (briefData.risk === "High") return "#FCA5A5"
                                            if (briefData.risk === "Medium") return "#FDE68A"
                                            return ThemeManager.success
                                        }
                                    }
                                    
                                    Text {
                                        text: briefData ? (briefData.risk_reason || "") : ""
                                        font.pixelSize: Theme.typography.caption.size
                                        color: ThemeManager.foreground()
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                        opacity: 0.8
                                    }
                                }
                            }
                        }
                        
                        // Actions
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: briefData !== null && briefData.actions && briefData.actions.length > 0
                            
                            Text {
                                text: "✅ What to do now"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Bold
                                color: ThemeManager.success
                            }
                            
                            Repeater {
                                model: briefData ? briefData.actions : []
                                delegate: Text {
                                    text: "• " + modelData
                                    font.pixelSize: Theme.typography.body.size
                                    color: ThemeManager.foreground()
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                    lineHeight: 1.4
                                }
                            }
                        }
                        
                        // Explain Event Button (prominent)
                        Button {
                            Layout.fillWidth: true
                            Layout.topMargin: Theme.spacing_sm
                            implicitHeight: 40
                            
                            text: "🔍 Explain Event in Detail"
                            
                            background: Rectangle {
                                color: parent.hovered ? Qt.lighter(ThemeManager.accent, 1.2) : ThemeManager.accent
                                radius: Theme.radii_xs
                            }
                            
                            contentItem: Text {
                                text: parent.text
                                color: "#FFFFFF"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Bold
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            
                            onClicked: requestExplanation()
                        }

                        
                        // Event info footer
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: briefInfoCol.implicitHeight + Theme.spacing_sm * 2
                            color: ThemeManager.elevated()
                            radius: Theme.radii_xs
                            
                            ColumnLayout {
                                id: briefInfoCol
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_sm
                                spacing: 2
                                
                                Text {
                                    text: selectedEvent ? (selectedEvent.source || selectedEvent.provider || "Unknown") + " · ID: " + (selectedEvent.event_id || "N/A") : ""
                                    font.pixelSize: Theme.typography.caption.size
                                    color: ThemeManager.muted()
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
                
                // =============================================
                // DETAILED EXPLANATION (shown when explanationMode === "detailed")
                // =============================================
                
                // AI Result display - wrapped in Flickable for scrolling
                Flickable {
                    id: aiResultFlickable
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: explanationMode === "detailed" && aiData !== null && !aiBusy && aiError === ""
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
                    
                        // ===========================================
                        // QUICK BRIEF SECTION (NEW - At top for easy scanning)
                        // ===========================================
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: quickBriefContent.implicitHeight + Theme.spacing_md * 2
                            color: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.15)
                            radius: Theme.radii_sm
                            border.color: ThemeManager.accent
                            border.width: 1
                            visible: false  // Brief summary is for "brief" mode only
                            
                            ColumnLayout {
                                id: quickBriefContent
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_md
                                spacing: Theme.spacing_sm
                                
                                // User-friendly brief (always visible when available)
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: Theme.spacing_xs
                                    visible: aiData && aiData.brief_user
                                    
                                    Text {
                                        text: "💡 Quick Summary"
                                        font.pixelSize: Theme.typography.body.size
                                        font.weight: Font.Bold
                                        color: ThemeManager.accent
                                    }
                                    
                                    Text {
                                        Layout.fillWidth: true
                                        text: aiData ? (aiData.brief_user || "") : ""
                                        font.pixelSize: Theme.typography.body.size + 1
                                        color: ThemeManager.foreground()
                                        wrapMode: Text.Wrap
                                        lineHeight: 1.5
                                    }
                                }
                                
                                // Technical brief (collapsible)
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: Theme.spacing_xs
                                    visible: aiData && aiData.brief_technical
                                    
                                    Rectangle {
                                        id: techBriefHeader
                                        Layout.fillWidth: true
                                        implicitHeight: techBriefHeaderRow.implicitHeight + Theme.spacing_xs * 2
                                        color: techBriefMouseArea.containsMouse ? Qt.rgba(ThemeManager.foreground().r, ThemeManager.foreground().g, ThemeManager.foreground().b, 0.05) : "transparent"
                                        radius: Theme.radii_xs
                                        
                                        property bool expanded: false
                                        
                                        RowLayout {
                                            id: techBriefHeaderRow
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacing_xs
                                            spacing: Theme.spacing_xs
                                            
                                            Text {
                                                text: techBriefHeader.expanded ? "▼" : "▶"
                                                font.pixelSize: Theme.typography.caption.size
                                                color: ThemeManager.muted()
                                            }
                                            
                                            Text {
                                                text: "🔧 Technical Brief"
                                                font.pixelSize: Theme.typography.caption.size
                                                font.weight: Font.Medium
                                                color: ThemeManager.muted()
                                            }
                                            
                                            Item { Layout.fillWidth: true }
                                        }
                                        
                                        MouseArea {
                                            id: techBriefMouseArea
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: techBriefHeader.expanded = !techBriefHeader.expanded
                                        }
                                    }
                                    
                                    // Technical content (shown when expanded)
                                    Text {
                                        visible: techBriefHeader.expanded
                                        Layout.fillWidth: true
                                        Layout.leftMargin: Theme.spacing_md
                                        text: aiData ? (aiData.brief_technical || "") : ""
                                        font.pixelSize: Theme.typography.caption.size
                                        font.family: "Consolas, Monaco, monospace"
                                        color: ThemeManager.muted()
                                        wrapMode: Text.Wrap
                                        lineHeight: 1.4
                                    }
                                }
                                
                                // Confidence and Evidence
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: Theme.spacing_xs
                                    visible: aiData !== null && (aiData.confidence !== undefined || (aiData.evidence && aiData.evidence.length > 0))
                                    
                                    // Confidence indicator
                                    Text {
                                        visible: aiData !== null && aiData.confidence !== undefined
                                        text: "📊 Confidence: " + (aiData ? String(aiData.confidence || "N/A") : "N/A")
                                        font.pixelSize: Theme.typography.caption.size
                                        font.weight: Font.Medium
                                        color: {
                                            if (!aiData || aiData.confidence === undefined) return ThemeManager.muted()
                                            var conf = Number(aiData.confidence)
                                            if (conf >= 0.8) return ThemeManager.success
                                            if (conf >= 0.5) return ThemeManager.warning
                                            return ThemeManager.muted()
                                        }
                                    }
                                    
                                    // Evidence
                                    Text {
                                        visible: aiData !== null && aiData.evidence && aiData.evidence.length > 0
                                        Layout.fillWidth: true
                                        text: {
                                            if (!aiData || !aiData.evidence) return ""
                                            var items = Array.isArray(aiData.evidence) ? aiData.evidence : [String(aiData.evidence)]
                                            return "📋 " + items.join(", ")
                                        }
                                        font.pixelSize: Theme.typography.caption.size
                                        color: ThemeManager.muted()
                                        elide: Text.ElideRight
                                        wrapMode: Text.NoWrap
                                    }
                                }
                                
                                // "Explain simpler" button
                                Button {
                                    Layout.alignment: Qt.AlignLeft
                                    visible: aiData && aiData.detail_level !== "simplified"
                                    
                                    text: "🔄 Explain simpler"
                                    implicitHeight: 28
                                    
                                    background: Rectangle {
                                        color: parent.hovered ? ThemeManager.info : Qt.rgba(ThemeManager.info.r, ThemeManager.info.g, ThemeManager.info.b, 0.7)
                                        radius: Theme.radii_xs
                                    }
                                    
                                    contentItem: Text {
                                        text: parent.text
                                        color: "#FFFFFF"
                                        font.pixelSize: Theme.typography.caption.size
                                        font.weight: Font.Medium
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    
                                    onClicked: requestSimplifiedExplanation()
                                }
                                
                                // Indicator when simplified
                                Row {
                                    spacing: Theme.spacing_xs
                                    visible: aiData && aiData.detail_level === "simplified"
                                    
                                    Text {
                                        text: "✨"
                                        font.pixelSize: Theme.typography.caption.size
                                    }
                                    
                                    Text {
                                        text: "Simplified explanation"
                                        font.pixelSize: Theme.typography.caption.size
                                        color: ThemeManager.info
                                        font.italic: true
                                    }
                                }
                            }
                        }
                    
                        // Plain Summary (highlighted, prominent)
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: plainSummaryText.implicitHeight + Theme.spacing_md * 2
                            color: Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.1)
                            radius: Theme.radii_xs
                            visible: false  // Summary belongs to brief mode only; hide in detailed view
                            
                            Text {
                                id: plainSummaryText
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_md
                                text: aiData ? (aiData.plain_summary || "") : ""
                                font.pixelSize: Theme.typography.body.size + 1
                                font.weight: Font.Medium
                                color: ThemeManager.foreground()
                                wrapMode: Text.Wrap
                                lineHeight: 1.5
                            }
                        }
                    
                        // Title (fallback if no plain_summary)
                        Text {
                            text: aiData ? (aiData.title || aiData.short_title || "Event Analysis") : ""
                            font.pixelSize: Theme.typography.h4 ? Theme.typography.h4.size : 18
                            font.weight: Font.Bold
                            color: ThemeManager.foreground()
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                            visible: !aiData || !aiData.plain_summary || aiData.plain_summary.length === 0
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
                        
                        // Source indicator (deterministic vs AI)
                        Text {
                            visible: aiData && aiData.source
                            text: aiData && aiData.source === "ai" ? "🤖 AI Enhanced" : 
                                  aiData && aiData.source === "cached" ? "💾 Cached" : "⚡ Instant Analysis"
                            font.pixelSize: Theme.typography.caption.size
                            color: aiData && aiData.source === "ai" ? ThemeManager.accent : ThemeManager.muted()
                            opacity: 0.8
                        }
                        
                        // What happened section
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: aiData && (aiData.what_happened || aiData.explanation)
                            
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
                        
                        // Why this usually happens section (now supports list)
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: aiData && (
                                (Array.isArray(aiData.why_it_happened) && aiData.why_it_happened.length > 0) ||
                                (aiData.why_it_happens && aiData.why_it_happens.length > 0)
                            )
                            
                            Text {
                                text: "🔍 Why this usually happens:"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                color: ThemeManager.info
                            }
                            
                            Text {
                                text: {
                                    if (!aiData) return ""
                                    if (Array.isArray(aiData.why_it_happened)) {
                                        return aiData.why_it_happened.map(function(item) { return "• " + item }).join("\n")
                                    }
                                    return aiData.why_it_happens || ""
                                }
                                font.pixelSize: Theme.typography.body.size
                                color: ThemeManager.foreground()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.4
                            }
                        }
                        
                        // What it affects section (new in V4)
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: aiData && Array.isArray(aiData.what_it_affects) && aiData.what_it_affects.length > 0
                            
                            Text {
                                text: "⚠️ What it affects:"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                color: ThemeManager.warning || "#FBBF24"
                            }
                            
                            Text {
                                text: aiData && Array.isArray(aiData.what_it_affects) ? 
                                    aiData.what_it_affects.map(function(item) { return "• " + item }).join("\n") : ""
                                font.pixelSize: Theme.typography.body.size
                                color: ThemeManager.foreground()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.4
                            }
                        }
                        
                        // Recommended actions section (now supports list)
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: aiData && (
                                (Array.isArray(aiData.recommended_actions) && aiData.recommended_actions.length > 0) ||
                                aiData.what_to_do || aiData.what_you_can_do || aiData.recommendation
                            )
                            
                            Text {
                                text: "✅ What you should do:"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                color: ThemeManager.success
                            }
                            
                            Text {
                                text: {
                                    if (!aiData) return ""
                                    if (Array.isArray(aiData.recommended_actions) && aiData.recommended_actions.length > 0) {
                                        return aiData.recommended_actions.map(function(item) { return "• " + item }).join("\n")
                                    }
                                    return aiData.what_to_do || aiData.what_you_can_do || aiData.recommendation || ""
                                }
                                font.pixelSize: Theme.typography.body.size
                                color: ThemeManager.foreground()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.4
                            }
                        }
                        
                        // When to worry section (new in V4)
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: aiData && Array.isArray(aiData.when_to_worry) && aiData.when_to_worry.length > 0
                            
                            Text {
                                text: "🚨 When to worry:"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                color: ThemeManager.error || "#EF4444"
                            }
                            
                            Text {
                                text: aiData && Array.isArray(aiData.when_to_worry) ? 
                                    aiData.when_to_worry.map(function(item) { return "• " + item }).join("\n") : ""
                                font.pixelSize: Theme.typography.body.size
                                color: ThemeManager.foreground()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                lineHeight: 1.4
                            }
                        }
                        
                        // Technical details (collapsible)
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_xs
                            visible: Boolean(aiData && (aiData.technical_details || aiData.tech_notes))
                            
                            // Collapsible header
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: techHeaderRow.implicitHeight + Theme.spacing_xs * 2
                                color: techDetailsMouseArea.containsMouse ? Qt.rgba(ThemeManager.foreground().r, ThemeManager.foreground().g, ThemeManager.foreground().b, 0.05) : "transparent"
                                radius: Theme.radii_xs
                                
                                property bool expanded: false
                                
                                RowLayout {
                                    id: techHeaderRow
                                    anchors.fill: parent
                                    anchors.margins: Theme.spacing_xs
                                    spacing: Theme.spacing_xs
                                    
                                    Text {
                                        text: parent.parent.expanded ? "▼" : "▶"
                                        font.pixelSize: Theme.typography.caption.size
                                        color: ThemeManager.muted()
                                    }
                                    
                                    Text {
                                        text: "🔧 Technical details"
                                        font.pixelSize: Theme.typography.caption.size
                                        font.weight: Font.Medium
                                        color: ThemeManager.muted()
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                }
                                
                                MouseArea {
                                    id: techDetailsMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: parent.expanded = !parent.expanded
                                }
                            }
                            
                            // Technical content (shown when expanded)
                            Text {
                                visible: parent.children[0].expanded
                                text: {
                                    if (!aiData) return ""
                                    if (aiData.technical_details) {
                                        var details = aiData.technical_details
                                        var lines = []
                                        if (details.provider) lines.push("Provider: " + details.provider)
                                        if (details.event_id) lines.push("Event ID: " + details.event_id)
                                        if (details.level) lines.push("Level: " + details.level)
                                        if (details.extracted_entities) {
                                            var entities = details.extracted_entities
                                            for (var key in entities) {
                                                if (entities[key] && entities[key].length > 0) {
                                                    lines.push(key + ": " + (Array.isArray(entities[key]) ? entities[key].join(", ") : entities[key]))
                                                }
                                            }
                                        }
                                        return lines.join("\n")
                                    }
                                    return aiData.tech_notes || ""
                                }
                                font.pixelSize: Theme.typography.caption.size
                                font.family: "Consolas, Monaco, monospace"
                                color: ThemeManager.muted()
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                Layout.leftMargin: Theme.spacing_md
                                opacity: 0.9
                            }
                        }
                        
                        // AI Enhancement button (for deterministic results)
                        Button {
                            visible: aiData && aiData.source === "deterministic"
                            Layout.alignment: Qt.AlignHCenter
                            Layout.topMargin: Theme.spacing_sm
                            
                            text: "🤖 Get AI Enhanced Analysis"
                            implicitHeight: 36
                            implicitWidth: implicitContentWidth + Theme.spacing_lg * 2
                            
                            background: Rectangle {
                                color: parent.hovered ? ThemeManager.accent : Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.8)
                                radius: Theme.radii_xs
                            }
                            
                            contentItem: Text {
                                text: parent.text
                                color: "#FFFFFF"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            
                            onClicked: {
                                aiBusy = true
                                if (typeof Backend !== "undefined" && Backend.requestAIEnhancement) {
                                    Backend.requestAIEnhancement(selectedEventIndex)
                                }
                            }
                        }
                        
                        // Ask Chatbot to Help button
                        Button {
                            visible: aiData !== null && selectedEvent !== null
                            Layout.alignment: Qt.AlignHCenter
                            Layout.topMargin: Theme.spacing_sm
                            
                            text: "💬 Ask Chatbot to Help Resolve"
                            implicitHeight: 36
                            implicitWidth: implicitContentWidth + Theme.spacing_lg * 2
                            
                            background: Rectangle {
                                color: parent.hovered ? Theme.primary : Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.8)
                                radius: Theme.radii_xs
                            }
                            
                            contentItem: Text {
                                text: parent.text
                                color: "#FFFFFF"
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            
                            onClicked: {
                                // Set the selected event context for chatbot
                                // This will also navigate to AI Assistant page
                                if (typeof Backend !== "undefined" && Backend.setEventContextForChat) {
                                    var eventContext = {
                                        event_id: selectedEvent.event_id,
                                        provider: selectedEvent.source || selectedEvent.provider,
                                        level: selectedEvent.level,
                                        message: selectedEvent.message || "",
                                        time_created: selectedEvent.time_created || selectedEvent.timestamp,
                                        explanation: aiData
                                    }
                                    Backend.setEventContextForChat(JSON.stringify(eventContext))
                                    console.log("[EventViewer] Sent event context to chatbot, navigation will follow")
                                }
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
                
                // No event selected prompt — replaced by Brief Summary above
                // (kept as invisible placeholder for compatibility)
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: explanationMode === "none" && !aiBusy && aiError === ""
                    
                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: Theme.spacing_sm
                        
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: "👈 Select an event to see a summary"
                            font.pixelSize: Theme.typography.body.size
                            color: ThemeManager.muted()
                        }
                    }
                }

            }
        }
    }
}
