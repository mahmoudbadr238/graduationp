import QtQuick 2.15
import QtQuick.Controls 2.15
import "../ui"

ComboBox {
    id: control

    implicitWidth: 200
    implicitHeight: 36
    font.pixelSize: ThemeManager.fontSize_body
    leftPadding: 12
    rightPadding: 30

    contentItem: Text {
        text: control.displayText
        color: control.enabled ? ThemeManager.foreground() : ThemeManager.muted()
        font: control.font
        leftPadding: 12
        rightPadding: 30
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Text {
        x: control.width - width - 10
        y: (control.height - height) / 2
        text: "\u25BE"
        font.pixelSize: ThemeManager.fontSize_small
        color: control.enabled ? ThemeManager.muted() : ThemeManager.border()
    }

    background: Rectangle {
        radius: 8
        color: control.enabled ? ThemeManager.elevated() : ThemeManager.surface()
        border.color: control.pressed ? ThemeManager.accent : ThemeManager.border()
        border.width: control.activeFocus ? 2 : 1

        Behavior on border.color { ColorAnimation { duration: 120 } }
    }

    delegate: ItemDelegate {
        width: control.width
        height: 36

        contentItem: Text {
            text: modelData
            color: highlighted ? ThemeManager.selectionForeground : ThemeManager.foreground()
            font: control.font
            leftPadding: 12
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            color: highlighted ? ThemeManager.accent : ThemeManager.elevated()
        }

        highlighted: control.highlightedIndex === index
    }

    popup: Popup {
        y: control.height + 4
        width: control.width
        implicitHeight: contentItem.implicitHeight + 2
        padding: 1

        background: Rectangle {
            color: ThemeManager.panel()
            border.color: ThemeManager.border()
            border.width: 1
            radius: 8
        }

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }
}
