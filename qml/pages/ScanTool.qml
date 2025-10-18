import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import "../ui"

AppSurface {
    id: root
    property int scanProgress: 0
    property string scanStatus: "idle"
    property int selectedScanType: -1  // 0=Quick, 1=Full, 2=Deep
    
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
                        title: "Scan Mode Selection"
                        subtitle: "Choose scan type"
                    }
                    
                    GridLayout {
                        Layout.fillWidth: true
                        columns: root.isWideScreen ? 3 : 1
                        rowSpacing: Theme.spacing_lg
                        columnSpacing: Theme.spacing_lg
                        
                        Rectangle {
                            Layout.preferredWidth: root.isWideScreen ? 300 : 400
                            Layout.preferredHeight: 200
                            color: Theme.surface
                            radius: Theme.radii_md
                            border.color: selectedScanType === 0 ? ThemeManager.accent : Theme.border
                            border.width: selectedScanType === 0 ? 2 : 1
                            
                            Behavior on border.color {
                                ColorAnimation { duration: Theme.duration_fast }
                            }
                            Behavior on border.width {
                                NumberAnimation { duration: Theme.duration_fast }
                            }
                            
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    selectedScanType = 0
                                    console.log("Quick Scan selected")
                                }
                                
                                Rectangle {
                                    anchors.fill: parent
                                    color: parent.containsMouse ? Theme.elevatedPanel : "transparent"
                                    radius: Theme.radii_md
                                    Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
                                }
                            }
                            
                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: Theme.spacing_md
                                width: parent.width - 32
                                
                                Text {
                                    text: "🚀"
                                    color: Theme.primary
                                    font.pixelSize: 48
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "Quick Scan"
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.h2.size
                                    font.weight: Font.Medium
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "~5 minutes"
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                        
                        Rectangle {
                            Layout.preferredWidth: root.isWideScreen ? 300 : 400
                            Layout.preferredHeight: 200
                            color: Theme.surface
                            radius: Theme.radii_md
                            border.color: selectedScanType === 1 ? ThemeManager.accent : Theme.border
                            border.width: selectedScanType === 1 ? 2 : 1
                            
                            Behavior on border.color {
                                ColorAnimation { duration: Theme.duration_fast }
                            }
                            Behavior on border.width {
                                NumberAnimation { duration: Theme.duration_fast }
                            }
                            
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    selectedScanType = 1
                                    console.log("Full Scan selected")
                                }
                                
                                Rectangle {
                                    anchors.fill: parent
                                    color: parent.containsMouse ? Theme.elevatedPanel : "transparent"
                                    radius: Theme.radii_md
                                    Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
                                }
                            }
                            
                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: Theme.spacing_md
                                width: parent.width - 32
                                
                                Text {
                                    text: "🔍"
                                    color: Theme.primary
                                    font.pixelSize: 48
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "Full Scan"
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.h2.size
                                    font.weight: Font.Medium
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "~30 minutes"
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                        
                        Rectangle {
                            Layout.preferredWidth: root.isWideScreen ? 300 : 400
                            Layout.preferredHeight: 200
                            color: Theme.surface
                            radius: Theme.radii_md
                            border.color: selectedScanType === 2 ? ThemeManager.accent : Theme.border
                            border.width: selectedScanType === 2 ? 2 : 1
                            
                            Behavior on border.color {
                                ColorAnimation { duration: Theme.duration_fast }
                            }
                            Behavior on border.width {
                                NumberAnimation { duration: Theme.duration_fast }
                            }
                            
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    selectedScanType = 2
                                    console.log("Deep Scan selected")
                                }
                                
                                Rectangle {
                                    anchors.fill: parent
                                    color: parent.containsMouse ? Theme.elevatedPanel : "transparent"
                                    radius: Theme.radii_md
                                    Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
                                }
                            }
                            
                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: Theme.spacing_md
                                width: parent.width - 32
                                
                                Text {
                                    text: "🔬"
                                    color: Theme.primary
                                    font.pixelSize: 48
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "Deep Scan"
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.h2.size
                                    font.weight: Font.Medium
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "~2 hours"
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
