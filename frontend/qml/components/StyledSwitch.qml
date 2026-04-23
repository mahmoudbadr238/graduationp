import QtQuick 2.15
import QtQuick.Controls 2.15
import "../ui"

Switch {
    id: control

    implicitWidth: Math.max(48, implicitIndicatorWidth)
    implicitHeight: 24
    spacing: 8
    padding: 0

    indicator: Rectangle {
        implicitWidth: 44
        implicitHeight: 24
        x: control.mirrored ? control.width - width : 0
        y: (control.height - height) / 2
        radius: height / 2
        color: control.checked ? ThemeManager.accent : ThemeManager.elevated()
        border.color: control.checked ? ThemeManager.accent : ThemeManager.border()
        border.width: 1
        opacity: control.enabled ? 1.0 : 0.45

        Behavior on color { ColorAnimation { duration: 120 } }

        Rectangle {
            width: 18
            height: 18
            radius: 9
            x: control.checked ? parent.width - width - 3 : 3
            y: 3
            color: ThemeManager.selectionForeground

            Behavior on x { NumberAnimation { duration: 120 } }
        }
    }

    contentItem: Text {
        text: control.text
        color: control.enabled ? ThemeManager.foreground() : ThemeManager.muted()
        font.pixelSize: ThemeManager.fontSize_body
        verticalAlignment: Text.AlignVCenter
        leftPadding: !control.mirrored && control.indicator ? control.indicator.width + control.spacing : 0
        rightPadding: control.mirrored && control.indicator ? control.indicator.width + control.spacing : 0
        elide: Text.ElideRight
    }
}
