import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"

Column {
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24
    
    PageHeader {
        title: "Security Features"
        subtitle: "Protection status and compliance"
    }
    
    AnimatedCard {
        width: parent.width - 48
        implicitHeight: 360
        
        Column {
            spacing: 16
            width: parent.width
            
            Repeater {
                model: ListModel {
                    ListElement { feature: "Windows Defender"; status: "Active"; statusType: "success" }
                    ListElement { feature: "Firewall"; status: "Enabled"; statusType: "success" }
                    ListElement { feature: "BitLocker"; status: "Encrypted"; statusType: "success" }
                    ListElement { feature: "Secure Boot"; status: "Enabled"; statusType: "success" }
                    ListElement { feature: "TPM 2.0"; status: "Available"; statusType: "success" }
                }
                
                Rectangle {
                    width: parent.width - 40
                    height: 48
                    color: Theme.surface
                    radius: 8
                    border.color: Theme.border
                    border.width: 1
                    
                    Behavior on color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                    Behavior on border.color {
                        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                    }
                    
                    Row {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 16
                        
                        Text {
                            text: model.feature
                            color: Theme.text
                            font.pixelSize: 14
                            width: 180
                            anchors.verticalCenter: parent.verticalCenter
                            
                            Behavior on color {
                                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
                            }
                        }
                        
                        Rectangle {
                            width: 12
                            height: 12
                            radius: 6
                            color: model.statusType === "success" ? Theme.success : Theme.warning
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        
                        Text {
                            text: model.status
                            color: model.statusType === "success" ? Theme.success : Theme.warning
                            font.pixelSize: 14
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
        }
    }
}
