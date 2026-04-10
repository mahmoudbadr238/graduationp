import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Item {
    id: root
    anchors.fill: parent

    // ── Live stat values (polled from bridge) ──
    property real cpuPercent: 0
    property real ramPercent: 0
    property real ramUsedGb: 0
    property real ramTotalGb: 0
    property real netSentMbps: 0
    property real netRecvMbps: 0
    property real diskPercent: 0
    property bool monitorRunning: false
    property bool rtpEnabled: false

    // ── Log console model ──
    property var logEntries: []

    // ── Helpers ──
    function statusColor(value) {
        if (value > 90) return ThemeManager.danger
        if (value > 70) return ThemeManager.warning
        return ThemeManager.success
    }

    function formatMbps(val) {
        if (val < 0.01) return "0 B/s"
        if (val < 1) return (val * 1024).toFixed(0) + " KB/s"
        return val.toFixed(2) + " MB/s"
    }

    // ── Auto-start monitor & poll stats ──
    Component.onCompleted: {
        if (typeof ResourceMonitor !== "undefined") {
            ResourceMonitor.start()
            monitorRunning = true
        }
    }

    // ── Poll timer (syncs bridge → QML properties) ──
    Timer {
        id: pollTimer
        interval: 2000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            if (typeof ResourceMonitor !== "undefined") {
                cpuPercent = ResourceMonitor.getCpuPercent()
                ramPercent = ResourceMonitor.getRamPercent()
                ramUsedGb = ResourceMonitor.getRamUsedGb()
                ramTotalGb = ResourceMonitor.getRamTotalGb()
                netSentMbps = ResourceMonitor.getNetSentMbps()
                netRecvMbps = ResourceMonitor.getNetRecvMbps()
                diskPercent = ResourceMonitor.getDiskPercent()
                monitorRunning = ResourceMonitor.getIsRunning()
            }
            if (typeof RTPBridge !== "undefined") {
                rtpEnabled = RTPBridge.getStatus()
            }
        }
    }

    // ── Alert & RTP signals → log console ──
    Connections {
        target: typeof ResourceMonitor !== "undefined" ? ResourceMonitor : null
        enabled: target !== null
        function onAlertTriggered(title, message) {
            addLog("⚠️ " + title + ": " + message)
        }
    }

    Connections {
        target: typeof RTPBridge !== "undefined" ? RTPBridge : null
        enabled: target !== null
        function onThreatDetected(msg) { addLog(msg) }
        function onProcessScanned(msg) { addLog(msg) }
        function onStatusMessage(msg) { addLog("🛡️ RTP: " + msg) }
    }

    function addLog(text) {
        var ts = new Date().toLocaleTimeString(Qt.locale(), "HH:mm:ss")
        var newEntries = logEntries.slice()
        newEntries.unshift("[" + ts + "] " + text)
        if (newEntries.length > 200) newEntries = newEntries.slice(0, 200)
        logEntries = newEntries
    }

    // ── Main layout ──
    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: parent.width
            spacing: 0

            // ─────────────────────────────────────────────────────
            // PADDED CONTENT
            // ─────────────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 28
                Layout.rightMargin: 28
                Layout.topMargin: 24
                Layout.bottomMargin: 24
                spacing: 20

                // ── Header ──
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        text: "Live System Monitor"
                        font.pixelSize: 24
                        font.bold: true
                        color: ThemeManager.foreground()
                    }

                    Item { Layout.fillWidth: true }

                    // Monitor toggle
                    Rectangle {
                        width: monitorLabel.implicitWidth + 32
                        height: 32
                        radius: 6
                        color: monitorRunning
                               ? Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.12)
                               : Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.12)
                        border.color: monitorRunning ? ThemeManager.success : ThemeManager.danger
                        border.width: 1

                        Text {
                            id: monitorLabel
                            anchors.centerIn: parent
                            text: monitorRunning ? "● Monitoring Active" : "○ Monitor Stopped"
                            font.pixelSize: 12
                            font.bold: true
                            color: monitorRunning ? ThemeManager.success : ThemeManager.danger
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (typeof ResourceMonitor !== "undefined") {
                                    if (monitorRunning) ResourceMonitor.stop()
                                    else ResourceMonitor.start()
                                }
                            }
                        }
                    }
                }

                // ═══════════════════════════════════════════════
                // ENGINE STATUS SECTION
                // ═══════════════════════════════════════════════
                Rectangle {
                    Layout.fillWidth: true
                    height: 72
                    radius: 12
                    color: ThemeManager.panel()
                    border.color: ThemeManager.border()
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 16

                        // Glowing dot
                        Rectangle {
                            width: 14; height: 14; radius: 7
                            color: rtpEnabled ? ThemeManager.success : ThemeManager.muted()
                            border.color: rtpEnabled ? ThemeManager.success : ThemeManager.border()
                            border.width: 2

                            // Glow animation
                            SequentialAnimation on opacity {
                                running: rtpEnabled
                                loops: Animation.Infinite
                                NumberAnimation { from: 1.0; to: 0.4; duration: 1200; easing.type: Easing.InOutSine }
                                NumberAnimation { from: 0.4; to: 1.0; duration: 1200; easing.type: Easing.InOutSine }
                            }
                        }

                        ColumnLayout {
                            spacing: 2
                            Text {
                                text: "Real-Time Protection (WMI)"
                                font.pixelSize: 15
                                font.bold: true
                                color: ThemeManager.foreground()
                            }
                            Text {
                                text: rtpEnabled ? "ACTIVE — Monitoring all process launches" : "INACTIVE — Click to enable"
                                font.pixelSize: 12
                                color: rtpEnabled ? ThemeManager.success : ThemeManager.muted()
                            }
                        }

                        Item { Layout.fillWidth: true }

                        // RTP toggle button
                        Rectangle {
                            width: rtpBtnText.implicitWidth + 24
                            height: 34
                            radius: 8
                            color: rtpBtnMouse.containsMouse
                                   ? Qt.lighter(rtpEnabled ? ThemeManager.danger : ThemeManager.success, 1.15)
                                   : (rtpEnabled ? ThemeManager.danger : ThemeManager.success)

                            Text {
                                id: rtpBtnText
                                anchors.centerIn: parent
                                text: rtpEnabled ? "Disable RTP" : "Enable RTP"
                                font.pixelSize: 12
                                font.bold: true
                                color: "#ffffff"
                            }

                            MouseArea {
                                id: rtpBtnMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (typeof RTPBridge !== "undefined") {
                                        RTPBridge.toggle()
                                    }
                                }
                            }
                        }
                    }
                }

                // ═══════════════════════════════════════════════
                // RESOURCE GAUGES
                // ═══════════════════════════════════════════════
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    // ── CPU Card ──
                    Rectangle {
                        Layout.fillWidth: true
                        height: 160
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "🖥️  CPU"
                                    font.pixelSize: 14; font.bold: true
                                    color: ThemeManager.foreground()
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: cpuPercent.toFixed(1) + "%"
                                    font.pixelSize: 28; font.bold: true
                                    color: statusColor(cpuPercent)
                                }
                            }

                            // Progress bar
                            Rectangle {
                                Layout.fillWidth: true; height: 10; radius: 5
                                color: ThemeManager.surface()

                                Rectangle {
                                    width: parent.width * Math.min(cpuPercent / 100, 1)
                                    height: parent.height; radius: 5
                                    color: statusColor(cpuPercent)

                                    Behavior on width {
                                        NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
                                    }
                                }
                            }

                            Text {
                                text: cpuPercent > 90 ? "⚠ Critical load" :
                                      cpuPercent > 70 ? "Elevated usage" : "Normal operation"
                                font.pixelSize: 11
                                color: ThemeManager.muted()
                            }
                        }
                    }

                    // ── RAM Card ──
                    Rectangle {
                        Layout.fillWidth: true
                        height: 160
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "🧠  Memory"
                                    font.pixelSize: 14; font.bold: true
                                    color: ThemeManager.foreground()
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: ramPercent.toFixed(1) + "%"
                                    font.pixelSize: 28; font.bold: true
                                    color: statusColor(ramPercent)
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true; height: 10; radius: 5
                                color: ThemeManager.surface()

                                Rectangle {
                                    width: parent.width * Math.min(ramPercent / 100, 1)
                                    height: parent.height; radius: 5
                                    color: statusColor(ramPercent)

                                    Behavior on width {
                                        NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
                                    }
                                }
                            }

                            Text {
                                text: ramUsedGb.toFixed(1) + " / " + ramTotalGb.toFixed(1) + " GB used"
                                font.pixelSize: 11
                                color: ThemeManager.muted()
                            }
                        }
                    }

                    // ── Network Card ──
                    Rectangle {
                        Layout.fillWidth: true
                        height: 160
                        radius: 12
                        color: ThemeManager.panel()
                        border.color: ThemeManager.border()
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "🌐  Network"
                                    font.pixelSize: 14; font.bold: true
                                    color: ThemeManager.foreground()
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: formatMbps(netSentMbps + netRecvMbps)
                                    font.pixelSize: 22; font.bold: true
                                    color: ThemeManager.accent
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 20

                                ColumnLayout {
                                    spacing: 2
                                    Text { text: "↑ Upload"; font.pixelSize: 10; color: ThemeManager.muted() }
                                    Text {
                                        text: formatMbps(netSentMbps)
                                        font.pixelSize: 14; font.bold: true
                                        color: ThemeManager.success
                                    }
                                }

                                ColumnLayout {
                                    spacing: 2
                                    Text { text: "↓ Download"; font.pixelSize: 10; color: ThemeManager.muted() }
                                    Text {
                                        text: formatMbps(netRecvMbps)
                                        font.pixelSize: 14; font.bold: true
                                        color: ThemeManager.accent
                                    }
                                }
                            }

                            Text {
                                text: "Live throughput"
                                font.pixelSize: 11
                                color: ThemeManager.muted()
                            }
                        }
                    }
                }

                // ═══════════════════════════════════════════════
                // DISK USAGE (compact bar)
                // ═══════════════════════════════════════════════
                Rectangle {
                    Layout.fillWidth: true
                    height: 50
                    radius: 10
                    color: ThemeManager.panel()
                    border.color: ThemeManager.border()
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 14

                        Text {
                            text: "💾  Disk"
                            font.pixelSize: 13; font.bold: true
                            color: ThemeManager.foreground()
                        }

                        Rectangle {
                            Layout.fillWidth: true; height: 8; radius: 4
                            color: ThemeManager.surface()

                            Rectangle {
                                width: parent.width * Math.min(diskPercent / 100, 1)
                                height: parent.height; radius: 4
                                color: statusColor(diskPercent)

                                Behavior on width {
                                    NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
                                }
                            }
                        }

                        Text {
                            text: diskPercent.toFixed(1) + "%"
                            font.pixelSize: 13; font.bold: true
                            color: statusColor(diskPercent)
                            Layout.preferredWidth: 50
                        }
                    }
                }

                // ═══════════════════════════════════════════════
                // LIVE LOG CONSOLE
                // ═══════════════════════════════════════════════
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 220
                    radius: 12
                    color: ThemeManager.panel()
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 1
                        spacing: 0

                        // Console header
                        Rectangle {
                            Layout.fillWidth: true
                            height: 38
                            color: ThemeManager.surface()
                            radius: 12

                            // Square off bottom corners
                            Rectangle {
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                height: 12
                                color: parent.color
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 8

                                Text {
                                    text: "📋  Event Console"
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: ThemeManager.foreground()
                                }

                                Text {
                                    text: logEntries.length + " entries"
                                    font.pixelSize: 11
                                    color: ThemeManager.muted()
                                }

                                Item { Layout.fillWidth: true }

                                Rectangle {
                                    width: clearText.implicitWidth + 16
                                    height: 24
                                    radius: 5
                                    color: clearMouse.containsMouse ? ThemeManager.elevated() : "transparent"
                                    border.color: ThemeManager.border()
                                    border.width: 1

                                    Text {
                                        id: clearText
                                        anchors.centerIn: parent
                                        text: "Clear"
                                        font.pixelSize: 11
                                        color: ThemeManager.muted()
                                    }

                                    MouseArea {
                                        id: clearMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: logEntries = []
                                    }
                                }
                            }
                        }

                        // Log list
                        ListView {
                            id: logView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: logEntries

                            delegate: Rectangle {
                                width: logView.width
                                height: logText.implicitHeight + 12
                                color: index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02)

                                Text {
                                    id: logText
                                    anchors {
                                        left: parent.left; right: parent.right
                                        verticalCenter: parent.verticalCenter
                                        margins: 14
                                    }
                                    text: modelData
                                    font.pixelSize: 11
                                    font.family: "Consolas, monospace"
                                    color: {
                                        if (modelData.indexOf("⚠") >= 0 || modelData.indexOf("THREAT") >= 0)
                                            return ThemeManager.danger
                                        if (modelData.indexOf("🛡") >= 0)
                                            return ThemeManager.success
                                        if (modelData.indexOf("🔧") >= 0)
                                            return ThemeManager.accent
                                        return ThemeManager.muted()
                                    }
                                    wrapMode: Text.WordWrap
                                }
                            }

                            // Empty state
                            Rectangle {
                                anchors.centerIn: parent
                                visible: logEntries.length === 0
                                width: emptyText.implicitWidth + 40
                                height: emptyText.implicitHeight + 20
                                color: "transparent"

                                Text {
                                    id: emptyText
                                    anchors.centerIn: parent
                                    text: "No events yet. Enable RTP or wait for resource alerts."
                                    font.pixelSize: 12
                                    color: ThemeManager.muted()
                                }
                            }
                        }
                    }
                }

            } // end padded content
        } // end ColumnLayout
    } // end ScrollView
}
