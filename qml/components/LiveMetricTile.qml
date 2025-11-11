import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"

Rectangle {
    id: tile
    radius: Theme.radii.md
    color: Theme.glass.card
    border.color: Theme.glass.border
    border.width: 1
    
    // NO hardcoded dimensions - use implicit sizing from content
    implicitWidth: contentColumn.implicitWidth + Theme.spacing.lg * 2
    implicitHeight: contentColumn.implicitHeight + Theme.spacing.lg * 2

    // Smooth color transitions
    Behavior on color {
        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
    }
    Behavior on border.color {
        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
    }

    property string label: "Metric"
    property string valueText: "--"
    property string hint: ""
    property bool positive: true

    ColumnLayout {
        id: contentColumn
        anchors.fill: parent
        anchors.margins: Theme.spacing.lg
        spacing: Theme.spacing.xs

        Text {
            text: label
            color: Theme.muted
            font.pixelSize: Theme.typography.caption.size
            font.weight: Theme.typography.caption.weight
            Layout.fillWidth: true

            Behavior on color {
                ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
            }
        }

        Text {
            text: valueText
            color: positive ? Theme.neon.green : Theme.neon.purple
            font.pixelSize: Theme.typography.h1.size
            font.weight: Font.DemiBold
            Layout.fillWidth: true
            wrapMode: Text.WrapAnywhere
            maximumLineCount: 2
            horizontalAlignment: Text.AlignHCenter

            Behavior on color {
                ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
            }
        }

        Text {
            text: hint
            color: Theme.muted
            font.pixelSize: Theme.typography.caption.size
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            visible: hint.length > 0

            Behavior on color {
                ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
            }
        }
    }

    // Neon glow pulse
    SequentialAnimation on border.color {
        loops: Animation.Infinite
        running: true
        ColorAnimation {
            from: Theme.glass.border
            to: Theme.glass.borderActive
            duration: 900
        }
        ColorAnimation {
            from: Theme.glass.borderActive
            to: Theme.glass.border
            duration: 900
        }
    }
}