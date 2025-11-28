import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Item {
    id: root
    
    property int fontSizeTrigger: ThemeManager.fontSizeUpdateTrigger

    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()
        
        Flickable {
            anchors.fill: parent
            anchors.margins: 32
            contentWidth: width
            contentHeight: mainColumn.implicitHeight
            clip: true
            
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            ColumnLayout {
                id: mainColumn
                width: parent.width
                spacing: 24

                // Page Title
                Text {
                    text: "Settings"
                    font.pixelSize: ThemeManager.fontSize_h1()
                    font.bold: true
                    color: ThemeManager.foreground()
                    Layout.bottomMargin: 10
                }

                // ===== APPEARANCE SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: appearanceContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: appearanceContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "Appearance"
                            font.pixelSize: ThemeManager.fontSize_h3()
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        // Theme Mode Row
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Theme Mode:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body()
                                Layout.preferredWidth: 200
                            }

                            ComboBox {
                                id: themeModeCombo
                                model: ["Light", "Dark", "System"]
                                Layout.fillWidth: true
                                Layout.maximumWidth: 300
                                
                                property int previousIndex: -1
                                
                                Component.onCompleted: reloadThemeMode()
                                
                                onCurrentIndexChanged: {
                                    if (currentIndex !== previousIndex) {
                                        previousIndex = currentIndex
                                        var modes = ["light", "dark", "system"]
                                        if (SettingsService) {
                                            SettingsService.themeMode = modes[currentIndex]
                                        }
                                    }
                                }
                                
                                function reloadThemeMode() {
                                    var modes = ["light", "dark", "system"]
                                    var savedMode = SettingsService ? SettingsService.themeMode : "dark"
                                    var newIndex = modes.indexOf(savedMode)
                                    previousIndex = newIndex
                                    currentIndex = newIndex
                                }
                                
                                background: Rectangle {
                                    color: ThemeManager.surface()
                                    radius: 6
                                    border.color: ThemeManager.border()
                                    border.width: 1
                                }
                                contentItem: Text {
                                    text: themeModeCombo.currentText
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body()
                                    leftPadding: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                                delegate: ItemDelegate {
                                    width: themeModeCombo.width
                                    contentItem: Text {
                                        text: modelData
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body()
                                    }
                                    background: Rectangle {
                                        color: highlighted ? ThemeManager.elevated() : ThemeManager.surface()
                                    }
                                }
                                popup: Popup {
                                    y: themeModeCombo.height
                                    width: themeModeCombo.width
                                    implicitHeight: contentItem.implicitHeight
                                    padding: 1
                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: themeModeCombo.popup.visible ? themeModeCombo.delegateModel : null
                                    }
                                    background: Rectangle {
                                        color: ThemeManager.surface()
                                        border.color: ThemeManager.border()
                                        radius: 6
                                    }
                                }
                            }
                            
                            Item { Layout.fillWidth: true }
                        }

                        // Font Size Row
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Font Size:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body()
                                Layout.preferredWidth: 200
                            }

                            ComboBox {
                                id: fontSizeCombo
                                model: ["Small", "Medium", "Large"]
                                Layout.fillWidth: true
                                Layout.maximumWidth: 300
                                
                                property int previousIndex: -1
                                
                                Component.onCompleted: reloadFontSize()
                                
                                onCurrentIndexChanged: {
                                    if (currentIndex !== previousIndex) {
                                        previousIndex = currentIndex
                                        var sizes = ["small", "medium", "large"]
                                        if (SettingsService) {
                                            SettingsService.fontSize = sizes[currentIndex]
                                        }
                                        ThemeManager.setFontSize(sizes[currentIndex])
                                    }
                                }
                                
                                function reloadFontSize() {
                                    var sizes = ["small", "medium", "large"]
                                    var savedSize = SettingsService ? SettingsService.fontSize : "medium"
                                    var newIndex = sizes.indexOf(savedSize)
                                    previousIndex = newIndex
                                    currentIndex = newIndex
                                }
                                
                                background: Rectangle {
                                    color: ThemeManager.surface()
                                    radius: 6
                                    border.color: ThemeManager.border()
                                    border.width: 1
                                }
                                contentItem: Text {
                                    text: fontSizeCombo.currentText
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body()
                                    leftPadding: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                                delegate: ItemDelegate {
                                    width: fontSizeCombo.width
                                    contentItem: Text {
                                        text: modelData
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body()
                                    }
                                    background: Rectangle {
                                        color: highlighted ? ThemeManager.elevated() : ThemeManager.surface()
                                    }
                                }
                                popup: Popup {
                                    y: fontSizeCombo.height
                                    width: fontSizeCombo.width
                                    implicitHeight: contentItem.implicitHeight
                                    padding: 1
                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: fontSizeCombo.popup.visible ? fontSizeCombo.delegateModel : null
                                    }
                                    background: Rectangle {
                                        color: ThemeManager.surface()
                                        border.color: ThemeManager.border()
                                        radius: 6
                                    }
                                }
                            }
                            
                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                // ===== MONITORING SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: monitoringContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: monitoringContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "Monitoring"
                            font.pixelSize: ThemeManager.fontSize_h3()
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Live Monitoring:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body()
                                Layout.preferredWidth: 200
                            }

                            Switch {
                                checked: true
                                onCheckedChanged: {
                                    if (Backend) {
                                        if (checked) Backend.startLive()
                                        else Backend.stopLive()
                                    }
                                }
                            }
                            
                            Item { Layout.fillWidth: true }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Update Interval (sec):"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body()
                                Layout.preferredWidth: 200
                            }

                            SpinBox {
                                id: intervalSpinner
                                from: 1
                                to: 60
                                value: 2
                                Layout.preferredWidth: 120
                                Component.onCompleted: {
                                    value = SettingsService ? SettingsService.updateIntervalMs / 1000 : 2
                                }
                                onValueChanged: {
                                    if (SettingsService) SettingsService.updateIntervalMs = value * 1000
                                }
                            }
                            
                            Item { Layout.fillWidth: true }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Monitor GPU:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body()
                                Layout.preferredWidth: 200
                            }

                            Switch {
                                id: gpuSwitch
                                Component.onCompleted: {
                                    checked = SettingsService ? SettingsService.enableGpuMonitoring : true
                                }
                                onCheckedChanged: {
                                    if (SettingsService) SettingsService.enableGpuMonitoring = checked
                                }
                            }
                            
                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                // ===== STARTUP SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: startupContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: startupContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "Startup"
                            font.pixelSize: ThemeManager.fontSize_h3()
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Run on Startup:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body()
                                Layout.preferredWidth: 200
                            }

                            Switch {
                                id: startupSwitch
                                Component.onCompleted: {
                                    checked = SettingsService ? SettingsService.startWithSystem : false
                                }
                                onCheckedChanged: {
                                    if (SettingsService) SettingsService.startWithSystem = checked
                                }
                            }
                            
                            Item { Layout.fillWidth: true }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Minimize to Tray:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body()
                                Layout.preferredWidth: 200
                            }

                            Switch { checked: true }
                            
                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                // ===== PRIVACY SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: privacyContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: privacyContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "Privacy"
                            font.pixelSize: ThemeManager.fontSize_h3()
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Send Error Reports:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body()
                                Layout.preferredWidth: 200
                            }

                            Switch {
                                id: telemetrySwitch
                                Component.onCompleted: {
                                    checked = SettingsService ? SettingsService.sendErrorReports : false
                                }
                                onCheckedChanged: {
                                    if (SettingsService) SettingsService.sendErrorReports = checked
                                }
                            }
                            
                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                // Spacer
                Item { Layout.preferredHeight: 40 }
            }
        }
    }
}
