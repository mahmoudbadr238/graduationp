import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs
import "../components"
import "../theme"

AppSurface {
    id: root
    
    // Scanning state properties
    property bool fileScanning: false
    property bool urlScanning: false
    
    Item {
        anchors.fill: parent
        
        // Listen for backend scan results
        Connections {
            target: typeof Backend !== 'undefined' ? Backend : null
            
            function onScanFinished(scanType, result) {
                console.log("Scan finished:", scanType)
                
                if (scanType === "file") {
                    fileResultArea.text = JSON.stringify(result, null, 2)
                    root.fileScanning = false
                } else if (scanType === "url") {
                    urlResultArea.text = JSON.stringify(result, null, 2)
                    root.urlScanning = false
                }
            }
            
            function onToast(level, message) {
                console.log("[" + level + "] " + message)
            }
        }
        
        Flickable {
            id: flickable
            anchors.fill: parent
            anchors.margins: Theme.spacing_lg
            clip: true
            contentHeight: contentLayout.implicitHeight + Theme.spacing_lg * 2
            contentWidth: width
            boundsBehavior: Flickable.StopAtBounds
            
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
            }
            
            // Enable mouse wheel and touchpad scrolling with WheelHandler
            WheelHandler {
                target: flickable
                orientation: Qt.Vertical
                
                onWheel: function(event) {
                    // Smooth scrolling with pixel delta
                    var delta = event.angleDelta.y
                    if (delta !== 0) {
                        flickable.flick(0, delta * 5)
                    }
                }
            }
            
            ColumnLayout {
                id: contentLayout
                width: parent.width
                spacing: Theme.spacing_lg
                
                PageHeader {
                    title: "Security Scan Tool"
                    subtitle: "Scan files and URLs for threats using VirusTotal"
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.spacing_md
                }
                
                // File Scanner Section
                SectionHeader {
                    title: "File Scanner"
                    subtitle: "Scan local files for malware and threats"
                    Layout.fillWidth: true
                }
                
                Panel {
                    Layout.fillWidth: true
                    
                    ColumnLayout {
                        width: parent.width - Theme.spacing_md * 2
                        spacing: Theme.spacing_md
                        
                        RowLayout {
                            spacing: Theme.spacing_md
                            Layout.fillWidth: true
                            
                            TextField {
                                id: filePathField
                                placeholderText: "Enter file path or click Browse..."
                                Layout.fillWidth: true
                                font.pixelSize: Theme.typography.body.size
                                
                                background: Rectangle {
                                    color: Theme.surface
                                    border.color: parent.activeFocus ? Theme.primary : Theme.border
                                    border.width: parent.activeFocus ? 2 : 1
                                    radius: Theme.radii_sm
                                }
                                
                                color: Theme.text
                                padding: Theme.spacing_sm
                            }
                            
                            Button {
                                text: "Browse..."
                                Layout.preferredWidth: 120
                                onClicked: fileDialog.open()
                                padding: Theme.spacing_sm
                                
                                background: Rectangle {
                                    color: parent.hovered ? Theme.elevatedPanel : Theme.panel
                                    border.color: Theme.border
                                    border.width: 1
                                    radius: Theme.radii_sm
                                }
                                
                                contentItem: Text {
                                    text: parent.text
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.body.size
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                        
                        Button {
                            text: root.fileScanning ? "Scanning..." : "Scan File"
                            enabled: !root.fileScanning && filePathField.text.length > 0
                            Layout.preferredWidth: 150
                            
                            onClicked: {
                                if (typeof Backend !== 'undefined') {
                                    root.fileScanning = true
                                    fileResultArea.text = "Scanning file...\n\nCalculating hash and checking VirusTotal database..."
                                    Backend.scanFile(filePathField.text)
                                }
                            }
                            
                            background: Rectangle {
                                color: parent.enabled ? (parent.pressed ? Qt.darker(Theme.primary, 1.2) : 
                                       (parent.hovered ? Qt.lighter(Theme.primary, 1.1) : Theme.primary)) : Theme.muted
                                radius: Theme.radii_sm
                                
                                Behavior on color {
                                    ColorAnimation { duration: Theme.duration_fast }
                                }
                            }
                            
                            contentItem: Row {
                                spacing: Theme.spacing_sm
                                Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
                                
                                BusyIndicator {
                                    width: 16
                                    height: 16
                                    running: root.fileScanning
                                    visible: running
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                
                                Text {
                                    text: parent.parent.text
                                    color: parent.parent.enabled ? "#FFFFFF" : Theme.text
                                    font.pixelSize: Theme.typography.body.size
                                    font.weight: Font.Medium
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                        
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 300
                            color: Theme.surface
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radii_sm
                            
                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_sm
                                clip: true
                                
                                TextArea {
                                    id: fileResultArea
                                    readOnly: true
                                    wrapMode: TextArea.Wrap
                                    text: "Scan results will appear here..."
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.mono.size
                                    font.family: "Consolas, Monaco, monospace"
                                    selectByMouse: true
                                    
                                    background: Rectangle {
                                        color: "transparent"
                                    }
                                }
                            }
                        }
                    }
                }
                
                // URL Scanner Section  
                SectionHeader {
                    title: "URL Scanner"
                    subtitle: "Check URLs for phishing and malware"
                    Layout.fillWidth: true
                }
                
                Panel {
                    Layout.fillWidth: true
                    
                    ColumnLayout {
                        width: parent.width - Theme.spacing_md * 2
                        spacing: Theme.spacing_md
                        
                        TextField {
                            id: urlField
                            placeholderText: "Enter URL (e.g., https://example.com)"
                            Layout.fillWidth: true
                            font.pixelSize: Theme.typography.body.size
                            
                            background: Rectangle {
                                color: Theme.surface
                                border.color: parent.activeFocus ? Theme.primary : Theme.border
                                border.width: parent.activeFocus ? 2 : 1
                                radius: Theme.radii_sm
                            }
                            
                            color: Theme.text
                            padding: Theme.spacing_sm
                        }
                        
                        Button {
                            text: root.urlScanning ? "Scanning..." : "Scan URL"
                            enabled: !root.urlScanning && urlField.text.length > 0
                            Layout.preferredWidth: 150
                            
                            onClicked: {
                                if (typeof Backend !== 'undefined') {
                                    root.urlScanning = true
                                    urlResultArea.text = "Scanning URL...\n\nChecking VirusTotal database..."
                                    Backend.scanUrl(urlField.text)
                                }
                            }
                            
                            background: Rectangle {
                                color: parent.enabled ? (parent.pressed ? Qt.darker(Theme.primary, 1.2) : 
                                       (parent.hovered ? Qt.lighter(Theme.primary, 1.1) : Theme.primary)) : Theme.muted
                                radius: Theme.radii_sm
                                
                                Behavior on color {
                                    ColorAnimation { duration: Theme.duration_fast }
                                }
                            }
                            
                            contentItem: Row {
                                spacing: Theme.spacing_sm
                                Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
                                
                                BusyIndicator {
                                    width: 16
                                    height: 16
                                    running: root.urlScanning
                                    visible: running
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                
                                Text {
                                    text: parent.parent.text
                                    color: parent.parent.enabled ? "#FFFFFF" : Theme.text
                                    font.pixelSize: Theme.typography.body.size
                                    font.weight: Font.Medium
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                        
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 300
                            color: Theme.surface
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radii_sm
                            
                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing_sm
                                clip: true
                                
                                TextArea {
                                    id: urlResultArea
                                    readOnly: true
                                    wrapMode: TextArea.Wrap
                                    text: "Scan results will appear here..."
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.mono.size
                                    font.family: "Consolas, Monaco, monospace"
                                    selectByMouse: true
                                    
                                    background: Rectangle {
                                        color: "transparent"
                                    }
                                }
                            }
                        }
                    }
                }
                
                // Info Panel
                Card {
                    Layout.fillWidth: true
                    hoverable: false
                    padding: Theme.spacing_md
                    
                    RowLayout {
                        width: parent.width - Theme.spacing_md * 2
                        spacing: Theme.spacing_md
                        
                        AlertTriangle {
                            width: 24
                            height: 24
                        }
                        
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            
                            Text {
                                text: "VirusTotal Integration Required"
                                color: Theme.text
                                font.pixelSize: Theme.typography.body.size
                                font.weight: Font.Medium
                            }
                            
                            Text {
                                text: "This feature requires a VirusTotal API key. Create a .env file in the project root with VT_API_KEY=your_key_here"
                                color: Theme.muted
                                font.pixelSize: Theme.typography.mono.size
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }
        
        // File Dialog
        FileDialog {
            id: fileDialog
            title: "Select file to scan"
            nameFilters: ["All files (*)"]
            onAccepted: {
                // Convert file URL to local path
                var path = fileDialog.selectedFile.toString()
                // Remove file:/// prefix on Windows
                if (Qt.platform.os === "windows") {
                    path = path.replace(/^(file:\/{3})/, "")
                } else {
                    path = path.replace(/^(file:\/{2})/, "")
                }
                filePathField.text = decodeURIComponent(path)
            }
        }
    }
}