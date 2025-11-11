import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"
import "../../theme"

AppSurface {
    id: root

    property var snapshotData: ({
        "security": {
            "firewall": false,
            "antivirus": false,
            "tpm": false,
            "secure_boot": false,
            "uac": false
        },
        "is_admin": false
    })

    Column {
        width: Math.min(800, parent.width - Theme.spacing_md * 2)
        spacing: Theme.spacing_lg

        PageHeader {
            title: "Security Features"
            subtitle: "Protection status and compliance"
        }

        Rectangle {
            width: parent.width
            height: 60
            color: root.snapshotData.is_admin ? Theme.success + "20" : Theme.warning + "20"
            radius: 8
            border.color: root.snapshotData.is_admin ? Theme.success : Theme.warning
            border.width: 1

            Row {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    color: root.snapshotData.is_admin ? Theme.success : Theme.warning
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        anchors.centerIn: parent
                        text: root.snapshotData.is_admin ? "OK" : "!"
                        color: Theme.bg
                        font.pixelSize: 16
                        font.bold: true
                    }
                }

                Column {
                    spacing: 2
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        text: root.snapshotData.is_admin ? "Administrator Privileges Active" : "Limited Privileges"
                        color: Theme.text
                        font.pixelSize: 14
                        font.bold: true
                    }

                    Text {
                        text: root.snapshotData.is_admin ? "All security features available" : "Some features may be limited. Run as administrator for full access."
                        color: Theme.textSecondary
                        font.pixelSize: 12
                    }
                }
            }
        }

        AnimatedCard {
            width: parent.width
            implicitHeight: securityColumn.height + 40

            Column {
                id: securityColumn
                spacing: 16
                width: parent.width - 40
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 20

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
                        width: parent.width
                        height: 60
                        color: Theme.surface
                        radius: 8
                        border.color: Theme.border
                        border.width: 1

                        Row {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 16

                            Text {
                                text: modelData.feature
                                color: Theme.text
                                font.pixelSize: 14
                                font.weight: Font.Medium
                                width: 180
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Rectangle {
                                width: 12
                                height: 12
                                radius: 6
                                color: {
                                    if (modelData.enabled) {
                                        return Theme.success;
                                    } else {
                                        // Check if status indicates "Not Available" or "Not Active"
                                        var status = modelData.status.toLowerCase();
                                        if (status.includes("not available") || status.includes("not supported")) {
                                            return Theme.textSecondary;
                                        } else if (status.includes("not active") || status.includes("disabled") || status.includes("not enabled")) {
                                            return Theme.error;
                                        } else {
                                            return Theme.warning;
                                        }
                                    }
                                }
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: modelData.status
                                color: {
                                    if (modelData.enabled) {
                                        return Theme.success;
                                    } else {
                                        // Check if status indicates "Not Available" or "Not Active"
                                        var status = modelData.status.toLowerCase();
                                        if (status.includes("not available") || status.includes("not supported")) {
                                            return Theme.textSecondary;
                                        } else if (status.includes("not active") || status.includes("disabled") || status.includes("not enabled")) {
                                            return Theme.error;
                                        } else {
                                            return Theme.warning;
                                        }
                                    }
                                }
                                font.pixelSize: 14
                                font.weight: Font.Medium
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                }
            }
        }
    }
}
