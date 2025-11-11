import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"
import "../../theme"

AppSurface {
    id: root

    // This property will be set by SystemSnapshot.qml Loader
    property var snapshotData: ({
        "net": {
            "send_rate_mbps": 0,
            "recv_rate_mbps": 0,
            "send_rate": {"value": 0, "unit": "bps", "formatted": "0.00 bps"},
            "recv_rate": {"value": 0, "unit": "bps", "formatted": "0.00 bps"},
            "adapters": []
        }
    })

    ScrollView {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        Column {
            spacing: 18
            width: Math.max(800, parent.width - 48)
            topPadding: 0
            bottomPadding: 120

            Component.onCompleted: {
                // Ensure layout is properly initialized
            }

        PageHeader {
            title: "Network Usage"
            subtitle: "Live throughput & adapter details"
        }
    
    Row {
        spacing: 18
        width: parent.width
        
        AnimatedCard {
            width: (parent.width - 18) / 2
            implicitHeight: 340
            
            Column {
                spacing: 10
                width: parent.width
                
                Text {
                    text: {
                        var unit = "Mbps"; // Default
                        if (root.snapshotData && root.snapshotData.net && root.snapshotData.net.send_rate) {
                            unit = root.snapshotData.net.send_rate.unit || "Mbps";
                        }
                        return "Upload (" + unit + ")";
                    }
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }                LineChartLive {
                    id: upChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#6ee7a8"
                }
                
                LiveMetricTile {
                    label: "Up"
                    valueText: {
                        if (root.snapshotData && root.snapshotData.net) {
                            // Use new auto-scaling format if available
                            if (root.snapshotData.net.send_rate && root.snapshotData.net.send_rate.formatted) {
                                return root.snapshotData.net.send_rate.formatted;
                            }
                            // Fallback to old Mbps format
                            var rate = root.snapshotData.net.send_rate_mbps || 0;
                            return rate.toFixed(2) + " Mbps";
                        }
                        return "0.00 bps";
                    }
                    positive: true
                    width: parent.width - 40
                }
            }
        }
        
        AnimatedCard {
            width: (parent.width - 18) / 2
            implicitHeight: 340
            
            Column {
                spacing: 10
                width: parent.width
                
                Text {
                    text: {
                        var unit = "Mbps"; // Default
                        if (root.snapshotData && root.snapshotData.net && root.snapshotData.net.recv_rate) {
                            unit = root.snapshotData.net.recv_rate.unit || "Mbps";
                        }
                        return "Download (" + unit + ")";
                    }
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }                LineChartLive {
                    id: downChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#a66bff"
                }
                
                LiveMetricTile {
                    label: "Down"
                    valueText: {
                        if (root.snapshotData && root.snapshotData.net) {
                            // Use new auto-scaling format if available
                            if (root.snapshotData.net.recv_rate && root.snapshotData.net.recv_rate.formatted) {
                                return root.snapshotData.net.recv_rate.formatted;
                            }
                            // Fallback to old Mbps format
                            var rate = root.snapshotData.net.recv_rate_mbps || 0;
                            return rate.toFixed(2) + " Mbps";
                        }
                        return "0.00 bps";
                    }
                    positive: true
                    width: parent.width - 40
                }
            }
        }
    }

    // Adapter Details Section
    AnimatedCard {
        width: parent.width
        implicitHeight: adapterColumn.height + 80

        Column {
            id: adapterColumn
            width: parent.width - 40
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 20
            anchors.bottomMargin: 20
            spacing: 16

            Text {
                text: "Adapter Details"
                color: Theme.text
                font.pixelSize: 18
                font.bold: true
            }

            Repeater {
                model: root.snapshotData.net && root.snapshotData.net.adapters ? 
                       root.snapshotData.net.adapters : []

                Rectangle {
                    width: parent.width
                    height: adapterItem.height + 24
                    color: Theme.surface
                    radius: 8
                    border.color: Theme.border
                    border.width: 1

                    Row {
                        id: adapterItem
                        width: parent.width - 32
                        anchors.centerIn: parent
                        spacing: 16

                        // Status indicator
                        Rectangle {
                            width: 10
                            height: 10
                            radius: 5
                            color: modelData.is_up ? Theme.success : Theme.error
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        // Adapter info
                        Column {
                            spacing: 4
                            width: parent.width - 26

                            Row {
                                spacing: 12
                                width: parent.width

                                Text {
                                    text: modelData.name
                                    color: Theme.text
                                    font.pixelSize: 14
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                    width: Math.min(implicitWidth, parent.width - 80)
                                }

                                Rectangle {
                                    height: 18
                                    width: statusLabel.width + 12
                                    radius: 9
                                    color: modelData.is_up ? Theme.success + "20" : Theme.error + "20"
                                    border.color: modelData.is_up ? Theme.success : Theme.error
                                    border.width: 1
                                    anchors.verticalCenter: parent.verticalCenter

                                    Text {
                                        id: statusLabel
                                        anchors.centerIn: parent
                                        text: modelData.is_up ? "Active" : "Inactive"
                                        color: modelData.is_up ? Theme.success : Theme.error
                                        font.pixelSize: 10
                                        font.bold: true
                                    }
                                }
                            }

                            Text {
                                text: {
                                    var ips = [];
                                    if (modelData.addresses && modelData.addresses.length > 0) {
                                        for (var i = 0; i < modelData.addresses.length; i++) {
                                            ips.push(modelData.addresses[i].address);
                                        }
                                        return ips.join(", ");
                                    }
                                    return "No IP configured";
                                }
                                color: Theme.textSecondary
                                font.pixelSize: 12
                                font.family: "Consolas"
                                elide: Text.ElideRight
                                width: parent.width
                            }
                        }
                    }
                }
            }

            // Empty state
            Text {
                visible: !root.snapshotData.net || !root.snapshotData.net.adapters || 
                         root.snapshotData.net.adapters.length === 0
                text: "No network adapters found"
                color: Theme.textSecondary
                font.pixelSize: 13
                font.italic: true
            }
        }
    }

    // Charts are updated by the live data from backend
    Connections {
        target: root
        function onSnapshotDataChanged() {
            if (root.snapshotData && root.snapshotData.net) {
                var uploadMbps = root.snapshotData.net.send_rate_mbps || 0;
                var downloadMbps = root.snapshotData.net.recv_rate_mbps || 0;
                upChart.pushValue(Math.min(1, uploadMbps / 100)); // Normalize to 0-1 range (max 100 Mbps)
                downChart.pushValue(Math.min(1, downloadMbps / 100));
            }
        }
    }
        }
    }
}