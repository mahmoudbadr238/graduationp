import QtQuick 2.15
import QtQuick.Controls 2.15
import "../ui"

ComboBox {
    id: control

    font.pixelSize: ThemeManager.fontSize_body()

    leftPadding: 12
    rightPadding: indicator.width + 8
    topPadding: 8
    bottomPadding: 8

    // ── Editable text input ────────────────────────────────────────────────
    contentItem: TextInput {
        text: control.editable ? control.editText : control.displayText
        color: control.enabled ? ThemeManager.foreground() : ThemeManager.muted()
        font: control.font
        verticalAlignment: Text.AlignVCenter
        selectByMouse: true
        selectionColor: ThemeManager.selectionBackground
        selectedTextColor: ThemeManager.selectionForeground
        readOnly: !control.editable
        clip: true
    }

    // ── Drop-down arrow indicator ──────────────────────────────────────────
    indicator: Text {
        x: control.width - width - 10
        y: (control.height - height) / 2
        text: "\u25BE"                 // ▾ small down triangle
        font.pixelSize: 14
        color: control.enabled ? ThemeManager.muted() : ThemeManager.border()
    }

    // ── Background rectangle ───────────────────────────────────────────────
    background: Rectangle {
        implicitWidth: 200
        implicitHeight: 36
        radius: 8
        color: control.enabled ? ThemeManager.elevated() : ThemeManager.surface()
        border.color: control.activeFocus   ? ThemeManager.accent
                     : control.hovered      ? ThemeManager.muted()
                                            : ThemeManager.border()
        border.width: control.activeFocus ? 2 : 1

        Behavior on border.color { ColorAnimation { duration: 120 } }
    }

    // ── Dropdown popup ─────────────────────────────────────────────────────
    popup: Popup {
        y: control.height + 4
        width: control.width
        implicitHeight: contentItem.implicitHeight + 2
        padding: 1

        background: Rectangle {
            color: ThemeManager.panel()
            border.color: ThemeManager.border()
            radius: 8
            layer.enabled: true
        }

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }

    // ── Delegate for each row ──────────────────────────────────────────────
    delegate: ItemDelegate {
        width: control.width
        height: 36

        contentItem: Text {
            text: modelData
            color: highlighted ? ThemeManager.selectionForeground
                               : ThemeManager.foreground()
            font: control.font
            verticalAlignment: Text.AlignVCenter
            leftPadding: 12
        }

        background: Rectangle {
            color: highlighted ? ThemeManager.accent
                 : hovered     ? ThemeManager.elevated()
                               : "transparent"
            radius: 4
        }

        highlighted: control.highlightedIndex === index
    }
}
