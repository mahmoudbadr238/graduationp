import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import "../theme"

AppSurface {
    id: root

    // Bind to global snapshot data from main window - use proper binding
    property var snapshotData: window.globalSnapshotData

    ScrollView {
        anchors.fill: parent
        anchors.margins: Theme.spacing_m
        clip: true
        
        ColumnLayout {
            width: Math.max(320, parent.width - Theme.spacing_m * 2)
            spacing: 0
            
            TabBar {
                id: tabBar
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredHeight: 48
                background: Rectangle {
                    color: Theme.panel
                    radius: Theme.radius
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                }
                
                TabButton {
                    text: "Overview"
                    width: implicitWidth
                    padding: 12
                    
                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.type.body
                        color: parent.checked ? "white" : Theme.muted
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        
                        Behavior on color {
                            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                        }
                    }
                    
                    background: Rectangle {
                        color: parent.checked ? Theme.primary : (parent.hovered ? Theme.elevatedPanel : "transparent")
                        radius: 8
                        opacity: parent.checked ? 0.85 : 1.0
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }
                }
                
                TabButton {
                    text: "OS Info"
                    width: implicitWidth
                    padding: 12
                    
                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.type.body
                        color: parent.checked ? "white" : Theme.muted
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        
                        Behavior on color {
                            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                        }
                    }
                    
                    background: Rectangle {
                        color: parent.checked ? Theme.primary : (parent.hovered ? Theme.elevatedPanel : "transparent")
                        radius: 8
                        opacity: parent.checked ? 0.85 : 1.0
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }
                }
                
                TabButton {
                    text: "Hardware"
                    width: implicitWidth
                    padding: 12
                    
                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.type.body
                        color: parent.checked ? "white" : Theme.muted
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        
                        Behavior on color {
                            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                        }
                    }
                    
                    background: Rectangle {
                        color: parent.checked ? Theme.primary : (parent.hovered ? Theme.elevatedPanel : "transparent")
                        radius: 8
                        opacity: parent.checked ? 0.85 : 1.0
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }
                }
                
                TabButton {
                    text: "Network"
                    width: implicitWidth
                    padding: 12
                    
                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.type.body
                        color: parent.checked ? "white" : Theme.muted
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        
                        Behavior on color {
                            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                        }
                    }
                    
                    background: Rectangle {
                        color: parent.checked ? Theme.primary : (parent.hovered ? Theme.elevatedPanel : "transparent")
                        radius: 8
                        opacity: parent.checked ? 0.85 : 1.0
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }
                }
                
                TabButton {
                    text: "Security"
                    width: implicitWidth
                    padding: 12

                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: Theme.type.body
                        color: parent.checked ? "white" : Theme.muted
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap

                        Behavior on color {
                            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                        }
                    }

                    background: Rectangle {
                        color: parent.checked ? Theme.primary : (parent.hovered ? Theme.elevatedPanel : "transparent")
                        radius: 8
                        opacity: parent.checked ? 0.85 : 1.0
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }
                }
            }            StackLayout {
                currentIndex: tabBar.currentIndex
                Layout.fillWidth: true
                Layout.minimumHeight: 800
                
                Loader {
                    id: overviewLoader
                    source: "snapshot/OverviewPage.qml"
                    Layout.fillWidth: true
                    asynchronous: true
                    
                    onLoaded: {
                        if (item) {
                            item.snapshotData = Qt.binding(function() { return root.snapshotData })
                        }
                    }
                    
                    BusyIndicator {
                        anchors.centerIn: parent
                        running: overviewLoader.status === Loader.Loading
                        visible: running
                    }
                }
                Loader {
                    id: osInfoLoader
                    source: "snapshot/OSInfoPage.qml"
                    Layout.fillWidth: true
                    asynchronous: true

                    onLoaded: {
                        if (item) {
                            item.snapshotData = Qt.binding(function() { return root.snapshotData })
                        }
                    }

                    BusyIndicator {
                        anchors.centerIn: parent
                        running: osInfoLoader.status === Loader.Loading
                        visible: running
                    }
                }
                Loader {
                    id: hardwareLoader
                    source: "snapshot/HardwarePage.qml"
                    Layout.fillWidth: true
                    asynchronous: true

                    onLoaded: {
                        if (item) {
                            item.snapshotData = Qt.binding(function() { return root.snapshotData })
                        }
                    }

                    BusyIndicator {
                        anchors.centerIn: parent
                        running: hardwareLoader.status === Loader.Loading
                        visible: running
                    }
                }
                Loader {
                    id: networkLoader
                    source: "snapshot/NetworkPage.qml"
                    Layout.fillWidth: true
                    asynchronous: true

                    onLoaded: {
                        if (item) {
                            item.snapshotData = Qt.binding(function() { return root.snapshotData })
                        }
                    }

                    BusyIndicator {
                        anchors.centerIn: parent
                        running: networkLoader.status === Loader.Loading
                        visible: running
                    }
                }
                Loader {
                    id: securityLoader
                    source: "snapshot/SecurityPage.qml"
                    Layout.fillWidth: true
                    asynchronous: true

                    onLoaded: {
                        if (item) {
                            item.snapshotData = Qt.binding(function() { return root.snapshotData })
                        }
                    }

                    BusyIndicator {
                        anchors.centerIn: parent
                        running: securityLoader.status === Loader.Loading
                        visible: running
                    }
                }
            }
        }
    } // ScrollView
}
