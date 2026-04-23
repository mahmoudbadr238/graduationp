import QtQuick 2.15
import QtQuick.Controls 2.15
import "../ui"

SpinBox {
    id: control

    implicitWidth: 120
    implicitHeight: 36

    contentItem: TextInput {
        z: 2
        text: control.textFromValue(control.value, control.locale)
        readOnly: !control.editable
        validator: control.validator
        inputMethodHints: Qt.ImhDigitsOnly
        color: control.enabled ? ThemeManager.foreground() : ThemeManager.muted()
        selectionColor: ThemeManager.selectionBackground
        selectedTextColor: ThemeManager.selectionForeground
        font.pixelSize: ThemeManager.fontSize_body
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Text.AlignVCenter

        onEditingFinished: {
            if (control.editable) {
                control.value = control.valueFromText(text, control.locale)
            }
        }
    }

    background: Rectangle {
        radius: 8
        color: control.enabled ? ThemeManager.elevated() : ThemeManager.surface()
        border.color: control.activeFocus ? ThemeManager.accent : ThemeManager.border()
        border.width: control.activeFocus ? 2 : 1
    }

    up.indicator: Rectangle {
        implicitWidth: 24
        implicitHeight: 14
        x: control.width - width - 8
        y: 4
        radius: 4
        color: control.up.pressed ? ThemeManager.surface() : "transparent"
        border.color: ThemeManager.border()
        border.width: 1

        Text {
            anchors.centerIn: parent
            text: "+"
            color: ThemeManager.foreground()
            font.pixelSize: ThemeManager.fontSize_small
            font.bold: true
        }
    }

    down.indicator: Rectangle {
        implicitWidth: 24
        implicitHeight: 14
        x: control.width - width - 8
        y: control.height - height - 4
        radius: 4
        color: control.down.pressed ? ThemeManager.surface() : "transparent"
        border.color: ThemeManager.border()
        border.width: 1

        Text {
            anchors.centerIn: parent
            text: "\u2212"
            color: ThemeManager.foreground()
            font.pixelSize: ThemeManager.fontSize_small
            font.bold: true
        }
    }
}
