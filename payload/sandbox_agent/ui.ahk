#Requires AutoHotkey v2.0
; ============================================================================
; Sentinel Sandbox UI — visible interaction layer
; Called by agent.ps1 with arguments: SamplePath OutDir MonitorSeconds
;
; Performs observable GUI activity so the VM screen shows real interaction:
;   - Smooth mouse sweeps across the desktop
;   - Opens and annotates Notepad
;   - Moves cursor over taskbar / Start button
;   - Logs each action to OutDir\steps.jsonl
; ============================================================================

#SingleInstance Force
SetTitleMatchMode 2
CoordMode "Mouse", "Screen"

; ─── Parse argv ─────────────────────────────────────────────────────────────
SamplePath   := A_Args.Length >= 1 ? A_Args[1] : "unknown.exe"
OutDir        := A_Args.Length >= 2 ? A_Args[2] : "C:\Sandbox\out"
MonitorSecs   := A_Args.Length >= 3 ? Integer(A_Args[3]) : 30
SampleName    := SubStr(SamplePath, InStr(SamplePath, "\",, 0) + 1)
StepsFile     := OutDir . "\steps.jsonl"

; ─── Logging ────────────────────────────────────────────────────────────────
LogStep(status, msg) {
    global StepsFile
    t := FormatTime(, "HH:mm:ss")
    line := '{"time":"' t '","status":"' status '","source":"ahk","message":"' msg '"}'
    try FileAppend line "`n", StepsFile, "UTF-8"
}

; ─── Smooth mouse move ───────────────────────────────────────────────────────
SmoothMove(tx, ty, steps := 20) {
    MouseGetPos &cx, &cy
    Loop steps {
        nx := cx + (tx - cx) * A_Index // steps
        ny := cy + (ty - cy) * A_Index // steps
        MouseMove nx, ny, 0
        Sleep 18
    }
}

; ─── Screenshot via PowerShell (best-effort) ────────────────────────────────
TakeShot(label := "") {
    global OutDir
    t := A_TickCount
    p := OutDir . "\shots\ahk_" . (label != "" ? label . "_" : "") . t . ".png"
    cmd := 'powershell.exe -NoP -NonI -Command "'
         . 'Add-Type -An System.Windows.Forms,System.Drawing;'
         . '$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;'
         . '$img=[System.Drawing.Bitmap]::new($b.W,$b.H);'
         . '$g=[System.Drawing.Graphics]::FromImage($img);'
         . '$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);'
         . '$img.Save(''' . p . ''',[System.Drawing.Imaging.ImageFormat]::Png)"'
    try RunWait cmd,, "Hide"
}

; ────────────────────────────────────────────────────────────────────────────
; MAIN SEQUENCE
; ────────────────────────────────────────────────────────────────────────────

LogStep "Running", "AHK interaction started | sample=" . SampleName

W := A_ScreenWidth
H := A_ScreenHeight
cx := W // 2
cy := H // 2

; ── Phase 1: Desktop orientation sweep ───────────────────────────────────────
LogStep "Running", "Phase 1: desktop sweep"
SmoothMove cx, cy, 28
Sleep 250
SmoothMove W * 0.15, H * 0.15, 24
Sleep 180
SmoothMove W * 0.85, H * 0.15, 24
Sleep 180
SmoothMove W * 0.85, H * 0.85, 24
Sleep 180
SmoothMove W * 0.15, H * 0.85, 24
Sleep 180
SmoothMove cx, cy, 24
LogStep "OK", "Phase 1 complete"
TakeShot "sweep"

; ── Phase 2: Taskbar hover (Start button + notification area) ─────────────────
LogStep "Running", "Phase 2: taskbar interaction"
SmoothMove W // 2, H - 20, 20     ; center taskbar
Sleep 400
SmoothMove 20, H - 20, 16         ; Start button approximation
Sleep 600
SmoothMove W - 80, H - 20, 16     ; clock / notification area
Sleep 400
SmoothMove cx, cy, 20             ; return to center
LogStep "OK", "Phase 2 complete"
TakeShot "taskbar"

; ── Phase 3: Notepad annotation ──────────────────────────────────────────────
LogStep "Running", "Phase 3: Notepad annotation"
Run "notepad.exe",, "Normal", &npPID
if WinWait("Untitled - Notepad",, 8) {
    WinActivate "Untitled - Notepad"
    Sleep 800
    ; Move cursor to Notepad window center
    WinGetPos &wx, &wy, &ww, &wh, "Untitled - Notepad"
    SmoothMove wx + ww // 2, wy + wh // 2, 18
    Sleep 200
    Click wx + ww // 2, wy + wh // 2

    ts := FormatTime(, "yyyy-MM-dd HH:mm:ss")
    SendText "=== Sentinel Sandbox Analysis ===`r`n"
    SendText "Timestamp : " . ts . "`r`n"
    SendText "Sample    : " . SampleName . "`r`n"
    SendText "Monitor   : " . MonitorSecs . "s`r`n"
    SendText "Status    : Detonation in progress`r`n"
    SendText "Note      : THIS IS AN ISOLATED ANALYSIS VM`r`n"
    SendText "=================================`r`n"

    TakeShot "notepad"
    LogStep "OK", "Notepad annotated"

    Sleep 1500
    ; Close without saving
    WinClose "Untitled - Notepad"
    Sleep 500
    if WinExist("Notepad") {
        Send "!{F4}"
        Sleep 300
    }
    ; Dismiss "Save?" dialog if it appeared
    if WinExist("Notepad") {
        Send "n"
    }
    LogStep "OK", "Notepad closed"
} else {
    LogStep "Failed", "Notepad did not open — timeout"
}

; ── Phase 4: Final center + screenshot ───────────────────────────────────────
SmoothMove cx, cy, 20
Sleep 300
TakeShot "final"
LogStep "OK", "AHK interaction complete"

ExitApp 0
