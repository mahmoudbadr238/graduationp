import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import "../ui"

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
                        title: "Scan History"
                        subtitle: "All completed and scheduled scans"
                    }
                    
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing_md
                        
                        DebouncedButton {
                            text: isProcessing ? "Exporting..." : "Export CSV"
                            Layout.preferredHeight: 36
                            Layout.preferredWidth: 140
                            debounceMs: 1000
                            
                            Accessible.role: Accessible.Button
                            Accessible.name: "Export CSV"
                            
                            onClicked: {
                                // Simulate CSV export
                                var toast = globalToast || root.parent.parent.parent.parent.parent
                                if (toast && toast.show) {
                                    toast.show("✓ CSV exported successfully to Downloads folder", 3000, "success")
                                }
                                console.log("Exporting scan history to CSV...")
                            }
                        }
                        
                        Item { Layout.fillWidth: true }
                        
                        Text {
                            text: "Total scans: 42"
                            color: Theme.muted
                            font.pixelSize: Theme.typography.body.size
                        }
                    }
                    
                    // Header row
                    Rectangle {
                        Layout.fillWidth: true
                        height: 40
                        color: Theme.surface
                        radius: Theme.radii_sm
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing_md
                            spacing: Theme.spacing_md
                            
                            Text {
                                text: "Date & Time"
                                color: Theme.muted
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                Layout.preferredWidth: 180
                            }
                            Text {
                                text: "Scan Type"
                                color: Theme.muted
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                Layout.fillWidth: true
                            }
                            Text {
                                text: "Findings"
                                color: Theme.muted
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                Layout.preferredWidth: 80
                                horizontalAlignment: Text.AlignHCenter
                            }
                            Text {
                                text: "Status"
                                color: Theme.muted
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                                Layout.minimumWidth: 140
                            }
                        }
                    }
                    
                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Theme.border
                    }
                    ListView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 400
                        model: ListModel {
                            ListElement { date: "2024-01-15 14:23"; type: "Full System Scan"; findings: "0"; status: "Clean"; statusType: "success" }
                            ListElement { date: "2024-01-15 08:45"; type: "Quick Scan"; findings: "0"; status: "Clean"; statusType: "success" }
                            ListElement { date: "2024-01-14 22:10"; type: "Network Scan"; findings: "12"; status: "Devices Found"; statusType: "info" }
                            ListElement { date: "2024-01-14 16:30"; type: "Malware Scan"; findings: "2"; status: "Threats Blocked"; statusType: "warning" }
                            ListElement { date: "2024-01-13 11:15"; type: "Registry Scan"; findings: "0"; status: "Clean"; statusType: "success" }
                        }
                        spacing: Theme.spacing_sm
                        clip: true
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 56
                            color: mouseArea.containsMouse ? Qt.lighter(Theme.panel, 1.1) : 
                                   (index % 2 === 0 ? Theme.panel : "transparent")
                            radius: Theme.radii_sm
                            
                            Behavior on color {
                                ColorAnimation { duration: Theme.duration_fast }
                            }
                            
                            MouseArea {
                                id: mouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                
                                onClicked: {
                                    console.log("Show details for scan:", model.type, model.date)
                                    var toast = globalToast || root.parent.parent.parent.parent.parent
                                    if (toast && toast.show) {
                                        toast.show("Scan details: " + model.type + " - " + model.status, 2500, "info")
                                    }
                                }
                            }
                            
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_md
                                spacing: Theme.spacing_md
                                Text {
                                    text: model.date
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.preferredWidth: 180
                                }
                                Text {
                                    text: model.type
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: model.findings
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignHCenter
                                }
                                Rectangle {
                                    Layout.preferredWidth: 8
                                    Layout.preferredHeight: 8
                                    radius: 4
                                    color: {
                                        switch(model.statusType) {
                                            case "success": return Theme.success
                                            case "warning": return Theme.warning
                                            case "info": return Theme.primary
                                            default: return Theme.muted
                                        }
                                    }
                                }
                                Text {
                                    text: model.status
                                    color: {
                                        switch(model.statusType) {
                                            case "success": return Theme.success
                                            case "warning": return Theme.warning
                                            case "info": return Theme.primary
                                            default: return Theme.muted
                                        }
                                    }
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.minimumWidth: 120
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
