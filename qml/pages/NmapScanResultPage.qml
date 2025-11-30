import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

/**
 * NmapScanResultPage - Displays real-time Nmap scan output
 * 
 * Shows a console-style view with auto-scrolling output,
 * status indicator, and export functionality.
 */
Item {
    id: root
    anchors.fill: parent
    
    // Properties passed from NetworkScan page
    property string scanType: ""
    property string targetHost: ""
    property string displayTitle: ""
    property string scanId: ""
    
    // Internal state
    property string scanOutput: ""
    property string scanStatus: "running"  // running, completed, failed
    property string reportPath: ""
    property int exitCode: -1
    
    // Connect to backend signals
    Connections {
        target: Backend || null
        enabled: target !== null && root.visible
        
        function onNmapScanOutput(id, text) {
            if (id === root.scanId || root.scanId === "") {
                // First output - capture scanId if we don't have it
                if (root.scanId === "" && id) {
                    root.scanId = id
                }
                root.scanOutput += text
                // Auto-scroll to bottom
                outputArea.cursorPosition = outputArea.text.length
            }
        }
        
        function onNmapScanFinished(id, success, code, path) {
            if (id === root.scanId || root.scanId === "") {
                root.scanStatus = success ? "completed" : "failed"
                root.exitCode = code
                root.reportPath = path || ""
                
                if (success) {
                    root.scanOutput += "\n\n[Scan completed successfully]"
                } else {
                    root.scanOutput += "\n\n[Scan failed with exit code " + code + "]"
                }
            }
        }
    }
    
    // Clear state when becoming visible with new scan
    onVisibleChanged: {
        if (visible && scanOutput === "") {
            scanStatus = "running"
            reportPath = ""
            exitCode = -1
        }
    }
    
    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()
        
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16
            
            // Header with back button
            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                
                // Back button
                Rectangle {
                    width: 40
                    height: 40
                    radius: 8
                    color: backBtn.containsMouse ? ThemeManager.elevated() : ThemeManager.panel()
                    
                    Text {
                        anchors.centerIn: parent
                        text: "←"
                        color: ThemeManager.foreground()
                        font.pixelSize: 18
                        font.bold: true
                    }
                    
                    MouseArea {
                        id: backBtn
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            // Reset state and go back
                            root.scanOutput = ""
                            root.scanId = ""
                            root.scanStatus = "running"
                            window.loadRoute("net-scan")
                        }
                    }
                }
                
                // Title
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    
                    Text {
                        text: root.displayTitle || "Nmap Scan"
                        color: ThemeManager.foreground()
                        font.pixelSize: 20
                        font.bold: true
                    }
                    
                    Text {
                        text: root.targetHost ? "Target: " + root.targetHost : "Scanning local network"
                        color: ThemeManager.muted()
                        font.pixelSize: 12
                    }
                }
                
                // Status badge
                Rectangle {
                    width: statusText.implicitWidth + 24
                    height: 32
                    radius: 16
                    color: {
                        if (root.scanStatus === "running") return ThemeManager.info
                        if (root.scanStatus === "completed") return ThemeManager.success
                        return ThemeManager.danger
                    }
                    
                    Text {
                        id: statusText
                        anchors.centerIn: parent
                        text: {
                            if (root.scanStatus === "running") return "Running..."
                            if (root.scanStatus === "completed") return "Completed"
                            return "Failed"
                        }
                        color: "#FFFFFF"
                        font.pixelSize: 12
                        font.bold: true
                    }
                }
            }
            
            // Console output panel
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: ThemeManager.panel()
                radius: 12
                border.color: ThemeManager.border()
                border.width: 1
                
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12
                    
                    // Console header
                    RowLayout {
                        Layout.fillWidth: true
                        
                        Text {
                            text: "📟 Scan Output"
                            color: ThemeManager.foreground()
                            font.pixelSize: 14
                            font.bold: true
                        }
                        
                        Item { Layout.fillWidth: true }
                        
                        // Running indicator
                        RowLayout {
                            spacing: 8
                            visible: root.scanStatus === "running"
                            
                            Rectangle {
                                width: 8
                                height: 8
                                radius: 4
                                color: ThemeManager.success
                                
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite
                                    running: root.scanStatus === "running"
                                    NumberAnimation { to: 0.3; duration: 500 }
                                    NumberAnimation { to: 1.0; duration: 500 }
                                }
                            }
                            
                            Text {
                                text: "Scanning..."
                                color: ThemeManager.muted()
                                font.pixelSize: 11
                            }
                        }
                    }
                    
                    // Console text area
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        
                        TextArea {
                            id: outputArea
                            text: root.scanOutput || "Waiting for scan output..."
                            readOnly: true
                            wrapMode: TextEdit.Wrap
                            color: root.scanOutput ? ThemeManager.foreground() : ThemeManager.muted()
                            font.family: "Consolas, Monaco, 'Courier New', monospace"
                            font.pixelSize: 12
                            selectByMouse: true
                            
                            background: Rectangle {
                                color: ThemeManager.isDark() ? "#0D0D0D" : "#F5F5F5"
                                radius: 6
                            }
                            
                            // Auto-scroll behavior
                            onTextChanged: {
                                cursorPosition = text.length
                            }
                        }
                    }
                }
            }
            
            // Footer with actions
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                
                // Report path display
                Text {
                    visible: root.reportPath !== ""
                    text: "📄 " + root.reportPath
                    color: ThemeManager.muted()
                    font.pixelSize: 11
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                    Layout.maximumWidth: 400
                }
                
                Item { Layout.fillWidth: true }
                
                // Copy to clipboard button
                Rectangle {
                    width: copyBtn.implicitWidth + 24
                    height: 36
                    radius: 8
                    color: copyBtnArea.containsMouse ? ThemeManager.elevated() : ThemeManager.panel()
                    border.color: ThemeManager.border()
                    border.width: 1
                    
                    Text {
                        id: copyBtn
                        anchors.centerIn: parent
                        text: "📋 Copy Output"
                        color: ThemeManager.foreground()
                        font.pixelSize: 12
                    }
                    
                    MouseArea {
                        id: copyBtnArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            outputArea.selectAll()
                            outputArea.copy()
                            outputArea.deselect()
                            if (Backend) {
                                Backend.toast("success", "Output copied to clipboard")
                            }
                        }
                    }
                }
                
                // Save as TXT button
                Rectangle {
                    width: saveBtn.implicitWidth + 24
                    height: 36
                    radius: 18
                    color: saveBtnArea.containsMouse ? Qt.darker(ThemeManager.accent, 1.1) : ThemeManager.accent
                    
                    Text {
                        id: saveBtn
                        anchors.centerIn: parent
                        text: root.reportPath ? "📁 Open Report" : "💾 Save as .txt"
                        color: "#FFFFFF"
                        font.pixelSize: 12
                        font.bold: true
                    }
                    
                    MouseArea {
                        id: saveBtnArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (Backend) {
                                if (root.reportPath) {
                                    // Open existing report
                                    Backend.openNmapReport(root.reportPath)
                                } else {
                                    // Request export
                                    Backend.exportNmapScanReport(root.scanId)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
