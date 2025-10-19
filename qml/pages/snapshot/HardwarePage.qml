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
        "cpu": {"usage": 0, "freq_current": 0, "core_count": 0},
        "mem": {"used": 0, "total": 0, "percent": 0},
        "gpu": {"available": false, "usage": 0},
        "disk": [{"used": 0, "total": 0, "percent": 0, "mountpoint": "C:\\"}]
    })

    onSnapshotDataChanged: {
        if (snapshotData && snapshotData.cpu) {
            cpuChart.pushValue(snapshotData.cpu.usage / 100.0);
        }
        if (snapshotData && snapshotData.mem) {
            memChart.pushValue(snapshotData.mem.percent / 100.0);
        }
        if (snapshotData && snapshotData.gpu && snapshotData.gpu.available) {
            gpuChart.pushValue((snapshotData.gpu.usage || 0) / 100.0);
        }
    }

    PageHeader {
        title: "Hardware Usage"
        subtitle: "Live system performance"
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
                    text: "CPU Usage"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }

                LineChartLive {
                    id: cpuChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#6ee7a8"
                }

                LiveMetricTile {
                    label: "CPU"
                    valueText: root.snapshotData.cpu ? root.snapshotData.cpu.usage.toFixed(1) + "%" : "N/A"
                    hint: root.snapshotData.cpu ? root.snapshotData.cpu.core_count + " cores @ " + (root.snapshotData.cpu.freq_current / 1000).toFixed(2) + " GHz" : ""
                    positive: root.snapshotData.cpu ? root.snapshotData.cpu.usage < 80 : true
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
                    text: "Memory Usage"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }

                LineChartLive {
                    id: memChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#a66bff"
                }

                LiveMetricTile {
                    label: "RAM"
                    valueText: root.snapshotData.mem ? root.snapshotData.mem.percent.toFixed(1) + "%" : "N/A"
                    hint: root.snapshotData.mem ? (root.snapshotData.mem.used / (1024**3)).toFixed(1) + " GB / " + (root.snapshotData.mem.total / (1024**3)).toFixed(1) + " GB" : ""
                    positive: root.snapshotData.mem ? root.snapshotData.mem.percent < 80 : true
                    width: parent.width - 40
                }
            }
        }
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
                    text: "GPU Usage"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }

                LineChartLive {
                    id: gpuChart
                    width: parent.width - 40
                    height: 140
                    stroke: "#66c7ff"
                }

                LiveMetricTile {
                    label: "GPU"
                    valueText: root.snapshotData.gpu && root.snapshotData.gpu.available ? (root.snapshotData.gpu.usage || 0).toFixed(1) + "%" : "N/A"
                    hint: root.snapshotData.gpu && root.snapshotData.gpu.available ? (root.snapshotData.gpu.name || "GPU") : "No GPU detected"
                    positive: root.snapshotData.gpu && root.snapshotData.gpu.available ? (root.snapshotData.gpu.usage || 0) < 80 : true
                    width: parent.width - 40
                }
            }
        }

        AnimatedCard {
            width: (parent.width - 18) / 2
            implicitHeight: 340

            Column {
                spacing: 16
                width: parent.width

                Text {
                    text: "Storage"
                    color: Theme.text
                    font.pixelSize: 18
                    font.bold: true

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }

                Text {
                    text: root.snapshotData.disk && root.snapshotData.disk.length > 0 ? 
                          root.snapshotData.disk[0].mountpoint + " - " + (root.snapshotData.disk[0].used / (1024**3)).toFixed(0) + " GB used (" + root.snapshotData.disk[0].percent.toFixed(1) + "%)" : "N/A"
                    color: Theme.muted
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    width: parent.width - 40

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }

                Rectangle {
                    width: parent.width - 40
                    height: 24
                    radius: 12
                    color: Theme.surface
                    border.color: Theme.border
                    border.width: 1

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                    Behavior on border.color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }

                    Rectangle {
                        width: root.snapshotData.disk && root.snapshotData.disk.length > 0 ? parent.width * (root.snapshotData.disk[0].percent / 100.0) : 0
                        height: parent.height
                        radius: 12
                        color: root.snapshotData.disk && root.snapshotData.disk.length > 0 && root.snapshotData.disk[0].percent > 80 ? "#ff6b6b" : "#a66bff"

                        Behavior on width {
                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                        }
                    }
                }

                Text {
                    text: root.snapshotData.disk && root.snapshotData.disk.length > 0 ? 
                          (root.snapshotData.disk[0].used / (1024**3)).toFixed(0) + " GB used / " + (root.snapshotData.disk[0].total / (1024**3)).toFixed(0) + " GB total" : "N/A"
                    color: Theme.muted
                    font.pixelSize: 13

                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
            }
        }
    }
}
