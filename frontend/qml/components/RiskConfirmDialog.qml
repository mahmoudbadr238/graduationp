import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Dialog {
    id: popup
    objectName: "riskConfirmDialog"

    property string featureId: ""
    property bool newState: false
    property string featureLabel: ""

    signal acceptedFeature(string featureId, bool newState)
    signal rejectedFeature(string featureId)

    parent: Overlay.overlay
    width: Math.min(440, parent ? parent.width - 48 : 440)
    implicitHeight: dialogCard.implicitHeight
    height: implicitHeight
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    margins: 24
    modal: true
    focus: true
    dim: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Item { }

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.6)
    }

    contentItem: Rectangle {
        id: dialogCard
        width: popup.width
        implicitHeight: dialogContent.implicitHeight + 48
        color: ThemeManager.elevated()
        radius: 14
        border.color: ThemeManager.error || "#EF4444"
        border.width: 2

        ColumnLayout {
            id: dialogContent
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    width: 40
                    height: 40
                    radius: 20
                    color: Qt.rgba(1, 0.3, 0.3, 0.15)

                    Text {
                        anchors.centerIn: parent
                        text: "!"
                        font.pixelSize: 22
                        font.bold: true
                        color: ThemeManager.error || "#EF4444"
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: popup.newState
                          ? "Enable " + popup.featureLabel + "?"
                          : "Disable " + popup.featureLabel + "?"
                    color: ThemeManager.foreground()
                    font.pixelSize: ThemeManager.fontSize_h2
                    font.bold: true
                    wrapMode: Text.Wrap
                }
            }

            Text {
                text: popup.newState
                      ? "Enabling <b>" + popup.featureLabel + "</b> will modify your system's security configuration."
                      : "Are you sure? <b>Warning:</b> Disabling <b>" + popup.featureLabel + "</b> significantly increases the risk of system compromise."
                color: ThemeManager.muted()
                font.pixelSize: ThemeManager.fontSize_body
                wrapMode: Text.Wrap
                textFormat: Text.RichText
                Layout.fillWidth: true
                lineHeight: 1.4
            }

            Text {
                visible: popup.featureId === "uac"
                text: "A system reboot is required for UAC changes to take effect."
                color: "#F59E0B"
                font.pixelSize: ThemeManager.fontSize_small
                font.italic: true
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                Button {
                    id: cancelButton
                    text: "Cancel"
                    flat: true
                    implicitWidth: 96
                    implicitHeight: 36
                    onClicked: popup.reject()

                    contentItem: Text {
                        text: cancelButton.text
                        color: ThemeManager.muted()
                        font.pixelSize: ThemeManager.fontSize_body
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        implicitWidth: 96
                        implicitHeight: 36
                        radius: 8
                        color: cancelButton.hovered ? ThemeManager.surface() : "transparent"
                        border.color: ThemeManager.border()
                        border.width: 1
                    }
                }

                Button {
                    id: confirmButton
                    text: popup.newState ? "Enable" : "Disable"
                    implicitWidth: popup.newState ? 96 : 110
                    implicitHeight: 36
                    onClicked: popup.accept()

                    contentItem: Text {
                        text: confirmButton.text
                        color: "white"
                        font.pixelSize: ThemeManager.fontSize_body
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        implicitWidth: Math.max(96, confirmButton.contentItem.implicitWidth + 24)
                        implicitHeight: 36
                        radius: 8
                        color: confirmButton.hovered
                               ? Qt.darker(
                                     popup.newState ? ThemeManager.success : (ThemeManager.error || "#EF4444"),
                                     1.15
                                 )
                               : (popup.newState ? ThemeManager.success : (ThemeManager.error || "#EF4444"))
                    }
                }
            }
        }
    }

    onAccepted: popup.acceptedFeature(popup.featureId, popup.newState)
    onRejected: popup.rejectedFeature(popup.featureId)

    function show(fId, state) {
        featureId = fId
        newState = state
        featureLabel = _labelFor(fId)
        popup.open()
    }

    function _labelFor(fId) {
        var onLinux = (typeof Backend !== "undefined" && Backend && Backend.isLinux)
        switch (fId) {
        case "firewall":
            return onLinux ? "System Firewall (UFW)" : "Windows Firewall"
        case "rdp":
            return "Remote Desktop"
        case "uac":
            return onLinux ? "Privilege Escalation (sudo)" : "User Account Control"
        default:
            return fId
        }
    }
}
