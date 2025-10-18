import QtQuick 2.15
import QtQuick.Controls 2.15
import "../ui"

Button {
    id: control
    
    property int debounceMs: 500
    property bool isProcessing: false
    
    enabled: !isProcessing
    focusPolicy: Qt.StrongFocus
    
    // Focus ring
    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        radius: parent.radius + 2
        color: "transparent"
        border.color: Theme.focusRing
        border.width: Theme.focusRingWidth
        opacity: control.activeFocus ? 1.0 : 0.0
        z: 100
        
        Behavior on opacity {
            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }
    
    background: Rectangle {
        implicitWidth: 140
        implicitHeight: 40
        color: control.pressed ? Qt.darker(ThemeManager.accent, 1.3) :
               control.hovered ? Qt.lighter(ThemeManager.accent, 1.1) :
               ThemeManager.accent
        radius: 8
        opacity: control.enabled ? 1.0 : 0.5
        
        Behavior on color {
            ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }
    
    contentItem: Text {
        text: control.text
        font.pixelSize: 14
        font.weight: Font.Medium
        color: "white"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    
    onClicked: {
        if (!isProcessing) {
            isProcessing = true
            debounceTimer.start()
        }
    }
    
    Timer {
        id: debounceTimer
        interval: control.debounceMs
        onTriggered: control.isProcessing = false
    }
}
