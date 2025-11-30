import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

/**
 * NetworkScan (Nmap Scan) - Main scan selection page
 * 
 * Displays 8 scan options with appropriate host inputs.
 * Each scan type maps to a specific Nmap command executed by the backend.
 */
Item {
    id: root
    anchors.fill: parent
    
    // Check if nmap is available
    property bool nmapAvailable: Backend ? Backend.nmapAvailable : false
    
    // Regex for host validation (IP or hostname only)
    readonly property var hostRegex: /^[a-zA-Z0-9][a-zA-Z0-9.\-:]*$/
    
    // Validate host input
    function isValidHost(host) {
        if (!host || host.trim() === "") return false
        var trimmed = host.trim()
        if (trimmed.length > 256) return false
        // Check for dangerous characters
        if (/[;&|$(){}[\]<>`\\!@#%^*=+'"'\n\r\t]/.test(trimmed)) return false
        return hostRegex.test(trimmed)
    }
    
    // Start a scan
    function startScan(scanType, hostField) {
        // Check nmap availability first
        if (!Backend) {
            console.error("Backend not available")
            return
        }
        
        if (!Backend.nmapAvailable) {
            Backend.toast("error", "Nmap is not installed. Please install Nmap from https://nmap.org and restart Sentinel.")
            return
        }
        
        // Get host if applicable
        var host = hostField ? hostField.text.trim() : ""
        
        // Validate host for scans that require it
        var requiresHost = ["port_scan", "os_detect", "service_version", "firewall_detect", "vuln_scan", "protocol_scan"]
        if (requiresHost.indexOf(scanType) >= 0) {
            if (!host) {
                Backend.toast("error", "Please enter a target IP or hostname")
                return
            }
            if (!isValidHost(host)) {
                Backend.toast("error", "Invalid host format. Use IP address or hostname only.")
                return
            }
        }
        
        // Call backend to start scan
        Backend.runNmapScan(scanType, host)
        
        // Navigate to result page
        window.loadRoute("nmap-result")
    }
    
    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16
            
            // Header
            Text {
                text: "Nmap Scan"
                color: ThemeManager.foreground()
                font.pixelSize: 24
                font.bold: true
            }
            
            // Nmap not installed warning
            Rectangle {
                Layout.fillWidth: true
                height: 50
                radius: 8
                color: ThemeManager.danger
                visible: !root.nmapAvailable
                
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12
                    
                    Text {
                        text: "⚠"
                        color: "#FFFFFF"
                        font.pixelSize: 18
                    }
                    
                    Text {
                        text: "Nmap is not installed. Please download and install Nmap from nmap.org, then restart Sentinel."
                        color: "#FFFFFF"
                        font.pixelSize: 13
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
            }
            
            // Scrollable scan options list
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                
                ColumnLayout {
                    width: parent.width
                    spacing: 12
                    
                    // ========== ROW 1: Discover live hosts ==========
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 16
                            spacing: 16
                            
                            Text {
                                text: "Discover live hosts on my network"
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                Layout.fillWidth: true
                            }
                            
                            // Scan button
                            Rectangle {
                                width: 90
                                height: 36
                                radius: 18
                                color: scanBtn1.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                                border.color: ThemeManager.accent
                                border.width: 1
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Scan"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                
                                MouseArea {
                                    id: scanBtn1
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startScan("host_discovery", null)
                                }
                            }
                        }
                    }
                    
                    // ========== ROW 2: Map network structure ==========
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 16
                            spacing: 16
                            
                            Text {
                                text: "Map the network structure"
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                Layout.fillWidth: true
                            }
                            
                            Rectangle {
                                width: 90
                                height: 36
                                radius: 18
                                color: scanBtn2.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                                border.color: ThemeManager.accent
                                border.width: 1
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Scan"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                
                                MouseArea {
                                    id: scanBtn2
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startScan("network_map", null)
                                }
                            }
                        }
                    }
                    
                    // ========== ROW 3: Scan ports ==========
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 16
                            spacing: 16
                            
                            Text {
                                text: "Scan open/closed/filtered ports"
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                Layout.preferredWidth: 280
                            }
                            
                            // HOST label + input
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                
                                Text {
                                    text: "HOST"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 12
                                    font.bold: true
                                }
                                
                                TextField {
                                    id: hostInput3
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 200
                                    placeholderText: "ex :- 192.168.1.10"
                                    color: ThemeManager.foreground()
                                    placeholderTextColor: ThemeManager.muted()
                                    font.pixelSize: 12
                                    maximumLength: 256
                                    
                                    background: Rectangle {
                                        color: "transparent"
                                        border.color: ThemeManager.border()
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }
                            
                            Rectangle {
                                width: 90
                                height: 36
                                radius: 18
                                color: scanBtn3.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                                border.color: ThemeManager.accent
                                border.width: 1
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Scan"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                
                                MouseArea {
                                    id: scanBtn3
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startScan("port_scan", hostInput3)
                                }
                            }
                        }
                    }
                    
                    // ========== ROW 4: Detect OS ==========
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 16
                            spacing: 16
                            
                            Text {
                                text: "Detect operating systems"
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                Layout.preferredWidth: 280
                            }
                            
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                
                                Text {
                                    text: "HOST"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 12
                                    font.bold: true
                                }
                                
                                TextField {
                                    id: hostInput4
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 200
                                    placeholderText: "ex :- 192.168.1.10"
                                    color: ThemeManager.foreground()
                                    placeholderTextColor: ThemeManager.muted()
                                    font.pixelSize: 12
                                    maximumLength: 256
                                    
                                    background: Rectangle {
                                        color: "transparent"
                                        border.color: ThemeManager.border()
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }
                            
                            Rectangle {
                                width: 90
                                height: 36
                                radius: 18
                                color: scanBtn4.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                                border.color: ThemeManager.accent
                                border.width: 1
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Scan"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                
                                MouseArea {
                                    id: scanBtn4
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startScan("os_detect", hostInput4)
                                }
                            }
                        }
                    }
                    
                    // ========== ROW 5: Service versions ==========
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 16
                            spacing: 16
                            
                            Text {
                                text: "Identify service names and versions"
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                Layout.preferredWidth: 280
                            }
                            
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                
                                Text {
                                    text: "HOST"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 12
                                    font.bold: true
                                }
                                
                                TextField {
                                    id: hostInput5
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 200
                                    placeholderText: "ex :- 192.168.1.10"
                                    color: ThemeManager.foreground()
                                    placeholderTextColor: ThemeManager.muted()
                                    font.pixelSize: 12
                                    maximumLength: 256
                                    
                                    background: Rectangle {
                                        color: "transparent"
                                        border.color: ThemeManager.border()
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }
                            
                            Rectangle {
                                width: 90
                                height: 36
                                radius: 18
                                color: scanBtn5.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                                border.color: ThemeManager.accent
                                border.width: 1
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Scan"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                
                                MouseArea {
                                    id: scanBtn5
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startScan("service_version", hostInput5)
                                }
                            }
                        }
                    }
                    
                    // ========== ROW 6: Firewall detection ==========
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 16
                            spacing: 16
                            
                            Text {
                                text: "Detect firewalls and filtering mechanisms"
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                Layout.preferredWidth: 280
                            }
                            
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                
                                Text {
                                    text: "HOST"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 12
                                    font.bold: true
                                }
                                
                                TextField {
                                    id: hostInput6
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 200
                                    placeholderText: "ex :- 192.168.1.10"
                                    color: ThemeManager.foreground()
                                    placeholderTextColor: ThemeManager.muted()
                                    font.pixelSize: 12
                                    maximumLength: 256
                                    
                                    background: Rectangle {
                                        color: "transparent"
                                        border.color: ThemeManager.border()
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }
                            
                            Rectangle {
                                width: 90
                                height: 36
                                radius: 18
                                color: scanBtn6.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                                border.color: ThemeManager.accent
                                border.width: 1
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Scan"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                
                                MouseArea {
                                    id: scanBtn6
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startScan("firewall_detect", hostInput6)
                                }
                            }
                        }
                    }
                    
                    // ========== ROW 7: Vulnerability scan ==========
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 16
                            spacing: 16
                            
                            Text {
                                text: "Find known vulnerabilities"
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                Layout.preferredWidth: 280
                            }
                            
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                
                                Text {
                                    text: "HOST"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 12
                                    font.bold: true
                                }
                                
                                TextField {
                                    id: hostInput7
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 200
                                    placeholderText: "ex :- 192.168.1.10"
                                    color: ThemeManager.foreground()
                                    placeholderTextColor: ThemeManager.muted()
                                    font.pixelSize: 12
                                    maximumLength: 256
                                    
                                    background: Rectangle {
                                        color: "transparent"
                                        border.color: ThemeManager.border()
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }
                            
                            Rectangle {
                                width: 90
                                height: 36
                                radius: 18
                                color: scanBtn7.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                                border.color: ThemeManager.accent
                                border.width: 1
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Scan"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                
                                MouseArea {
                                    id: scanBtn7
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startScan("vuln_scan", hostInput7)
                                }
                            }
                        }
                    }
                    
                    // ========== ROW 8: Protocol analysis ==========
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 20
                            anchors.rightMargin: 16
                            spacing: 16
                            
                            Text {
                                text: "Analyze specific protocols"
                                color: ThemeManager.foreground()
                                font.pixelSize: 14
                                Layout.preferredWidth: 280
                            }
                            
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                
                                Text {
                                    text: "HOST"
                                    color: ThemeManager.muted()
                                    font.pixelSize: 12
                                    font.bold: true
                                }
                                
                                TextField {
                                    id: hostInput8
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 200
                                    placeholderText: "ex :- 192.168.1.10"
                                    color: ThemeManager.foreground()
                                    placeholderTextColor: ThemeManager.muted()
                                    font.pixelSize: 12
                                    maximumLength: 256
                                    
                                    background: Rectangle {
                                        color: "transparent"
                                        border.color: ThemeManager.border()
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }
                            
                            Rectangle {
                                width: 90
                                height: 36
                                radius: 18
                                color: scanBtn8.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                                border.color: ThemeManager.accent
                                border.width: 1
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "Scan"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                
                                MouseArea {
                                    id: scanBtn8
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.startScan("protocol_scan", hostInput8)
                                }
                            }
                        }
                    }
                    
                    // Bottom spacing
                    Item { height: 20 }
                }
            }
        }
    }
}