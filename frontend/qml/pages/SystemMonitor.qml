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
    property string rtpCapabilityState: (typeof RTPBridge !== "undefined" && RTPBridge) ? RTPBridge.getCapabilityState() : "unsupported"
    property string rtpCapabilityDetail: (typeof RTPBridge !== "undefined" && RTPBridge) ? RTPBridge.getCapabilityDetail() : "Real-Time Protection is not available on this platform."
    property bool rtpConfiguredEnabled: (typeof RTPBridge !== "undefined" && RTPBridge && typeof RTPBridge.getConfiguredEnabled === "function") ? RTPBridge.getConfiguredEnabled() : false
    property string rtpMonitoringState: (typeof RTPBridge !== "undefined" && RTPBridge && typeof RTPBridge.getMonitoringState === "function") ? RTPBridge.getMonitoringState() : "unsupported"
    property string rtpProcessScannerState: (typeof RTPBridge !== "undefined" && RTPBridge && typeof RTPBridge.getProcessScannerState === "function") ? RTPBridge.getProcessScannerState() : "unsupported"
    property string rtpRuntimeDetail: (typeof RTPBridge !== "undefined" && RTPBridge && typeof RTPBridge.getRuntimeDetail === "function") ? RTPBridge.getRuntimeDetail() : rtpCapabilityDetail
    property bool rtpAvailable: typeof RTPBridge !== "undefined" && RTPBridge !== null && rtpCapabilityState !== "unsupported"

    // ── Log console model (ListModel for efficient prepend) ──
    ListModel { id: logModel }

    // ── Max log entries ──
    readonly property int maxLogEntries: 200

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

    function syncRtpState() {
        if (typeof RTPBridge === "undefined" || !RTPBridge)
            return

        rtpEnabled = RTPBridge.getStatus()
        if (typeof RTPBridge.getCapabilityState === "function")
            rtpCapabilityState = RTPBridge.getCapabilityState()
        if (typeof RTPBridge.getCapabilityDetail === "function")
            rtpCapabilityDetail = RTPBridge.getCapabilityDetail()
        if (typeof RTPBridge.getConfiguredEnabled === "function")
            rtpConfiguredEnabled = RTPBridge.getConfiguredEnabled()
        if (typeof RTPBridge.getMonitoringState === "function")
            rtpMonitoringState = RTPBridge.getMonitoringState()
        if (typeof RTPBridge.getProcessScannerState === "function")
            rtpProcessScannerState = RTPBridge.getProcessScannerState()
        if (typeof RTPBridge.getRuntimeDetail === "function")
            rtpRuntimeDetail = RTPBridge.getRuntimeDetail()
        else
            rtpRuntimeDetail = rtpCapabilityDetail
    }

    // ── Start monitor when page becomes visible ──
    // ResourceMonitor is registered as null at startup and replaced at 500ms.
    // The poll timer syncs monitorRunning every 2s; the visible handler handles
    // the case where the user opens this page before the poll fires.
    function _startMonitorIfNeeded() {
        if (typeof ResourceMonitor === "undefined" || !ResourceMonitor) return
        if (!ResourceMonitor.getIsRunning()) {
            ResourceMonitor.start()
        }
        monitorRunning = ResourceMonitor.getIsRunning()
    }

    Component.onCompleted: {
        if (visible) _startMonitorIfNeeded()
        syncRtpState()
    }

    onVisibleChanged: {
        if (visible) _startMonitorIfNeeded()
    }

    // ── Poll timer (syncs bridge → QML properties) ──
    // Only poll while this page is visible; triggeredOnStart refreshes data
    // immediately on each navigation to this page.
    Timer {
        id: pollTimer
        interval: 2000
        running: root.visible
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            if (typeof ResourceMonitor !== "undefined" && ResourceMonitor) {
                cpuPercent = ResourceMonitor.getCpuPercent()
                ramPercent = ResourceMonitor.getRamPercent()
                ramUsedGb = ResourceMonitor.getRamUsedGb()
                ramTotalGb = ResourceMonitor.getRamTotalGb()
                netSentMbps = ResourceMonitor.getNetSentMbps()
                netRecvMbps = ResourceMonitor.getNetRecvMbps()
                diskPercent = ResourceMonitor.getDiskPercent()
                monitorRunning = ResourceMonitor.getIsRunning()
            }
            syncRtpState()
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
        function onStatusMessage(msg) {
            addLog("🛡️ RTP: " + msg)
            syncRtpState()
        }
        function onProtectionStatusChanged(active) { syncRtpState() }
        function onCapabilityChanged() { syncRtpState() }

        // Pre-formatted log line from bridge (Allowed / Blocked per process)
        function onNew_event_log(logLine) {
            logModel.insert(0, { "entry": logLine })
            while (logModel.count > maxLogEntries)
                logModel.remove(logModel.count - 1)
        }
    }

    function addLog(text) {
        var ts = new Date().toLocaleTimeString(Qt.locale(), "HH:mm:ss")
        logModel.insert(0, { "entry": "[" + ts + "] " + text })
        while (logModel.count > maxLogEntries)
            logModel.remove(logModel.count - 1)
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
                        font.pixelSize: ThemeManager.fontSize_h1
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
                            font.pixelSize: ThemeManager.fontSize_small
                            font.bold: true
                            color: monitorRunning ? ThemeManager.success : ThemeManager.danger
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (typeof ResourceMonitor !== "undefined" && ResourceMonitor) {
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
                    height: 88
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
                            color: rtpCapabilityState === "degraded"
                                   ? ThemeManager.warning
                                   : (rtpMonitoringState === "running" ? ThemeManager.success : ThemeManager.muted())
                            border.color: rtpCapabilityState === "degraded"
                                          ? ThemeManager.warning
                                          : (rtpMonitoringState === "running" ? ThemeManager.success : ThemeManager.border())
                            border.width: 2

                            // Glow animation
                            SequentialAnimation on opacity {
                                running: rtpMonitoringState === "running"
                                loops: Animation.Infinite
                                NumberAnimation { from: 1.0; to: 0.4; duration: 1200; easing.type: Easing.InOutSine }
                                NumberAnimation { from: 0.4; to: 1.0; duration: 1200; easing.type: Easing.InOutSine }
                            }
                        }

                        ColumnLayout {
                            spacing: 2
                            Text {
                                text: "Real-Time Protection"
                                font.pixelSize: ThemeManager.fontSize_body
                                font.bold: true
                                color: ThemeManager.foreground()
                            }
                            Text {
                                Layout.fillWidth: true
                                text: !rtpAvailable
                                      ? "Not available on this platform"
                                      : rtpRuntimeDetail
                                font.pixelSize: ThemeManager.fontSize_small
                                wrapMode: Text.WordWrap
                                color: !rtpAvailable
                                       ? ThemeManager.muted()
                                       : (rtpCapabilityState === "degraded"
                                          ? ThemeManager.warning
                                          : (rtpMonitoringState === "running"
                                             ? ThemeManager.success
                                             : ThemeManager.muted()))
                            }
                        }

                        Item { Layout.fillWidth: true }

                        // RTP toggle button — hidden when not available
                        Rectangle {
                            visible: rtpAvailable && rtpCapabilityState === "available"
                            width: rtpBtnText.implicitWidth + 24
                            height: 34
                            radius: 8
                            color: rtpBtnMouse.containsMouse
                                   ? Qt.lighter(rtpEnabled ? ThemeManager.danger : ThemeManager.success, 1.15)
                                   : (rtpEnabled ? ThemeManager.danger : ThemeManager.success)

                            Text {
                                id: rtpBtnText
                                anchors.centerIn: parent
                                text: rtpEnabled ? "Disable" : "Enable"
                                font.pixelSize: ThemeManager.fontSize_small
                                font.bold: true
                                color: "#ffffff"
                            }

                            MouseArea {
                                id: rtpBtnMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (typeof RTPBridge !== "undefined" && RTPBridge) {
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
                                font.pixelSize: ThemeManager.fontSize_small
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
                                font.pixelSize: ThemeManager.fontSize_small
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
                                font.pixelSize: ThemeManager.fontSize_small
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
                                    font.pixelSize: ThemeManager.fontSize_small
                                    font.bold: true
                                    color: ThemeManager.foreground()
                                }

                                Text {
                                    text: logModel.count + " entries"
                                    font.pixelSize: ThemeManager.fontSize_small
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
                                        font.pixelSize: ThemeManager.fontSize_small
                                        color: ThemeManager.muted()
                                    }

                                    MouseArea {
                                        id: clearMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: logModel.clear()
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
                            model: logModel

                            delegate: Rectangle {
                                id: logRow
                                width: logView.width
                                height: logText.implicitHeight + 12
                                color: rowHover.containsMouse
                                       ? Qt.rgba(1, 1, 1, 0.04)
                                       : (index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02))

                                // Detect whether this entry can be whitelisted
                                readonly property string _entry: model.entry || ""
                                readonly property bool _isFlagged: _entry.indexOf("RTP: Flagged") >= 0
                                readonly property bool _isBlocked: _entry.indexOf("RTP: Blocked") >= 0
                                readonly property bool _canWhitelist: _isFlagged || _isBlocked

                                // Extract process name from "RTP: Flagged/Blocked <name> (PID"
                                readonly property string _processName: {
                                    var m = _entry.match(/RTP: (?:Flagged|Blocked) (.+?) \(PID/)
                                    return m ? m[1].trim() : ""
                                }

                                HoverHandler { id: rowHover }

                                Text {
                                    id: logText
                                    anchors {
                                        left: parent.left
                                        right: whitelistBtn.visible ? whitelistBtn.left : parent.right
                                        verticalCenter: parent.verticalCenter
                                        leftMargin: 14
                                        rightMargin: whitelistBtn.visible ? 6 : 14
                                    }
                                    text: logRow._entry
                                    font.pixelSize: ThemeManager.fontSize_small
                                    font.family: "Consolas, monospace"
                                    color: {
                                        var t = logRow._entry
                                        if (t.indexOf("Blocked") >= 0 || t.indexOf("THREAT") >= 0)
                                            return ThemeManager.danger
                                        if (t.indexOf("Flagged") >= 0 || t.indexOf("⚠") >= 0)
                                            return ThemeManager.warning
                                        if (t.indexOf("🛡") >= 0)
                                            return ThemeManager.success
                                        if (t.indexOf("Allowed") >= 0)
                                            return ThemeManager.muted()
                                        if (t.indexOf("🔧") >= 0)
                                            return ThemeManager.accent
                                        return ThemeManager.muted()
                                    }
                                    wrapMode: Text.WordWrap
                                }

                                // "Whitelist" action button — shown on hover for flagged/blocked rows
                                Rectangle {
                                    id: whitelistBtn
                                    anchors {
                                        right: parent.right
                                        rightMargin: 10
                                        verticalCenter: parent.verticalCenter
                                    }
                                    width: wlLabel.implicitWidth + 16
                                    height: 22
                                    radius: 4
                                    visible: logRow._canWhitelist
                                             && logRow._processName !== ""
                                             && rowHover.containsMouse
                                    color: wlMouse.containsMouse
                                           ? ThemeManager.warning
                                           : Qt.rgba(ThemeManager.warning.r,
                                                     ThemeManager.warning.g,
                                                     ThemeManager.warning.b, 0.18)
                                    border.color: ThemeManager.warning
                                    border.width: 1

                                    Text {
                                        id: wlLabel
                                        anchors.centerIn: parent
                                        text: "Whitelist"
                                        font.pixelSize: ThemeManager.fontSize_caption
                                        font.bold: true
                                        color: wlMouse.containsMouse ? "#000" : ThemeManager.warning
                                    }

                                    ToolTip.visible: wlMouse.containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: "Add '" + logRow._processName
                                                  + "' to user whitelist — RTP will allow it in future"

                                    MouseArea {
                                        id: wlMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof RTPBridge !== "undefined" && RTPBridge
                                                    && logRow._processName !== "") {
                                                var added = RTPBridge.addUserWhitelistEntry(
                                                    logRow._processName)
                                                var msg = added
                                                    ? ("✅ Whitelisted: " + logRow._processName)
                                                    : ("ℹ️ Already whitelisted: " + logRow._processName)
                                                addLog(msg)
                                            }
                                        }
                                    }
                                }
                            }

                            // Empty state
                            Rectangle {
                                anchors.centerIn: parent
                                visible: logModel.count === 0
                                width: emptyText.implicitWidth + 40
                                height: emptyText.implicitHeight + 20
                                color: "transparent"

                                Text {
                                    id: emptyText
                                    anchors.centerIn: parent
                                    text: "No events yet. Enable RTP or launch an app to see process scan activity."
                                    font.pixelSize: ThemeManager.fontSize_small
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
