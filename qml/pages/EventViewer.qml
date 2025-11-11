import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import "../theme"

AppSurface {
    id: root
    
    // Glassmorphic background gradient
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.bg }
            GradientStop { position: 1.0; color: Qt.darker(Theme.bg, 1.1) }
        }
    }
    
    Item {
        anchors.fill: parent

        // Event list model
        ListModel {
            id: eventModel
        }

        // Connect to backend
        Connections {
            target: typeof Backend !== 'undefined' ? Backend : null

            function onEventsLoaded(events) {
                eventModel.clear()
                for (var i = 0; i < events.length; i++) {
                    eventModel.append(events[i])
                }
            }

            function onToast(level, message) {
                console.log("[" + level + "] " + message)
            }
        }

    ScrollView {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        clip: true

        ColumnLayout {
            width: Math.max(800, parent.width - Theme.spacing_md * 2)
            spacing: Theme.spacing_lg

            // Header Panel with Glassmorphism
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: contentColumn.height + Theme.spacing_xl * 2
                radius: 16
                color: Theme.glass.panel
                border.color: Theme.glass.border
                border.width: 1

                // Neon gradient overlay
                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Theme.glass.gradientStart }
                        GradientStop { position: 1.0; color: Theme.glass.gradientEnd }
                    }
                }

                ColumnLayout {
                    id: contentColumn
                    anchors.centerIn: parent
                    width: parent.width - Theme.spacing_xl * 2
                    spacing: Theme.spacing_lg

                    SectionHeader {
                        title: "Windows Event Viewer"
                        subtitle: "Monitor and analyze system events in real-time"
                    }

                    RowLayout {
                        spacing: Theme.spacing_md

                        Button {
                            text: "Load Recent Events"
                            Layout.preferredWidth: 180
                            Layout.preferredHeight: 44
                            enabled: typeof Backend !== 'undefined'

                            onClicked: {
                                if (typeof Backend !== 'undefined') {
                                    Backend.loadRecentEvents()
                                }
                            }

                            contentItem: Text {
                                text: parent.text
                                color: Theme.text
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter

                                Behavior on color {
                                    ColorAnimation { duration: Theme.duration_fast }
                                }
                            }
                            background: Rectangle {
                                color: parent.pressed ? Qt.darker(Theme.primary, 1.2) : parent.hovered ? Qt.lighter(Theme.primary, 1.1) : Theme.primary
                                radius: Theme.radii_sm
                                opacity: parent.enabled ? 1.0 : 0.5
                                border.color: parent.hovered ? Theme.neon.purpleGlow : "transparent"
                                border.width: 2
                                
                                Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
                                Behavior on border.color { ColorAnimation { duration: Theme.duration_fast } }
                            }
                        }

                        Rectangle {
                            Layout.preferredWidth: 200
                            Layout.preferredHeight: 44
                            radius: Theme.radii_sm
                            color: Theme.glass.overlay
                            border.color: Theme.glass.border
                            border.width: 1

                            RowLayout {
                                anchors.centerIn: parent
                                spacing: Theme.spacing_sm

                                Rectangle {
                                    width: 8
                                    height: 8
                                    radius: 4
                                    color: eventModel.count > 0 ? Theme.neon.green : Theme.muted
                                    
                                    Behavior on color { ColorAnimation { duration: Theme.duration_medium } }
                                }

                                Text {
                                    text: "Events: " + eventModel.count
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.body.size
                                    font.weight: Font.Medium

                                    Behavior on color {
                                        ColorAnimation { duration: Theme.duration_fast }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: eventModel.count === 0

                ColumnLayout {
                    spacing: Theme.spacing_lg
                    
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 120
                        color: Theme.surface
                        radius: Theme.radii_md
                        border.color: Theme.border
                        border.width: 1
                        
                        Behavior on color {
                            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                        }
                        
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: Theme.spacing_md
                            
                            Text {
                                text: "�"
                                font.pixelSize: 32
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: "Click 'Load Recent Events' to view Windows event logs"
                                color: Theme.muted
                                font.pixelSize: Theme.typography.body.size
                                Layout.alignment: Qt.AlignHCenter
                                
                                Behavior on color {
                                    ColorAnimation { duration: 300 }
                                }
                            }
                        }
                    }
                }
            }

            // Event List Panel with Glassmorphism
            Rectangle {
                Layout.fillWidth: true
                visible: eventModel.count > 0
                radius: 16
                color: Theme.glass.panel
                border.color: Theme.glass.border
                border.width: 1
                implicitHeight: eventListContent.height + Theme.spacing_xl * 2

                ColumnLayout {
                    id: eventListContent
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: Theme.spacing_xl
                    spacing: Theme.spacing_lg

                    SectionHeader {
                        title: "Recent Events"
                        subtitle: "Latest " + eventModel.count + " events from Windows Event Log"
                    }                    ListView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 500
                        model: eventModel
                        spacing: Theme.spacing_sm
                        clip: true

                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 80
                            color: Theme.glass.card
                            radius: Theme.radii_sm
                            border.color: Qt.rgba(0.5, 0.4, 1.0, 0.15)
                            border.width: 1

                            // Hover glow effect
                            Rectangle {
                                anchors.fill: parent
                                radius: parent.radius
                                color: Theme.neon.purpleDim
                                opacity: mouseArea.containsMouse ? 0.3 : 0
                                
                                Behavior on opacity {
                                    NumberAnimation { duration: Theme.duration_fast }
                                }
                            }

                            MouseArea {
                                id: mouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                            }

                            Behavior on color {
                                ColorAnimation { duration: Theme.duration_fast }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_md
                                spacing: Theme.spacing_md

                                // Neon accent bar
                                Rectangle {
                                    Layout.preferredWidth: 4
                                    Layout.fillHeight: true
                                    radius: 2
                                    color: {
                                        switch(model.level) {
                                            case "ERROR": return Theme.neon.red
                                            case "WARNING": return Theme.warning
                                            case "SUCCESS": return Theme.neon.green
                                            case "FAILURE": return Theme.neon.red
                                            case "INFO": return Theme.neon.blue
                                            default: return Theme.neon.purple
                                        }
                                    }

                                    // Glow effect
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.margins: -2
                                        radius: parent.radius
                                        color: "transparent"
                                        border.color: parent.color
                                        border.width: 2
                                        opacity: 0.3
                                    }

                                    Behavior on color {
                                        ColorAnimation { duration: 300 }
                                    }
                                }
                                
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    
                                    RowLayout {
                                        spacing: Theme.spacing_sm
                                        
                                        Text {
                                            text: model.level
                                            color: {
                                                switch(model.level) {
                                                    case "ERROR": return Theme.neon.red
                                                    case "WARNING": return Theme.warning
                                                    case "SUCCESS": return Theme.neon.green
                                                    case "FAILURE": return Theme.neon.red
                                                    case "INFO": return Theme.neon.blue
                                                    default: return Theme.neon.purple
                                                }
                                            }
                                            font.pixelSize: Theme.typography.mono.size
                                            font.weight: Font.Bold

                                            Behavior on color {
                                                ColorAnimation { duration: Theme.duration_fast }
                                            }
                                        }                                        Text {
                                            text: "•"
                                            color: Theme.muted
                                            font.pixelSize: Theme.typography.mono.size
                                        }
                                        
                                        Text {
                                            text: model.source
                                            color: Theme.muted
                                            font.pixelSize: Theme.typography.mono.size
                                            
                                            Behavior on color {
                                                ColorAnimation { duration: 300 }
                                            }
                                        }
                                        
                                        Text {
                                            text: "•"
                                            color: Theme.muted
                                            font.pixelSize: Theme.typography.mono.size
                                        }
                                        
                                        Text {
                                            text: model.timestamp
                                            color: Theme.muted
                                            font.pixelSize: Theme.typography.mono.size
                                            
                                            Behavior on color {
                                                ColorAnimation { duration: 300 }
                                            }
                                        }
                                    }
                                    
                                    Text {
                                        text: model.message
                                        color: Theme.text
                                        font.pixelSize: Theme.typography.body.size
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                        maximumLineCount: 2
                                        elide: Text.ElideRight
                                        
                                        Behavior on color {
                                            ColorAnimation { duration: 300 }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    } // Item wrapper

    Component.onCompleted: {
        // Auto-load events when page opens (with delay to ensure Backend is ready)
        Qt.callLater(function() {
            if (typeof Backend !== 'undefined' && Backend) {
                Backend.loadRecentEvents()
            }
        })
    }
}
