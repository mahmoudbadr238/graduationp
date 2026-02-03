import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

// Report Preview Dialog - Shows scan report with option to save
Popup {
    id: reportDialog
    
    // Properties
    property string reportTitle: "Scan Report"
    property string reportContent: ""
    property string defaultFileName: "report.txt"
    property bool isFileReport: true  // true = file scan, false = URL scan
    
    // Signals
    signal saveRequested(string filePath)
    signal copyRequested()
    
    // Dialog setup
    width: Math.min(parent.width * 0.85, 800)
    height: Math.min(parent.height * 0.85, 700)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    
    // Animation
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 200 }
        NumberAnimation { property: "scale"; from: 0.9; to: 1.0; duration: 200; easing.type: Easing.OutBack }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 150 }
        NumberAnimation { property: "scale"; from: 1.0; to: 0.95; duration: 150 }
    }
    
    // Save file dialog
    FileDialog {
        id: saveDialog
        title: "Save Report"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Text files (*.txt)", "All files (*)"]
        currentFile: "file:///" + defaultFileName
        onAccepted: {
            var path = selectedFile.toString()
            // Remove file:/// prefix
            if (path.startsWith("file:///")) {
                path = path.substring(8)
            }
            saveRequested(path)
        }
    }
    
    background: Rectangle {
        color: ThemeManager.panel()
        radius: 16
        border.color: ThemeManager.border()
        border.width: 1
        
        // Shadow effect
        layer.enabled: true
        layer.effect: Item {
            Rectangle {
                anchors.fill: parent
                anchors.margins: -8
                color: "#40000000"
                radius: 20
                z: -1
            }
        }
    }
    
    contentItem: ColumnLayout {
        spacing: 0
        
        // Header
        Rectangle {
            Layout.fillWidth: true
            height: 60
            color: "transparent"
            
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 16
                spacing: 16
                
                // Icon and title
                RowLayout {
                    spacing: 12
                    
                    Text {
                        text: isFileReport ? "📄" : "🌐"
                        font.pixelSize: 28
                    }
                    
                    ColumnLayout {
                        spacing: 2
                        
                        Text {
                            text: reportTitle
                            font.pixelSize: 18
                            font.bold: true
                            color: ThemeManager.foreground()
                        }
                        
                        Text {
                            text: "Review the results below"
                            font.pixelSize: 12
                            color: ThemeManager.muted()
                        }
                    }
                }
                
                Item { Layout.fillWidth: true }
                
                // Close button
                Rectangle {
                    width: 32
                    height: 32
                    radius: 16
                    color: closeHover.containsMouse ? ThemeManager.surface() : "transparent"
                    
                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 16
                        color: ThemeManager.muted()
                    }
                    
                    MouseArea {
                        id: closeHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: reportDialog.close()
                    }
                }
            }
        }
        
        // Divider
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: ThemeManager.border()
        }
        
        // Report content area
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 4
            clip: true
            
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded
            
            TextArea {
                id: reportTextArea
                text: reportContent
                readOnly: true
                wrapMode: TextArea.Wrap
                selectByMouse: true
                font.family: "Consolas, Monaco, 'Courier New', monospace"
                font.pixelSize: 13
                color: ThemeManager.foreground()
                padding: 20
                
                background: Rectangle {
                    color: ThemeManager.surface()
                    radius: 8
                }
            }
        }
        
        // Divider
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: ThemeManager.border()
        }
        
        // Footer with buttons
        Rectangle {
            Layout.fillWidth: true
            height: 70
            color: "transparent"
            
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                spacing: 12
                
                // Info text
                Text {
                    text: "💡 You can copy or save this report for your records"
                    font.pixelSize: 12
                    color: ThemeManager.muted()
                    Layout.fillWidth: true
                }
                
                // Copy button
                Button {
                    id: copyBtn
                    text: copyBtn.copied ? "✓ Copied!" : "📋 Copy"
                    property bool copied: false
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 40
                    
                    onClicked: {
                        copyRequested()
                        copied = true
                        copyTimer.restart()
                    }
                    
                    Timer {
                        id: copyTimer
                        interval: 2000
                        onTriggered: copyBtn.copied = false
                    }
                    
                    background: Rectangle {
                        color: copyBtn.copied 
                            ? ThemeManager.success 
                            : (copyBtn.hovered ? ThemeManager.surface() : "transparent")
                        radius: 8
                        border.color: copyBtn.copied ? ThemeManager.success : ThemeManager.border()
                        border.width: 1
                    }
                    
                    contentItem: Text {
                        text: copyBtn.text
                        color: copyBtn.copied ? "#FFFFFF" : ThemeManager.foreground()
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                
                // Save button
                Button {
                    id: saveBtn
                    text: "💾 Save Report"
                    Layout.preferredWidth: 130
                    Layout.preferredHeight: 40
                    
                    onClicked: saveDialog.open()
                    
                    background: Rectangle {
                        color: saveBtn.hovered 
                            ? Qt.lighter(ThemeManager.primary, 1.1) 
                            : ThemeManager.primary
                        radius: 8
                    }
                    
                    contentItem: Text {
                        text: saveBtn.text
                        color: "#FFFFFF"
                        font.pixelSize: 13
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                
                // Close button
                Button {
                    text: "Close"
                    Layout.preferredWidth: 80
                    Layout.preferredHeight: 40
                    
                    onClicked: reportDialog.close()
                    
                    background: Rectangle {
                        color: parent.hovered ? ThemeManager.surface() : "transparent"
                        radius: 8
                        border.color: ThemeManager.border()
                        border.width: 1
                    }
                    
                    contentItem: Text {
                        text: parent.text
                        color: ThemeManager.foreground()
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }
    }
    
    // Helper function to show with content
    function showReport(title, content, fileName, isFile) {
        reportTitle = title || "Scan Report"
        reportContent = content || ""
        defaultFileName = fileName || "report.txt"
        isFileReport = isFile !== false
        open()
    }
}
