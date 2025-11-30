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
                        width: parent.width
                        model: eventModel
                        spacing: 2

                        delegate: Rectangle {
                            width: ListView.view ? ListView.view.width : 500
                            height: 50
                            color: {
                                var isDark = ThemeManager ? ThemeManager.isDark() : true
                                return isDark ? 
                                       (index % 2 === 0 ? "#0B1020" : "#050814") : 
                                       (index % 2 === 0 ? "#F3F4F6" : "#FFFFFF")
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
                    text: eventModel.count === 0 ? "No events" : "Total: " + eventModel.count
                    color: ThemeManager.muted()
                    font.pixelSize: 10
                    Layout.alignment: Qt.AlignRight
                    Layout.rightMargin: 8
                    Layout.topMargin: 8
                }
            }
        }
    }

    // Data model
    ListModel {
        id: eventModel
    }
}
