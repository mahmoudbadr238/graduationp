import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Item {
    id: root
    anchors.fill: parent

    // ── State ───────────────────────────────────────────────────────────────
    property var    historyItems: []
    property bool   loading: false
    property string _histReqId: ""   // last request_id sent — stale signals are ignored

    // ── Lifecycle ───────────────────────────────────────────────────────────
    Component.onCompleted: {
        if (typeof Backend !== "undefined") {
            var rid = "scan-history-" + Date.now()
            _histReqId = rid
            loading = true
            Backend.listScanHistory(200, rid)
        }
    }

    // ── Backend wiring ───────────────────────────────────────────────────────
    Connections {
        target: Backend || null
        enabled: target !== null

        function onScanHistoryLoaded(request_id, items) {
            if (request_id !== _histReqId && request_id !== "") return
            historyItems = items || []
            loading = false
        }
    }

    // ── Layout ───────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // ── Header bar ──────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "Scan History"
                font.pixelSize: 22; font.bold: true
                color: ThemeManager.foreground()
            }

            Text {
                visible: historyItems.length > 0
                text: historyItems.length + " scan" + (historyItems.length !== 1 ? "s" : "")
                font.pixelSize: 13; color: ThemeManager.muted()
                Layout.alignment: Qt.AlignVCenter
            }

            Item { Layout.fillWidth: true }

            BusyIndicator {
                running: loading
                Layout.preferredWidth: 22; Layout.preferredHeight: 22
            }

            Button {
                text: "Refresh"
                Layout.preferredWidth: 88; Layout.preferredHeight: 32
                onClicked: {
                    if (Backend) {
                        var rrid = "scan-history-" + Date.now()
                        _histReqId = rrid
                        loading = true
                        Backend.listScanHistory(200, rrid)
                    }
                }
                background: Rectangle {
                    color: parent.hovered ? ThemeManager.surface() : "transparent"
                    radius: 6; border.color: ThemeManager.border(); border.width: 1
                }
                contentItem: Text {
                    text: parent.text; color: ThemeManager.foreground()
                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        // ── Column headers ───────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; height: 34
            color: ThemeManager.surface(); radius: 6
            visible: historyItems.length > 0
            RowLayout {
                anchors { fill: parent; leftMargin: 14; rightMargin: 14 }
                spacing: 12
                Text { text: "Verdict";    font.pixelSize: 11; font.bold: true; color: ThemeManager.muted(); Layout.preferredWidth: 72 }
                Text { text: "File";       font.pixelSize: 11; font.bold: true; color: ThemeManager.muted(); Layout.fillWidth: true }
                Text { text: "Confidence"; font.pixelSize: 11; font.bold: true; color: ThemeManager.muted(); Layout.preferredWidth: 80; horizontalAlignment: Text.AlignHCenter }
                Text { text: "Date";       font.pixelSize: 11; font.bold: true; color: ThemeManager.muted(); Layout.preferredWidth: 160 }
                Item { Layout.preferredWidth: 64 }
            }
        }

        // ── Empty state ──────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; height: 100
            color: ThemeManager.surface(); radius: 10
            visible: !loading && historyItems.length === 0
            Text {
                anchors.centerIn: parent
                text: "No scans recorded yet.\nRun a file scan to populate history."
                font.pixelSize: 13; color: ThemeManager.muted()
                horizontalAlignment: Text.AlignHCenter
            }
        }

        // ── Scrollable list ──────────────────────────────────────────────────
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: parent.width
                spacing: 6

                Repeater {
                    model: historyItems   // newest-first from DB

                    delegate: Rectangle {
                        width: parent ? parent.width : 0
                        height: rowLayout.implicitHeight + 18
                        color: ThemeManager.panel(); radius: 8
                        border.width: 1
                        border.color: {
                            var r = modelData.verdict_risk || ""
                            if (r === "Failed")              return ThemeManager.border()
                            if (r === "Critical" || r === "High") return ThemeManager.danger
                            if (r === "Medium") return ThemeManager.warning
                            return ThemeManager.border()
                        }

                        // Hover highlight
                        Rectangle {
                            anchors.fill: parent; radius: parent.radius
                            color: rowHover.containsMouse ? Qt.rgba(1,1,1,0.04) : "transparent"
                        }

                        RowLayout {
                            id: rowLayout
                            anchors { fill: parent; leftMargin: 14; rightMargin: 14; topMargin: 10; bottomMargin: 10 }
                            spacing: 12

                            // Verdict badge
                            Rectangle {
                                Layout.preferredWidth: 72; height: 24; radius: 5
                                color: {
                                    var r = modelData.verdict_risk || ""
                                    if (r === "Failed")
                                        return Qt.rgba(0.5, 0.5, 0.5, 0.18)
                                    if (r === "Critical" || r === "High")
                                        return Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.18)
                                    if (r === "Medium")
                                        return Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.18)
                                    return Qt.rgba(ThemeManager.success.r, ThemeManager.success.g, ThemeManager.success.b, 0.14)
                                }
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.verdict_risk || "Low"
                                    font.pixelSize: 10; font.bold: true
                                    color: {
                                        var r = modelData.verdict_risk || ""
                                        if (r === "Failed")                 return ThemeManager.muted()
                                        if (r === "Critical" || r === "High") return ThemeManager.danger
                                        if (r === "Medium") return ThemeManager.warning
                                        return ThemeManager.success
                                    }
                                }
                            }

                            // File name + SHA256
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 1
                                Text {
                                    text: modelData.file_name || "(unknown)"
                                    font.pixelSize: 13; font.bold: true
                                    color: ThemeManager.foreground()
                                    elide: Text.ElideMiddle; Layout.fillWidth: true
                                }
                                Text {
                                    visible: !!(modelData.sha256)
                                    text: modelData.sha256 || ""
                                    font.pixelSize: 10
                                    color: ThemeManager.muted()
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                            }

                            // Confidence
                            Text {
                                Layout.preferredWidth: 80
                                text: (modelData.confidence || 0) + "%"
                                font.pixelSize: 12; color: ThemeManager.muted()
                                horizontalAlignment: Text.AlignHCenter
                            }

                            // Date
                            Text {
                                Layout.preferredWidth: 160
                                text: (modelData.created_at || "").replace("T", "  ")
                                font.pixelSize: 11; color: ThemeManager.muted()
                            }

                            // Open button — disabled when report_path is blank (Failed rows)
                            Button {
                                text: "Open"
                                Layout.preferredWidth: 64; Layout.preferredHeight: 28
                                enabled: !!(modelData.report_path) && modelData.verdict_risk !== "Failed"
                                onClicked: {
                                    if (Backend && modelData.report_path)
                                        Backend.loadScanReport(modelData.report_path)
                                }
                                background: Rectangle {
                                    color: parent.enabled
                                           ? (parent.hovered ? Qt.lighter(ThemeManager.primary, 1.15) : ThemeManager.primary)
                                           : ThemeManager.surface()
                                    radius: 5
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: parent.enabled ? "#ffffff" : ThemeManager.muted()
                                    font.pixelSize: 11; font.bold: true
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        MouseArea {
                            id: rowHover
                            anchors.fill: parent; hoverEnabled: true
                            cursorShape: modelData.report_path ? Qt.PointingHandCursor : Qt.ArrowCursor
                            z: -1
                            onClicked: {
                                if (Backend && modelData.report_path)
                                    Backend.loadScanReport(modelData.report_path)
                            }
                        }
                    }
                }

                Item { height: 16 }
            }
        }
    }
}


