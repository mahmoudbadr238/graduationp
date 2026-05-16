import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../ui"

Item {
    id: root

    property int fontSizeTrigger: ThemeManager.fontSizeUpdateTrigger
    property int themeTrigger: ThemeManager.themeModeUpdateTrigger

    // ── Reactive sync: when SettingsService signals fire, reload UI ──
    Connections {
        target: typeof SettingsService !== "undefined" ? SettingsService : null
        enabled: target !== null

        function onThemeModeChanged() {
            themeModeCombo.reloadThemeMode()
        }
        function onFontSizeChanged() {
            fontSizeCombo.reloadFontSize()
        }
        function onStartWithSystemChanged() {
            startupSwitch.reloadFromService()
        }
        function onCloseToTrayChanged() {
            minimizeToTraySwitch.reloadFromService()
        }
        function onEnableGpuMonitoringChanged() {
            gpuSwitch.reloadFromService()
        }
        function onUpdateIntervalMsChanged() {
            intervalSpinner.reloadFromService()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()

        Flickable {
            anchors.fill: parent
            anchors.margins: 32
            contentWidth: width
            contentHeight: mainColumn.implicitHeight
            clip: true

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            ColumnLayout {
                id: mainColumn
                width: parent.width
                spacing: 24

                // Page Title
                Text {
                    text: "Settings"
                    font.pixelSize: ThemeManager.fontSize_h1
                    font.bold: true
                    color: ThemeManager.foreground()
                }

                Text {
                    text: "Manage local preferences, startup behavior, and runtime controls that are supported in this session."
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_body
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.bottomMargin: 10
                }

                // ===== APPEARANCE SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: appearanceContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: appearanceContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "Appearance"
                            font.pixelSize: ThemeManager.fontSize_h3
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        Text {
                            text: "Theme and typography choices apply locally to this device."
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        // Theme Mode Row
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Theme Mode:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            StyledComboBox {
                                id: themeModeCombo
                                model: ["Light", "Dark", "System"]
                                Layout.fillWidth: true
                                Layout.maximumWidth: 300

                                property bool isInitializing: true

                                Component.onCompleted: {
                                    reloadThemeMode()
                                    isInitializing = false
                                }

                                onCurrentIndexChanged: {
                                    if (isInitializing) return
                                    var modes = ["light", "dark", "system"]
                                    if (currentIndex >= 0 && currentIndex < modes.length) {
                                        ThemeManager.setThemeMode(modes[currentIndex])
                                    }
                                }

                                function reloadThemeMode() {
                                    var modes = ["light", "dark", "system"]
                                    var savedMode = SettingsService ? SettingsService.themeMode : "dark"
                                    var newIndex = modes.indexOf(savedMode)
                                    if (newIndex >= 0) {
                                        isInitializing = true
                                        currentIndex = newIndex
                                        isInitializing = false
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }

                        // Font Size Row
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Font Size:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            StyledComboBox {
                                id: fontSizeCombo
                                model: ["Small", "Medium", "Large"]
                                Layout.fillWidth: true
                                Layout.maximumWidth: 300

                                property bool isInitializing: true

                                Component.onCompleted: {
                                    reloadFontSize()
                                    isInitializing = false
                                }

                                onCurrentIndexChanged: {
                                    if (isInitializing) return
                                    var sizes = ["small", "medium", "large"]
                                    if (currentIndex >= 0 && currentIndex < sizes.length) {
                                        ThemeManager.setFontSize(sizes[currentIndex])
                                    }
                                }

                                function reloadFontSize() {
                                    var sizes = ["small", "medium", "large"]
                                    var savedSize = SettingsService ? SettingsService.fontSize : "medium"
                                    var newIndex = sizes.indexOf(savedSize)
                                    if (newIndex >= 0) {
                                        isInitializing = true
                                        currentIndex = newIndex
                                        isInitializing = false
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                // ===== MONITORING SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: monitoringContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: monitoringContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "Monitoring"
                            font.pixelSize: ThemeManager.fontSize_h3
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        Text {
                            text: "Controls dashboard telemetry refresh and optional GPU polling. These settings do not override real-time protection safety checks."
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Background Telemetry:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            StyledSwitch {
                                id: liveMonitoringSwitch
                                checked: true

                                Component.onCompleted: {
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        checked = SettingsService.liveMonitoring
                                    } else if (typeof Backend !== 'undefined' && Backend && Backend.live !== undefined) {
                                        checked = Backend.live
                                    }
                                }

                                onCheckedChanged: {
                                    // Persist the toggle state
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        SettingsService.liveMonitoring = checked
                                    }
                                    // Start / stop backend monitoring
                                    if (typeof Backend !== 'undefined' && Backend) {
                                        if (checked) Backend.startLive()
                                        else Backend.stopLive()
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Telemetry Refresh (sec):"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            StyledSpinBox {
                                id: intervalSpinner
                                from: 1
                                to: 60
                                value: 2
                                Layout.preferredWidth: 120

                                property bool isInitializing: true

                                Component.onCompleted: {
                                    reloadFromService()
                                    isInitializing = false
                                }

                                onValueChanged: {
                                    if (isInitializing) return
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        SettingsService.updateIntervalMs = value * 1000
                                    }
                                }

                                function reloadFromService() {
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        isInitializing = true
                                        value = SettingsService.updateIntervalMs / 1000
                                        isInitializing = false
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "GPU Telemetry:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            StyledSwitch {
                                id: gpuSwitch

                                property bool isInitializing: true

                                Component.onCompleted: {
                                    reloadFromService()
                                    isInitializing = false
                                }

                                onCheckedChanged: {
                                    if (isInitializing) return
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        SettingsService.enableGpuMonitoring = checked
                                    }
                                }

                                function reloadFromService() {
                                    isInitializing = true
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        checked = SettingsService.enableGpuMonitoring
                                    } else {
                                        checked = true
                                    }
                                    isInitializing = false
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                // ===== AI CONFIGURATION SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: aiContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: aiContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "AI Configuration"
                            font.pixelSize: ThemeManager.fontSize_h3
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        Text {
                            text: "Cloud AI features (event explanation, Security Assistant) require a free Groq API key. Get one at console.groq.com/keys."
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        // ── Status chip ──────────────────────────────────
                        Rectangle {
                            Layout.fillWidth: true
                            height: 36
                            radius: 8
                            color: {
                                if (groqStatusLabel.text === "Configured")
                                    return Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.12)
                                if (groqStatusLabel.text === "Not configured")
                                    return Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.12)
                                return Qt.rgba(ThemeManager.info.r, ThemeManager.info.g, ThemeManager.info.b, 0.12)
                            }
                            border.color: {
                                if (groqStatusLabel.text === "Configured")   return ThemeManager.success
                                if (groqStatusLabel.text === "Not configured") return ThemeManager.warning
                                return ThemeManager.info
                            }
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 8

                                Text {
                                    id: groqStatusLabel
                                    text: {
                                        var svc = (typeof SettingsService !== "undefined") ? SettingsService : null
                                        if (!svc) return "Settings unavailable"
                                        return svc.groqApiKeyConfigured ? "Configured" : "Not configured"
                                    }
                                    color: {
                                        if (text === "Configured")     return ThemeManager.success
                                        if (text === "Not configured") return ThemeManager.warning
                                        return ThemeManager.info
                                    }
                                    font.pixelSize: ThemeManager.fontSize_small
                                    font.bold: true
                                }

                                Text {
                                    id: groqTestStatusText
                                    text: ""
                                    color: text.indexOf("valid") >= 0 ? ThemeManager.success : ThemeManager.danger
                                    font.pixelSize: ThemeManager.fontSize_small
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                            }
                        }

                        // ── Key input row ─────────────────────────────────
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            // Show the masked saved key as placeholder;
                            // clear it when the user starts typing a new one.
                            StyledTextField {
                                id: groqKeyField
                                Layout.fillWidth: true
                                placeholderText: {
                                    var svc = (typeof SettingsService !== "undefined") ? SettingsService : null
                                    if (svc && svc.groqApiKeyConfigured)
                                        return svc.groqApiKeyMasked || "••••••••••••"
                                    return "gsk_..."
                                }
                                echoMode: groqKeyVisible.checked ? TextInput.Normal : TextInput.Password
                                // Prevent the masked placeholder from being saved as the key
                                property bool hasNewInput: text.length > 0
                            }

                            // Show / hide toggle
                            Rectangle {
                                id: groqKeyVisible
                                property bool checked: false
                                width: 34
                                height: 34
                                radius: 6
                                color: checked
                                       ? Qt.rgba(ThemeManager.accent.r, ThemeManager.accent.g, ThemeManager.accent.b, 0.18)
                                       : ThemeManager.elevated()
                                border.color: ThemeManager.border()
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: parent.checked ? "🙈" : "👁"
                                    font.pixelSize: 14
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: parent.checked = !parent.checked
                                }
                            }
                        }

                        // ── Action buttons ────────────────────────────────
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            // Save button
                            Rectangle {
                                width: saveBtnText.implicitWidth + 28
                                height: 36
                                radius: 8
                                color: saveMa.containsMouse
                                       ? Qt.lighter(ThemeManager.accent, 1.15) : ThemeManager.accent

                                Text {
                                    id: saveBtnText
                                    anchors.centerIn: parent
                                    text: "Save Key"
                                    font.pixelSize: ThemeManager.fontSize_small
                                    font.bold: true
                                    color: ThemeManager.selectionForeground
                                }

                                MouseArea {
                                    id: saveMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var svc = (typeof SettingsService !== "undefined") ? SettingsService : null
                                        if (!svc) return
                                        var newKey = groqKeyField.text.trim()
                                        if (!groqKeyField.hasNewInput) {
                                            // Nothing typed — no-op
                                            return
                                        }
                                        svc.saveGroqApiKey(newKey)
                                        groqKeyField.text = ""
                                        groqTestStatusText.text = newKey ? "Key saved." : "Key cleared."
                                    }
                                }
                            }

                            // Clear button (only shown when configured)
                            Rectangle {
                                visible: {
                                    var svc = (typeof SettingsService !== "undefined") ? SettingsService : null
                                    return svc ? svc.groqApiKeyConfigured : false
                                }
                                width: clearBtnText.implicitWidth + 28
                                height: 36
                                radius: 8
                                color: clearMa.containsMouse
                                       ? Qt.lighter(ThemeManager.danger, 1.15) : ThemeManager.danger

                                Text {
                                    id: clearBtnText
                                    anchors.centerIn: parent
                                    text: "Clear Key"
                                    font.pixelSize: ThemeManager.fontSize_small
                                    font.bold: true
                                    color: "#ffffff"
                                }

                                MouseArea {
                                    id: clearMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var svc = (typeof SettingsService !== "undefined") ? SettingsService : null
                                        if (svc) {
                                            svc.saveGroqApiKey("")
                                            groqKeyField.text = ""
                                            groqTestStatusText.text = "Key cleared."
                                        }
                                    }
                                }
                            }

                            // Test Connection button
                            Rectangle {
                                width: testBtnText.implicitWidth + 28
                                height: 36
                                radius: 8
                                property bool testing: false
                                color: testing ? ThemeManager.elevated()
                                               : (testMa.containsMouse ? ThemeManager.elevated() : ThemeManager.surface())
                                border.color: ThemeManager.border()
                                border.width: 1

                                Text {
                                    id: testBtnText
                                    anchors.centerIn: parent
                                    text: parent.testing ? "Testing…" : "Test Connection"
                                    font.pixelSize: ThemeManager.fontSize_small
                                    color: ThemeManager.foreground()
                                }

                                MouseArea {
                                    id: testMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var svc = (typeof SettingsService !== "undefined") ? SettingsService : null
                                        if (!svc) return
                                        parent.testing = true
                                        groqTestStatusText.text = "Connecting…"
                                        svc.testGroqConnection()
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }
                    }

                    // React to key changes and test results
                    Connections {
                        target: typeof SettingsService !== "undefined" ? SettingsService : null
                        function onGroqApiKeyChanged() {
                            // Refresh the status chip label binding
                            groqStatusLabel.text = Qt.binding(function() {
                                var svc = (typeof SettingsService !== "undefined") ? SettingsService : null
                                if (!svc) return "Settings unavailable"
                                return svc.groqApiKeyConfigured ? "Configured" : "Not configured"
                            })
                        }
                        function onGroqTestResult(status, message) {
                            // Find the test button Rectangle and clear the testing flag
                            testBtnText.parent.testing = false
                            groqTestStatusText.text = message
                        }
                    }
                }

                // ===== STARTUP SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: startupContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: startupContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "Startup"
                            font.pixelSize: ThemeManager.fontSize_h3
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        Text {
                            text: "Startup and tray options are capability-gated so unsupported behavior is not advertised as active."
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            ColumnLayout {
                                Layout.preferredWidth: 200
                                spacing: 2
                                Text {
                                    text: "Run on Startup:"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                }
                                Text {
                                    text: (typeof SettingsService !== "undefined" && SettingsService && SettingsService.supportsAutostart)
                                          ? "Starts Sentinel automatically when you sign in on supported Windows builds"
                                          : "Autostart is not configured for this platform in the current release"
                                    color: ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_small
                                }
                            }

                            StyledSwitch {
                                id: startupSwitch
                                enabled: typeof SettingsService !== "undefined" && SettingsService && SettingsService.supportsAutostart

                                property bool isInitializing: true

                                Component.onCompleted: {
                                    reloadFromService()
                                    isInitializing = false
                                }

                                onCheckedChanged: {
                                    if (isInitializing) return
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        SettingsService.startWithSystem = checked
                                    }
                                }

                                function reloadFromService() {
                                    isInitializing = true
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        checked = SettingsService.startWithSystem
                                    } else {
                                        checked = false
                                    }
                                    isInitializing = false
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            ColumnLayout {
                                Layout.preferredWidth: 200
                                spacing: 2
                                Text {
                                    text: "Close to Tray:"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                }
                                Text {
                                    text: (typeof SettingsService !== "undefined" && SettingsService && SettingsService.supportsCloseToTray)
                                          ? "Keep Sentinel running in the system tray when the main window is closed"
                                          : "System tray is not available in this session"
                                    color: ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_small
                                }
                            }

                            StyledSwitch {
                                id: minimizeToTraySwitch
                                enabled: typeof SettingsService !== "undefined" && SettingsService && SettingsService.supportsCloseToTray

                                property bool isInitializing: true

                                Component.onCompleted: {
                                    reloadFromService()
                                    isInitializing = false
                                }

                                onCheckedChanged: {
                                    if (isInitializing) return
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        SettingsService.closeToTray = checked
                                    }
                                }

                                function reloadFromService() {
                                    isInitializing = true
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        checked = SettingsService.closeToTray
                                    } else {
                                        checked = false
                                    }
                                    isInitializing = false
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                // ===== DIAGNOSTICS SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: diagnosticsContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: diagnosticsContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        Text {
                            text: "Diagnostics"
                            font.pixelSize: ThemeManager.fontSize_h3
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        Text {
                            text: "Crash and support diagnostics stay local in this release."
                            color: ThemeManager.muted()
                            font.pixelSize: ThemeManager.fontSize_small
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 10
                            color: Qt.rgba(ThemeManager.info.r, ThemeManager.info.g, ThemeManager.info.b, 0.10)
                            border.color: Qt.rgba(ThemeManager.info.r, ThemeManager.info.g, ThemeManager.info.b, 0.32)
                            border.width: 1
                            implicitHeight: diagnosticsNotice.implicitHeight + 24

                            Text {
                                id: diagnosticsNotice
                                anchors.fill: parent
                                anchors.margins: 12
                                text: "Sentinel does not automatically send error reports in this build. Diagnostic output remains on the device until you export or review it manually."
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }

                // ===== RESET SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: resetContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: resetContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        Text {
                            text: "Danger Zone"
                            font.pixelSize: ThemeManager.fontSize_h3
                            font.bold: true
                            color: ThemeManager.danger
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    text: "Reset All Settings"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    font.bold: true
                                }
                                Text {
                                    text: "Resets local preferences only. History, quarantine records, and scan results stay intact."
                                    color: ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_small
                                }
                            }

                            Rectangle {
                                width: resetBtnText.implicitWidth + 24
                                height: 34
                                radius: 8
                                color: resetMouse.containsMouse
                                       ? Qt.lighter(ThemeManager.danger, 1.15)
                                       : ThemeManager.danger

                                Text {
                                    id: resetBtnText
                                    anchors.centerIn: parent
                                    text: "Reset to Defaults"
                                    font.pixelSize: ThemeManager.fontSize_small
                                    font.bold: true
                                    color: "#ffffff"
                                }

                                MouseArea {
                                    id: resetMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof SettingsService !== 'undefined' && SettingsService) {
                                            SettingsService.resetToDefaults()
                                            // Sync ThemeManager
                                            ThemeManager.setThemeMode("dark")
                                            ThemeManager.setFontSize("medium")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Spacer
                Item { Layout.preferredHeight: 40 }
            }
        }
    }
}
