import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
AppSurface {
    id: root
    
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
                        title: "DLP Status Overview"
                        subtitle: "Data Loss Prevention metrics"
                    }
                    
                    GridLayout {
                        Layout.fillWidth: true
                        columns: root.isWideScreen ? 4 : 2
                        rowSpacing: Theme.spacing_lg
                        columnSpacing: Theme.spacing_lg
                        
                        Rectangle {
                            Layout.preferredWidth: root.isWideScreen ? 200 : 160
                            Layout.preferredHeight: 100
                            color: Theme.surface
                            radius: Theme.radii_md
                            border.color: Theme.border
                            border.width: 1
                            
                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: Theme.spacing_sm
                                
                                Text {
                                    text: "Total Blocks"
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "1,247"
                                    color: Theme.success
                                    font.pixelSize: 28
                                    font.weight: Font.Bold
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                        
                        Rectangle {
                            Layout.preferredWidth: root.isWideScreen ? 200 : 160
                            Layout.preferredHeight: 100
                            color: Theme.surface
                            radius: Theme.radii_md
                            border.color: Theme.border
                            border.width: 1
                            
                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: Theme.spacing_sm
                                
                                Text {
                                    text: "Compliance Score"
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "98%"
                                    color: Theme.success
                                    font.pixelSize: 28
                                    font.weight: Font.Bold
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                        
                        Rectangle {
                            Layout.preferredWidth: root.isWideScreen ? 200 : 160
                            Layout.preferredHeight: 100
                            color: Theme.surface
                            radius: Theme.radii_md
                            border.color: Theme.border
                            border.width: 1
                            
                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: Theme.spacing_sm
                                
                                Text {
                                    text: "Policies Active"
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "24"
                                    color: Theme.primary
                                    font.pixelSize: 28
                                    font.weight: Font.Bold
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                        
                        Rectangle {
                            Layout.preferredWidth: root.isWideScreen ? 200 : 160
                            Layout.preferredHeight: 100
                            color: Theme.surface
                            radius: Theme.radii_md
                            border.color: Theme.border
                            border.width: 1
                            
                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: Theme.spacing_sm
                                
                                Text {
                                    text: "Protected Files"
                                    color: Theme.muted
                                    font.pixelSize: Theme.typography.body.size
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    text: "8,432"
                                    color: Theme.primary
                                    font.pixelSize: 28
                                    font.weight: Font.Bold
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
