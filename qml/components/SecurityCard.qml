import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Rectangle {
    id: card
    
    property string title: ""
    property string value: ""
    property string subtitle: ""  // Secondary text line
    property bool isGood: true
    property bool isWarning: false  // Yellow warning state
    property bool isNeutral: false  // Gray/neutral state for N/A items

    color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
    radius: 12
    border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
    border.width: 1
    implicitWidth: 180
    implicitHeight: 110
    
    // Status color logic: good (green), warning (yellow/amber), bad (red), neutral (gray)
    readonly property color statusColor: {
        if (card.isNeutral) {
            return ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
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

        Text {
            text: card.title
            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
            font.pixelSize: 11
            font.weight: Font.Medium
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        Text {
            text: card.value
            color: card.statusColor
            font.pixelSize: 18
            font.bold: true
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        
        Text {
            text: card.subtitle
            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
            font.pixelSize: 10
            visible: card.subtitle.length > 0
            Layout.fillWidth: true
            elide: Text.ElideRight
            opacity: 0.8
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
