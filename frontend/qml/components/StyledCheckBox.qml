import QtQuick 2.15
import QtQuick.Controls 2.15
import "../ui"

CheckBox {
    id: control

    implicitHeight: 24
    spacing: 8
    padding: 0

    indicator: Rectangle {
        implicitWidth: 18
        implicitHeight: 18
        x: control.mirrored ? control.width - width : 0
        y: (control.height - height) / 2
        radius: 4
        color: control.checked ? ThemeManager.accent : ThemeManager.elevated()
        border.color: control.checked ? ThemeManager.accent : ThemeManager.border()
        border.width: 1
        opacity: control.enabled ? 1.0 : 0.45

        Text {
            anchors.centerIn: parent
            text: "\u2713"
            color: ThemeManager.selectionForeground
            font.pixelSize: ThemeManager.fontSize_small
            visible: control.checked
        }
    }

    contentItem: Text {
        text: control.text
        color: control.enabled ? ThemeManager.foreground() : ThemeManager.muted()
        font.pixelSize: ThemeManager.fontSize_body
        verticalAlignment: Text.AlignVCenter
        leftPadding: !control.mirrored && control.indicator ? control.indicator.width + control.spacing : 0
        rightPadding: control.mirrored && control.indicator ? control.indicator.width + control.spacing : 0
        wrapMode: Text.WordWrap
    }
}
