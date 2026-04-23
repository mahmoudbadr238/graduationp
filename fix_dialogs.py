import re
with open('frontend/qml/pages/ScanCenter.qml', 'r', encoding='utf-8') as f:
    text = f.read()

exec_dialog = '''    SentinelDialog {
        id: execConfirmDlg
        
        titleText: "Allow Sample Execution"
        iconText: "⚠"
        iconColor: ThemeManager.warning
        iconBgColor: Qt.rgba(ThemeManager.warning.r, ThemeManager.warning.g, ThemeManager.warning.b, 0.15)
        
        bodyText: "<b>This will run the sample inside an isolated VM.</b><br><br>Only proceed if you trust your sandbox environment and understand that the sample will execute with its normal code path."
        
        primaryButtonText: "Yes"
        secondaryButtonText: "No"
        primaryButtonColor: ThemeManager.warning
        
        onAccepted: {
            root.optExec = true
        }
        onRejected: {
            root.optExec = false
            root.optGuiAuto = false
        }
    }'''

err_dialog = '''    SentinelDialog {
        id: errDlg
        property string msg: ""
        
        titleText: "Scan Failed"
        iconText: "⚠"
        iconColor: ThemeManager.danger
        iconBgColor: Qt.rgba(ThemeManager.danger.r, ThemeManager.danger.g, ThemeManager.danger.b, 0.15)
        
        bodyText: errDlg.msg
        primaryButtonText: "OK"
        showSecondaryButton: false
    }'''

# Replace execConfirmDlg
text = re.sub(r'    Dialog \{\s+id: execConfirmDlg.*?^\s+onRejected: \{.*?^\s+\}\n\s+\}', exec_dialog, text, flags=re.MULTILINE | re.DOTALL)

# Replace errDlg
text = re.sub(r'    Dialog \{\s+id: errDlg.*?^\s+\}', err_dialog, text, flags=re.MULTILINE | re.DOTALL)

with open('frontend/qml/pages/ScanCenter.qml', 'w', encoding='utf-8') as f:
    f.write(text)
