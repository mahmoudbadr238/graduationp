import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    width: 240
    color: Theme.panel
    radius: Theme.radii_lg
    
    // Smooth color transition
    Behavior on color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    
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
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        spacing: 10
        ListView {
                id: navList
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: ListModel {
                    ListElement { label: "Event Viewer"; icon: "" }
                    ListElement { label: "System Snapshot"; icon: "" }
                    ListElement { label: "Scan History"; icon: "" }
                    ListElement { label: "Network Scan"; icon: "" }
                    ListElement { label: "Scan Tool"; icon: "" }
                    ListElement { label: "Data Loss Prevention"; icon: "" }
                    ListElement { label: "Settings"; icon: "" }
                }
                spacing: 10
                clip: true
                currentIndex: root.currentIndex
                delegate: ItemDelegate {
                    width: ListView.view.width
                    height: 40
                    focusPolicy: Qt.StrongFocus
                    
                    // Override default background
                    background: Rectangle {
                        color: "transparent"
                    }
                    
                    Accessible.role: Accessible.ListItem
                    Accessible.name: model.label
                    onClicked: {
                        root.currentIndex = index
                        root.navigationChanged(index)
                    }
                    
                    // Focus ring
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -2
                        radius: Theme.radii_sm + 2
                        color: "transparent"
                        border.color: Theme.focusRing
                        border.width: Theme.focusRingWidth
                        opacity: parent.activeFocus ? 1.0 : 0.0
                        z: 100
                        
                        Behavior on opacity {
                            NumberAnimation { duration: Theme.duration_fast }
                        }
                    }
                    
                    Rectangle {
                        id: selectionPill
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.ListView.isCurrentItem ? 6 : 0
                        height: 28
                        radius: 3
                        color: Theme.primary
                        opacity: parent.ListView.isCurrentItem ? 0.85 : 0
                        Behavior on width { NumberAnimation { duration: Theme.duration_fast } }
                        Behavior on opacity { NumberAnimation { duration: Theme.duration_fast } }
                    }
                    Rectangle {
                        anchors.fill: parent
                        color: parent.ListView.isCurrentItem ? "transparent" : (parent.hovered ? Theme.elevatedPanel : "transparent")
                        radius: Theme.radii_sm
                        z: -1
                        Behavior on color { ColorAnimation { duration: Theme.duration_fast } }
                    }
                    RowLayout {
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Theme.spacing_md
                        Text {
                            text: model.icon
                            font.pixelSize: 20
                            Layout.preferredWidth: 28
                            horizontalAlignment: Text.AlignHCenter
                            color: Theme.text
                            
                            Behavior on color {
                                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                            }
                        }
                        Text {
                            text: model.label
                            color: Theme.text
                            font.pixelSize: Theme.typography.body.size
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            
                            Behavior on color {
                                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                            }
                        }
                    }
                }
            }
    }
}
