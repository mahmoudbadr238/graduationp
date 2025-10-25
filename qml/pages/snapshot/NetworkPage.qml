import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"

Column {
    id: root
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24

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
    
    AnimatedCard {
        width: parent.width - 48
        implicitHeight: 120
        
        Column {
            spacing: 10
            width: parent.width
            
            Text {
                text: "Adapter Details"
                color: Theme.text
                font.pixelSize: 16
                font.bold: true
                
                Behavior on color {
                    ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                }
            }
            
            Text {
                text: {
                    if (root.snapshotData && root.snapshotData.net && root.snapshotData.net.adapters && root.snapshotData.net.adapters.length > 0) {
                        var adapter = root.snapshotData.net.adapters[0];
                        var name = adapter.name || "Unknown";
                        var ips = [];
                        if (adapter.addresses) {
                            for (var i = 0; i < adapter.addresses.length; i++) {
                                if (adapter.addresses[i].address) {
                                    ips.push(adapter.addresses[i].address);
                                }
                            }
                        }
                        return name + (ips.length > 0 ? " — " + ips.join(", ") : "");
                    }
                    return "No network adapters detected";
                }
                color: Theme.muted
                wrapMode: Text.Wrap
                width: parent.width - 40
                font.pixelSize: 14

                Behavior on color {
                    ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                }
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