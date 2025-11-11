import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../components"
import "../../theme"

Column {
    id: root
    spacing: 18
    anchors.fill: parent
    anchors.margins: 24

    // This property will be set by SystemSnapshot.qml Loader
    property var snapshotData: ({
        "os": {"name": "N/A", "version": "N/A", "build": "N/A", "architecture": "N/A"}
    })

    PageHeader {
        title: "Operating System"
        subtitle: "Version, build, and update information"
    }    AnimatedCard {
        width: parent.width - 48
        implicitHeight: 280
        
        Grid {
            columns: 2
            columnSpacing: 40
            rowSpacing: 16
            
            Text {
                text: "Operating System:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text {
                text: root.snapshotData.os ? (root.snapshotData.os.product_name || root.snapshotData.os.name || "N/A") : "N/A"
                color: Theme.text
                font.pixelSize: 14
                font.bold: true
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }

            Text {
                text: "Version:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text {
                text: {
                    if (root.snapshotData.os) {
                        var parts = [];
                        if (root.snapshotData.os.display_version) parts.push(root.snapshotData.os.display_version);
                        if (root.snapshotData.os.build_number) parts.push("Build " + root.snapshotData.os.build_number);
                        else if (root.snapshotData.os.version) parts.push(root.snapshotData.os.version);
                        return parts.length > 0 ? parts.join(" - ") : "N/A";
                    }
                    return "N/A";
                }
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }

            Text {
                text: "Architecture:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text {
                text: root.snapshotData.os ? root.snapshotData.os.architecture || "N/A" : "N/A"
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }

            Text {
                text: "Machine:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text {
                text: root.snapshotData.os ? root.snapshotData.os.machine || "N/A" : "N/A"
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }            Text {
                text: "Uptime:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text {
                text: {
                    if (root.snapshotData.os && root.snapshotData.os.uptime) {
                        var seconds = root.snapshotData.os.uptime;
                        var days = Math.floor(seconds / 86400);
                        var hours = Math.floor((seconds % 86400) / 3600);
                        var minutes = Math.floor((seconds % 3600) / 60);
                        if (days > 0) return days + " days, " + hours + " hours";
                        if (hours > 0) return hours + " hours, " + minutes + " minutes";
                        return minutes + " minutes";
                    }
                    return "N/A";
                }
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }

            Text {
                text: "Hostname:"
                color: Theme.muted
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
            Text {
                text: root.snapshotData.os ? root.snapshotData.os.hostname || "N/A" : "N/A"
                color: Theme.text
                font.pixelSize: 14
                Behavior on color { ColorAnimation { duration: 300; easing.type: Easing.InOutQuad } }
            }
        }
    }
}
