import QtQuick
import QtQuick.Controls
import "../theme"

/**
 * PageWrapper - Lazy-loading page container
 * 
 * Only instantiates child component when page is active
 * Prevents background pages from consuming resources
 * Shows loading state while component loads
 */
Item {
    id: root
    // Don't use anchors.fill here - StackView manages size automatically
    // This prevents "conflicting anchors" warning in StackView transitions
    width: parent ? parent.width : 0
    height: parent ? parent.height : 0
    
    property alias sourceComponent: loader.sourceComponent
    property bool showLoading: true
    
    Loader {
        id: loader
        anchors.fill: parent
        asynchronous: true
        
        // Only load when page is visible AND active
        active: {
            if (!root.Window.window) return false
            if (!root.Window.window.visible) return false
            if (root.StackView.status !== StackView.Active) return false
            return true
        }
        
        onStatusChanged: {
            if (status === Loader.Ready) {
                contentFade.start()
            }
        }
    }
    
    // Loading indicator (shown while component loads)
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        visible: loader.status === Loader.Loading && root.showLoading
        
        Column {
            anchors.centerIn: parent
            spacing: 16
            
            BusyIndicator {
                anchors.horizontalCenter: parent.horizontalCenter
                running: parent.parent.visible
            }
            
            Text {
                text: "Loading..."
                color: "#8B97B0"
                font.pixelSize: 14
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }
    }
    
    // Fade-in animation when content ready
    PropertyAnimation {
        id: contentFade
        target: loader
        property: "opacity"
        from: 0.0
        to: 1.0
        duration: 120
        easing.type: Easing.OutCubic
    }
}
