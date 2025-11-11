import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import "../theme"

AppSurface {
    id: root
    
    property bool isScanning: false
    property string scanResults: ""
    
    // Connect to backend
    Connections {
        target: typeof Backend !== 'undefined' ? Backend : null
        
        function onScanFinished(type, result) {
            if (type === "network") {
                isScanning = false
                
                if (result.error) {
                    scanResults = "Error: " + result.error
                } else {
                    scanResults = "Network Scan Results\n"
                    scanResults += "Target: " + result.target + "\n"
                    scanResults += "Status: " + result.status + "\n"
                    scanResults += "Hosts found: " + (result.hosts ? result.hosts.length : 0) + "\n\n"
                    
                    if (result.hosts && result.hosts.length > 0) {
                        for (var i = 0; i < result.hosts.length; i++) {
                            var host = result.hosts[i]
                            scanResults += "Host " + (i + 1) + ":\n"
                            scanResults += "  Address: " + host.address + "\n"
                            scanResults += "  Status: " + host.status + "\n"
                            if (host.ports_found) {
                                scanResults += "  Ports: " + host.ports_found + "\n"
                            }
                            scanResults += "\n"
                        }
                    }
                }
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
                        title: "Network Scanner"
                        subtitle: "Scan your network for devices using Nmap"
                    }
                    
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing_md
                        
                        TextField {
                            id: targetField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            placeholderText: "Enter target (e.g., 192.168.1.0/24 or 192.168.1.1)"
                            text: "192.168.1.0/24"
                            enabled: !isScanning && typeof Backend !== 'undefined'
                            
                            color: Theme.text
                            placeholderTextColor: Theme.muted
                            
                            background: Rectangle {
                                color: Theme.surface
                                border.color: targetField.activeFocus ? Theme.primary : Theme.border
                                border.width: 1
                                radius: Theme.radii_sm
                                
                                Behavior on color {
                                    ColorAnimation { duration: 300 }
                                }
                                Behavior on border.color {
                                    ColorAnimation { duration: 300 }
                                }
                            }
                        }
                        
                        CheckBox {
                            id: fastCheckbox
                            text: "Fast Scan"
                            checked: true
                            enabled: !isScanning
                            
                            contentItem: Text {
                                text: parent.text
                                color: Theme.text
                                font.pixelSize: Theme.typography.body.size
                                leftPadding: parent.indicator.width + parent.spacing
                                verticalAlignment: Text.AlignVCenter
                                
                                Behavior on color {
                                    ColorAnimation { duration: 300 }
                                }
                            }
                        }
                        
                        Button {
                            text: isScanning ? "Scanning..." : "Start Scan"
                            Layout.preferredWidth: 140
                            Layout.preferredHeight: 44
                            enabled: !isScanning && typeof Backend !== 'undefined' && targetField.text.length > 0
                            
                            onClicked: {
                                if (typeof Backend !== 'undefined') {
                                    isScanning = true
                                    scanResults = "Scanning " + targetField.text + "...\nThis may take a few minutes."
                                    Backend.runNetworkScan(targetField.text, fastCheckbox.checked)
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
                            
                            BusyIndicator {
                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                width: 24
                                height: 24
                                running: isScanning
                                visible: isScanning
                            }
                        }
                    }
                    
                    Text {
                        text: typeof Backend === 'undefined' ? 
                              "Backend not available" : 
                              "Requires Nmap to be installed. Fast scan checks top 100 ports (~30s), Full scan includes service detection (~5 min)"
                        color: Theme.muted
                        font.pixelSize: Theme.typography.mono.size
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        
                        Behavior on color {
                            ColorAnimation { duration: 300 }
                        }
                    }
                }
            }
            
            Panel {
                Layout.fillWidth: true
                visible: scanResults.length > 0
                
                ColumnLayout {
                    spacing: Theme.spacing_lg
                    SectionHeader {
                        title: "Scan Results"
                        subtitle: isScanning ? "Scanning in progress..." : "Completed scan output"
                    }
                    
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 400
                        clip: true
                        
                        Rectangle {
                            width: parent.width
                            height: Math.max(400, resultsText.contentHeight + 32)
                            color: Theme.surface
                            radius: Theme.radii_md
                            border.color: Theme.border
                            border.width: 1
                            
                            Behavior on color {
                                ColorAnimation { duration: 300 }
                            }
                            
                            Text {
                                id: resultsText
                                anchors.fill: parent
                                anchors.margins: 16
                                text: scanResults
                                color: Theme.text
                                font.family: "Consolas"
                                font.pixelSize: Theme.typography.body.size
                                wrapMode: Text.WordWrap
                                
                                Behavior on color {
                                    ColorAnimation { duration: 300 }
                                }
                            }
                        }
                    }
                    
                    Button {
                        text: "Clear Results"
                        Layout.preferredWidth: 140
                        Layout.preferredHeight: 36
                        enabled: !isScanning
                        
                        onClicked: scanResults = ""
                        
                        contentItem: Text {
                            text: parent.text
                            color: Theme.muted
                            font.pixelSize: Theme.typography.mono.size
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            color: parent.pressed ? Theme.elevatedPanel : parent.hovered ? Theme.panel : "transparent"
                            radius: Theme.radii_sm
                            border.color: Theme.border
                            border.width: 1
                            opacity: parent.enabled ? 1.0 : 0.5
                            Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
                        }
                    }
                }
            }
        }
    }
}

