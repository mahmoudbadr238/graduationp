import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import "../ui"

AppSurface {
    id: root
    ScrollView {
        anchors.fill: parent
        clip: true
        ColumnLayout {
            width: Math.max(800, parent.width - Theme.spacing_md * 2)
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Theme.spacing_lg

            Panel {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: Theme.spacing_md
                    SectionHeader {
                        title: "General Settings"
                        subtitle: "Startup and system options"
                    }
                }
            }
            Panel {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: Theme.spacing_md
                    SectionHeader {
                        title: "Scan Preferences"
                        subtitle: "Scheduled and depth options"
                    }
                }
            }
            Panel {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: Theme.spacing_md
                    SectionHeader {
                        title: "Notification Settings"
                        subtitle: "Notification and alert options"
                    }
                }
            }
            
            // Enhanced Appearance section with Theme Selector
            Panel {
                Layout.fillWidth: true
                
                ColumnLayout {
                    spacing: Theme.spacing_lg
                    width: parent.width
                    
                    SectionHeader {
                        title: "Appearance"
                        subtitle: "Theme and UI customization"
                    }
                    
                    ColumnLayout {
                        spacing: Theme.spacing_md
                        Layout.fillWidth: true
                        
                        Text {
                            text: "Theme Mode"
                            font.pixelSize: 16
                            font.weight: Font.Medium
                            color: ThemeManager.foreground()
                        }
                        
                        ComboBox {
                            id: themeSelector
                            Layout.preferredWidth: 250
                            model: ["Dark", "Light", "System"]
                            
                            Component.onCompleted: {
                                // Set initial index based on current theme
                                if (ThemeManager.themeMode === "dark") currentIndex = 0
                                else if (ThemeManager.themeMode === "light") currentIndex = 1
                                else currentIndex = 2
                            }
                            
                            onActivated: function(index) {
                                var newMode = index === 0 ? "dark" : index === 1 ? "light" : "system"
                                console.log("Theme changed to:", newMode)
                                ThemeManager.themeMode = newMode
                            }
                            
                            delegate: ItemDelegate {
                                width: themeSelector.width
                                text: modelData
                                highlighted: themeSelector.highlightedIndex === index
                                
                                background: Rectangle {
                                    color: highlighted ? ThemeManager.accent : ThemeManager.panel()
                                    radius: 4
                                    
                                    Behavior on color {
                                        ColorAnimation { duration: 140 }
                                    }
                                }
                                
                                contentItem: Text {
                                    text: parent.text
                                    color: highlighted ? "#ffffff" : ThemeManager.foreground()
                                    font: themeSelector.font
                                    elide: Text.ElideRight
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 12
                                }
                            }
                            
                            background: Rectangle {
                                implicitWidth: 250
                                implicitHeight: 44
                                color: ThemeManager.panel()
                                border.color: themeSelector.activeFocus ? ThemeManager.accent : ThemeManager.border()
                                border.width: themeSelector.activeFocus ? 2 : 1
                                radius: 8
                                
                                Behavior on border.color {
                                    ColorAnimation { duration: 140 }
                                }
                                
                                Behavior on color {
                                    ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                                }
                            }
                            
                            contentItem: Text {
                                leftPadding: 16
                                rightPadding: themeSelector.indicator.width + 16
                                text: themeSelector.displayText
                                font.pixelSize: 15
                                font.weight: Font.Medium
                                color: ThemeManager.foreground()
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }
                            
                            indicator: Canvas {
                                id: canvas
                                x: themeSelector.width - width - 12
                                y: themeSelector.topPadding + (themeSelector.availableHeight - height) / 2
                                width: 12
                                height: 8
                                contextType: "2d"
                                
                                Connections {
                                    target: ThemeManager
                                    function onThemeModeChanged() {
                                        canvas.requestPaint()
                                    }
                                }
                                
                                onPaint: {
                                    context.reset()
                                    context.moveTo(0, 0)
                                    context.lineTo(width, 0)
                                    context.lineTo(width / 2, height)
                                    context.closePath()
                                    context.fillStyle = ThemeManager.foreground()
                                    context.fill()
                                }
                            }
                            
                            popup: Popup {
                                y: themeSelector.height + 4
                                width: themeSelector.width
                                implicitHeight: contentItem.implicitHeight
                                padding: 4
                                
                                background: Rectangle {
                                    color: ThemeManager.panel()
                                    border.color: ThemeManager.border()
                                    border.width: 1
                                    radius: 8
                                }
                                
                                contentItem: ListView {
                                    clip: true
                                    implicitHeight: contentHeight
                                    model: themeSelector.popup.visible ? themeSelector.delegateModel : null
                                    currentIndex: themeSelector.highlightedIndex
                                    
                                    ScrollIndicator.vertical: ScrollIndicator { }
                                }
                            }
                        }
                        
                        Text {
                            text: "Choose how Sentinel looks. 'System' follows your OS theme preference."
                            font.pixelSize: 14
                            color: ThemeManager.muted()
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            Layout.preferredWidth: 500
                        }
                    }
                }
            }
            
            Panel {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: Theme.spacing_md
                    SectionHeader {
                        title: "Updates & Maintenance"
                        subtitle: "App and database updates, logs"
                    }
                }
            }
        }
    }
}
