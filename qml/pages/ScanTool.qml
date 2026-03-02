import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../ui"
import "../components"

Item {
    id: root
    anchors.fill: parent

    // ============================================================
    // PROPERTIES
    // ============================================================
    property int  currentTab: 0

    // File scan
    property bool   fileScanningInProgress: false
    property string fileScanStage: ""
    property var    fileScanResult: null
    property string selectedFilePath: ""
    property bool   useSandbox: true
    property bool   blockNetwork: true
    property int    sandboxTimeout: 30

    property bool   sandboxLiveViewVisible: false
    property var    sandboxStats: ({
        running_time_ms: 0, process_count: 0, file_count: 0,
        registry_count: 0, network_count: 0, suspicious_count: 0
    })
    property var sandboxEvents: []

    // VMware Lab (collapsible)
    property bool vmwareExpanded: false
    property int  vmwareMonitorSeconds: 30
    property bool vmwareDisableNetwork: false
    property bool vmwareKillOnFinish: true
    property var  sandboxLab: (typeof SandboxLab !== "undefined") ? SandboxLab : null

    // Sandbox availability
    property bool   integratedSandboxAvailable: false
    property string integratedSandboxStatus: ""
    property bool   sandboxAvailable: false
    property var    sandboxMethods: []

    // URL scan
    property bool   urlCheckingInProgress: false
    property string urlScanStage: ""
    property int    urlScanProgressValue: 0
    property var    urlCheckResult: null
    property bool   useUrlSandbox: false
    property bool   blockDownloads: true
    property bool   blockPrivateIPs: true
    property bool   urlSandboxAvailable: false
    property string urlSandboxStatus: ""

    property string currentReportContent: ""
    property string currentReportFileName: ""

    // ============================================================
    // LIFECYCLE
    // ============================================================
    Component.onCompleted: {
        if (typeof Backend !== "undefined") {
            integratedSandboxAvailable = Backend.integratedSandboxAvailable()
            integratedSandboxStatus    = Backend.integratedSandboxStatus()
            urlSandboxAvailable        = Backend.urlSandboxAvailable()
            urlSandboxStatus           = Backend.urlSandboxStatus()
            sandboxAvailable           = Backend.sandboxAvailable()
            sandboxMethods             = Backend.sandboxMethods()
        }
    }

    // ============================================================
    // FILE DIALOG
    // ============================================================
    FileDialog {
        id: fileDialog
        title: "Select file to scan"
        nameFilters: ["All files (*)"]
        onAccepted: {
            var p = selectedFile.toString()
            if (p.startsWith("file:///")) p = p.substring(8)
            if (Qt.platform.os === "windows" && p.charAt(0) === "/") p = p.substring(1)
            selectedFilePath   = p
            filePathInput.text = p
        }
    }

    // ============================================================
    // BACKEND CONNECTIONS
    // ============================================================
    Connections {
        target: Backend || null
        enabled: target !== null

        function onLocalScanStarted() {
            fileScanningInProgress = true
            fileScanResult         = null
        }
        function onLocalScanProgress(stage) { fileScanStage = stage }
        function onLocalScanFinished(result) {
            fileScanningInProgress = false
            fileScanStage          = ""
            fileScanResult         = result
            if (result && result.report_content) {
                currentReportContent  = result.report_content
                currentReportFileName = "scan_report_" + (result.file_name || "file") + ".txt"
            }
        }

        function onIntegratedSandboxStarted() {
            fileScanningInProgress = true
            fileScanResult = null
            sandboxEvents = []
            sandboxStats = { running_time_ms:0, process_count:0, file_count:0,
                             registry_count:0, network_count:0, suspicious_count:0 }
        }
        function onIntegratedSandboxProgress(stage) {
            fileScanStage = stage
            if (stage.toLowerCase().includes("sandbox")) sandboxLiveViewVisible = true
        }
        function onIntegratedSandboxFinished(result) {
            fileScanningInProgress = false
            fileScanStage          = ""
            fileScanResult         = result
            sandboxLiveViewVisible = false
            if (result && result.report_content) {
                currentReportContent  = result.report_content
                currentReportFileName = "scan_report_" + (result.file_name || "file") + ".txt"
            }
        }

        function onSandboxEventBatch(eventsJson) {
            try {
                var ev = JSON.parse(eventsJson)
                for (var i = 0; i < ev.length; i++) sandboxEvents.push(ev[i])
                sandboxEvents = sandboxEvents.slice()
            } catch(e) {}
        }
        function onSandboxStatsUpdate(statsJson) {
            try { sandboxStats = JSON.parse(statsJson) } catch(e) {}
        }
        function onSandboxSessionEnded(summaryJson) { sandboxLiveViewVisible = false }

        function onSandboxPreviewFrameReady(frameNumber) {
            if (sandboxLiveViewComp) {
                sandboxLiveViewComp.frameNumber      = frameNumber
                sandboxLiveViewComp.previewAvailable = true
            }
        }
        function onSandboxWindowFound(found) {
            if (sandboxLiveViewComp) {
                if (found) {
                    sandboxLiveViewComp.previewAvailable = true
                } else if ((sandboxLiveViewComp.frameNumber || 0) <= 0) {
                    sandboxLiveViewComp.previewAvailable = false
                    sandboxLiveViewComp.previewStatus    = "No visible app window (console/background process)"
                }
            }
        }
        function onSandboxPreviewStarted() {
            if (sandboxLiveViewComp) sandboxLiveViewComp.previewStatus = "Searching for sandbox window..."
        }
        function onSandboxPreviewStopped() {
            if (sandboxLiveViewComp) {
                sandboxLiveViewComp.previewAvailable = false
                sandboxLiveViewComp.frameNumber      = 0
            }
        }

        function onUrlScanStarted() {
            urlCheckingInProgress = true
            urlCheckResult        = null
            urlScanStage          = ""
            urlScanProgressValue  = 0
        }
        function onUrlScanProgress(stage, progress) {
            urlScanStage         = stage
            urlScanProgressValue = progress
        }
        function onUrlScanFinished(result) {
            urlCheckingInProgress = false
            urlScanStage          = ""
            urlScanProgressValue  = 100
            urlCheckResult        = result
            if (result && result.report_content) {
                currentReportContent  = result.report_content
                currentReportFileName = "url_report.txt"
            }
        }
        function onLocalUrlCheckFinished(result) {
            urlCheckingInProgress = false
            urlCheckResult        = result
            if (result && result.report_content) {
                currentReportContent  = result.report_content
                currentReportFileName = "url_report.txt"
            }
        }
    }

    // ============================================================
    // HELPERS
    // ============================================================
    function verdictColor(v) {
        if (!v) return ThemeManager.muted()
        switch(v.toLowerCase()) {
            case "malicious":        return ThemeManager.danger
            case "likely_malicious": return ThemeManager.danger
            case "suspicious":       return ThemeManager.warning
            case "safe":             return ThemeManager.success
            default:                 return ThemeManager.foreground()
        }
    }
    function verdictIcon(v) {
        if (!v) return "?"
        switch(v.toLowerCase()) {
            case "malicious":        return "X"
            case "likely_malicious": return "!"
            case "suspicious":       return "^"
            case "safe":             return "OK"
            default:                 return "?"
        }
    }
    function verdictLabel(v) {
        if (!v) return "Unknown"
        switch(v.toLowerCase()) {
            case "malicious":        return "MALICIOUS"
            case "likely_malicious": return "Likely Malicious"
            case "suspicious":       return "Suspicious"
            case "safe":             return "Safe"
            default:                 return v
        }
    }
    function scoreColor(s) {
        if (s >= 80) return ThemeManager.danger
        if (s >= 50) return "#ff6b35"
        if (s >= 20) return ThemeManager.warning
        return ThemeManager.success
    }
    function fmtBytes(b) {
        if (b < 1024)       return b + " B"
        if (b < 1048576)    return (b/1024).toFixed(1)    + " KB"
        if (b < 1073741824) return (b/1048576).toFixed(1) + " MB"
        return (b/1073741824).toFixed(1) + " GB"
    }
    function severityColor(s) {
        switch(s) {
            case "critical": return ThemeManager.danger
            case "high":     return "#ff4444"
            case "medium":   return ThemeManager.warning
            default:         return ThemeManager.info
        }
    }

    function startFileScan() {
        if (!selectedFilePath || selectedFilePath.length === 0) {
            if (Backend) Backend.toast("warning", "Please select a file first")
            return
        }
        fileScanResult = null
        if (Backend)
            Backend.runIntegratedScan(selectedFilePath, useSandbox, blockNetwork, sandboxTimeout)
    }
    function startUrlCheck() {
        var url = urlInput.text.trim()
        if (!url) { if (Backend) Backend.toast("warning", "Please enter a URL first"); return }
        urlCheckResult        = null
        urlCheckingInProgress = true
        urlScanStage          = "Initializing..."
        urlScanProgressValue  = 0
        if (Backend) {
            if (useUrlSandbox && urlSandboxAvailable)
                Backend.scanUrlSandbox(url, blockDownloads, blockPrivateIPs, true, 30)
            else
                Backend.scanUrlStatic(url, blockPrivateIPs, true, 30)
        }
    }
    function cancelUrlCheck() {
        if (Backend) Backend.cancelUrlScan()
        urlCheckingInProgress = false; urlScanStage = ""; urlScanProgressValue = 0
    }

    // ============================================================
    // MAIN LAYOUT
    // ============================================================
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_lg
        spacing: Theme.spacing_md

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 0
            ColumnLayout {
                spacing: 3
                Text {
                    text: "Local Scan Tool"
                    font.pixelSize: 26; font.bold: true
                    color: ThemeManager.foreground()
                }
                Text {
                    text: "100% Offline Security Analysis  |  No Network Required"
                    font.pixelSize: 12; color: ThemeManager.muted()
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                height: 28; width: hdBadge.implicitWidth + 20; radius: 14
                color: integratedSandboxAvailable
                    ? Qt.rgba(0,0.8,0.4,0.15) : Qt.rgba(1,0.6,0,0.15)
                Text {
                    id: hdBadge; anchors.centerIn: parent
                    text: integratedSandboxAvailable
                        ? "Available (" + integratedSandboxStatus + ")"
                        : integratedSandboxStatus
                    font.pixelSize: 11
                    color: integratedSandboxAvailable ? ThemeManager.success : ThemeManager.warning
                }
            }
        }

        // Tab bar
        RowLayout {
            Layout.fillWidth: true
            spacing: 4
            Repeater {
                model: [{ icon: "F", lbl: "File Scan" }, { icon: "W", lbl: "URL Check" }]
                Rectangle {
                    Layout.preferredWidth: 140; height: 40; radius: 8
                    color: currentTab === index ? ThemeManager.primary : ThemeManager.surface()
                    border.color: currentTab === index ? "transparent" : ThemeManager.border()
                    border.width: 1
                    RowLayout {
                        anchors.centerIn: parent; spacing: 8
                        Text { text: modelData.lbl
                               color: currentTab === index ? "#ffffff" : ThemeManager.foreground()
                               font.pixelSize: 13; font.bold: currentTab === index }
                    }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: currentTab = index
                    }
                }
            }
            Item { Layout.fillWidth: true }
        }

        // Content
        StackLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            currentIndex: currentTab

            // ============================================================
            // FILE SCAN TAB
            // ============================================================
            Item {
                id: fileScanTab
                ScrollView {
                    anchors.fill: parent; clip: true; contentWidth: availableWidth
                    ColumnLayout {
                        width: fileScanTab.width
                        spacing: Theme.spacing_md

                        // File input card
                        Rectangle {
                            Layout.fillWidth: true
                            height: fileInputCol.implicitHeight + 36
                            color: ThemeManager.panel(); radius: 12
                            border.color: ThemeManager.border(); border.width: 1
                            ColumnLayout {
                                id: fileInputCol
                                anchors { fill: parent; margins: 18 }
                                spacing: 14
                                Text {
                                    text: "Select File to Scan"
                                    font.pixelSize: 15; font.bold: true
                                    color: ThemeManager.foreground()
                                }
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 10
                                    Rectangle {
                                        Layout.fillWidth: true; height: 42
                                        color: ThemeManager.surface(); radius: 8
                                        border.color: filePathInput.activeFocus ? ThemeManager.primary : ThemeManager.border()
                                        border.width: 1
                                        TextField {
                                            id: filePathInput
                                            anchors { fill: parent; margins: 2 }
                                            placeholderText: "Enter file path or click Browse..."
                                            text: selectedFilePath; maximumLength: 2048
                                            color: ThemeManager.foreground(); placeholderTextColor: ThemeManager.muted()
                                            font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; leftPadding: 12
                                            background: Rectangle { color: "transparent" }
                                            onTextChanged: selectedFilePath = text
                                        }
                                    }
                                    Button {
                                        text: "Browse"; Layout.preferredWidth: 100; Layout.preferredHeight: 42
                                        onClicked: fileDialog.open()
                                        background: Rectangle {
                                            color: parent.hovered ? Qt.lighter(ThemeManager.accent,1.1) : ThemeManager.accent; radius: 8
                                        }
                                        contentItem: Text {
                                            text: parent.text; color: "#ffffff"; font.pixelSize: 13; font.bold: true
                                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 24
                                    // Sandbox toggle
                                    RowLayout {
                                        spacing: 8
                                        Rectangle {
                                            width: 44; height: 24; radius: 12
                                            color: useSandbox ? ThemeManager.primary : ThemeManager.surface()
                                            border.color: ThemeManager.border()
                                            opacity: integratedSandboxAvailable ? 1.0 : 0.5
                                            Rectangle {
                                                x: useSandbox ? parent.width-width-3 : 3
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 18; height: 18; radius: 9; color: "#ffffff"
                                                Behavior on x { NumberAnimation { duration: 140 } }
                                            }
                                            MouseArea {
                                                anchors.fill: parent; enabled: integratedSandboxAvailable
                                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onClicked: useSandbox = !useSandbox
                                            }
                                        }
                                        Text {
                                            text: "Run in Sandbox"; font.pixelSize: 13
                                            color: integratedSandboxAvailable ? ThemeManager.foreground() : ThemeManager.muted()
                                        }
                                    }
                                    // Block network toggle
                                    RowLayout {
                                        spacing: 8; visible: useSandbox
                                        Rectangle {
                                            width: 44; height: 24; radius: 12
                                            color: blockNetwork ? ThemeManager.accent : ThemeManager.surface()
                                            border.color: ThemeManager.border()
                                            opacity: (integratedSandboxAvailable && useSandbox) ? 1.0 : 0.5
                                            Rectangle {
                                                x: blockNetwork ? parent.width-width-3 : 3
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 18; height: 18; radius: 9; color: "#ffffff"
                                                Behavior on x { NumberAnimation { duration: 140 } }
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: integratedSandboxAvailable && useSandbox
                                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onClicked: blockNetwork = !blockNetwork
                                            }
                                        }
                                        Text {
                                            text: "Block Network"; font.pixelSize: 13
                                            color: (integratedSandboxAvailable && useSandbox) ? ThemeManager.foreground() : ThemeManager.muted()
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Button {
                                        text: fileScanningInProgress ? "Scanning: " + (fileScanStage||"...") : "Scan File"
                                        Layout.preferredWidth: 148; Layout.preferredHeight: 42
                                        enabled: !fileScanningInProgress && selectedFilePath.length > 0
                                        onClicked: startFileScan()
                                        background: Rectangle {
                                            color: parent.enabled
                                                ? (parent.hovered ? Qt.lighter(ThemeManager.primary,1.1) : ThemeManager.primary)
                                                : ThemeManager.muted()
                                            radius: 8
                                        }
                                        contentItem: Text {
                                            text: parent.text; color: "#ffffff"; font.pixelSize: 13; font.bold: true
                                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                            }
                        }

                        // VMware Sandbox Lab (collapsible)
                        Rectangle {
                            Layout.fillWidth: true
                            height: vmwareHeader.height + (vmwareExpanded ? vmwareBody.implicitHeight + 14 : 0)
                            color: ThemeManager.panel(); radius: 12
                            border.color: ThemeManager.border(); border.width: 1
                            clip: true
                            Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutQuad } }

                            RowLayout {
                                id: vmwareHeader
                                anchors { left: parent.left; right: parent.right; top: parent.top }
                                height: 48
                                anchors.leftMargin: 16; anchors.rightMargin: 16
                                Text {
                                    text: "VMware Sandbox Lab"
                                    font.pixelSize: 14; font.bold: true; color: ThemeManager.foreground()
                                }
                                Text {
                                    Layout.fillWidth: true; leftPadding: 12
                                    text: sandboxLab ? sandboxLab.availabilityMessage : "VMware controller not registered"
                                    font.pixelSize: 11
                                    color: (sandboxLab && sandboxLab.available) ? ThemeManager.muted() : ThemeManager.warning
                                    elide: Text.ElideRight
                                }
                                Text { text: vmwareExpanded ? "^" : "v"; font.pixelSize: 12; color: ThemeManager.muted() }
                                MouseArea {
                                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: vmwareExpanded = !vmwareExpanded
                                }
                            }

                            ColumnLayout {
                                id: vmwareBody
                                anchors { left: parent.left; right: parent.right; top: vmwareHeader.bottom }
                                anchors.leftMargin: 16; anchors.rightMargin: 16
                                spacing: 12

                                Rectangle { Layout.fillWidth: true; height: 1; color: ThemeManager.border() }

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 16
                                    RowLayout {
                                        spacing: 6
                                        Text { text: "Monitor (s)"; font.pixelSize: 12; color: ThemeManager.muted() }
                                        Rectangle {
                                            width: 60; height: 30; color: ThemeManager.surface(); radius: 6
                                            border.color: ThemeManager.border(); border.width: 1
                                            TextField {
                                                anchors { fill: parent; margins: 2 }
                                                text: vmwareMonitorSeconds.toString(); inputMethodHints: Qt.ImhDigitsOnly
                                                maximumLength: 4; color: ThemeManager.foreground(); font.pixelSize: 12
                                                verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter
                                                background: Rectangle { color: "transparent" }
                                                onEditingFinished: {
                                                    var v = parseInt(text)
                                                    vmwareMonitorSeconds = (!isNaN(v) && v > 0) ? v : vmwareMonitorSeconds
                                                    text = vmwareMonitorSeconds.toString()
                                                }
                                            }
                                        }
                                    }
                                    RowLayout { spacing: 6; CheckBox { checked: vmwareDisableNetwork; onClicked: vmwareDisableNetwork = checked }; Text { text: "Disable Network"; font.pixelSize: 12; color: ThemeManager.muted() } }
                                    RowLayout { spacing: 6; CheckBox { checked: vmwareKillOnFinish; onClicked: vmwareKillOnFinish = checked }; Text { text: "Kill on Finish"; font.pixelSize: 12; color: ThemeManager.muted() } }
                                    Item { Layout.fillWidth: true }
                                    Button {
                                        text: (sandboxLab && sandboxLab.busy) ? "Running..." : "Detonate in VMware"
                                        Layout.preferredWidth: 148; Layout.preferredHeight: 34
                                        enabled: !!(sandboxLab && !sandboxLab.busy && sandboxLab.available && selectedFilePath.length > 0)
                                        onClicked: sandboxLab.runFileInSandbox(selectedFilePath, vmwareMonitorSeconds, vmwareDisableNetwork, vmwareKillOnFinish)
                                        background: Rectangle {
                                            color: parent.enabled ? (parent.hovered ? Qt.lighter(ThemeManager.primary,1.1) : ThemeManager.primary) : ThemeManager.muted(); radius: 8
                                        }
                                        contentItem: Text { text: parent.text; color: "#ffffff"; font.pixelSize: 12; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 12
                                    Rectangle {
                                        width: 300; height: 170; color: ThemeManager.surface(); radius: 8
                                        border.color: ThemeManager.border(); border.width: 1
                                        Image {
                                            anchors { fill: parent; margins: 2 }
                                            source: sandboxLab ? (sandboxLab.replayMode ? sandboxLab.replayFramePath : sandboxLab.liveFrameSource) : ""
                                            fillMode: Image.PreserveAspectFit; cache: false
                                            visible: sandboxLab ? (sandboxLab.replayMode ? sandboxLab.replayFramePath.length > 0 : sandboxLab.liveFrameSource.length > 0) : false
                                        }
                                        Text {
                                            anchors.centerIn: parent
                                            text: sandboxLab ? sandboxLab.liveViewState : "No feed"
                                            color: ThemeManager.muted(); font.pixelSize: 11
                                            visible: sandboxLab ? !(sandboxLab.replayMode ? sandboxLab.replayFramePath.length > 0 : sandboxLab.liveFrameSource.length > 0) : true
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true; spacing: 6
                                        Text { text: "Automation Steps"; font.pixelSize: 12; font.bold: true; color: ThemeManager.foreground() }
                                        ListView {
                                            Layout.fillWidth: true; height: 130
                                            model: sandboxLab ? sandboxLab.stepsModel : []; clip: true
                                            delegate: Text {
                                                text: model.time + " [" + model.status + "] " + model.message; font.pixelSize: 11
                                                color: model.status === "Failed" ? ThemeManager.danger : model.status === "OK" ? ThemeManager.success : ThemeManager.muted()
                                                elide: Text.ElideRight; width: parent ? parent.width : 0
                                            }
                                        }
                                        Text { text: sandboxLab ? sandboxLab.verdictSummary : ""; font.pixelSize: 12; color: ThemeManager.foreground(); visible: !!(sandboxLab && sandboxLab.verdictSummary.length > 0) }
                                        Text { text: sandboxLab ? sandboxLab.lastError : ""; font.pixelSize: 11; color: ThemeManager.danger; visible: !!(sandboxLab && sandboxLab.lastError.length > 0); wrapMode: Text.Wrap; Layout.fillWidth: true }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 10
                                    Button {
                                        text: "Open Run Folder"; Layout.preferredHeight: 30
                                        enabled: !!(sandboxLab && sandboxLab.lastRunFolder.length > 0)
                                        onClicked: sandboxLab.openLastRunFolder()
                                        background: Rectangle { color: parent.hovered ? ThemeManager.surface() : "transparent"; radius: 6; border.color: ThemeManager.border(); border.width: 1 }
                                        contentItem: Text { text: parent.text; font.pixelSize: 11; color: ThemeManager.foreground(); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                    Button {
                                        text: "Proof Media"; Layout.preferredHeight: 30
                                        enabled: !!(sandboxLab && (sandboxLab.proofGifPath.length > 0 || sandboxLab.proofMp4Path.length > 0))
                                        onClicked: sandboxLab.openProofMedia()
                                        background: Rectangle { color: parent.hovered ? ThemeManager.surface() : "transparent"; radius: 6; border.color: ThemeManager.border(); border.width: 1 }
                                        contentItem: Text { text: parent.text; font.pixelSize: 11; color: ThemeManager.foreground(); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                    Item { Layout.fillWidth: true }
                                }

                                Item { height: 2 }
                            }
                        }

                        // Scanning progress
                        Rectangle {
                            Layout.fillWidth: true; height: 56
                            color: ThemeManager.panel(); radius: 12
                            visible: fileScanningInProgress && !sandboxLiveViewVisible
                            RowLayout {
                                anchors.centerIn: parent; spacing: 14
                                BusyIndicator { running: fileScanningInProgress; Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
                                Text { text: fileScanStage || "Scanning..."; font.pixelSize: 13; color: ThemeManager.foreground() }
                            }
                        }

                        // Sandbox Live View
                        SandboxLiveView {
                            id: sandboxLiveViewComp
                            Layout.fillWidth: true
                            visible: sandboxLiveViewVisible; isActive: sandboxLiveViewVisible
                            stats: sandboxStats; events: sandboxEvents
                            onCancelClicked: { if (Backend) Backend.cancelSandbox() }
                        }

                        // Results card
                        Rectangle {
                            Layout.fillWidth: true
                            height: resultCol.implicitHeight + 36
                            color: ThemeManager.panel(); radius: 12; border.width: 2
                            border.color: {
                                if (!fileScanResult) return ThemeManager.border()
                                var v = (fileScanResult.verdict || "").toLowerCase()
                                if (v === "malicious" || v === "likely_malicious") return ThemeManager.danger
                                if (v === "suspicious") return ThemeManager.warning
                                return ThemeManager.success
                            }
                            visible: fileScanResult !== null

                            ColumnLayout {
                                id: resultCol
                                anchors { fill: parent; margins: 20 }
                                spacing: 16

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: fileScanResult ? verdictLabel(fileScanResult.verdict) : ""
                                        font.pixelSize: 22; font.bold: true
                                        color: fileScanResult ? verdictColor(fileScanResult.verdict) : ThemeManager.foreground()
                                    }
                                    Item { Layout.fillWidth: true }
                                    Rectangle {
                                        width: 76; height: 36; radius: 8
                                        color: fileScanResult ? scoreColor(fileScanResult.score) : ThemeManager.muted()
                                        Text {
                                            anchors.centerIn: parent
                                            text: fileScanResult ? fileScanResult.score + "/100" : ""
                                            font.pixelSize: 15; font.bold: true; color: "#ffffff"
                                        }
                                    }
                                }

                                Text { text: fileScanResult ? fileScanResult.summary : ""; font.pixelSize: 13; color: ThemeManager.foreground(); wrapMode: Text.Wrap; Layout.fillWidth: true }

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 4; columnSpacing: 16; rowSpacing: 6
                                    Text { text: "File:";   color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: fileScanResult ? fileScanResult.file_name : ""; color: ThemeManager.foreground(); font.pixelSize: 12; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                    Text { text: "Size:";   color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: fileScanResult ? fmtBytes(fileScanResult.file_size) : ""; color: ThemeManager.foreground(); font.pixelSize: 12 }
                                    Text { text: "SHA256:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text {
                                        text: fileScanResult && fileScanResult.sha256 ? fileScanResult.sha256.substring(0,32) + "..." : ""
                                        color: ThemeManager.foreground(); font.pixelSize: 11; font.family: "Consolas"; Layout.columnSpan: 3
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 10
                                    Repeater {
                                        model: [
                                            { lbl: "YARA",    val: fileScanResult ? (fileScanResult.yara_matches_count || 0).toString() : "0", b: fileScanResult && fileScanResult.yara_matches_count > 0 },
                                            { lbl: "IOCs",    val: fileScanResult && fileScanResult.iocs_found ? "!" : "OK",                    b: !!(fileScanResult && fileScanResult.iocs_found) },
                                            { lbl: "PE",      val: fileScanResult && fileScanResult.pe_analyzed ? "OK" : "-",                  b: false },
                                            { lbl: "Sandbox", val: fileScanResult && fileScanResult.has_sandbox ? "OK" : "-",                  b: false }
                                        ]
                                        Rectangle {
                                            Layout.preferredWidth: 80; height: 46; color: ThemeManager.surface(); radius: 8
                                            Column {
                                                anchors.centerIn: parent; spacing: 2
                                                Text { text: modelData.val; font.pixelSize: 17; font.bold: true; color: modelData.b ? ThemeManager.danger : ThemeManager.foreground(); anchors.horizontalCenter: parent.horizontalCenter }
                                                Text { text: modelData.lbl; font.pixelSize: 10; color: ThemeManager.muted(); anchors.horizontalCenter: parent.horizontalCenter }
                                            }
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                }

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 10
                                    Button {
                                        text: "Full Report"; Layout.preferredWidth: 120; Layout.preferredHeight: 38
                                        onClicked: { if (currentReportContent) reportPreviewDialog.showReport("Security Scan Report", currentReportContent, currentReportFileName, true) }
                                        background: Rectangle { color: parent.hovered ? Qt.lighter(ThemeManager.primary,1.1) : ThemeManager.primary; radius: 8 }
                                        contentItem: Text { text: parent.text; color: "#ffffff"; font.pixelSize: 12; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                    Button {
                                        text: "Scan Another"; Layout.preferredWidth: 120; Layout.preferredHeight: 38
                                        onClicked: { fileScanResult = null; currentReportContent = ""; selectedFilePath = ""; filePathInput.text = "" }
                                        background: Rectangle { color: parent.hovered ? ThemeManager.surface() : "transparent"; radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                                        contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }

                        // Features info (idle)
                        Rectangle {
                            Layout.fillWidth: true
                            height: featCol.implicitHeight + 32
                            color: ThemeManager.surface(); radius: 12
                            visible: !fileScanningInProgress && fileScanResult === null
                            ColumnLayout {
                                id: featCol
                                anchors { fill: parent; margins: 18 }
                                spacing: 10
                                Text { text: "Analysis Features (100% Offline)"; font.pixelSize: 13; font.bold: true; color: ThemeManager.foreground() }
                                GridLayout {
                                    Layout.fillWidth: true; columns: 2; columnSpacing: 24; rowSpacing: 6
                                    Repeater {
                                        model: [
                                            "SHA256 Hash Computation",   "PE Header Analysis",
                                            "Entropy Calculation",        "YARA Rule Matching",
                                            "IOC Extraction",             "Suspicious Import Detection",
                                            integratedSandboxAvailable ? "Process Sandbox (Job Object)" : "Process Sandbox (unavailable)",
                                            integratedSandboxAvailable ? "Network Blocking" : "Network Blocking (unavailable)"
                                        ]
                                        Text {
                                            text: (index < 6 || integratedSandboxAvailable ? "[OK] " : "[ ] ") + modelData
                                            font.pixelSize: 12
                                            color: (index < 6 || integratedSandboxAvailable) ? ThemeManager.muted() : ThemeManager.border()
                                        }
                                    }
                                }
                            }
                        }

                        Item { height: Theme.spacing_md }
                    }
                }
            }

            // ============================================================
            // URL CHECK TAB
            // ============================================================
            Item {
                id: urlCheckTab
                ScrollView {
                    anchors.fill: parent; clip: true; contentWidth: availableWidth
                    ColumnLayout {
                        width: urlCheckTab.width; spacing: Theme.spacing_md

                        // URL input card
                        Rectangle {
                            Layout.fillWidth: true
                            height: urlInputCol.implicitHeight + 36
                            color: ThemeManager.panel(); radius: 12; border.color: ThemeManager.border(); border.width: 1
                            ColumnLayout {
                                id: urlInputCol
                                anchors { fill: parent; margins: 18 }; spacing: 14
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: "URL Scanner"; font.pixelSize: 16; font.bold: true; color: ThemeManager.foreground() }
                                    Item { Layout.fillWidth: true }
                                    Rectangle {
                                        height: 24; width: urlBadge.implicitWidth + 16; radius: 12
                                        color: urlSandboxAvailable ? Qt.rgba(0,0.8,0.4,0.15) : Qt.rgba(1,0.8,0,0.15)
                                        Text { id: urlBadge; anchors.centerIn: parent; text: urlSandboxAvailable ? "Sandbox Ready" : "Static Only"; font.pixelSize: 11; color: urlSandboxAvailable ? ThemeManager.success : ThemeManager.warning }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 10
                                    Rectangle {
                                        Layout.fillWidth: true; height: 46; color: ThemeManager.surface(); radius: 8
                                        border.color: urlInput.activeFocus ? ThemeManager.primary : ThemeManager.border(); border.width: 1
                                        TextField {
                                            id: urlInput; anchors { fill: parent; margins: 2 }
                                            placeholderText: "Enter URL to analyze (e.g. https://example.com)"; maximumLength: 2048
                                            color: ThemeManager.foreground(); placeholderTextColor: ThemeManager.muted()
                                            font.pixelSize: 14; verticalAlignment: Text.AlignVCenter; leftPadding: 14
                                            background: Rectangle { color: "transparent" }
                                            Keys.onReturnPressed: startUrlCheck(); Keys.onEnterPressed: startUrlCheck()
                                        }
                                    }
                                    Button {
                                        text: urlCheckingInProgress ? "Scanning..." : "Scan URL"
                                        Layout.preferredWidth: 128; Layout.preferredHeight: 46
                                        enabled: !urlCheckingInProgress && urlInput.text.trim().length > 0
                                        onClicked: startUrlCheck()
                                        background: Rectangle { color: parent.enabled ? (parent.hovered ? Qt.lighter(ThemeManager.primary,1.1) : ThemeManager.primary) : ThemeManager.muted(); radius: 8 }
                                        contentItem: Text { text: parent.text; color: "#ffffff"; font.pixelSize: 13; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 28
                                    RowLayout {
                                        spacing: 8
                                        Rectangle {
                                            width: 44; height: 24; radius: 12; color: useUrlSandbox ? ThemeManager.primary : ThemeManager.surface(); border.color: ThemeManager.border(); opacity: urlSandboxAvailable ? 1.0 : 0.5
                                            Rectangle { x: useUrlSandbox ? parent.width-width-3 : 3; anchors.verticalCenter: parent.verticalCenter; width: 18; height: 18; radius: 9; color: "#ffffff"; Behavior on x { NumberAnimation { duration: 140 } } }
                                            MouseArea { anchors.fill: parent; enabled: urlSandboxAvailable && !urlCheckingInProgress; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: useUrlSandbox = !useUrlSandbox }
                                        }
                                        Text { text: "Sandbox Detonation"; font.pixelSize: 13; color: urlSandboxAvailable ? ThemeManager.foreground() : ThemeManager.muted() }
                                    }
                                    RowLayout {
                                        spacing: 8
                                        Rectangle {
                                            width: 44; height: 24; radius: 12; color: blockPrivateIPs ? ThemeManager.accent : ThemeManager.surface(); border.color: ThemeManager.border()
                                            Rectangle { x: blockPrivateIPs ? parent.width-width-3 : 3; anchors.verticalCenter: parent.verticalCenter; width: 18; height: 18; radius: 9; color: "#ffffff"; Behavior on x { NumberAnimation { duration: 140 } } }
                                            MouseArea { anchors.fill: parent; enabled: !urlCheckingInProgress; cursorShape: Qt.PointingHandCursor; onClicked: blockPrivateIPs = !blockPrivateIPs }
                                        }
                                        Text { text: "Block Private IPs"; font.pixelSize: 13; color: ThemeManager.foreground() }
                                    }
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }

                        // Progress
                        Rectangle {
                            Layout.fillWidth: true; height: 78; color: ThemeManager.panel(); radius: 12; visible: urlCheckingInProgress
                            ColumnLayout { anchors { fill: parent; margins: 14 }; spacing: 8
                                RowLayout { Layout.fillWidth: true
                                    BusyIndicator { running: urlCheckingInProgress; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
                                    Text { text: urlScanStage || "Analyzing..."; font.pixelSize: 13; color: ThemeManager.foreground() }
                                    Item { Layout.fillWidth: true }
                                    Text { text: urlScanProgressValue + "%"; font.pixelSize: 13; font.bold: true; color: ThemeManager.primary }
                                    Button {
                                        text: "Cancel"; Layout.preferredWidth: 72; Layout.preferredHeight: 26; onClicked: cancelUrlCheck()
                                        background: Rectangle { color: parent.hovered ? ThemeManager.danger : "transparent"; radius: 6; border.color: ThemeManager.danger; border.width: 1 }
                                        contentItem: Text { text: parent.text; color: parent.hovered ? "#ffffff" : ThemeManager.danger; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                }
                                Rectangle { Layout.fillWidth: true; height: 5; color: ThemeManager.surface(); radius: 3
                                    Rectangle { width: parent.width*(urlScanProgressValue/100); height: parent.height; color: ThemeManager.primary; radius: 3; Behavior on width { NumberAnimation { duration: 200 } } }
                                }
                            }
                        }

                        // URL Results card
                        Rectangle {
                            Layout.fillWidth: true
                            height: urlResCol.implicitHeight + 36
                            color: ThemeManager.panel(); radius: 12; border.width: 2
                            border.color: {
                                if (!urlCheckResult) return ThemeManager.border()
                                var v = urlCheckResult.verdict || ""
                                if (v === "malicious" || v === "likely_malicious") return ThemeManager.danger
                                if (v === "suspicious") return ThemeManager.warning
                                return ThemeManager.success
                            }
                            visible: urlCheckResult !== null && urlCheckResult.success !== false

                            ColumnLayout {
                                id: urlResCol; anchors { fill: parent; margins: 20 }; spacing: 16

                                RowLayout {
                                    Layout.fillWidth: true; spacing: 14
                                    ColumnLayout {
                                        spacing: 2
                                        Text { text: verdictLabel(urlCheckResult ? urlCheckResult.verdict : ""); font.pixelSize: 22; font.bold: true; color: verdictColor(urlCheckResult ? urlCheckResult.verdict : "") }
                                        Text { text: urlCheckResult && urlCheckResult.explanation ? urlCheckResult.explanation.confidence + " confidence" : ""; font.pixelSize: 11; color: ThemeManager.muted() }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Rectangle {
                                        width: 72; height: 72; radius: 36; color: "transparent"
                                        border.color: scoreColor(urlCheckResult ? urlCheckResult.score : 0); border.width: 6
                                        ColumnLayout { anchors.centerIn: parent; spacing: 0
                                            Text { text: urlCheckResult ? urlCheckResult.score : 0; font.pixelSize: 22; font.bold: true; color: scoreColor(urlCheckResult ? urlCheckResult.score : 0); Layout.alignment: Qt.AlignHCenter }
                                            Text { text: "/100"; font.pixelSize: 10; color: ThemeManager.muted(); Layout.alignment: Qt.AlignHCenter }
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: explainInner.implicitHeight + 24
                                    color: ThemeManager.surface(); radius: 8
                                    visible: !!(urlCheckResult && urlCheckResult.explanation)
                                    ColumnLayout {
                                        id: explainInner; anchors { fill: parent; margins: 12 }; spacing: 10
                                        Repeater {
                                            model: [
                                                { h: "What It Is",     k: "what_it_is",  c: ThemeManager.primary },
                                                { h: "Risk",           k: "why_risky",   c: ThemeManager.warning },
                                                { h: "Recommendation", k: "what_to_do",  c: ThemeManager.success }
                                            ]
                                            ColumnLayout { spacing: 3
                                                Text { text: modelData.h; font.pixelSize: 11; font.bold: true; color: modelData.c }
                                                Text { text: urlCheckResult && urlCheckResult.explanation ? (urlCheckResult.explanation[modelData.k]||"") : ""; font.pixelSize: 12; color: ThemeManager.foreground(); wrapMode: Text.Wrap; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

                                GridLayout { Layout.fillWidth: true; columns: 2; columnSpacing: 16; rowSpacing: 6
                                    Text { text: "URL:";         color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: urlCheckResult ? (urlCheckResult.url||"") : ""; color: ThemeManager.foreground(); font.pixelSize: 12; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                    Text { text: "Final URL:";   color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: urlCheckResult ? (urlCheckResult.final_url||"") : ""; color: (urlCheckResult && urlCheckResult.url !== urlCheckResult.final_url) ? ThemeManager.warning : ThemeManager.foreground(); font.pixelSize: 12; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                    Text { text: "HTTP Status:"; color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: urlCheckResult && urlCheckResult.http_status ? urlCheckResult.http_status.toString() : "N/A"; color: ThemeManager.foreground(); font.pixelSize: 12 }
                                    Text { text: "Redirects:";   color: ThemeManager.muted(); font.pixelSize: 12 }
                                    Text { text: urlCheckResult ? (urlCheckResult.redirect_count||0).toString() : "0"; color: (urlCheckResult && urlCheckResult.redirect_count > 2) ? ThemeManager.warning : ThemeManager.foreground(); font.pixelSize: 12 }
                                }

                                Rectangle {
                                    Layout.fillWidth: true; height: evListCol.implicitHeight + 20
                                    color: ThemeManager.surface(); radius: 8; visible: !!(urlCheckResult && urlCheckResult.evidence && urlCheckResult.evidence.length > 0)
                                    ColumnLayout { id: evListCol; anchors { fill: parent; margins: 10 }; spacing: 6
                                        Text { text: "Evidence (" + (urlCheckResult ? urlCheckResult.evidence_count : 0) + " findings)"; font.pixelSize: 12; font.bold: true; color: ThemeManager.foreground() }
                                        Repeater {
                                            model: urlCheckResult && urlCheckResult.evidence ? urlCheckResult.evidence : []
                                            Rectangle {
                                                Layout.fillWidth: true; height: evItemRow.implicitHeight + 14; radius: 6; border.width: 1
                                                color: Qt.rgba(severityColor(modelData.severity).r, severityColor(modelData.severity).g, severityColor(modelData.severity).b, 0.1)
                                                border.color: severityColor(modelData.severity)
                                                RowLayout { id: evItemRow; anchors { fill: parent; margins: 7 }; spacing: 10
                                                    Rectangle { width: 54; height: 20; radius: 4; color: severityColor(modelData.severity); Text { anchors.centerIn: parent; text: modelData.severity ? modelData.severity.toUpperCase() : "INFO"; font.pixelSize: 9; font.bold: true; color: "#ffffff" } }
                                                    ColumnLayout { Layout.fillWidth: true; spacing: 1
                                                        Text { text: modelData.title || ""; font.pixelSize: 12; font.bold: true; color: ThemeManager.foreground() }
                                                        Text { text: modelData.detail || ""; font.pixelSize: 11; color: ThemeManager.muted(); wrapMode: Text.Wrap; Layout.fillWidth: true }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                RowLayout { Layout.fillWidth: true; spacing: 10
                                    Button {
                                        text: "Full Report"; Layout.preferredWidth: 120; Layout.preferredHeight: 38
                                        visible: !!(currentReportContent && urlCheckResult)
                                        onClicked: { if (currentReportContent) reportPreviewDialog.showReport("URL Safety Report", currentReportContent, currentReportFileName, false) }
                                        background: Rectangle { color: parent.hovered ? Qt.lighter(ThemeManager.primary,1.1) : ThemeManager.primary; radius: 8 }
                                        contentItem: Text { text: parent.text; color: "#ffffff"; font.pixelSize: 12; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                    Button {
                                        text: "Check Another"; Layout.preferredWidth: 120; Layout.preferredHeight: 38
                                        onClicked: { urlCheckResult = null; currentReportContent = ""; urlInput.text = "" }
                                        background: Rectangle { color: parent.hovered ? ThemeManager.surface() : "transparent"; radius: 8; border.color: ThemeManager.border(); border.width: 1 }
                                        contentItem: Text { text: parent.text; color: ThemeManager.foreground(); font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                    }
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }

                        // Error card
                        Rectangle {
                            Layout.fillWidth: true; height: 88
                            color: Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.08)
                            radius: 12; border.color: ThemeManager.danger; border.width: 1
                            visible: urlCheckResult !== null && urlCheckResult.success === false
                            RowLayout { anchors { fill: parent; margins: 18 }; spacing: 14
                                Text { text: "X"; font.pixelSize: 28; color: ThemeManager.danger }
                                ColumnLayout { Layout.fillWidth: true; spacing: 3
                                    Text { text: "Scan Failed"; font.pixelSize: 15; font.bold: true; color: ThemeManager.danger }
                                    Text { text: urlCheckResult && urlCheckResult.error ? urlCheckResult.error : "Unknown error"; font.pixelSize: 12; color: ThemeManager.foreground(); wrapMode: Text.Wrap; Layout.fillWidth: true }
                                }
                            }
                        }

                        // Features info (idle)
                        Rectangle {
                            Layout.fillWidth: true; height: urlFeatCol.implicitHeight + 32
                            color: ThemeManager.surface(); radius: 12
                            visible: !urlCheckingInProgress && urlCheckResult === null
                            ColumnLayout { id: urlFeatCol; anchors { fill: parent; margins: 18 }; spacing: 12
                                Text { text: "Local URL Analysis"; font.pixelSize: 15; font.bold: true; color: ThemeManager.foreground() }
                                Text { text: "100% local - no data sent to external servers"; font.pixelSize: 12; color: ThemeManager.muted() }
                                GridLayout { Layout.fillWidth: true; columns: 2; columnSpacing: 32; rowSpacing: 6
                                    Repeater {
                                        model: [
                                            "URL normalization & validation", "Suspicious TLD detection",
                                            "Punycode / homograph detection",  "Redirect chain tracking",
                                            "Content analysis & forms",        "JavaScript obfuscation check",
                                            "IOC extraction (IPs, domains)",   "YARA rule matching",
                                            "Evidence-based scoring",          "AI-powered explanations"
                                        ]
                                        Text { text: "[OK] " + modelData; font.pixelSize: 12; color: ThemeManager.muted() }
                                    }
                                }
                                RowLayout { spacing: 8
                                    Text { text: urlSandboxAvailable ? "Sandbox detonation available (WebView2)" : "Static analysis only - WebView2 not found"; font.pixelSize: 12; color: urlSandboxAvailable ? ThemeManager.success : ThemeManager.muted() }
                                }
                            }
                        }

                        Item { height: Theme.spacing_md }
                    }
                }
            }
        }
    }

    // ============================================================
    // REPORT PREVIEW DIALOG
    // ============================================================
    ReportPreviewDialog {
        id: reportPreviewDialog
        parent: Overlay.overlay
        onSaveRequested: function(filePath) { if (Backend && currentReportContent) Backend.saveReportToFile(currentReportContent, filePath) }
        onCopyRequested: { if (Backend && currentReportContent) Backend.copyToClipboard(currentReportContent) }
    }
}
