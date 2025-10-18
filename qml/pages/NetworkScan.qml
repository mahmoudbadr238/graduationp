import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import "../ui"

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
                        title: "Network Scan Control"
                        subtitle: "Scan your network for devices and threats"
                    }
                    
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing_lg
                        
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing_md
                            
                            Text {
                                text: "Scan local network for connected devices and potential threats"
                                color: Theme.muted
                                font.pixelSize: Theme.typography.body.size
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            
                            Text {
                                text: "This scan will discover all devices on your network and check for security vulnerabilities."
                                color: Theme.muted
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                        
                        DebouncedButton {
                            text: isProcessing ? "Scanning..." : "Start Network Scan"
                            Layout.preferredWidth: 200
                            Layout.preferredHeight: 50
                            Layout.alignment: Qt.AlignTop
                            debounceMs: 3000
                            
                            Accessible.role: Accessible.Button
                            Accessible.name: "Start Network Scan"
                            
                            onClicked: {
                                console.log("Starting network scan...")
                                var toast = globalToast || root.parent.parent.parent.parent.parent
                                if (toast && toast.show) {
                                    toast.show("Network scan started - this may take a few minutes", 3000, "info")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
