import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCharts
import "../theme"

Card {
    id: lineChartCard
    
    // Properties
    property string title: "Chart"
    property list<real> historyData: []
    property real minValue: 0
    property real maxValue: 100
    property string valueUnit: "%"
    property color lineColor: Theme.primary
    property color areaColor: Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.15)
    property int pointCount: Math.max(5, Math.min(60, historyData.length))
    
    // Auto-ranging mode (for CPU/Memory)
    property bool autoRangeY: true
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing_md
        spacing: Theme.spacing_md
        
        // Title
        Text {
            id: chartTitle
            text: lineChartCard.title
            color: Theme.text_primary
            font.pixelSize: Theme.typography.body.size
            font.weight: Theme.typography.body.weight
            Layout.fillWidth: true
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
                
                // X-Axis (simplified)
                ValueAxis {
                    id: xAxis
                    min: 0
                    max: Math.max(1, lineChartCard.pointCount - 1)
                    labelsVisible: false
                    gridVisible: true
                    gridLineColor: Theme.divider
                }
                
                // Y-Axis
                ValueAxis {
                    id: yAxis
                    min: lineChartCard.minValue
                    max: lineChartCard.maxValue
                    tickCount: 5
                    labelsColor: Theme.text_secondary
                    gridLineColor: Theme.divider
                }
                
                // Line Series
                LineSeries {
                    id: lineSeries
                    name: lineChartCard.title
                    axisX: xAxis
                    axisY: yAxis
                    
                    color: lineChartCard.lineColor
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
                visible: lineChartCard.historyData.length === 0
            }
        }
        
        // Footer with current/max values
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing_lg
            
            // Current value
            ColumnLayout {
                spacing: 4
                
                Text {
                    text: "Current"
                    color: Theme.text_secondary
                    font.pixelSize: Theme.typography.caption.size
                }
                
                Text {
                    text: {
                        if (lineChartCard.historyData.length > 0) {
                            const val = lineChartCard.historyData[lineChartCard.historyData.length - 1]
                            return val.toFixed(1) + lineChartCard.valueUnit
                        }
                        return "—"
                    }
                    color: Theme.text_primary
                    font.pixelSize: Theme.typography.body.size
                    font.weight: Font.DemiBold
                }
            }
            
            // Average value
            ColumnLayout {
                spacing: 4
                
                Text {
                    text: "Average"
                    color: Theme.text_secondary
                    font.pixelSize: Theme.typography.caption.size
                }
                
                Text {
                    text: {
                        if (lineChartCard.historyData.length > 0) {
                            const sum = lineChartCard.historyData.reduce((a, b) => a + b, 0)
                            const avg = sum / lineChartCard.historyData.length
                            return avg.toFixed(1) + lineChartCard.valueUnit
                        }
                        return "—"
                    }
                    color: Theme.text_primary
                    font.pixelSize: Theme.typography.body.size
                    font.weight: Font.DemiBold
                }
            }
            
            // Peak value
            ColumnLayout {
                spacing: 4
                
                Text {
                    text: "Peak"
                    color: Theme.text_secondary
                    font.pixelSize: Theme.typography.caption.size
                }
                
                Text {
                    text: {
                        if (lineChartCard.historyData.length > 0) {
                            const peak = Math.max(...lineChartCard.historyData)
                            return peak.toFixed(1) + lineChartCard.valueUnit
                        }
                        return "—"
                    }
                    color: Theme.text_primary
                    font.pixelSize: Theme.typography.body.size
                    font.weight: Font.DemiBold
                }
            }
            
            Item { Layout.fillWidth: true }
        }
    }
    
    // Update chart data when historyData changes
    onHistoryDataChanged: {
        updateChartData()
    }
    
    // Update on component complete
    Component.onCompleted: {
        updateChartData()
    }
    
    function updateChartData() {
        if (!chartView) return
        
        // Clear existing series
        lineSeries.clear()
        
        // Calculate Y-axis range if auto-ranging
        if (autoRangeY && historyData.length > 0) {
            const maxData = Math.max(...historyData)
            const minData = Math.min(...historyData)
            
            // Add 10% padding
            const padding = (maxData - minData) * 0.1
            yAxis.min = Math.max(0, minData - padding)
            yAxis.max = maxData + padding
        } else {
            yAxis.min = minValue
            yAxis.max = maxValue
        }
        
        // Add data points to line series
        for (let i = 0; i < historyData.length; i++) {
            lineSeries.append(i, historyData[i])
        }
        
        // Update X-axis range
        if (historyData.length > 1) {
            xAxis.max = historyData.length - 1
        }
    }
}
