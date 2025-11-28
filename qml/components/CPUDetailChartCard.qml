import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ui"

Card {
    id: cpuChartCard
    
    // Properties
    property string title: "CPU Usage"
    property list<real> historyData: []
    property list<real> coreData: []
    property string viewMode: "overall"  // "overall" or "detailed"
    property color lineColor: ThemeManager.accent
    
    // Theme-aware property to trigger canvas repaint
    property color currentBorderColor: ThemeManager.border()
    onCurrentBorderColorChanged: canvas.requestPaint()
    
    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.margins: 12
        spacing: 12
        
        // Header with title and toggle button
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            
            Text {
                text: cpuChartCard.title
                color: ThemeManager.foreground()
                font.pixelSize: 13
                font.weight: Font.Normal
            }
            
            Item { Layout.fillWidth: true }
            
            // Toggle button
            Rectangle {
                width: 120
                height: 32
                radius: 6
                color: ThemeManager.panel()
                border.color: ThemeManager.accent
                border.width: 1
                
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        cpuChartCard.viewMode = (cpuChartCard.viewMode === "overall") ? "detailed" : "overall"
                    }
                }
                
                Text {
                    anchors.centerIn: parent
                    text: cpuChartCard.viewMode === "overall" ? "Overall" : "Detailed"
                    color: ThemeManager.accent
                    font.pixelSize: 11
                    font.weight: Font.Medium
                }
            }
        }
        
        // Legend for detailed view
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: cpuChartCard.viewMode === "detailed" ? 40 : 0
            visible: cpuChartCard.viewMode === "detailed"
            color: "transparent"
            
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                spacing: 18
                
                Text {
                    text: cpuChartCard.viewMode === "detailed" ? "Core Utilization" : ""
                    color: ThemeManager.muted()
                    font.pixelSize: 11
                    font.weight: Font.Medium
                }
                
                Item { Layout.fillWidth: true }
                
                Text {
                    text: cpuChartCard.coreData.length > 0 ? 
                          "Cores: " + cpuChartCard.coreData.length : ""
                    color: ThemeManager.muted()
                    font.pixelSize: 11
                }
            }
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
                    const ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    
                    // Determine which data to display
                    const displayData = cpuChartCard.viewMode === "overall" ? 
                                       cpuChartCard.historyData : 
                                       cpuChartCard.coreData
                    
                    if (displayData.length === 0) return
                    
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
                    
                    // Calculate scaling
                    const max_val = Math.max(100, Math.max(...displayData) * 1.1)
                    const min_val = 0
                    const val_range = max_val - min_val
                    const data_len = displayData.length
                    
                    // Draw line
                    ctx.strokeStyle = cpuChartCard.lineColor
                    ctx.lineWidth = 2.5
                    ctx.lineJoin = "round"
                    ctx.lineCap = "round"
                    
                    ctx.beginPath()
                    for (let i = 0; i < displayData.length; i++) {
                        const x = (i / Math.max(1, data_len - 1)) * width
                        const normalized = (displayData[i] - min_val) / val_range
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
                visible: cpuChartCard.viewMode === "overall" ? 
                        cpuChartCard.historyData.length === 0 : 
                        cpuChartCard.coreData.length === 0
            }
        }
        
        // Footer stats
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 70
            color: ThemeManager.elevated()
            radius: 8
            visible: cpuChartCard.viewMode === "overall"
            
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
                            if (cpuChartCard.historyData.length > 0) {
                                const val = cpuChartCard.historyData[cpuChartCard.historyData.length - 1]
                                return val.toFixed(1) + "%"
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
                            if (cpuChartCard.historyData.length > 0) {
                                const sum = cpuChartCard.historyData.reduce((a, b) => a + b, 0)
                                const avg = sum / cpuChartCard.historyData.length
                                return avg.toFixed(1) + "%"
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
                            if (cpuChartCard.historyData.length > 0) {
                                const peak = Math.max(...cpuChartCard.historyData)
                                return peak.toFixed(1) + "%"
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
        
        // Detailed stats for core data
        ColumnLayout {
            Layout.fillWidth: true
            visible: cpuChartCard.viewMode === "detailed"
            spacing: 8
            
            Text {
                text: "Per-Core Utilization:"
                color: ThemeManager.muted()
                font.pixelSize: 11
                font.weight: Font.Medium
            }
            
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                color: "transparent"
                
                RowLayout {
                    anchors.fill: parent
                    spacing: 8
                    
                    Repeater {
                        model: Math.min(cpuChartCard.coreData.length, 8)
                        
                        Rectangle {
                            Layout.preferredWidth: 40
                            Layout.fillHeight: true
                            radius: 4
                            color: ThemeManager.panel()
                            border.color: ThemeManager.accent
                            border.width: 1
                            
                            Column {
                                anchors.centerIn: parent
                                spacing: 2
                                
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "C" + (index + 1)
                                    color: ThemeManager.muted()
                                    font.pixelSize: 9
                                }
                                
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: cpuChartCard.coreData[index].toFixed(0) + "%"
                                    color: ThemeManager.accent
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                    }
                    
                    Item { Layout.fillWidth: true }
                }
            }
            
            Text {
                text: cpuChartCard.coreData.length > 8 ? 
                      "+ " + (cpuChartCard.coreData.length - 8) + " more cores" : ""
                color: ThemeManager.muted()
                font.pixelSize: 10
                visible: cpuChartCard.coreData.length > 8
            }
        }
    }
}
