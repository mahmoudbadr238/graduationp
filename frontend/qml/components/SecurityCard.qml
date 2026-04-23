import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Rectangle {
    id: card
    
    property string title: ""
    property string value: ""
    property string subtitle: ""  // Secondary text line
    property string note: ""      // Optional tertiary note
    property bool isGood: true
    property bool isWarning: false  // Yellow warning state
    property bool isNeutral: false  // Gray/neutral state for N/A items

    // Interactive toggle support
    property bool toggleable: false          // Show a switch
    property bool toggleChecked: false       // Bound to switch state
    signal toggleRequested(bool newState)    // Emitted when user flips the switch

    color: ThemeManager.panel()
    radius: 12
    border.color: ThemeManager.border()
    border.width: 1
    implicitWidth: 180
    implicitHeight: 132
    
    // Status color logic: good (green), warning (yellow/amber), bad (red), neutral (gray)
    readonly property color statusColor: {
        if (card.isNeutral) {
            return ThemeManager.muted()
        } else if (card.isGood) {
            return ThemeManager.success
        } else if (card.isWarning) {
            return "#F59E0B"  // Amber/yellow for warnings
        } else {
            return ThemeManager.error || "#EF4444"  // Red for bad states
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 6

        // Title row with optional switch
        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                text: card.title
                color: ThemeManager.muted()
                font.pixelSize: ThemeManager.fontSize_small
                font.weight: Font.Medium
                Layout.fillWidth: true
                elide: Text.ElideRight
            }

            StyledSwitch {
                id: cardSwitch
                visible: card.toggleable
                checked: card.toggleChecked
                scale: 0.65
                Layout.alignment: Qt.AlignVCenter

                // Intercept: do NOT auto-commit. Emit signal and let parent decide.
                onClicked: {
                    // Revert visual state immediately; the parent will set
                    // toggleChecked after the confirmation dialog is accepted.
                    checked = card.toggleChecked
                    card.toggleRequested(!card.toggleChecked)
                }
            }
        }

        Text {
            text: card.value
            color: card.statusColor
            font.pixelSize: ThemeManager.fontSize_h3
            font.bold: true
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        
        Text {
            text: card.subtitle
            color: ThemeManager.muted()
            font.pixelSize: ThemeManager.fontSize_caption
            visible: card.subtitle.length > 0
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            maximumLineCount: card.note.length > 0 ? 1 : 2
            elide: Text.ElideRight
            opacity: 0.8
        }

        Text {
            text: card.note
            color: ThemeManager.muted()
            font.pixelSize: ThemeManager.fontSize_small
            visible: card.note.length > 0
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            opacity: 0.72
        }

        Item { Layout.fillHeight: true }
    }
    
    // Subtle status indicator dot
    Rectangle {
        width: 8
        height: 8
        radius: 4
        color: card.statusColor
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 12
        opacity: 0.9
    }
}
