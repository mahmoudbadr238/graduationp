import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../ui"

Item {
    id: root
    property alias contentItem: contentLoader.sourceComponent
    property string title: ""
    property string subtitle: ""

    anchors.fill: parent

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        // Header
        ColumnLayout {
            spacing: 4
            Layout.fillWidth: true

            Text {
                text: root.title
                color: ThemeManager.foreground()
                font.pixelSize: ThemeManager.fontSize_h1
                font.bold: true
            }

            Text {
                visible: root.subtitle !== ""
                text: root.subtitle
                color: ThemeManager.muted()
                font.pixelSize: ThemeManager.fontSize_body
            }
        }

        // Main content area - scrollable
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AlwaysOff }

            ColumnLayout {
                width: parent.width - 16
                spacing: 20

                Loader {
                    id: contentLoader
                    Layout.fillWidth: true
                }

                Item { Layout.fillHeight: true }
            }
        }
    }
}
