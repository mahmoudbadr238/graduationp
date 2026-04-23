import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Dialog {
    id: sentinelDialogRoot
    parent: Overlay.overlay

    // Firm width constraint
    width: Math.min(520, parent ? parent.width - 48 : 520)
    implicitHeight: (dialogHeader.visible ? dialogHeader.implicitHeight : 0)
                    + bodyScrollView.implicitHeight
                    + (dialogFooter.visible ? dialogFooter.implicitHeight : 0)
                    + padding * 2
    height: implicitHeight
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    margins: 24

    modal: true
    focus: true
    dim: true
    closePolicy: Popup.CloseOnEscape
    
    padding: 24

    property string titleText: "Confirmation"
    property string bodyText: ""
    property string iconText: ""
    property color iconColor: ThemeManager.foreground()
    property color iconBgColor: "transparent"
    
    // Styling properties
    property color dialogBorderColor: ThemeManager.border()
    property color dialogBorderBgOverlay: "transparent"

    // Header properties
    property bool showHeader: true

    // Button properties
    property string primaryButtonText: "OK"
    property color primaryButtonColor: ThemeManager.accent
    property string secondaryButtonText: "Cancel"
    property bool showSecondaryButton: true

    // Custom content injection
    default property alias customContent: customContentContainer.data

    background: Rectangle {
        color: ThemeManager.panel()
        radius: 12
        border.color: sentinelDialogRoot.dialogBorderColor
        border.width: sentinelDialogRoot.dialogBorderColor !== ThemeManager.border() ? 2 : 1

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: sentinelDialogRoot.dialogBorderBgOverlay
        }
    }

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.6)
    }

    // 1. Native Header
    header: Item {
        id: dialogHeader
        visible: sentinelDialogRoot.showHeader && (sentinelDialogRoot.titleText !== "" || sentinelDialogRoot.iconText !== "")
        implicitWidth: headerLayout.implicitWidth
        implicitHeight: headerLayout.implicitHeight + 16
        
        RowLayout {
            id: headerLayout
            width: parent.width - 48
            x: 24
            y: 24
            spacing: 12

            Rectangle {
                visible: sentinelDialogRoot.iconText !== ""
                width: 40; height: 40; radius: 20
                color: sentinelDialogRoot.iconBgColor
                Text {
                    anchors.centerIn: parent
                    text: sentinelDialogRoot.iconText
                    font.pixelSize: 22
                    color: sentinelDialogRoot.iconColor
                }
            }

            Text {
                text: sentinelDialogRoot.titleText
                color: ThemeManager.foreground()
                font.pixelSize: ThemeManager.fontSize_h2
                font.bold: true
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
        }
    }

    // 2. Native Body (Scrollable if needed)
    contentItem: ScrollView {
        id: bodyScrollView
        clip: true
        
        // Bounded height allows it to shrink to content, but scroll if massive
        implicitHeight: Math.min(bodyLayout.implicitHeight, Overlay.overlay ? Overlay.overlay.height - 250 : 600)

        ColumnLayout {
            id: bodyLayout
            width: bodyScrollView.availableWidth
            spacing: 16

            Text {
                visible: sentinelDialogRoot.bodyText !== ""
                text: sentinelDialogRoot.bodyText
                color: ThemeManager.muted()
                font.pixelSize: ThemeManager.fontSize_body
                wrapMode: Text.Wrap
                textFormat: Text.RichText
                Layout.fillWidth: true
                lineHeight: 1.4
            }

            // A ColumnLayout acts as the host so injected Layout.fillWidth items work natively
            ColumnLayout {
                id: customContentContainer
                Layout.fillWidth: true
                spacing: 16
            }
        }
    }

    // 3. Footer — uses Rectangle+MouseArea instead of Button so that the
    // Fusion QML Controls style cannot collapse the height to zero.
    // In Fusion style, Button.implicitHeight is driven by QStyle metrics which
    // may ignore background.implicitHeight entirely, producing a 0-height button.
    // A plain Rectangle is not affected by the style system.
    footer: Item {
        id: dialogFooter
        implicitWidth: footerLayout.implicitWidth
        implicitHeight: footerLayout.implicitHeight + 24

        RowLayout {
            id: footerLayout
            width: parent.width - 48
            x: 24
            y: 8
            spacing: 12

            Item { Layout.fillWidth: true }

            // Secondary action (Cancel / back)
            Rectangle {
                id: secondaryActionRect
                visible: sentinelDialogRoot.showSecondaryButton
                implicitWidth: 96
                implicitHeight: 36
                radius: 8
                color: cancelArea.containsMouse ? ThemeManager.surface() : "transparent"
                border.color: ThemeManager.border()
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: sentinelDialogRoot.secondaryButtonText
                    color: ThemeManager.muted()
                    font.pixelSize: ThemeManager.fontSize_body
                }

                MouseArea {
                    id: cancelArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sentinelDialogRoot.reject()
                }
            }

            // Primary action (OK / confirm)
            Rectangle {
                id: primaryActionRect
                implicitWidth: Math.max(96, primaryActionLabel.implicitWidth + 32)
                implicitHeight: 36
                radius: 8
                color: {
                    if (okArea.pressed)       return Qt.darker(sentinelDialogRoot.primaryButtonColor, 1.3)
                    if (okArea.containsMouse) return Qt.darker(sentinelDialogRoot.primaryButtonColor, 1.15)
                    return sentinelDialogRoot.primaryButtonColor
                }

                Text {
                    id: primaryActionLabel
                    anchors.centerIn: parent
                    text: sentinelDialogRoot.primaryButtonText
                    color: "white"
                    font.pixelSize: ThemeManager.fontSize_body
                    font.bold: true
                }

                MouseArea {
                    id: okArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sentinelDialogRoot.accept()
                }
            }
        }
    }

    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150 } }
    exit:  Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120 } }
}
