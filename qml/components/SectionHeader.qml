import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: sectionHeader
    property string title: ""
    property string subtitle: ""

    // Allow parent ColumnLayout to stretch width when desired, while
    // preserving correct height from the text content.
    Layout.fillWidth: true

    implicitWidth: Math.max(titleText.implicitWidth, subtitleText.visible ? subtitleText.implicitWidth : 0)
    implicitHeight: titleText.implicitHeight + (subtitleText.visible ? (Theme.spacing_xs + subtitleText.implicitHeight) : 0)

    Column {
        id: layout
        spacing: Theme.spacing_xs

        Text {
            id: titleText
            text: sectionHeader.title
            color: Theme.text
            font.pixelSize: Theme.typography.h2.size
            font.weight: Theme.typography.h2.weight
            elide: Text.ElideRight
            
            Behavior on color {
                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
            }
        }
        Text {
            id: subtitleText
            text: sectionHeader.subtitle
            color: Theme.muted
            font.pixelSize: Theme.typography.body.size
            font.weight: Theme.typography.body.weight
            elide: Text.ElideRight
            visible: sectionHeader.subtitle !== ""
            
            Behavior on color {
                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
            }
        }
    }
}
