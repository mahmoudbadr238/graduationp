import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"

/**
 * SidebarNav: Fixed-width navigation sidebar
 * Uses Layout.preferredWidth to maintain consistent width without pushing content
 */
Rectangle {
    id: root
    color: Theme.panel
    radius: 0  // Edge-to-edge sidebar
    
    // Fixed width - no responsive scaling
    implicitWidth: 260
    Layout.preferredWidth: 260
    
    property int currentIndex: 0
    signal navigationChanged(int index)
    
    function setCurrentIndex(index) {
        if (index >= 0 && index < navList.count) {
            root.currentIndex = index
            root.navigationChanged(index)
        }
    }
    
    Accessible.role: Accessible.List
    Accessible.name: "Navigation menu"
    
    // Smooth color transition
    Behavior on color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    
    // Right border separator
    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 1
        color: Theme.border
    }
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        anchors.topMargin: 16
        anchors.bottomMargin: 16
        spacing: 8
        
        ListView {
            id: navList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: ListModel {
                ListElement { label: "Event Viewer"; icon: "📋" }
                ListElement { label: "System Snapshot"; icon: "📊" }
                ListElement { label: "GPU Monitoring"; icon: "🎮" }
                ListElement { label: "Scan History"; icon: "📁" }
                ListElement { label: "Network Scan"; icon: "🌐" }
                ListElement { label: "Scan Tool"; icon: "🔍" }
                ListElement { label: "Data Loss Prevention"; icon: "🛡️" }
                ListElement { label: "Settings"; icon: "⚙️" }
            }
            spacing: 4
            clip: true
            currentIndex: root.currentIndex
            
            delegate: ItemDelegate {
                width: ListView.view.width
                height: 44
                focusPolicy: Qt.StrongFocus
                hoverEnabled: true
                padding: 0
                
                background: Rectangle {
                    color: {
                        if (ListView.isCurrentItem) {
                            return Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.2)
                        } else if (parent.hovered) {
                            return Qt.rgba(1, 1, 1, 0.08)
                        }
                        return "transparent"
                    }
                    radius: 8
                    
                    Behavior on color {
                        ColorAnimation { duration: 200; easing.type: Easing.InOutQuad }
                    }
                }
                
                // Left indicator for selected item
                Rectangle {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 0
                    width: ListView.isCurrentItem ? 4 : 0
                    height: 24
                    radius: 2
                    color: Theme.primary
                    
                    Behavior on width {
                        NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                    }
                }
                
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8
                    
                    Label {
                        text: model.icon
                        font.pixelSize: 18
                        Layout.preferredWidth: 24
                        Layout.preferredHeight: 24
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    
                    Label {
                        text: model.label
                        font.pixelSize: 13
                        font.weight: ListView.isCurrentItem ? Font.DemiBold : Font.Normal
                        color: Theme.text
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        
                        Behavior on font.weight {
                            NumberAnimation { duration: 200 }
                        }
                    }
                }
                
                onClicked: {
                    console.log("[SIDEBAR] Item clicked:", model.label, "index:", index)
                    root.currentIndex = index
                    root.navigationChanged(index)
                }
            }
        }
    }
}
