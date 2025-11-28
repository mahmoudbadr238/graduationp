import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCharts
import "../theme"

Card {
    id: dualChartCard
    
    // Properties
    property string title: "Chart"
    property list<real> historyDataUp: []
    property list<real> historyDataDown: []
    property real minValue: 0
    property real maxValue: 100
    property string valueUnit: "%"
    property color lineColorUp: Theme.success
    property color lineColorDown: Theme.warning
    property color areaColorUp: Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.15)
    property color areaColorDown: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.15)
    property string labelUp: "Upload"
    property string labelDown: "Download"
    property int pointCount: Math.max(5, Math.min(60, Math.max(historyDataUp.length, historyDataDown.length)))
    
    // Auto-ranging mode
    property bool autoRangeY: true
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        spacing: Theme.spacing_md
        
        // Title
        Text {
            id: chartTitle
            text: dualChartCard.title
            color: Theme.text_primary
            font.pixelSize: Theme.typography.body.size
            font.weight: Theme.typography.body.weight
            Layout.fillWidth: true
        }
        
        // Legend
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing_lg
            
            RowLayout {
                spacing: 6
                Rectangle {
                    width: 12
                    height: 12
                    radius: 2
                    color: dualChartCard.lineColorUp
                }
                Text {
                    text: dualChartCard.labelUp
                    color: Theme.text_secondary
                    font.pixelSize: Theme.typography.caption.size
                }
            }
            
            RowLayout {
                spacing: 6
                Rectangle {
                    width: 12
                    height: 12
                    radius: 2
                    color: dualChartCard.lineColorDown
                }
                Text {
                    text: dualChartCard.labelDown
                    color: Theme.text_secondary
                    font.pixelSize: Theme.typography.caption.size
                }
            }
            
            Item { Layout.fillWidth: true }
        }
        
        // Chart Container with border
        Rectangle {
            id: chartContainer
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 200
            
            color: Theme.surface
            border.color: Theme.border
            border.width: 1
            radius: Theme.radius_sm
            
            ChartView {
                id: chartView
                anchors.fill: parent
                anchors.margins: 1
                
                backgroundColor: "transparent"
                plotAreaColor: "transparent"
                
                animationOptions: ChartView.SeriesAnimations
                animationDuration: 300
                
                // Remove margins/padding for compact chart
                margins.top: 10
                margins.bottom: 10
                margins.left: 10
                margins.right: 10
                
                antialiasing: true
                
                // X-Axis
                ValueAxis {
                    id: xAxis
                    min: 0
                    max: Math.max(1, dualChartCard.pointCount - 1)
                    labelsVisible: false
                    gridVisible: true
                    gridLineColor: Theme.divider
                }
                
                // Y-Axis
                ValueAxis {
                    id: yAxis
                    min: dualChartCard.minValue
                    max: dualChartCard.maxValue
                    tickCount: 5
                    labelsColor: Theme.text_secondary
                    gridLineColor: Theme.divider
                }
                
                // Upload Line Series
                LineSeries {
                    id: lineSeriesUp
                    name: dualChartCard.labelUp
                    axisX: xAxis
                    axisY: yAxis
                    
                    color: dualChartCard.lineColorUp
                    width: 2
                    useOpenGL: true
                }
                
                // Download Line Series
                LineSeries {
                    id: lineSeriesDown
                    name: dualChartCard.labelDown
                    axisX: xAxis
                    axisY: yAxis
                    
                    color: dualChartCard.lineColorDown
                    width: 2
                    useOpenGL: true
                }
            }
            
            // No data placeholder
            Text {
                anchors.centerIn: parent
                text: "No data yet"
                color: Theme.text_secondary
                font.pixelSize: Theme.typography.body.size
                visible: dualChartCard.historyDataUp.length === 0 && dualChartCard.historyDataDown.length === 0
            }
        }
        
        // Footer with current/peak values for both series
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing_lg
            
            // Upload Current/Peak
            ColumnLayout {
                spacing: 4
                
                Text {
                    text: "↑ " + dualChartCard.labelUp
                    color: Theme.text_secondary
                    font.pixelSize: Theme.typography.caption.size
                    font.weight: Font.Medium
                }
                
                RowLayout {
                    spacing: Theme.spacing_md
                    
                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: "Now"
                            color: Theme.text_secondary
                            font.pixelSize: Theme.typography.caption.size
                        }
                        Text {
                            text: {
                                if (dualChartCard.historyDataUp.length > 0) {
                                    const val = dualChartCard.historyDataUp[dualChartCard.historyDataUp.length - 1]
                                    return val.toFixed(1) + dualChartCard.valueUnit
                                }
                                return "—"
                            }
                            color: Theme.text_primary
                            font.pixelSize: Theme.typography.body.size
                            font.weight: Font.DemiBold
                        }
                    }
                    
                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: "Peak"
                            color: Theme.text_secondary
                            font.pixelSize: Theme.typography.caption.size
                        }
                        Text {
                            text: {
                                if (dualChartCard.historyDataUp.length > 0) {
                                    const peak = Math.max(...dualChartCard.historyDataUp)
                                    return peak.toFixed(1) + dualChartCard.valueUnit
                                }
                                return "—"
                            }
                            color: Theme.text_primary
                            font.pixelSize: Theme.typography.body.size
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }
            
            // Download Current/Peak
            ColumnLayout {
                spacing: 4
                
                Text {
                    text: "↓ " + dualChartCard.labelDown
                    color: Theme.text_secondary
                    font.pixelSize: Theme.typography.caption.size
                    font.weight: Font.Medium
                }
                
                RowLayout {
                    spacing: Theme.spacing_md
                    
                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: "Now"
                            color: Theme.text_secondary
                            font.pixelSize: Theme.typography.caption.size
                        }
                        Text {
                            text: {
                                if (dualChartCard.historyDataDown.length > 0) {
                                    const val = dualChartCard.historyDataDown[dualChartCard.historyDataDown.length - 1]
                                    return val.toFixed(1) + dualChartCard.valueUnit
                                }
                                return "—"
                            }
                            color: Theme.text_primary
                            font.pixelSize: Theme.typography.body.size
                            font.weight: Font.DemiBold
                        }
                    }
                    
                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: "Peak"
                            color: Theme.text_secondary
                            font.pixelSize: Theme.typography.caption.size
                        }
                        Text {
                            text: {
                                if (dualChartCard.historyDataDown.length > 0) {
                                    const peak = Math.max(...dualChartCard.historyDataDown)
                                    return peak.toFixed(1) + dualChartCard.valueUnit
                                }
                                return "—"
                            }
                            color: Theme.text_primary
                            font.pixelSize: Theme.typography.body.size
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }
            
            Item { Layout.fillWidth: true }
        }
    }
    
    // Update chart data when history changes
    onHistoryDataUpChanged: updateChartData()
    onHistoryDataDownChanged: updateChartData()
    
    Component.onCompleted: {
        updateChartData()
    }
    
    function updateChartData() {
        if (!chartView) return
        
        lineSeriesUp.clear()
        lineSeriesDown.clear()
        
        // Calculate Y-axis range if auto-ranging
        if (autoRangeY && (historyDataUp.length > 0 || historyDataDown.length > 0)) {
            const allData = [...historyDataUp, ...historyDataDown]
            const maxData = Math.max(...allData)
            const minData = Math.min(...allData)
            
            // Add 10% padding
            const padding = (maxData - minData) * 0.1
            yAxis.min = Math.max(0, minData - padding)
            yAxis.max = maxData + padding
        } else {
            yAxis.min = minValue
            yAxis.max = maxValue
        }
        
        // Add upload data points
        for (let i = 0; i < historyDataUp.length; i++) {
            lineSeriesUp.append(i, historyDataUp[i])
        }
        
        // Add download data points
        for (let i = 0; i < historyDataDown.length; i++) {
            lineSeriesDown.append(i, historyDataDown[i])
        }
        
        // Update X-axis range
        const maxLen = Math.max(historyDataUp.length, historyDataDown.length)
        if (maxLen > 1) {
            xAxis.max = maxLen - 1
        }
    }
}
