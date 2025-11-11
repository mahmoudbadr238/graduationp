import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import "../ui"
import "../theme"

AppSurface {
    id: root
    
    // Glassmorphic background gradient
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.bg }
            GradientStop { position: 1.0; color: Qt.darker(Theme.bg, 1.1) }
        }
    }
    
    ScrollView {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        clip: true
        
        ColumnLayout {
            width: Math.max(800, parent.width - Theme.spacing_md * 2)
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Theme.spacing_lg

            // General Settings Panel with Glassmorphism
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: generalContent.height + Theme.spacing_xl * 2
                radius: 16
                color: Theme.glass.panel
                border.color: Theme.glass.border
                border.width: 1

                // Neon gradient overlay
                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Theme.glass.gradientStart }
                        GradientStop { position: 1.0; color: Theme.glass.gradientEnd }
                    }
                }

                ColumnLayout {
                    id: generalContent
                    anchors.centerIn: parent
                    width: parent.width - Theme.spacing_xl * 2
                    spacing: Theme.spacing_md
                    
                    SectionHeader {
                        title: "General Settings"
                        subtitle: "Startup and system options"
                    }
                }
            }

            // Scan Preferences Panel with Glassmorphism
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: scanContent.height + Theme.spacing_xl * 2
                radius: 16
                color: Theme.glass.panel
                border.color: Theme.glass.border
                border.width: 1

                ColumnLayout {
                    id: scanContent
                    anchors.centerIn: parent
                    width: parent.width - Theme.spacing_xl * 2
                    spacing: Theme.spacing_md
                    
                    SectionHeader {
                        title: "Scan Preferences"
                        subtitle: "Scheduled and depth options"
                    }
                }
            }

            // Notification Settings Panel with Glassmorphism
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: notifContent.height + Theme.spacing_xl * 2
                radius: 16
                color: Theme.glass.panel
                border.color: Theme.glass.border
                border.width: 1

                ColumnLayout {
                    id: notifContent
                    anchors.centerIn: parent
                    width: parent.width - Theme.spacing_xl * 2
                    spacing: Theme.spacing_md
                    
                    SectionHeader {
                        title: "Notification Settings"
                        subtitle: "Notification and alert options"
                    }
                }
            }

            // Enhanced Appearance section with Theme Selector and Glassmorphism
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: appearanceContent.height + Theme.spacing_xl * 2
                radius: 16
                color: Theme.glass.panel
                border.color: Theme.glass.borderActive
                border.width: 2

                // Enhanced neon gradient for appearance section
                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(0.49, 0.36, 1.0, 0.15) }
                        GradientStop { position: 1.0; color: Theme.glass.gradientEnd }
                    }
                }

                ColumnLayout {
                    id: appearanceContent
                    anchors.centerIn: parent
                    width: parent.width - Theme.spacing_xl * 2
                    spacing: Theme.spacing_lg

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
                            color: Theme.text
                        }

                        ComboBox {
                            id: themeSelector
                            Layout.preferredWidth: 250
                            model: ["Dark", "Light", "System"]

                            Component.onCompleted: {
                                // Set initial index based on current theme
                                if (Theme.themeMode === "dark") currentIndex = 0
                                else if (Theme.themeMode === "light") currentIndex = 1
                                else currentIndex = 2
                            }
                            
                            onActivated: function(index) {
                                var newMode = index === 0 ? "dark" : index === 1 ? "light" : "system"
                                console.log("Theme changed to:", newMode)
                                Theme.themeMode = newMode
                            }
                            
                            delegate: ItemDelegate {
                                width: themeSelector.width
                                text: modelData
                                highlighted: themeSelector.highlightedIndex === index
                                
                                background: Rectangle {
                                    color: highlighted ? Theme.accent : Theme.panel
                                    radius: 4

                                    Behavior on color {
                                        ColorAnimation { duration: 140 }
                                    }
                                }
                                
                                contentItem: Text {
                                    text: parent.text
                                    color: highlighted ? "#ffffff" : Theme.text
                                    font: themeSelector.font
                                    elide: Text.ElideRight
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 12
                                }
                            }
                            
                            background: Rectangle {
                                implicitWidth: 250
                                implicitHeight: 44
                                color: Theme.panel
                                border.color: themeSelector.activeFocus ? Theme.accent : Theme.border
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
                                color: Theme.text
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
                                    target: Theme
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
                                    context.fillStyle = Theme.text
                                    context.fill()
                                }
                            }
                            
                            popup: Popup {
                                y: themeSelector.height + 4
                                width: themeSelector.width
                                implicitHeight: contentItem.implicitHeight
                                padding: 4
                                
                                background: Rectangle {
                                    color: Theme.panel
                                    border.color: Theme.border
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
                            color: Theme.muted
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
