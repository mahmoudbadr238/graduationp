import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"
import "../../theme"

AppSurface {
    id: root

    property var snapshotData: ({
        "net": {
            "adapters": []
        }
    })

    Column {
        width: Math.min(900, parent.width - Theme.spacing_md * 2)
        spacing: Theme.spacing_lg

        PageHeader {
            title: "Network Adapters"
            subtitle: "All network interfaces and their configuration"
        }

        // Summary card
        AnimatedCard {
            width: parent.width
            implicitHeight: 80

            Row {
                anchors.fill: parent
                anchors.margins: Theme.spacing_md
                spacing: Theme.spacing_xl

                Column {
                    spacing: 4
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        text: root.snapshotData.net && root.snapshotData.net.adapters ? 
                              root.snapshotData.net.adapters.length.toString() : "0"
                        color: Theme.primary
                        font.pixelSize: 32
                        font.bold: true
                    }

                    Text {
                        text: "Total Adapters"
                        color: Theme.textSecondary
                        font.pixelSize: 12
                    }
                }

                Rectangle {
                    width: 1
                    height: 40
                    color: Theme.border
                    anchors.verticalCenter: parent.verticalCenter
                }

                Column {
                    spacing: 4
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        text: {
                            if (!root.snapshotData.net || !root.snapshotData.net.adapters) return "0";
                            var active = 0;
                            for (var i = 0; i < root.snapshotData.net.adapters.length; i++) {
                                if (root.snapshotData.net.adapters[i].is_up) active++;
                            }
                            return active.toString();
                        }
                        color: Theme.success
                        font.pixelSize: 32
                        font.bold: true
                    }

                    Text {
                        text: "Active"
                        color: Theme.textSecondary
                        font.pixelSize: 12
                    }
                }

                Rectangle {
                    width: 1
                    height: 40
                    color: Theme.border
                    anchors.verticalCenter: parent.verticalCenter
                }

                Column {
                    spacing: 4
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        text: {
                            if (!root.snapshotData.net || !root.snapshotData.net.adapters) return "0";
                            var inactive = 0;
                            for (var i = 0; i < root.snapshotData.net.adapters.length; i++) {
                                if (!root.snapshotData.net.adapters[i].is_up) inactive++;
                            }
                            return inactive.toString();
                        }
                        color: Theme.error
                        font.pixelSize: 32
                        font.bold: true
                    }

                    Text {
                        text: "Inactive"
                        color: Theme.textSecondary
                        font.pixelSize: 12
                    }
                }
            }
        }

        // Adapters list
        Column {
            width: parent.width
            spacing: Theme.spacing_md

            Repeater {
                model: root.snapshotData.net && root.snapshotData.net.adapters ? 
                       root.snapshotData.net.adapters : []

                AnimatedCard {
                    width: parent.width
                    implicitHeight: adapterContent.height + 40

                    Column {
                        id: adapterContent
                        width: parent.width - 40
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: 20
                        spacing: Theme.spacing_md

                        // Adapter header
                        Row {
                            width: parent.width
                            spacing: Theme.spacing_md

                            Rectangle {
                                width: 10
                                height: 10
                                radius: 5
                                color: modelData.is_up ? Theme.success : Theme.error
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: modelData.name
                                color: Theme.text
                                font.pixelSize: 16
                                font.bold: true
                                anchors.verticalCenter: parent.verticalCenter
                                Layout.fillWidth: true
                            }

                            Rectangle {
                                height: 24
                                width: statusText.width + 16
                                radius: 12
                                color: modelData.is_up ? Theme.success + "20" : Theme.error + "20"
                                border.color: modelData.is_up ? Theme.success : Theme.error
                                border.width: 1
                                anchors.verticalCenter: parent.verticalCenter

                                Text {
                                    id: statusText
                                    anchors.centerIn: parent
                                    text: modelData.is_up ? "Active" : "Inactive"
                                    color: modelData.is_up ? Theme.success : Theme.error
                                    font.pixelSize: 11
                                    font.bold: true
                                }
                            }
                        }

                        // Separator
                        Rectangle {
                            width: parent.width
                            height: 1
                            color: Theme.border
                        }

                        // Adapter details
                        Column {
                            width: parent.width
                            spacing: Theme.spacing_sm

                            // Speed
                            Row {
                                width: parent.width
                                spacing: Theme.spacing_md

                                Text {
                                    text: "Speed:"
                                    color: Theme.textSecondary
                                    font.pixelSize: 13
                                    width: 120
                                }

                                Text {
                                    text: modelData.speed > 0 ? modelData.speed + " Mbps" : "Unknown"
                                    color: Theme.text
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                }
                            }

                            // IP Addresses
                            Column {
                                width: parent.width
                                spacing: 8

                                Text {
                                    text: "IP Addresses:"
                                    color: Theme.textSecondary
                                    font.pixelSize: 13
                                }

                                Repeater {
                                    model: modelData.addresses || []

                                    Row {
                                        width: parent.width
                                        spacing: Theme.spacing_md
                                        leftPadding: Theme.spacing_md

                                        Rectangle {
                                            width: 50
                                            height: 20
                                            radius: 4
                                            color: Theme.primary + "20"
                                            border.color: Theme.primary
                                            border.width: 1
                                            anchors.verticalCenter: parent.verticalCenter

                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.type
                                                color: Theme.primary
                                                font.pixelSize: 10
                                                font.bold: true
                                            }
                                        }

                                        Text {
                                            text: modelData.address
                                            color: Theme.text
                                            font.pixelSize: 13
                                            font.family: "Consolas"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: "/ " + (modelData.netmask || "")
                                            color: Theme.textSecondary
                                            font.pixelSize: 12
                                            font.family: "Consolas"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }

                                // Show message if no addresses
                                Text {
                                    visible: !modelData.addresses || modelData.addresses.length === 0
                                    text: "No IP addresses configured"
                                    color: Theme.textSecondary
                                    font.pixelSize: 12
                                    font.italic: true
                                    leftPadding: Theme.spacing_md
                                }
                            }
                        }
                    }
                }
            }

            // Empty state
            AnimatedCard {
                visible: !root.snapshotData.net || !root.snapshotData.net.adapters || 
                         root.snapshotData.net.adapters.length === 0
                width: parent.width
                implicitHeight: 120

                Column {
                    anchors.centerIn: parent
                    spacing: Theme.spacing_sm

                    Text {
                        text: "📡"
                        font.pixelSize: 48
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: "No network adapters found"
                        color: Theme.textSecondary
                        font.pixelSize: 14
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }
        }
    }
}
