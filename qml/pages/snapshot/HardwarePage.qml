import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../theme"

AppSurface {
    id: root

    property var snapshotData: ({
        "cpu": {"usage": 0, "freq_current": 0, "core_count": 0},
        "mem": {"used": 0, "total": 0, "percent": 0},
        "gpu": {"count": 0, "gpus": [], "name": "No GPU", "usage": 0, "memory_used": 0, "memory_total": 0},
        "disks": []
    })

    property var gpuCharts: []

    onSnapshotDataChanged: {
        if (snapshotData && snapshotData.cpu) {
            cpuChart.pushValue(snapshotData.cpu.usage / 100.0)
        }
        if (snapshotData && snapshotData.mem) {
            memChart.pushValue(snapshotData.mem.percent / 100.0)
        }
    }

    ScrollView {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: ScrollBar.AsNeeded
        contentWidth: availableWidth

        Flickable {
            width: parent.width
            contentWidth: width
            contentHeight: mainColumn.height + Theme.spacing_xxl

            ColumnLayout {
                id: mainColumn
                width: parent.width
                spacing: Theme.spacing_lg

                PageHeader {
                    title: "Hardware Usage"
                    subtitle: "Live system performance"
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing_md

                    AnimatedCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 340

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing_lg
                            spacing: Theme.spacing_sm

                            Text {
                                text: "CPU Usage"
                                color: Theme.text
                                font.pixelSize: Theme.typography.h3.size
                                font.weight: Theme.typography.h3.weight
                                Layout.fillWidth: true

                                Behavior on color {
                                    ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                                }
                            }

                            LineChartLive {
                                id: cpuChart
                                Layout.fillWidth: true
                                Layout.preferredHeight: 140
                                stroke: "#6ee7a8"
                            }

                            LiveMetricTile {
                                label: "CPU"
                                valueText: root.snapshotData.cpu ? root.snapshotData.cpu.usage.toFixed(1) + "%" : "N/A"
                                hint: root.snapshotData.cpu ? root.snapshotData.cpu.core_count + " cores @ " + 
                                      (root.snapshotData.cpu.freq_current / 1000).toFixed(2) + " GHz" : ""
                                positive: root.snapshotData.cpu ? root.snapshotData.cpu.usage < 80 : true
                                Layout.fillWidth: true
                            }
                        }
                    }

                    AnimatedCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 340

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing_lg
                            spacing: Theme.spacing_sm

                            Text {
                                text: "Memory Usage"
                                color: Theme.text
                                font.pixelSize: Theme.typography.h3.size
                                font.weight: Theme.typography.h3.weight
                                Layout.fillWidth: true

                                Behavior on color {
                                    ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                                }
                            }

                            LineChartLive {
                                id: memChart
                                Layout.fillWidth: true
                                Layout.preferredHeight: 140
                                stroke: "#a66bff"
                            }

                            LiveMetricTile {
                                label: "RAM"
                                valueText: root.snapshotData.mem ? root.snapshotData.mem.percent.toFixed(1) + "%" : "N/A"
                                hint: root.snapshotData.mem ? 
                                      (root.snapshotData.mem.used / (1024**3)).toFixed(1) + " GB / " + 
                                      (root.snapshotData.mem.total / (1024**3)).toFixed(1) + " GB" : ""
                                positive: root.snapshotData.mem ? root.snapshotData.mem.percent < 80 : true
                                Layout.fillWidth: true
                            }
                        }
                    }
                }

                // GPU Monitoring Section - Using New GPUBackend with live updates
                GPUMiniWidget {
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.spacing_md
                }

                Text {
                    text: "Storage Monitoring"
                    color: Theme.text
                    font.pixelSize: Theme.typography.h2.size
                    font.weight: Theme.typography.h2.weight
                    Layout.topMargin: Theme.spacing_md
                    Layout.fillWidth: true

                    Behavior on color {
                        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                    }
                }

                Repeater {
                    model: {
                        if (root.snapshotData && root.snapshotData.disks) {
                            var disks = root.snapshotData.disks
                            
                            // Partitions array schema
                            if (disks.partitions && disks.partitions.length > 0) {
                                return disks.partitions
                            }
                            
                            // Simple list schema - QVariantList from Python (not JS Array)
                            // Check for length instead of Array.isArray()
                            if (disks.length !== undefined && disks.length > 0) {
                                return disks
                            }
                        }
                        return []
                    }

                    delegate: AnimatedCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 180

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing_lg
                            spacing: Theme.spacing_md

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.spacing_sm

                                Text {
                                    text: modelData.mountpoint || "Drive"
                                    color: Theme.text
                                    font.pixelSize: Theme.typography.h3.size
                                    font.weight: Theme.typography.h3.weight
                                    Layout.fillWidth: true

                                    Behavior on color {
                                        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                                    }
                                }

                                StatusBadge {
                                    text: modelData.fstype || "NTFS"
                                    status: "info"
                                    small: true
                                }

                                Text {
                                    text: {
                                        if (modelData.used_gb !== undefined) {
                                            return modelData.percent.toFixed(1) + "%"
                                        }
                                        if (modelData.percent !== undefined) {
                                            return modelData.percent.toFixed(1) + "%"
                                        }
                                        return "0%"
                                    }
                                    color: {
                                        var pct = modelData.percent || 0
                                        return pct > 80 ? Theme.error : Theme.success
                                    }
                                    font.pixelSize: Theme.typography.h2.size
                                    font.weight: Font.DemiBold

                                    Behavior on color {
                                        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 24
                                radius: 12
                                color: Theme.surface
                                border.color: Theme.border
                                border.width: 1

                                Behavior on color {
                                    ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                                }
                                Behavior on border.color {
                                    ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                                }

                                Rectangle {
                                    width: {
                                        var pct = modelData.percent || 0
                                        return parent.width * (pct / 100.0)
                                    }
                                    height: parent.height
                                    radius: 12
                                    color: {
                                        var pct = modelData.percent || 0
                                        return pct > 80 ? Theme.error : "#a66bff"
                                    }
                                    Behavior on width {
                                        NumberAnimation { duration: Theme.duration.medium; easing.type: Easing.OutCubic }
                                    }
                                    Behavior on color {
                                        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
                                    }
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.spacing_lg

                                Text {
                                    text: {
                                        if (modelData.used_gb !== undefined) {
                                            return modelData.used_gb.toFixed(0) + " GB used"
                                        }
                                        if (modelData.used !== undefined) {
                                            return (modelData.used / (1024**3)).toFixed(0) + " GB used"
                                        }
                                        return "0 GB used"
                                    }
                                    color: Theme.textSecondary || "#888888"
                                    font.pixelSize: Theme.typography ? Theme.typography.body.size : 15

                                    Behavior on color {
                                        ColorAnimation { duration: Theme.duration_fast; easing.type: Easing.InOutQuad }
                                    }
                                }

                                Text {
                                    text: {
                                        if (modelData.total_gb !== undefined) {
                                            return modelData.total_gb.toFixed(0) + " GB total"
                                        }
                                        if (modelData.total !== undefined) {
                                            return (modelData.total / (1024**3)).toFixed(0) + " GB total"
                                        }
                                        return "0 GB total"
                                    }
                                    color: Theme.textSecondary || "#888888"
                                    font.pixelSize: Theme.typography ? Theme.typography.body.size : 15

                                    Behavior on color {
                                        ColorAnimation { duration: Theme.duration_fast; easing.type: Easing.InOutQuad }
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: {
                                        if (modelData.free_gb !== undefined) {
                                            return modelData.free_gb.toFixed(0) + " GB free"
                                        }
                                        if (modelData.free !== undefined) {
                                            return (modelData.free / (1024**3)).toFixed(0) + " GB free"
                                        }
                                        return "0 GB free"
                                    }
                                    color: Theme.success
                                    font.pixelSize: Theme.typography ? Theme.typography.body.size : 15

                                    Behavior on color {
                                        ColorAnimation { duration: Theme.duration_fast; easing.type: Easing.InOutQuad }
                                    }
                                }
                            }
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                }
            }
        }
    }
}
