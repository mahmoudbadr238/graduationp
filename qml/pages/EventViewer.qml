import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

AppSurface {
    id: root
    
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
                        title: "Welcome to Event Viewer"
                        subtitle: "Monitor and analyze system events in real-time"
                    }
                    
                    Button {
                        text: "Scan My Events"
                        Layout.preferredWidth: 180
                        Layout.preferredHeight: 44
                        Layout.alignment: Qt.AlignLeft
                        Accessible.role: Accessible.Button
                        Accessible.name: "Scan My Events"
                        contentItem: Text {
                            text: parent.text
                            color: Theme.text
                            font.pixelSize: Theme.typography.body.size
                            font.weight: Font.Medium
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            color: parent.pressed ? Qt.darker(Theme.primary, 1.2) : parent.hovered ? Qt.lighter(Theme.primary, 1.1) : Theme.primary
                            radius: Theme.radii_sm
                            Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
                        }
                    }
                }
            }
            
            Panel {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: Theme.spacing_lg
                    SectionHeader {
                        title: "Real-Time Scan"
                        subtitle: "Live event monitoring"
                    }
                    
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
                        Behavior on border.color {
                            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                        }
                        
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: Theme.spacing_md
                            
                            Text {
                                text: "🔴 LIVE"
                                color: Theme.danger
                                font.pixelSize: Theme.typography.h2.size
                                font.weight: Font.Bold
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: "Monitoring system events..."
                                color: Theme.muted
                                font.pixelSize: Theme.typography.body.size
                                Layout.alignment: Qt.AlignHCenter
                                
                                Behavior on color {
                                    ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                                }
                            }
                        }
                    }
                }
            }
            
            Panel {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: Theme.spacing_lg
                    SectionHeader {
                        title: "Events History"
                        subtitle: "Past events"
                    }
                    
                    ListView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 300
                        model: ListModel {
                            ListElement { eventId: "1000"; type: "critical"; message: "Failed login attempt detected"; time: "2m ago" }
                            ListElement { eventId: "1001"; type: "warning"; message: "System process anomaly detected"; time: "5m ago" }
                            ListElement { eventId: "1002"; type: "info"; message: "Security policy updated"; time: "12m ago" }
                            ListElement { eventId: "1003"; type: "success"; message: "Threat successfully blocked"; time: "18m ago" }
                        }
                        spacing: Theme.spacing_sm
                        clip: true
                        
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 72
                            color: Theme.panel
                            radius: Theme.radii_sm
                            
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_md
                                spacing: Theme.spacing_md
                                
                                AnimatedCard {
                                    Layout.fillWidth: true
                                    ColumnLayout {
                                        spacing: Theme.spacing_lg
                                        SectionHeader {
                                            title: "Welcome to Event Viewer"
                                            subtitle: "Monitor and analyze system events in real-time"
                                        }
                                        Button {
                                            text: "Scan My Events"
                                            Layout.preferredWidth: 180
                                            Layout.preferredHeight: 44
                                            Layout.alignment: Qt.AlignLeft
                                            Accessible.role: Accessible.Button
                                            Accessible.name: "Scan My Events"
                                            contentItem: Text {
                                                text: parent.text
                                                color: Theme.text
                                                font.pixelSize: Theme.typography.body.size
                                                font.weight: Font.Medium
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            background: Rectangle {
                                                color: parent.pressed ? Qt.darker(Theme.primary, 1.2) : parent.hovered ? Qt.lighter(Theme.primary, 1.1) : Theme.primary
                                                radius: Theme.radii_sm
                                                Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
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
    }
}
