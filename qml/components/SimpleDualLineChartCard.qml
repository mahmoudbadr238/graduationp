import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Card {
    id: simpleDualChartCard
    
    // Properties
    property string title: "Chart"
    property list<real> historyDataUp: []
    property list<real> historyDataDown: []
    property string valueUnit: "%"
    property color lineColorUp: ThemeManager.success
    property color lineColorDown: ThemeManager.warning
    property string labelUp: "Upload"
    property string labelDown: "Download"
    
    // Theme-aware property to trigger canvas repaint
    property color currentBorderColor: ThemeManager.border()
    onCurrentBorderColorChanged: canvas.requestPaint()
    
    // Helper function to format values with smart unit scaling (BPS -> KBPS -> MBPS -> GBPS)
    function formatValue(value) {
        if (valueUnit === "BPS") {
            // BPS to KBPS: divide by 1000
            if (value >= 1000000000) {  // >= 1 GBPS
                return (value / 1000000000).toFixed(2) + " GBPS"
            } else if (value >= 1000000) {  // >= 1 MBPS
                return (value / 1000000).toFixed(2) + " MBPS"
            } else if (value >= 1000) {  // >= 1 KBPS
                return (value / 1000).toFixed(2) + " KBPS"
            } else {
                return value.toFixed(0) + " BPS"
            }
        } else if (valueUnit === "%") {
            return value.toFixed(1) + "%"
        }
        return value.toFixed(1) + " " + valueUnit
    }
    
    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.margins: 12
        spacing: 12
        
        // Title
        Text {
            id: chartTitle
            text: simpleDualChartCard.title
            color: ThemeManager.foreground()
            font.pixelSize: 13
            font.weight: Font.Normal
            Layout.fillWidth: true
        }
        
        // Legend
        RowLayout {
            Layout.fillWidth: true
            spacing: 18
            
            RowLayout {
                spacing: 6
                Rectangle {
                    width: 12
                    height: 12
                    radius: 2
                    color: simpleDualChartCard.lineColorUp
                }
                Text {
                    text: simpleDualChartCard.labelUp
                    color: ThemeManager.muted()
                    font.pixelSize: 11
                }
            }
            
            RowLayout {
                spacing: 6
                Rectangle {
                    width: 12
                    height: 12
                    radius: 2
                    color: simpleDualChartCard.lineColorDown
                }
                Text {
                    text: simpleDualChartCard.labelDown
                    color: ThemeManager.muted()
                    font.pixelSize: 11
                }
            }
            
            Item { Layout.fillWidth: true }
        }
        
        // Canvas Chart
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 250
            
            color: ThemeManager.panel()
            border.color: ThemeManager.border()
            border.width: 1
            radius: 8
            
            Canvas {
                id: canvas
                anchors.fill: parent
                anchors.margins: 10
                
                onPaint: {
                    const has_up = historyDataUp.length > 0
                    const has_down = historyDataDown.length > 0
                    
                    if (!has_up && !has_down) return
                    
                    const ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    
                    // Draw background grid
                    ctx.strokeStyle = ThemeManager.border()
                    ctx.lineWidth = 1
                    ctx.globalAlpha = 0.5
                    
                    for (let i = 0; i <= 10; i++) {
                        const y = (height / 10) * i
                        ctx.beginPath()
                        ctx.moveTo(0, y)
                        ctx.lineTo(width, y)
                        ctx.stroke()
                    }
                    
                    ctx.globalAlpha = 1.0
                    
                    // Calculate scaling - keep data in BPS for calculations
                    const all_data = [...historyDataUp, ...historyDataDown]
                    let max_val = Math.max(1000, Math.max(...all_data) * 1.1)
                    const min_val = Math.min(...all_data) * 0.9
                    const val_range = max_val - min_val
                    const data_len = Math.max(historyDataUp.length, historyDataDown.length)
                    
                    // Determine display unit based on max value
                    let unit_scale = 1.0
                    let unit_label = "BPS"
                    if (simpleDualChartCard.valueUnit === "BPS") {
                        if (max_val >= 1000000000) {  // GBPS
                            unit_scale = 1 / 1000000000
                            unit_label = "GBPS"
                        } else if (max_val >= 1000000) {  // MBPS
                            unit_scale = 1 / 1000000
                            unit_label = "MBPS"
                        } else if (max_val >= 1000) {  // KBPS
                            unit_scale = 1 / 1000
                            unit_label = "KBPS"
                        }
                    }
                    
                    // Helper function to draw line
                    function drawLine(data, color) {
                        if (data.length === 0) return
                        
                        ctx.strokeStyle = color
                        ctx.lineWidth = 2.5
                        ctx.lineJoin = "round"
                        ctx.lineCap = "round"
                        
                        ctx.beginPath()
                        for (let i = 0; i < data.length; i++) {
                            const x = (i / Math.max(1, data_len - 1)) * width
                            const normalized = (data[i] * unit_scale - min_val * unit_scale) / (val_range * unit_scale)
                            const y = height - (normalized * height)
                            
                            if (i === 0) {
                                ctx.moveTo(x, y)
                            } else {
                                ctx.lineTo(x, y)
                            }
                        }
                        ctx.stroke()
                    }
                    
                    // Draw both lines
                    drawLine(historyDataUp, simpleDualChartCard.lineColorUp)
                    drawLine(historyDataDown, simpleDualChartCard.lineColorDown)
                    
                    // Draw Y-axis labels
                    ctx.fillStyle = ThemeManager.foreground()
                    ctx.font = "12px Arial"
                    ctx.textAlign = "right"
                    ctx.textBaseline = "middle"
                    
                    for (let i = 0; i <= 5; i++) {
                        const y = (height / 5) * i
                        const val = Math.round((1 - i / 5) * max_val)
                        ctx.fillText(val + unit_label, -5, y)
                    }
                }
            }
            
            // No data placeholder
            Text {
                anchors.centerIn: parent
                text: "No data yet"
                color: ThemeManager.muted()
                font.pixelSize: 13
                visible: simpleDualChartCard.historyDataUp.length === 0 && simpleDualChartCard.historyDataDown.length === 0
            }
        }
        
        // Footer stats
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 70
            color: ThemeManager.elevated()
            radius: 8
            
            RowLayout {
                anchors.fill: parent
                anchors.margins: 10
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12
                
                ColumnLayout {
                    Layout.preferredWidth: (parent.width - 24) / 2
                    spacing: 6
                    
                    Text {
                        text: "↑ " + simpleDualChartCard.labelUp
                        color: ThemeManager.muted()
                        font.pixelSize: 10
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                    }
                    
                    RowLayout {
                        spacing: 8
                        Layout.fillWidth: true
                        
                        ColumnLayout {
                            spacing: 0
                            
                            Text {
                                text: "Now"
                                color: ThemeManager.muted()
                                font.pixelSize: 9
                            }
                            Text {
                                text: simpleDualChartCard.historyDataUp.length > 0 ?
                                      simpleDualChartCard.formatValue(simpleDualChartCard.historyDataUp[simpleDualChartCard.historyDataUp.length - 1]) : "—"
                                color: ThemeManager.foreground()
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                        }
                        
                        ColumnLayout {
                            spacing: 0
                            
                            Text {
                                text: "Peak"
                                color: ThemeManager.muted()
                                font.pixelSize: 9
                            }
                            Text {
                                text: simpleDualChartCard.historyDataUp.length > 0 ?
                                      simpleDualChartCard.formatValue(Math.max(...simpleDualChartCard.historyDataUp)) : "—"
                                color: ThemeManager.foreground()
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                        }
                        
                        Item { Layout.fillWidth: true }
                    }
                }
                
                ColumnLayout {
                    Layout.preferredWidth: (parent.width - 24) / 2
                    spacing: 6
                    
                    Text {
                        text: "↓ " + simpleDualChartCard.labelDown
                        color: ThemeManager.muted()
                        font.pixelSize: 10
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                    }
                    
                    RowLayout {
                        spacing: 8
                        Layout.fillWidth: true
                        
                        ColumnLayout {
                            spacing: 0
                            
                            Text {
                                text: "Now"
                                color: ThemeManager.muted()
                                font.pixelSize: 9
                            }
                            Text {
                                text: simpleDualChartCard.historyDataDown.length > 0 ?
                                      simpleDualChartCard.formatValue(simpleDualChartCard.historyDataDown[simpleDualChartCard.historyDataDown.length - 1]) : "—"
                                color: ThemeManager.foreground()
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                        }
                        
                        ColumnLayout {
                            spacing: 0
                            
                            Text {
                                text: "Peak"
                                color: ThemeManager.muted()
                                font.pixelSize: 9
                            }
                            Text {
                                text: simpleDualChartCard.historyDataDown.length > 0 ?
                                      simpleDualChartCard.formatValue(Math.max(...simpleDualChartCard.historyDataDown)) : "—"
                                color: ThemeManager.foreground()
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                        }
                        
                        Item { Layout.fillWidth: true }
                    }
                }
            }
        }
    }
}
