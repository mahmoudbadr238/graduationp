import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../theme"

AppSurface {
    id: root

    property var snapshotData: ({
        "cpu": {"usage": 0, "freq_current": 0, "core_count": 0},
        "mem": {"used": 0, "total": 0, "percent": 0},
        "gpu": {"available": false, "usage": 0},
        "net": {
            "send_rate_mbps": 0,
            "recv_rate_mbps": 0,
            "send_rate": {"value": 0, "unit": "bps", "formatted": "0.00 bps"},
            "recv_rate": {"value": 0, "unit": "bps", "formatted": "0.00 bps"},
            "adapters": []
        },
        "disks": [{"used": 0, "total": 0, "percent": 0}],
        "security": {
            "windows_defender": {"enabled": false},
            "firewall": {"enabled": false},
            "secure_boot": {"enabled": false}
        }
    })

    ScrollView {
        anchors.fill: parent
        anchors.margins: Theme.spacing.md
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: Math.max(800, parent.parent.width - Theme.spacing.md * 4)
            spacing: Theme.spacing.lg

            PageHeader {
                title: "System Overview"
                subtitle: "Quick health check and key metrics"
                Layout.fillWidth: true
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 4
                columnSpacing: Theme.spacing.md
                rowSpacing: Theme.spacing.md

                LiveMetricTile {
                    label: "CPU"
                    valueText: root.snapshotData.cpu ? root.snapshotData.cpu.usage.toFixed(1) + "%" : "N/A"
                    hint: root.snapshotData.cpu ? root.snapshotData.cpu.core_count + " cores @ " +
                          (root.snapshotData.cpu.freq_current / 1000).toFixed(2) + " GHz" : ""
                    positive: root.snapshotData.cpu ? root.snapshotData.cpu.usage < 80 : true
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120
                }

                LiveMetricTile {
                    label: "Memory"
                    valueText: root.snapshotData.mem ? root.snapshotData.mem.percent.toFixed(1) + "%" : "N/A"
                    hint: root.snapshotData.mem ?
                          (root.snapshotData.mem.used / (1024**3)).toFixed(1) + " GB / " +
                          (root.snapshotData.mem.total / (1024**3)).toFixed(1) + " GB" : ""
                    positive: root.snapshotData.mem ? root.snapshotData.mem.percent < 80 : true
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120
                }

                LiveMetricTile {
                    label: "Disk"
                    valueText: {
                        if (root.snapshotData && root.snapshotData.disks) {
                            var dl = root.snapshotData.disks
                            
                            // Aggregate object schema
                            if (dl.total_capacity !== undefined && dl.total_used !== undefined) {
                                var totalPct = (dl.total_used / dl.total_capacity) * 100
                                return totalPct.toFixed(1) + "%"
                            }
                            
                            // Partitions array schema
                            if (dl.partitions && dl.partitions.length > 0) {
                                return Number(dl.partitions[0].percent).toFixed(1) + "%"
                            }
                            
                            // Simple list schema - QVariantList from Python (not a JS Array!)
                            // Check for length property instead of Array.isArray()
                            if (dl.length !== undefined && dl.length > 0) {
                                // Calculate average disk usage across all drives
                                var totalUsed = 0, totalCapacity = 0
                                for (var i = 0; i < dl.length; i++) {
                                    if (dl[i].used !== undefined && dl[i].total !== undefined) {
                                        totalUsed += dl[i].used
                                        totalCapacity += dl[i].total
                                    }
                                }
                                if (totalCapacity > 0) {
                                    var avgPct = (totalUsed / totalCapacity) * 100
                                    return avgPct.toFixed(1) + "%"
                                }
                            }
                        }
                        return "N/A"
                    }
                    hint: {
                        if (root.snapshotData && root.snapshotData.disks) {
                            var dl2 = root.snapshotData.disks
                            
                            // Aggregate object
                            if (dl2.total_capacity !== undefined && dl2.total_used !== undefined) {
                                var used = (dl2.total_used / (1024**3)).toFixed(0)
                                var total = (dl2.total_capacity / (1024**3)).toFixed(0)
                                var drives = dl2.partitions ? dl2.partitions.length : 0
                                return used + " GB / " + total + " GB (" + drives + " drives)"
                            }
                            
                            // Partitions array
                            if (dl2.partitions && dl2.partitions.length > 0) {
                                var p = dl2.partitions[0]
                                return p.used_gb.toFixed(0) + " GB / " + p.total_gb.toFixed(0) + " GB"
                            }
                            
                            // Simple list - show total across all drives (QVariantList)
                            if (dl2.length !== undefined && dl2.length > 0) {
                                var totalU = 0, totalT = 0
                                for (var j = 0; j < dl2.length; j++) {
                                    if (dl2[j].used !== undefined && dl2[j].total !== undefined) {
                                        totalU += dl2[j].used
                                        totalT += dl2[j].total
                                    }
                                }
                                if (totalT > 0) {
                                    return (totalU / (1024**3)).toFixed(0) + " GB / " + (totalT / (1024**3)).toFixed(0) + " GB (" + dl2.length + " drives)"
                                }
                            }
                        }
                        return ""
                    }
                    positive: {
                        if (root.snapshotData && root.snapshotData.disks) {
                            var dl3 = root.snapshotData.disks
                            
                            // Aggregate
                            if (dl3.total_capacity !== undefined && dl3.total_used !== undefined) {
                                var totalPct2 = (dl3.total_used / dl3.total_capacity) * 100
                                return totalPct2 < 80
                            }
                            
                            // Partitions
                            if (dl3.partitions && dl3.partitions.length > 0) {
                                return dl3.partitions[0].percent < 80
                            }
                            
                            // Simple list - check average (QVariantList)
                            if (dl3.length !== undefined && dl3.length > 0) {
                                var tU = 0, tT = 0
                                for (var k = 0; k < dl3.length; k++) {
                                    if (dl3[k].used !== undefined && dl3[k].total !== undefined) {
                                        tU += dl3[k].used
                                        tT += dl3[k].total
                                    }
                                }
                                if (tT > 0) {
                                    return ((tU / tT) * 100) < 80
                                }
                            }
                        }
                        return true
                    }
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120
                }

                LiveMetricTile {
                    label: "Network"
                    valueText: {
                        if (root.snapshotData && root.snapshotData.net) {
                            var down = "0.00 bps"
                            var up = "0.00 bps"

                            if (root.snapshotData.net.recv_rate && root.snapshotData.net.recv_rate.formatted) {
                                down = root.snapshotData.net.recv_rate.formatted
                            } else {
                                down = (root.snapshotData.net.recv_rate_mbps || 0).toFixed(2) + " Mbps"
                            }

                            if (root.snapshotData.net.send_rate && root.snapshotData.net.send_rate.formatted) {
                                up = root.snapshotData.net.send_rate.formatted
                            } else {
                                up = (root.snapshotData.net.send_rate_mbps || 0).toFixed(2) + " Mbps"
                            }

                            return " " + down + "\n " + up
                        }
                        return "N/A"
                    }
                    hint: root.snapshotData.net && root.snapshotData.net.adapters ?
                          root.snapshotData.net.adapters.length + " adapters" : ""
                    positive: true
                    Layout.fillWidth: true
                    Layout.preferredHeight: 140
                }
            }
        }
    }
}
