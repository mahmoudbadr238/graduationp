import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
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
        function onStartMinimizedChanged() {
            minimizeToTraySwitch.reloadFromService()
        }
        function onEnableGpuMonitoringChanged() {
            gpuSwitch.reloadFromService()
        }
        function onSendErrorReportsChanged() {
            telemetrySwitch.reloadFromService()
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

                            ComboBox {
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
                                        console.log("[SettingsPage] Theme changed to:", modes[currentIndex])
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

                                background: Rectangle {
                                    color: ThemeManager.surface()
                                    radius: 6
                                    border.color: ThemeManager.border()
                                    border.width: 1
                                }
                                contentItem: Text {
                                    text: themeModeCombo.currentText
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    leftPadding: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                                delegate: ItemDelegate {
                                    width: themeModeCombo.width
                                    contentItem: Text {
                                        text: modelData
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    background: Rectangle {
                                        color: highlighted ? ThemeManager.elevated() : ThemeManager.surface()
                                    }
                                }
                                popup: Popup {
                                    y: themeModeCombo.height
                                    width: themeModeCombo.width
                                    implicitHeight: contentItem.implicitHeight
                                    padding: 1
                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: themeModeCombo.popup.visible ? themeModeCombo.delegateModel : null
                                    }
                                    background: Rectangle {
                                        color: ThemeManager.surface()
                                        border.color: ThemeManager.border()
                                        radius: 6
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

                            ComboBox {
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
                                        console.log("[SettingsPage] Font size changed to:", sizes[currentIndex])
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

                                background: Rectangle {
                                    color: ThemeManager.surface()
                                    radius: 6
                                    border.color: ThemeManager.border()
                                    border.width: 1
                                }
                                contentItem: Text {
                                    text: fontSizeCombo.currentText
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                    leftPadding: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                                delegate: ItemDelegate {
                                    width: fontSizeCombo.width
                                    contentItem: Text {
                                        text: modelData
                                        color: ThemeManager.foreground()
                                        font.pixelSize: ThemeManager.fontSize_body
                                    }
                                    background: Rectangle {
                                        color: highlighted ? ThemeManager.elevated() : ThemeManager.surface()
                                    }
                                }
                                popup: Popup {
                                    y: fontSizeCombo.height
                                    width: fontSizeCombo.width
                                    implicitHeight: contentItem.implicitHeight
                                    padding: 1
                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: fontSizeCombo.popup.visible ? fontSizeCombo.delegateModel : null
                                    }
                                    background: Rectangle {
                                        color: ThemeManager.surface()
                                        border.color: ThemeManager.border()
                                        radius: 6
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

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Live Monitoring:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            Switch {
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
                                text: "Update Interval (sec):"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            SpinBox {
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
                                text: "Monitor GPU:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            Switch {
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
                                    text: "Adds Sentinel to Windows startup via Registry"
                                    color: ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_small
                                }
                            }

                            Switch {
                                id: startupSwitch

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
                                    text: "Minimize to Tray:"
                                    color: ThemeManager.foreground()
                                    font.pixelSize: ThemeManager.fontSize_body
                                }
                                Text {
                                    text: "Keep running in the system tray when closed"
                                    color: ThemeManager.muted()
                                    font.pixelSize: ThemeManager.fontSize_small
                                }
                            }

                            Switch {
                                id: minimizeToTraySwitch

                                property bool isInitializing: true

                                Component.onCompleted: {
                                    reloadFromService()
                                    isInitializing = false
                                }

                                onCheckedChanged: {
                                    if (isInitializing) return
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        SettingsService.startMinimized = checked
                                    }
                                }

                                function reloadFromService() {
                                    isInitializing = true
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        checked = SettingsService.startMinimized
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

                // ===== PRIVACY SECTION =====
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: privacyContent.implicitHeight + 48
                    color: ThemeManager.panel()
                    radius: 12
                    border.color: ThemeManager.border()
                    border.width: 1

                    ColumnLayout {
                        id: privacyContent
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 20

                        Text {
                            text: "Privacy"
                            font.pixelSize: ThemeManager.fontSize_h3
                            font.bold: true
                            color: ThemeManager.foreground()
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            Text {
                                text: "Send Error Reports:"
                                color: ThemeManager.foreground()
                                font.pixelSize: ThemeManager.fontSize_body
                                Layout.preferredWidth: 200
                            }

                            Switch {
                                id: telemetrySwitch

                                property bool isInitializing: true

                                Component.onCompleted: {
                                    reloadFromService()
                                    isInitializing = false
                                }

                                onCheckedChanged: {
                                    if (isInitializing) return
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        SettingsService.sendErrorReports = checked
                                    }
                                }

                                function reloadFromService() {
                                    isInitializing = true
                                    if (typeof SettingsService !== 'undefined' && SettingsService) {
                                        checked = SettingsService.sendErrorReports
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
                                    text: "Restore all settings to their original defaults"
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
