import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Item {
    id: root
    property alias contentItem: contentLoader.sourceComponent
    property string title: ""
    property string subtitle: ""

    anchors.fill: parent

    Theme { id: theme }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.paddingXL
        spacing: theme.gapLarge

        // Header
        ColumnLayout {
            spacing: 4
            Layout.fillWidth: true

            Text {
                text: root.title
                color: theme.colorTextPrimary
                font.pixelSize: 28
                font.bold: true
            }

            Text {
                visible: root.subtitle !== ""
                text: root.subtitle
                color: theme.colorTextSecondary
                font.pixelSize: 13
            }
        }

        // Main content area - scrollable
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                width: parent.width - 16
                spacing: theme.gapLarge

                Loader {
                    id: contentLoader
                    Layout.fillWidth: true
                }

                Item { Layout.fillHeight: true }
            }
        }
    }
}
