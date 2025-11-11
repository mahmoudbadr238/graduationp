import QtQuick 2.15
import "../theme"

Item {
    id: toastManager
    
    property var activeToasts: []
    property int maxToasts: 3
    property int toastSpacing: 12
    
    function show(message, duration = 3000, type = "info") {
        var component = Qt.createComponent("ToastNotification.qml")
        if (component.status === Component.Ready) {
            var toast = component.createObject(toastManager, {
                message: message,
                toastType: type,
                duration: duration
            })
            
            // Position toast
            toast.anchors.horizontalCenter = toastManager.horizontalCenter
            toast.y = toastManager.height - 80 - (activeToasts.length * (60 + toastSpacing))
            
            activeToasts.push(toast)
            
            // Auto-remove after duration
            toast.closing.connect(function() {
                var index = activeToasts.indexOf(toast)
                if (index > -1) {
                    activeToasts.splice(index, 1)
                    toast.destroy(300)
                    repositionToasts()
                }
            })
            
            // Limit max toasts
            if (activeToasts.length > maxToasts) {
                activeToasts[0].close()
            }
        }
    }
    
    function repositionToasts() {
        for (var i = 0; i < activeToasts.length; i++) {
            activeToasts[i].targetY = toastManager.height - 80 - (i * (60 + toastSpacing))
        }
    }
}
