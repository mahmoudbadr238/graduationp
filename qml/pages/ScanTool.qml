import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../ui"

Item {
    id: root
    anchors.fill: parent
    
    property string fileScanResult: ""
    property string urlScanResult: ""
    property bool fileScanningInProgress: false
    property bool urlScanningInProgress: false
    
    FileDialog {
        id: fileDialog
        title: "Select file to scan"
        nameFilters: ["All files (*)"]
        onAccepted: filePathInput.text = selectedFile.toString().replace("file:///", "")
    }
    
    Connections {
        target: Backend || null
        enabled: target !== null
        function onScanFinished(result) {
            if (result && result.type === "file") {
                fileScanResult = "Status: " + (result.detected ? "SUSPICIOUS" : "CLEAN") + "\nThreats: " + (result.threats || 0)
                fileScanningInProgress = false
                fileScanButton.enabled = true
                fileScanButton.text = "Scan File"
            } else if (result && result.type === "url") {
                urlScanResult = "Status: " + (result.detected ? "DANGEROUS" : "SAFE") + "\nThreats: " + (result.threats || 0)
                urlScanningInProgress = false
                urlScanButton.enabled = true
                urlScanButton.text = "Scan URL"
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        Text {
            text: "Scan Tool"
            font.pixelSize: 28
            font.bold: true
            color: ThemeManager.foreground()
        }

        Rectangle {
            Layout.fillWidth: true
            height: 280
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 12

                Text {
                    text: "File Scanner"
                    font.pixelSize: 14
                    font.bold: true
                    color: ThemeManager.foreground()
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    TextField {
                        id: filePathInput
                        Layout.fillWidth: true
                        placeholderText: "Enter file path..."
                        maximumLength: 2048
                        color: ThemeManager.foreground()
                        placeholderTextColor: ThemeManager.muted()
                        background: Rectangle {
                            color: ThemeManager.surface()
                            radius: 6
                            border.color: ThemeManager.border()
                            border.width: 1
                        }
                    }

                    Button {
                        text: "Browse"
                        Layout.preferredWidth: 100
                        
                        onClicked: fileDialog.open()
                        
                        background: Rectangle {
                            color: ThemeManager.accent
                            radius: 6
                        }

                        contentItem: Text {
                            text: parent.text
                            color: ThemeManager.foreground()
                            font.pixelSize: 11
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }

                Button {
                    id: fileScanButton
                    text: fileScanningInProgress ? "Scanning..." : "Scan File"
                    Layout.preferredWidth: 120
                    enabled: !fileScanningInProgress && filePathInput.text.length > 0
                    
                    onClicked: {
                        if (Backend && filePathInput.text.length > 0) {
                            fileScanningInProgress = true
                            fileScanResult = ""
                            fileScanButton.enabled = false
                            Backend.scanFile(filePathInput.text)
                        }
                    }
                    
                    background: Rectangle {
                        color: parent.enabled ? ThemeManager.accent : ThemeManager.muted()
                        radius: 6
                    }

                    contentItem: Text {
                        text: parent.text
                        color: ThemeManager.foreground()
                        font.pixelSize: 12
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
                
                // Result display
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: ThemeManager.surface()
                    radius: 6
                    visible: fileScanResult.length > 0 || fileScanningInProgress
                    
                    Text {
                        anchors.centerIn: parent
                        text: fileScanningInProgress ? "Scanning file..." : fileScanResult
                        color: fileScanResult.indexOf("CLEAN") > -1 ? ThemeManager.success : ThemeManager.danger
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 280
            color: ThemeManager.panel()
            radius: 12
            border.color: ThemeManager.border()
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 12

                Text {
                    text: "URL Scanner"
                    font.pixelSize: 14
                    font.bold: true
                    color: ThemeManager.foreground()
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    TextField {
                        id: urlInput
                        Layout.fillWidth: true
                        placeholderText: "https://example.com"
                        maximumLength: 2048
                        color: ThemeManager.foreground()
                        placeholderTextColor: ThemeManager.muted()
                        background: Rectangle {
                            color: ThemeManager.surface()
                            radius: 6
                            border.color: ThemeManager.border()
                            border.width: 1
                        }
                    }

                    Button {
                        id: urlScanButton
                        text: urlScanningInProgress ? "Scanning..." : "Scan"
                        Layout.preferredWidth: 100
                        enabled: !urlScanningInProgress && urlInput.text.length > 0
                        
                        onClicked: {
                            if (Backend && urlInput.text.length > 0) {
                                urlScanningInProgress = true
                                urlScanResult = ""
                                urlScanButton.enabled = false
                                Backend.scanUrl(urlInput.text)
                            }
                        }
                        
                        background: Rectangle {
                            color: parent.enabled ? ThemeManager.accent : ThemeManager.muted()
                            radius: 6
                        }

                        contentItem: Text {
                            text: parent.text
                            color: ThemeManager.foreground()
                            font.pixelSize: 11
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }
                
                // Result display
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: ThemeManager.surface()
                    radius: 6
                    visible: urlScanResult.length > 0 || urlScanningInProgress
                    
                    Text {
                        anchors.centerIn: parent
                        text: urlScanningInProgress ? "Scanning URL..." : urlScanResult
                        color: urlScanResult.indexOf("SAFE") > -1 ? ThemeManager.success : ThemeManager.danger
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}