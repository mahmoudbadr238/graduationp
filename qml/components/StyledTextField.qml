import QtQuick 2.15
import QtQuick.Controls 2.15
import "../ui"

TextField {
    id: control

    color: control.enabled ? ThemeManager.foreground() : ThemeManager.muted()
    selectionColor: ThemeManager.selectionBackground
    selectedTextColor: ThemeManager.selectionForeground
    placeholderTextColor: ThemeManager.muted()
    font.pixelSize: ThemeManager.fontSize_body()

    leftPadding: 12
    rightPadding: 12
    topPadding: 8
    bottomPadding: 8

    background: Rectangle {
        implicitWidth: 200
        implicitHeight: 36
        radius: 8
        color: control.enabled ? ThemeManager.elevated() : ThemeManager.surface()
        border.color: control.activeFocus ? ThemeManager.accent
                     : control.hovered    ? ThemeManager.muted()
                                          : ThemeManager.border()
        border.width: control.activeFocus ? 2 : 1

        Behavior on border.color { ColorAnimation { duration: 120 } }
    }
}
