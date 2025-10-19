import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"

Column {
    id: root
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24

    // This property will be set by SystemSnapshot.qml Loader
    property var snapshotData: ({
        "security": {
            "firewall": false,
            "antivirus": false,
            "tpm": false,
            "secure_boot": false,
            "uac": false
        }
    })

    PageHeader {
        title: "Security Features"
        subtitle: "Protection status and compliance"
    }    AnimatedCard {
        width: parent.width - 48
        implicitHeight: 360
        
        Column {
            spacing: 16
            width: parent.width

            Repeater {
                model: [
                    {
                        feature: "Windows Defender",
                        status: root.snapshotData.security && root.snapshotData.security.windows_defender ? root.snapshotData.security.windows_defender.status : "Unknown",
                        enabled: root.snapshotData.security && root.snapshotData.security.windows_defender ? root.snapshotData.security.windows_defender.enabled : false
                    },
                    {
                        feature: "Firewall",
                        status: root.snapshotData.security && root.snapshotData.security.firewall ? root.snapshotData.security.firewall.status : "Unknown",
                        enabled: root.snapshotData.security && root.snapshotData.security.firewall ? root.snapshotData.security.firewall.enabled : false
                    },
                    {
                        feature: "TPM 2.0",
                        status: root.snapshotData.security && root.snapshotData.security.tpm ? root.snapshotData.security.tpm.status : "Unknown",
                        enabled: root.snapshotData.security && root.snapshotData.security.tpm ? root.snapshotData.security.tpm.enabled : false
                    },
                    {
                        feature: "Secure Boot",
                        status: root.snapshotData.security && root.snapshotData.security.secure_boot ? root.snapshotData.security.secure_boot.status : "Unknown",
                        enabled: root.snapshotData.security && root.snapshotData.security.secure_boot ? root.snapshotData.security.secure_boot.enabled : false
                    },
                    {
                        feature: "BitLocker",
                        status: root.snapshotData.security && root.snapshotData.security.bitlocker ? root.snapshotData.security.bitlocker.status : "Unknown",
                        enabled: root.snapshotData.security && root.snapshotData.security.bitlocker ? root.snapshotData.security.bitlocker.enabled : false
                    },
                    {
                        feature: "UAC",
                        status: root.snapshotData.security && root.snapshotData.security.uac ? root.snapshotData.security.uac.status : "Unknown",
                        enabled: root.snapshotData.security && root.snapshotData.security.uac ? root.snapshotData.security.uac.enabled : false
                    }
                ]

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
                            text: modelData.feature
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
                            color: modelData.enabled ? Theme.success : Theme.warning
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: modelData.status
                            color: modelData.enabled ? Theme.success : Theme.warning
                            font.pixelSize: 14
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
        }
    }
}