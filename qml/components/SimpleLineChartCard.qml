import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Card {
    id: simpleChartCard
    
    // Properties
    property string title: "Chart"
    property list<real> historyData: []
    property string valueUnit: "%"
    property color lineColor: ThemeManager.accent
    property int pointCount: Math.max(5, Math.min(60, historyData.length))
    
    // Theme-aware property to trigger canvas repaint
    property color currentBorderColor: ThemeManager.border()
    onCurrentBorderColorChanged: canvas.requestPaint()
    
    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.margins: 12
        spacing: 12
        
        // Title
        Text {
            id: chartTitle
            text: simpleChartCard.title
            color: ThemeManager.foreground()
            font.pixelSize: 13
            font.weight: Font.Normal
            Layout.fillWidth: true
        }
        
        // Simple Bar Chart (no QtCharts)
        Rectangle {
            id: chartContainer
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 200
            
            color: ThemeManager.panel()
            border.color: ThemeManager.border()
            border.width: 1
            radius: 8
            
            Canvas {
                id: canvas
                anchors.fill: parent
                anchors.margins: 10
                
                onPaint: {
                    if (historyData.length === 0) return
                    
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
                    
                    // Calculate max value for scaling
                    const max_val = Math.max(100, Math.max(...historyData) * 1.1)
                    const min_val = Math.min(...historyData) * 0.9
                    const val_range = max_val - min_val
                    
                    // Draw line chart
                    ctx.strokeStyle = simpleChartCard.lineColor
                    ctx.lineWidth = 2
                    ctx.lineJoin = "round"
                    ctx.lineCap = "round"
                    
                    // Draw line
                    ctx.beginPath()
                    for (let i = 0; i < historyData.length; i++) {
                        const x = (i / Math.max(1, historyData.length - 1)) * width
                        const normalized = (historyData[i] - min_val) / val_range
                        const y = height - (normalized * height)
                        
                        if (i === 0) {
                            ctx.moveTo(x, y)
                        } else {
                            ctx.lineTo(x, y)
                        }
                    }
                    ctx.stroke()
                    
                    // Draw Y-axis labels
                    ctx.fillStyle = ThemeManager.foreground()
                    ctx.font = "12px Arial"
                    ctx.textAlign = "right"
                    ctx.textBaseline = "middle"
                    
                    for (let i = 0; i <= 5; i++) {
                        const y = (height / 5) * i
                        const val = Math.round((1 - i / 5) * max_val)
                        ctx.fillText(val + "%", -5, y)
                    }
                }
            }
            
            // No data placeholder
            Text {
                anchors.centerIn: parent
                text: "No data yet"
                color: ThemeManager.muted()
                font.pixelSize: 13
                visible: simpleChartCard.historyData.length === 0
            }
        }
        
        // Footer with current/max/avg values
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
                spacing: 20
                
                ColumnLayout {
                    spacing: 2
                    Layout.minimumWidth: 60
                    
                    Text {
                        text: "Current"
                        color: ThemeManager.muted()
                        font.pixelSize: 9
                    }
                    
                    Text {
                        text: {
                            if (simpleChartCard.historyData.length > 0) {
                                const val = simpleChartCard.historyData[simpleChartCard.historyData.length - 1]
                                return val.toFixed(1) + simpleChartCard.valueUnit
                            }
                            return "—"
                        }
                        color: ThemeManager.foreground()
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                    }
                }
                
                ColumnLayout {
                    spacing: 2
                    Layout.minimumWidth: 60
                    
                    Text {
                        text: "Average"
                        color: ThemeManager.muted()
                        font.pixelSize: 9
                    }
                    
                    Text {
                        text: {
                            if (simpleChartCard.historyData.length > 0) {
                                const sum = simpleChartCard.historyData.reduce((a, b) => a + b, 0)
                                const avg = sum / simpleChartCard.historyData.length
                                return avg.toFixed(1) + simpleChartCard.valueUnit
                            }
                            return "—"
                        }
                        color: ThemeManager.foreground()
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                    }
                }
                
                ColumnLayout {
                    spacing: 2
                    Layout.minimumWidth: 60
                    
                    Text {
                        text: "Peak"
                        color: ThemeManager.muted()
                        font.pixelSize: 9
                    }
                    
                    Text {
                        text: {
                            if (simpleChartCard.historyData.length > 0) {
                                const peak = Math.max(...simpleChartCard.historyData)
                                return peak.toFixed(1) + simpleChartCard.valueUnit
                            }
                            return "—"
                        }
                        color: ThemeManager.foreground()
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                    }
                }
                
                Item { Layout.fillWidth: true }
            }
        }
    }
    
    // Redraw when data changes
}
