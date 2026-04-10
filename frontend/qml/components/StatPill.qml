import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"


Rectangle {
    id: statpill
    color: Theme.surface
    radius: Theme.radii_sm
    border.color: Theme.border
    border.width: 1
    height: 32
    width: 96
    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_sm
        spacing: Theme.spacing_sm
        // TODO: Add icon and value
    }
}