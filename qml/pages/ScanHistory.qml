import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtCore
import "../components"
import "../ui"
import "../theme"

AppSurface {
    id: root
    
    property var scanData: []
    
    Item {
        anchors.fill: parent
        
        // Listen for backend scan history
        Connections {
            target: typeof Backend !== 'undefined' ? Backend : null
            
            function onScansLoaded(scans) {
                console.log("Scans loaded:", scans.length)
                root.scanData = scans
            }
        }
        
        Component.onCompleted: {
            if (typeof Backend !== 'undefined') {
                Backend.loadScanHistory()
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
                                if (typeof Backend !== 'undefined') {
                                    var timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
                                    var homePath = StandardPaths.writableLocation(StandardPaths.DownloadLocation)
                                    var csvPath = homePath + "/sentinel_scan_history_" + timestamp + ".csv"
                                    Backend.exportScanHistoryCSV(csvPath)
                                } else {
                                    console.log("Backend not available")
                                }
                            }
                        }
                        
                        Item { Layout.fillWidth: true }

                        Text {
                            text: "Total scans: " + (root.scanData ? root.scanData.length : 0)
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
                        model: root.scanData
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
                                    console.log("Show details for scan:", modelData.type, modelData.started_at)
                                    var toast = globalToast || root.parent.parent.parent.parent.parent
                                    if (toast && toast.show) {
                                        toast.show("Scan details: " + modelData.type + " - " + modelData.status, 2500, "info")
                                    }
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_md
                                spacing: Theme.spacing_md
                                Text {
                                    text: modelData.started_at || "N/A"
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.preferredWidth: 180
                                }
                                Text {
                                    text: modelData.type || "Unknown"
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: {
                                        if (modelData.findings && typeof modelData.findings === 'object') {
                                            return Object.keys(modelData.findings).length.toString()
                                        }
                                        return "0"
                                    }
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
                                        var status = modelData.status || "unknown"
                                        if (status === "completed" || status === "clean") return Theme.success
                                        if (status === "warning" || status === "threats") return Theme.warning
                                        if (status === "running") return Theme.primary
                                        return Theme.muted
                                    }
                                }
                                Text {
                                    text: model.status || ""
                                    color: {
                                        switch(model.statusType) {
                                            case "success": return Theme.success
                                            case "warning": return Theme.warning
                                            case "info": return Theme.primary
                                            default: return Theme.textSecondary
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
        } // ScrollView
    } // Item
}
}

