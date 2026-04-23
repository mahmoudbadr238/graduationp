import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: statpill

    property string label: ""
    property string value: ""
    property color accentColor: Theme.primary

    color: Theme.surface
    radius: Theme.radii_sm
    border.color: Theme.border
    border.width: 1
    height: 32
    implicitWidth: row.implicitWidth + Theme.spacing_md * 2

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: Theme.spacing_sm

        Rectangle {
            width: 6
            height: 6
            radius: 3
            color: statpill.accentColor
            visible: statpill.accentColor !== Qt.rgba(0, 0, 0, 0)
        }

        Text {
            text: statpill.label
            color: Theme.textSecondary
            font.pixelSize: Theme.typography.caption.size
            visible: statpill.label !== ""
        }

        Text {
            text: statpill.value
            color: Theme.text
            font.pixelSize: Theme.typography.caption.size
            font.weight: Font.Medium
            visible: statpill.value !== ""
        }
    }
}
