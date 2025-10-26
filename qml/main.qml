import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import "components"
import "pages"
import "theme"

ApplicationWindow {
    id: window
    visible: true
    width: 1400
    height: 900
    minimumWidth: 800
    minimumHeight: 600
    title: "Sentinel - Endpoint Security Suite v1.0.0"
    color: Theme.bg

    // Smooth theme transition
    Behavior on color {
        ColorAnimation { duration: Theme.duration.medium; easing.type: Easing.InOutQuad }
    }

    property bool sidebarCollapsed: false
    property int sidebarWidth: sidebarCollapsed ? Theme.spacing.xl * 4 : Theme.spacing.xl * 12

    // Settings persistence
    Settings {
        id: appSettings
        property string themeMode: "dark"
    }

    // Global toast manager
    ToastManager {
        id: globalToast
        anchors.fill: parent
        z: Theme.zIndex.toast
    }

    // Global snapshot data storage
    property var globalSnapshotData: ({
        "cpu": {"usage": 0, "freq_current": 0, "core_count": 0},
        "mem": {"used": 0, "total": 0, "percent": 0},
        "gpu": {"available": false, "usage": 0},
        "net": {"send_rate": 0, "recv_rate": 0},
        "disk": {"used": 0, "total": 0, "percent": 0}
    })

      // Listen for backend updates globally
    Connections {
        target: typeof Backend !== 'undefined' ? Backend : null

        function onSnapshotUpdated(data) {
            window.globalSnapshotData = data
        }

        function onToast(level, message) {
            globalToast.show(level, message)
        }
    }

    Component.onCompleted: {
        // Restore saved theme
        var savedTheme = appSettings.themeMode
        if (savedTheme) {
            Theme.themeMode = savedTheme
        }

        // Start live monitoring immediately when app loads
        if (typeof Backend !== 'undefined') {
            Backend.startLive()
            console.log("✓ Live monitoring started globally")
        } else {
            console.log("⚠ Backend not available")
        }
    }

    // Save theme changes
    Connections {
        target: Theme
        function onThemeModeChanged() {
            appSettings.themeMode = Theme.themeMode
        }
    }    // Keyboard shortcuts
    Shortcut {
        sequence: "Ctrl+1"
        onActivated: sidebar.setCurrentIndex(0)
    }
    Shortcut {
        sequence: "Ctrl+2"
        onActivated: sidebar.setCurrentIndex(1)
    }
    Shortcut {
        sequence: "Ctrl+3"
        onActivated: sidebar.setCurrentIndex(2)
    }
    Shortcut {
        sequence: "Ctrl+4"
        onActivated: sidebar.setCurrentIndex(3)
    }
    Shortcut {
        sequence: "Ctrl+5"
        onActivated: sidebar.setCurrentIndex(4)
    }
    Shortcut {
        sequence: "Ctrl+6"
        onActivated: sidebar.setCurrentIndex(5)
    }
    Shortcut {
        sequence: "Ctrl+7"
        onActivated: sidebar.setCurrentIndex(6)
    }
    Shortcut {
        sequence: "Esc"
        onActivated: sidebar.setCurrentIndex(0)  // Return to Event Viewer
    }
    
    Behavior on sidebarWidth {
        NumberAnimation { duration: Theme.duration.fast; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TopStatusBar {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            SidebarNav {
                id: sidebar
                Layout.preferredWidth: sidebarWidth
                Layout.fillHeight: true

                onNavigationChanged: function(index) {
                    stackView.replace(pageComponents[index])
                }
            }

            StackView {
                id: stackView
                Layout.fillWidth: true
                Layout.fillHeight: true
                initialItem: pageComponents[0]

                replaceEnter: Transition {
                    NumberAnimation {
                        property: "opacity"
                        from: 0.0
                        to: 1.0
                        duration: Theme.duration_fast
                        easing.type: Easing.OutCubic
                    }
                }

                replaceExit: Transition {
                    NumberAnimation {
                        property: "opacity"
                        from: 1.0
                        to: 0.0
                        duration: Theme.duration_fast
                        easing.type: Easing.InCubic
                    }
                }
            }
        }
    }    property list<Component> pageComponents: [
        Component { EventViewer {} },
        Component { SystemSnapshot {} },
        Component { GPUMonitoring {} },
        Component { ScanHistory {} },
        Component { NetworkScan {} },
        Component { ScanTool {} },
        Component { DataLossPrevention {} },
        Component { Settings {} }
    ]
}

