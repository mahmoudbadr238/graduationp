import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

/**
 * RiskConfirmDialog - Reusable confirmation dialog for dangerous security toggles.
 *
 * Usage:
 *   RiskConfirmDialog {
 *       id: riskDialog
 *       onAccepted: { // commit the action }
 *       onRejected: { // revert the toggle }
 *   }
 *   // To show:
 *   riskDialog.show("firewall", false)   // featureId, newState
 */
Popup {
    id: popup
    anchors.centerIn: parent
    width: Math.min(420, parent.width - 48)
    modal: true
    dim: true
    closePolicy: Popup.CloseOnEscape

    // Expose context so callers know what was confirmed
    property string featureId: ""
    property bool   newState: false
    property string featureLabel: ""

    signal accepted(string featureId, bool newState)
    signal rejected(string featureId)

    function show(fId, state) {
        featureId = fId
        newState  = state
        featureLabel = _labelFor(fId)
        popup.open()
    }

    function _labelFor(fId) {
        switch (fId) {
            case "firewall": return "Windows Firewall"
            case "rdp":      return "Remote Desktop"
            case "uac":      return "User Account Control"
            default:         return fId
        }
    }

    background: Rectangle {
        color: ThemeManager.panel()
        radius: 16
        border.color: ThemeManager.error || "#EF4444"
        border.width: 2

        // Subtle gradient overlay for urgency
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Qt.rgba(1, 0, 0, 0.04)
        }
    }

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.55)
    }

    contentItem: ColumnLayout {
        spacing: 16

        // Warning icon row
        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            Rectangle {
                width: 40; height: 40; radius: 20
                color: Qt.rgba(1, 0.3, 0.3, 0.15)

                Text {
                    anchors.centerIn: parent
                    text: "⚠"
                    font.pixelSize: 22
                    color: ThemeManager.error || "#EF4444"
                }
            }

            Text {
                text: popup.newState
                      ? "Enable " + popup.featureLabel + "?"
                      : "Disable " + popup.featureLabel + "?"
                color: ThemeManager.foreground()
                font.pixelSize: ThemeManager.fontSize_h2
                font.bold: true
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
        }

        // Warning body
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

        // UAC reboot notice
        Text {
            visible: popup.featureId === "uac"
            text: "A system reboot is required for UAC changes to take effect."
            color: "#F59E0B"
            font.pixelSize: ThemeManager.fontSize_small
            font.italic: true
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }

        Item { implicitHeight: 4 }

        // Action buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Item { Layout.fillWidth: true }

            Button {
                text: "Cancel"
                flat: true
                onClicked: {
                    popup.rejected(popup.featureId)
                    popup.close()
                }

                contentItem: Text {
                    text: parent.text
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_body
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    implicitWidth: 90; implicitHeight: 36
                    radius: 8
                    color: parent.hovered ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                    border.color: ThemeManager.border()
                }
            }

            Button {
                text: popup.newState ? "Enable" : "Disable"
                onClicked: {
                    popup.accepted(popup.featureId, popup.newState)
                    popup.close()
                }

                contentItem: Text {
                    text: parent.text
                    color: "white"
                    font.pixelSize: ThemeManager.fontSize_body
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    implicitWidth: 90; implicitHeight: 36
                    radius: 8
                    color: popup.newState
                           ? (parent.hovered ? Qt.darker(ThemeManager.success, 1.15) : ThemeManager.success)
                           : (parent.hovered ? Qt.darker(ThemeManager.error || "#EF4444", 1.15) : (ThemeManager.error || "#EF4444"))
                }
            }
        }
    }

    // Close animation
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150 } }
    exit:  Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120 } }
}
