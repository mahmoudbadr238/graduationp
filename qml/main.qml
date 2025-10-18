import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import "components"
import "pages"
import "ui"

ApplicationWindow {
    id: window
    visible: true
    width: 1400
    height: 900
    minimumWidth: 800
    minimumHeight: 600
    title: "Sentinel - Endpoint Security Suite"
    color: ThemeManager.background()
    
    // Smooth theme transition
    Behavior on color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    
    property bool sidebarCollapsed: false
    property int sidebarWidth: sidebarCollapsed ? 80 : 250
    
    // Settings persistence
    Settings {
        id: appSettings
        property string themeMode: "system"
    }
    
    // Global toast manager
    ToastManager {
        id: globalToast
        anchors.fill: parent
        z: 1000
    }
    
    Component.onCompleted: {
        // Restore saved theme
        var savedTheme = appSettings.themeMode
        if (savedTheme) {
            ThemeManager.themeMode = savedTheme
        }
        
        // Save theme changes
        ThemeManager.themeModeChanged.connect(function() {
            appSettings.themeMode = ThemeManager.themeMode
        })
    }
    
    // Keyboard shortcuts
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
        NumberAnimation { duration: Theme.duration_fast; easing.type: Easing.OutCubic }
    }
    
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        
        TopStatusBar {
            Layout.fillWidth: true
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
                
                pushEnter: Transition {
                    // Slide the incoming page from the right (no opacity animation here)
                    NumberAnimation {
                        property: "x"
                        from: stackView.width * 0.06
                        to: 0
                        duration: 220
                        easing.type: Easing.OutCubic
                    }
                }
                
                pushExit: Transition {
                    // No opacity animation to avoid conflicts
                }
                
                replaceEnter: Transition {
                    // Slide the incoming page from the right (no opacity animation here)
                    NumberAnimation {
                        property: "x"
                        from: stackView.width * 0.06
                        to: 0
                        duration: 220
                        easing.type: Easing.OutCubic
                    }
                }
                
                replaceExit: Transition {
                    // No opacity animation to avoid conflicts
                }
                
                popExit: Transition {
                    // Slide the outgoing page to the right (no opacity animation here)
                    NumberAnimation {
                        property: "x"
                        from: 0
                        to: stackView.width * 0.06
                        duration: 180
                        easing.type: Easing.InCubic
                    }
                }
            }
        }
    }
    
    property list<Component> pageComponents: [
        Component { EventViewer {} },
        Component { SystemSnapshot {} },
        Component { ScanHistory {} },
        Component { NetworkScan {} },
        Component { ScanTool {} },
        Component { DataLossPrevention {} },
        Component { Settings {} }
    ]
}

