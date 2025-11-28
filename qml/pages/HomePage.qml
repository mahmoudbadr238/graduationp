import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../ui"

Item {
    id: root
    anchors.fill: parent
    
    // Security facts data
    property var securityFacts: [
        {
            title: "Password Security",
            facts: [
                "Use passwords with at least 12 characters",
                "Include uppercase, lowercase, numbers & symbols",
                "Never reuse passwords across accounts",
                "Use a password manager for security",
                "Enable two-factor authentication (2FA)",
                "Change passwords every 90 days",
                "Avoid personal info in passwords",
                "Check if your passwords were leaked"
            ]
        },
        {
            title: "Phishing Protection",
            facts: [
                "Verify sender email addresses carefully",
                "Don't click links in suspicious emails",
                "Check URLs before entering credentials",
                "Look for HTTPS and valid certificates",
                "Be wary of urgent or threatening messages",
                "Report phishing attempts to IT",
                "Use email filtering and spam protection",
                "When in doubt, contact sender directly"
            ]
        },
        {
            title: "Malware Prevention",
            facts: [
                "Keep your operating system updated",
                "Install reputable antivirus software",
                "Don't download from untrusted sources",
                "Scan USB drives before opening files",
                "Be cautious with email attachments",
                "Avoid pirated software and cracks",
                "Regular system scans are essential",
                "Back up your data regularly"
            ]
        },
        {
            title: "Network Security",
            facts: [
                "Use WPA3 encryption for WiFi",
                "Avoid public WiFi for sensitive tasks",
                "Use a VPN on untrusted networks",
                "Change default router passwords",
                "Disable WPS on your router",
                "Enable your firewall at all times",
                "Monitor connected devices regularly",
                "Segment IoT devices on separate network"
            ]
        },
        {
            title: "Data Protection",
            facts: [
                "Encrypt sensitive files and folders",
                "Use secure file sharing services",
                "Shred documents before disposal",
                "Lock your screen when away",
                "Disable auto-fill for sensitive data",
                "Review app permissions regularly",
                "Use secure cloud storage with 2FA",
                "Know your organization's data policies"
            ]
        },
        {
            title: "Social Engineering",
            facts: [
                "Verify identity before sharing info",
                "Be cautious of unsolicited calls",
                "Don't share sensitive info on social media",
                "Question unusual requests from 'colleagues'",
                "Tailgating is a real security threat",
                "Report suspicious behavior immediately",
                "Trust but verify - always",
                "Attend security awareness training"
            ]
        }
    ]
    
    property int currentFactIndex: 0
    property var currentFact: securityFacts[currentFactIndex]
    
    // Auto-rotate facts every 15 seconds
    Timer {
        interval: 15000
        running: true
        repeat: true
        onTriggered: {
            currentFactIndex = (currentFactIndex + 1) % securityFacts.length
        }
    }
    
    Rectangle {
        anchors.fill: parent
        color: ThemeManager.isDark() ? ThemeManager.darkBg : ThemeManager.lightBg
        
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            
            // ===== HEADER =====
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 90
                color: ThemeManager.isDark() ? ThemeManager.darkBg : ThemeManager.lightBg
                
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 32
                    anchors.rightMargin: 32
                    anchors.topMargin: 16
                    spacing: 20
                    
                    Column {
                        spacing: 8
                        
                        Text {
                            text: "Welcome to Sentinel"
                            color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                            font.pixelSize: 28
                            font.bold: true
                        }
                        
                        Text {
                            text: "Your Endpoint Security Suite - Protecting what matters most"
                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                            font.pixelSize: 14
                        }
                    }
                    
                    Item { Layout.fillWidth: true }
                    
                    // Current time
                    Column {
                        spacing: 4
                        
                        Text {
                            id: timeText
                            text: Qt.formatTime(new Date(), "hh:mm AP")
                            color: ThemeManager.accent
                            font.pixelSize: 24
                            font.bold: true
                            horizontalAlignment: Text.AlignRight
                            
                            Timer {
                                interval: 1000
                                running: true
                                repeat: true
                                onTriggered: timeText.text = Qt.formatTime(new Date(), "hh:mm AP")
                            }
                        }
                        
                        Text {
                            text: Qt.formatDate(new Date(), "dddd, MMMM d, yyyy")
                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                }
            }
            
            // ===== SCROLLABLE CONTENT =====
            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: mainRow.implicitHeight + 48
                clip: true
                ScrollBar.vertical: ScrollBar { }
                
                RowLayout {
                    id: mainRow
                    width: parent.width - 48
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: 16
                    spacing: 24
                    
                    // ===== LEFT COLUMN =====
                    ColumnLayout {
                        Layout.preferredWidth: 420
                        Layout.maximumWidth: 450
                        Layout.alignment: Qt.AlignTop
                        spacing: 20
                        
                        // Security Facts Card
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 480
                            radius: 16
                            color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                            border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                            
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 24
                                spacing: 12
                                
                                // Title
                                Text {
                                    text: "Security Facts You Should Know"
                                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                    font.pixelSize: 16
                                    font.bold: true
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                
                                // Security Triangle with edge-tracing animation
                                SecurityTriangle {
                                    id: securityTriangle
                                    Layout.preferredWidth: 120
                                    Layout.preferredHeight: 110
                                    Layout.alignment: Qt.AlignHCenter
                                    live: true
                                    strokeColor: ThemeManager.isDark() ? "#4B5563" : "#9CA3AF"
                                    activeColor: ThemeManager.accent
                                    lineWidth: 3.5
                                }
                                
                                // Category title
                                Text {
                                    text: currentFact.title
                                    color: ThemeManager.accent
                                    font.pixelSize: 14
                                    font.bold: true
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                
                                // Facts list
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 10
                                    
                                    Repeater {
                                        model: currentFact.facts
                                        
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 12
                                            
                                            Text {
                                                text: (index + 1) + "."
                                                color: ThemeManager.accent
                                                font.pixelSize: 13
                                                font.bold: true
                                                Layout.preferredWidth: 24
                                                horizontalAlignment: Text.AlignRight
                                            }
                                            
                                            Text {
                                                text: modelData
                                                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                                font.pixelSize: 13
                                                Layout.fillWidth: true
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }
                                }
                                
                                Item { Layout.fillHeight: true }
                                
                                // Navigation buttons
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12
                                    
                                    Rectangle {
                                        Layout.preferredWidth: 80
                                        Layout.preferredHeight: 36
                                        radius: 8
                                        color: "transparent"
                                        border.color: ThemeManager.accent
                                        border.width: 1
                                        
                                        Text {
                                            anchors.centerIn: parent
                                            text: "Back"
                                            color: ThemeManager.accent
                                            font.pixelSize: 12
                                        }
                                        
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                currentFactIndex = (currentFactIndex - 1 + securityFacts.length) % securityFacts.length
                                            }
                                        }
                                    }
                                    
                                    // Page indicators
                                    Row {
                                        Layout.fillWidth: true
                                        Layout.alignment: Qt.AlignHCenter
                                        spacing: 6
                                        
                                        Repeater {
                                            model: securityFacts.length
                                            
                                            Rectangle {
                                                width: currentFactIndex === index ? 24 : 8
                                                height: 8
                                                radius: 4
                                                color: currentFactIndex === index ? ThemeManager.accent : (ThemeManager.isDark() ? "#374151" : "#D1D5DB")
                                                
                                                Behavior on width { NumberAnimation { duration: 200 } }
                                                Behavior on color { ColorAnimation { duration: 200 } }
                                            }
                                        }
                                    }
                                    
                                    Rectangle {
                                        Layout.preferredWidth: 80
                                        Layout.preferredHeight: 36
                                        radius: 8
                                        color: ThemeManager.accent
                                        
                                        Text {
                                            anchors.centerIn: parent
                                            text: "Next"
                                            color: "#050814"
                                            font.pixelSize: 12
                                            font.bold: true
                                        }
                                        
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                currentFactIndex = (currentFactIndex + 1) % securityFacts.length
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Quick Actions Card
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            radius: 16
                            color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                            border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                            
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 14
                                
                                Text {
                                    text: "Quick Actions"
                                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                    font.pixelSize: 16
                                    font.bold: true
                                }
                                
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    rowSpacing: 10
                                    columnSpacing: 10
                                    
                                    QuickActionButton {
                                        Layout.fillWidth: true
                                        icon: "🔍"
                                        label: "Quick Scan"
                                        onClicked: window.loadRoute("scan-tool")
                                    }
                                    
                                    QuickActionButton {
                                        Layout.fillWidth: true
                                        icon: "📊"
                                        label: "System Status"
                                        onClicked: window.loadRoute("snapshot")
                                    }
                                    
                                    QuickActionButton {
                                        Layout.fillWidth: true
                                        icon: "🌐"
                                        label: "Network Scan"
                                        onClicked: window.loadRoute("net-scan")
                                    }
                                    
                                    QuickActionButton {
                                        Layout.fillWidth: true
                                        icon: "📋"
                                        label: "Event Logs"
                                        onClicked: window.loadRoute("events")
                                    }
                                }
                            }
                        }
                    }
                    
                    // ===== RIGHT COLUMN =====
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: 20
                        
                        // System Health Overview
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 160
                            radius: 16
                            color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                            border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                            
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 14
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    
                                    Text {
                                        text: "System Health"
                                        color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                        font.pixelSize: 16
                                        font.bold: true
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    Rectangle {
                                        width: 80
                                        height: 26
                                        radius: 13
                                        color: ThemeManager.success
                                        opacity: 0.2
                                        
                                        Rectangle {
                                            anchors.fill: parent
                                            radius: 13
                                            color: "transparent"
                                            
                                            Text {
                                                anchors.centerIn: parent
                                                text: "Healthy"
                                                color: ThemeManager.success
                                                font.pixelSize: 11
                                                font.bold: true
                                            }
                                        }
                                    }
                                }
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 16
                                    
                                    StatusMetric {
                                        Layout.fillWidth: true
                                        label: "CPU"
                                        value: SnapshotService ? Math.round(SnapshotService.cpuUsage) + "%" : "N/A"
                                        barValue: SnapshotService ? SnapshotService.cpuUsage / 100 : 0
                                        accentColor: SnapshotService && SnapshotService.cpuUsage > 80 ? ThemeManager.danger :
                                                    SnapshotService && SnapshotService.cpuUsage > 60 ? ThemeManager.warning : ThemeManager.success
                                    }
                                    
                                    StatusMetric {
                                        Layout.fillWidth: true
                                        label: "Memory"
                                        value: SnapshotService ? Math.round(SnapshotService.memoryUsage) + "%" : "N/A"
                                        barValue: SnapshotService ? SnapshotService.memoryUsage / 100 : 0
                                        accentColor: SnapshotService && SnapshotService.memoryUsage > 80 ? ThemeManager.danger :
                                                    SnapshotService && SnapshotService.memoryUsage > 60 ? ThemeManager.warning : ThemeManager.success
                                    }
                                    
                                    StatusMetric {
                                        Layout.fillWidth: true
                                        label: "Disk"
                                        value: SnapshotService && SnapshotService.diskPartitions && SnapshotService.diskPartitions.length > 0 ? 
                                               Math.round(SnapshotService.diskPartitions[0].percent) + "%" : "N/A"
                                        barValue: SnapshotService && SnapshotService.diskPartitions && SnapshotService.diskPartitions.length > 0 ? 
                                                 SnapshotService.diskPartitions[0].percent / 100 : 0
                                        accentColor: SnapshotService && SnapshotService.diskPartitions && SnapshotService.diskPartitions.length > 0 &&
                                                    SnapshotService.diskPartitions[0].percent > 90 ? ThemeManager.danger :
                                                    SnapshotService && SnapshotService.diskPartitions && SnapshotService.diskPartitions.length > 0 &&
                                                    SnapshotService.diskPartitions[0].percent > 75 ? ThemeManager.warning : ThemeManager.success
                                    }
                                }
                            }
                        }
                        
                        // Security Status
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            radius: 16
                            color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                            border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                            
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 14
                                
                                Text {
                                    text: "Security Status"
                                    color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                    font.pixelSize: 16
                                    font.bold: true
                                }
                                
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    rowSpacing: 12
                                    columnSpacing: 20
                                    
                                    SecurityStatusItem {
                                        Layout.fillWidth: true
                                        label: "Firewall"
                                        status: SnapshotService && SnapshotService.securityInfo ? 
                                               SnapshotService.securityInfo.firewallStatus || "Unknown" : "Unknown"
                                        isGood: SnapshotService && SnapshotService.securityInfo && 
                                               SnapshotService.securityInfo.firewallStatus === "Enabled"
                                    }
                                    
                                    SecurityStatusItem {
                                        Layout.fillWidth: true
                                        label: "Antivirus"
                                        status: SnapshotService && SnapshotService.securityInfo ? 
                                               (SnapshotService.securityInfo.antivirus || "Unknown").substring(0, 20) : "Unknown"
                                        isGood: true
                                    }
                                    
                                    SecurityStatusItem {
                                        Layout.fillWidth: true
                                        label: "Secure Boot"
                                        status: SnapshotService && SnapshotService.securityInfo ? 
                                               SnapshotService.securityInfo.secureBoot || "Unknown" : "Unknown"
                                        isGood: SnapshotService && SnapshotService.securityInfo && 
                                               SnapshotService.securityInfo.secureBoot === "Enabled"
                                    }
                                    
                                    SecurityStatusItem {
                                        Layout.fillWidth: true
                                        label: "TPM"
                                        status: SnapshotService && SnapshotService.securityInfo ? 
                                               SnapshotService.securityInfo.tpmPresent || "Unknown" : "Unknown"
                                        isGood: SnapshotService && SnapshotService.securityInfo && 
                                               SnapshotService.securityInfo.tpmPresent === "Present"
                                    }
                                }
                            }
                        }
                        
                        // Network Status
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 130
                            radius: 16
                            color: ThemeManager.isDark() ? ThemeManager.darkPanel : ThemeManager.lightPanel
                            border.color: ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder
                            
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 14
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    
                                    Text {
                                        text: "Network Activity"
                                        color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                                        font.pixelSize: 16
                                        font.bold: true
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                    
                                    Row {
                                        spacing: 6
                                        Rectangle {
                                            width: 8
                                            height: 8
                                            radius: 4
                                            color: ThemeManager.success
                                        }
                                        Text {
                                            text: "Connected"
                                            color: ThemeManager.success
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 40
                                    
                                    Column {
                                        spacing: 4
                                        Text {
                                            text: "↑ Upload"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 11
                                        }
                                        Text {
                                            text: SnapshotService ? formatSpeed(SnapshotService.netUpBps) : "N/A"
                                            color: ThemeManager.success
                                            font.pixelSize: 18
                                            font.bold: true
                                        }
                                    }
                                    
                                    Column {
                                        spacing: 4
                                        Text {
                                            text: "↓ Download"
                                            color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                                            font.pixelSize: 11
                                        }
                                        Text {
                                            text: SnapshotService ? formatSpeed(SnapshotService.netDownBps) : "N/A"
                                            color: ThemeManager.warning
                                            font.pixelSize: 18
                                            font.bold: true
                                        }
                                    }
                                    
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }
                        
                        // Pro Tip Card
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 110
                            radius: 16
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: ThemeManager.accent }
                                GradientStop { position: 1.0; color: Qt.darker(ThemeManager.accent, 1.3) }
                            }
                            
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 16
                                
                                Column {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    
                                    Text {
                                        text: "💡 Pro Tip"
                                        color: "#050814"
                                        font.pixelSize: 14
                                        font.bold: true
                                    }
                                    
                                    Text {
                                        text: "Regular system scans help detect threats early. Schedule automatic scans for comprehensive protection."
                                        color: "#050814"
                                        font.pixelSize: 12
                                        wrapMode: Text.WordWrap
                                        width: parent.width
                                        opacity: 0.9
                                    }
                                }
                                
                                Rectangle {
                                    width: 100
                                    height: 40
                                    radius: 8
                                    color: "#050814"
                                    
                                    Text {
                                        anchors.centerIn: parent
                                        text: "Scan Now"
                                        color: ThemeManager.accent
                                        font.pixelSize: 12
                                        font.bold: true
                                    }
                                    
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: window.loadRoute("scan-tool")
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    // Helper function for network speed formatting
    function formatSpeed(bps) {
        if (!bps || bps === 0) return "0 B/s"
        if (bps >= 1000000000) return (bps / 1000000000).toFixed(1) + " GB/s"
        if (bps >= 1000000) return (bps / 1000000).toFixed(1) + " MB/s"
        if (bps >= 1000) return (bps / 1000).toFixed(1) + " KB/s"
        return bps.toFixed(0) + " B/s"
    }
    
    // ===== INLINE COMPONENTS =====
    
    component QuickActionButton: Rectangle {
        id: actionBtn
        height: 46
        radius: 10
        color: ThemeManager.isDark() ? ThemeManager.darkElevated : ThemeManager.lightElevated
        border.color: mouseArea.containsMouse ? ThemeManager.accent : (ThemeManager.isDark() ? ThemeManager.darkBorder : ThemeManager.lightBorder)
        
        property string icon: ""
        property string label: ""
        signal clicked()
        
        Behavior on border.color { ColorAnimation { duration: 150 } }
        
        scale: mouseArea.pressed ? 0.98 : 1.0
        Behavior on scale { NumberAnimation { duration: 100 } }
        
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            
            Text {
                text: actionBtn.icon
                font.pixelSize: 16
            }
            
            Text {
                text: actionBtn.label
                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                font.pixelSize: 12
                font.weight: Font.Medium
            }
            
            Item { Layout.fillWidth: true }
            
            Text {
                text: "→"
                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                font.pixelSize: 14
            }
        }
        
        MouseArea {
            id: mouseArea
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            hoverEnabled: true
            onClicked: actionBtn.clicked()
        }
    }
    
    component StatusMetric: ColumnLayout {
        property string label: ""
        property string value: ""
        property real barValue: 0
        property color accentColor: ThemeManager.accent
        
        spacing: 8
        
        RowLayout {
            Layout.fillWidth: true
            
            Text {
                text: label
                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                font.pixelSize: 11
            }
            
            Item { Layout.fillWidth: true }
            
            Text {
                text: value
                color: accentColor
                font.pixelSize: 14
                font.bold: true
            }
        }
        
        Rectangle {
            Layout.fillWidth: true
            height: 6
            radius: 3
            color: ThemeManager.isDark() ? "#1F2937" : "#E5E7EB"
            
            Rectangle {
                width: parent.width * Math.min(1, Math.max(0, barValue))
                height: parent.height
                radius: 3
                color: accentColor
                
                Behavior on width { NumberAnimation { duration: 300 } }
            }
        }
    }
    
    component SecurityStatusItem: RowLayout {
        property string label: ""
        property string status: ""
        property bool isGood: false
        
        spacing: 10
        
        Rectangle {
            width: 10
            height: 10
            radius: 5
            color: isGood ? ThemeManager.success : ThemeManager.warning
        }
        
        Column {
            Layout.fillWidth: true
            spacing: 2
            
            Text {
                text: label
                color: ThemeManager.isDark() ? ThemeManager.darkMuted : ThemeManager.lightMuted
                font.pixelSize: 10
            }
            
            Text {
                text: status
                color: ThemeManager.isDark() ? ThemeManager.darkText : ThemeManager.lightText
                font.pixelSize: 12
                font.bold: true
            }
        }
    }
}
