import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

AppSurface {
    id: root
    
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
            
            Panel {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: Theme.spacing_lg
                    SectionHeader {
                        title: "Windows Event Viewer"
                        subtitle: "Monitor and analyze system events in real-time"
                    }
                    
                    Button {
                        text: "Load Recent Events"
                        Layout.preferredWidth: 180
                        Layout.preferredHeight: 44
                        Layout.alignment: Qt.AlignLeft
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
                                ColorAnimation { duration: 300 }
                            }
                        }
                        background: Rectangle {
                            color: parent.pressed ? Qt.darker(Theme.primary, 1.2) : parent.hovered ? Qt.lighter(Theme.primary, 1.1) : Theme.primary
                            radius: Theme.radii_sm
                            opacity: parent.enabled ? 1.0 : 0.5
                            Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
                        }
                    }
                    
                    Text {
                        text: "Events loaded: " + eventModel.count
                        color: Theme.muted
                        font.pixelSize: Theme.typography.mono.size
                        
                        Behavior on color {
                            ColorAnimation { duration: 300 }
                        }
                    }
                }
            }
            
            Panel {
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
            
            Panel {
                Layout.fillWidth: true
                visible: eventModel.count > 0
                
                ColumnLayout {
                    spacing: Theme.spacing_lg
                    SectionHeader {
                        title: "Recent Events"
                        subtitle: "Latest " + eventModel.count + " events from Windows Event Log"
                    }
                    
                    ListView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 500
                        model: eventModel
                        spacing: Theme.spacing_sm
                        clip: true
                        
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 80
                            color: Theme.panel
                            radius: Theme.radii_sm
                            
                            Behavior on color {
                                ColorAnimation { duration: 300 }
                            }
                            
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_md
                                spacing: Theme.spacing_md
                                
                                Rectangle {
                                    Layout.preferredWidth: 8
                                    Layout.fillHeight: true
                                    radius: 4
                                    color: {
                                        switch(model.level) {
                                            case "ERROR": return Theme.danger
                                            case "WARNING": return Theme.warning
                                            case "SUCCESS": return Theme.success
                                            case "FAILURE": return Theme.danger
                                            case "INFO": return Theme.info
                                            default: return Theme.primary
                                        }
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
                                                    case "ERROR": return Theme.danger
                                                    case "WARNING": return Theme.warning
                                                    case "SUCCESS": return Theme.success
                                                    case "FAILURE": return Theme.danger
                                                    case "INFO": return Theme.info
                                                    default: return Theme.primary
                                                }
                                            }
                                            font.pixelSize: Theme.typography.mono.size
                                            font.weight: Font.Bold
                                            
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
}
