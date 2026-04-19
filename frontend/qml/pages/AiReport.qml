import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

// ─────────────────────────────────────────────────────────────────────────────
// AiReport  –  Full AI Security Analyst Detailed Report
// Reached via "Show More" from the ScanCenter Brief box.
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: reportRoot
    anchors.fill: parent

    // The ScanCenter page sets these before navigating here.
    // They are bound via the root-level alias properties in main.qml.
    property string briefText: ""
    property string detailedText: ""
    readonly property int titleFontSize: Math.max(ThemeManager.fontSize_body + 4, 20)
    readonly property int sectionTitleFontSize: Math.max(ThemeManager.fontSize_body + 2, 17)
    readonly property int briefFontSize: Math.max(ThemeManager.fontSize_body + 2, 16)
    readonly property int detailFontSize: Math.max(ThemeManager.fontSize_body + 1, 15)
    readonly property string normalizedBriefText: normalizeText(briefText)
    readonly property string normalizedDetailedText: normalizeText(detailedText)

    function normalizeText(value) {
        var text = (value || "").toString()
        text = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
        text = text.replace(/\n{3,}/g, "\n\n")
        return text.trim()
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeManager.background()

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 0
            spacing: 0

            // ── Header bar ────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 56
                color: ThemeManager.panel()
                z: 1

                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 1
                    color: ThemeManager.border()
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16; anchors.rightMargin: 16
                    spacing: 12

                    // ← Back button
                    Button {
                        text: "← Back"
                        flat: true
                        implicitHeight: 36; implicitWidth: 80
                        contentItem: Text {
                            text: parent.text
                            color: ThemeManager.accent
                            font.pixelSize: reportRoot.briefFontSize
                            font.weight: (Font.SemiBold || 600)
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            color: parent.hovered ? ThemeManager.surface() : "transparent"
                            radius: 8
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                        onClicked: {
                            if (typeof loadRoute === "function")
                                loadRoute("scan-tool")
                        }
                    }

                    // Page title
                    Text {
                        text: "🛡️  AI Security Analyst — Detailed Report"
                        color: ThemeManager.foreground()
                        font.pixelSize: reportRoot.titleFontSize
                        font.weight: (Font.Bold || 700)
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    // Export Log button
                    Button {
                        text: "Export Log"
                        implicitHeight: 36; implicitWidth: 110
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: reportRoot.briefFontSize
                            font.weight: (Font.SemiBold || 600)
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            color: parent.hovered
                                   ? Qt.darker(ThemeManager.accent, 1.08)
                                   : ThemeManager.accent
                            radius: 8
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                        onClicked: {
                            if (typeof Backend !== "undefined")
                                Backend.exportAiLog(reportRoot.normalizedDetailedText)
                        }
                    }
                }
            }

            // ── Scrollable report body ────────────────────────────────────
            ScrollView {
                id: reportScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AlwaysOff }

                ColumnLayout {
                    width: Math.max(320, Math.min(920, reportScroll.availableWidth - 48))
                    x: Math.max(24, (reportScroll.availableWidth - width) / 2)
                    spacing: 18

                    Item { height: 16 }

                    // Brief summary card
                    Rectangle {
                        visible: reportRoot.normalizedBriefText !== ""
                        Layout.fillWidth: true
                        implicitHeight: briefCol.height + 24
                        radius: 10
                        color: Qt.rgba(ThemeManager.accent.r || 0.2,
                                       ThemeManager.accent.g || 0.5,
                                       ThemeManager.accent.b || 1.0, 0.07)
                        border.width: 1
                        border.color: Qt.rgba(ThemeManager.accent.r || 0.2,
                                              ThemeManager.accent.g || 0.5,
                                              ThemeManager.accent.b || 1.0, 0.25)

                        Column {
                            id: briefCol
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.top: parent.top; anchors.margins: 12
                            spacing: 6

                            Text {
                                width: parent.width
                                text: "Brief"
                                color: ThemeManager.foreground()
                                font.pixelSize: reportRoot.sectionTitleFontSize
                                font.weight: (Font.SemiBold || 600)
                            }
                            Text {
                                width: parent.width
                                text: reportRoot.normalizedBriefText
                                color: ThemeManager.foreground()
                                font.pixelSize: reportRoot.briefFontSize
                                wrapMode: Text.WordWrap
                                lineHeight: 1.55
                            }
                        }
                    }

                    // Detailed report card
                    Rectangle {
                        visible: reportRoot.normalizedDetailedText !== ""
                        Layout.fillWidth: true
                        implicitHeight: detailCol.height + 28
                        radius: 10
                        color: ThemeManager.panel()
                        border.width: 1
                        border.color: ThemeManager.border()

                        Column {
                            id: detailCol
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.top: parent.top; anchors.margins: 14
                            spacing: 8

                            Text {
                                width: parent.width
                                text: "Detailed Analysis"
                                color: ThemeManager.foreground()
                                font.pixelSize: reportRoot.sectionTitleFontSize
                                font.weight: (Font.SemiBold || 600)
                            }

                            Rectangle {
                                width: parent.width
                                height: 1
                                color: ThemeManager.border()
                            }

                            TextArea {
                                width: parent.width
                                height: Math.max(220, contentHeight)
                                readOnly: true
                                selectByMouse: true
                                text: reportRoot.normalizedDetailedText
                                color: ThemeManager.foreground()
                                font.pixelSize: reportRoot.detailFontSize
                                wrapMode: TextEdit.Wrap
                                textFormat: TextEdit.PlainText
                                topPadding: 0
                                bottomPadding: 0
                                leftPadding: 0
                                rightPadding: 0
                                background: null
                            }
                        }
                    }

                    // Empty state
                    Item {
                        visible: reportRoot.normalizedDetailedText === ""
                        Layout.fillWidth: true
                        implicitHeight: 200
                        ColumnLayout {
                            anchors.centerIn: parent; spacing: 10
                            Text {
                                text: "🤖"
                                font.pixelSize: 48; opacity: 0.4
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: "No AI report available"
                                color: ThemeManager.muted()
                                font.pixelSize: reportRoot.sectionTitleFontSize
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: "Run a scan with the Sandbox option enabled to generate an AI report."
                                color: ThemeManager.muted()
                                font.pixelSize: reportRoot.briefFontSize
                                wrapMode: Text.WordWrap
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    Item { height: 24 }
                }
            }
        }
    }
}
