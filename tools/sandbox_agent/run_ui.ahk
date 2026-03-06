#Requires AutoHotkey v2.0
; ============================================================================
; Sentinel Sandbox — visible AHK interaction layer
; Called by run_ui_wrapper.ps1:
;   AutoHotkey64.exe run_ui.ahk <SamplePath> <OutDir> <JobId>
;
; What this does (all visually obvious on the VM monitor):
;   Phase 1 — Desktop sweep (mouse arcs across the desktop)
;   Phase 2 — Taskbar hover (Start, clock, notification area)
;   Phase 3 — Open sample via Win+R dialog (types full path, hits Enter)
;   Phase 4 — Notepad annotation (job details)
;   Phase 5 — Final screenshot + exit
;
; Logs every action to <OutDir>\steps.jsonl
; ============================================================================

#SingleInstance Force
SetTitleMatchMode 2
CoordMode "Mouse", "Screen"

; ─── Args ────────────────────────────────────────────────────────────────────
SamplePath := A_Args.Length >= 1 ? A_Args[1] : ""
OutDir     := A_Args.Length >= 2 ? A_Args[2] : "C:\Sandbox\out"
JobId      := A_Args.Length >= 3 ? A_Args[3] : "unknown"
SampleName := SubStr(SamplePath, InStr(SamplePath, "\",, 0) + 1)
StepsFile  := OutDir . "\steps.jsonl"

; ─── Helpers ─────────────────────────────────────────────────────────────────
LogStep(status, msg) {
    global StepsFile
    t    := FormatTime(, "HH:mm:ss")
    line := '{"time":"' . t . '","status":"' . status . '","source":"ahk","message":"' . msg . '"}'
    try FileAppend line "`n", StepsFile, "UTF-8"
}

SmoothMove(tx, ty, steps := 22) {
    MouseGetPos &cx, &cy
    Loop steps {
        frac := A_Index / steps
        MouseMove Round(cx + (tx - cx) * frac), Round(cy + (ty - cy) * frac), 0
        Sleep 16
    }
}

TakeShot(label := "") {
    global OutDir
    p := OutDir . "\shots\ahk_" . (label != "" ? label . "_" : "") . A_TickCount . ".png"
    cmd := 'powershell.exe -NoP -NonI -Command "'
         . 'Add-Type -An System.Windows.Forms,System.Drawing;'
         . '$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;'
         . '$img=[System.Drawing.Bitmap]::new($b.W,$b.H);'
         . '$g=[System.Drawing.Graphics]::FromImage($img);'
         . '$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);'
         . '$img.Save(''' . p . ''',[System.Drawing.Imaging.ImageFormat]::Png)"'
    try RunWait cmd,, "Hide"
}

; ── Main ─────────────────────────────────────────────────────────────────────
LogStep "Running", "AHK started | sample=" . SampleName

W := A_ScreenWidth
H := A_ScreenHeight
cx := Round(W / 2)
cy := Round(H / 2)

; ══ Phase 1: Desktop sweep ════════════════════════════════════════════════════
LogStep "Running", "Phase 1: Desktop sweep"
SmoothMove cx, cy, 30
Sleep 250
SmoothMove Round(W * 0.15), Round(H * 0.15), 24
Sleep 180
SmoothMove Round(W * 0.85), Round(H * 0.15), 24
Sleep 180
SmoothMove Round(W * 0.85), Round(H * 0.80), 24
Sleep 180
SmoothMove Round(W * 0.15), Round(H * 0.80), 24
Sleep 180
SmoothMove cx, cy, 24
LogStep "OK", "Phase 1 complete"
TakeShot "sweep"

; ══ Phase 2: Taskbar interaction ══════════════════════════════════════════════
LogStep "Running", "Phase 2: Taskbar interaction"
SmoothMove Round(W / 2), H - 18, 20
Sleep 400
SmoothMove 20, H - 18, 16          ; Start button area
Sleep 600
SmoothMove W - 80, H - 18, 16      ; Clock/notification area
Sleep 400
SmoothMove cx, cy, 20
LogStep "OK", "Phase 2 complete"
TakeShot "taskbar"

; ══ Phase 3: Open sample via Win+R ════════════════════════════════════════════
if (SamplePath != "") {
    LogStep "Running", "Phase 3: Opening sample via Win+R: " . SampleName

    ; Move cursor to center before opening dialog
    SmoothMove cx, Round(cy * 0.8), 18
    Sleep 300

    ; Open Run dialog
    Send "#r"
    if WinWait("Run",, 6) {
        WinActivate "Run"
        Sleep 600
        ; Clear any existing text
        Send "^a"
        Sleep 100
        Send "{Delete}"
        Sleep 100
        ; Type the full sample path (visible, one char at a time)
        SendText SamplePath
        Sleep 800
        TakeShot "run-dialog"
        LogStep "OK", "Run dialog filled: " . SamplePath
        ; Hit Enter to launch
        Send "{Enter}"
        Sleep 1500
        LogStep "OK", "Sample launched via Win+R"
        TakeShot "launched"
    } else {
        LogStep "Failed", "Win+R dialog did not open — timeout"
        ; Fallback: try ShellRun
        try {
            Run SamplePath,, "Normal"
            Sleep 1500
            LogStep "OK", "Sample opened via AHK Run"
            TakeShot "launched-fallback"
        } catch as e {
            LogStep "Failed", "Could not open sample: " . e.Message
        }
    }
} else {
    LogStep "Running", "Phase 3: No sample path provided — skipping open"
}

; ══ Phase 4: Notepad annotation ═══════════════════════════════════════════════
LogStep "Running", "Phase 4: Notepad annotation"
Run "notepad.exe",, "Normal", &npPID
if WinWait("Untitled - Notepad",, 8) {
    WinActivate "Untitled - Notepad"
    Sleep 700
    WinGetPos &wx, &wy, &ww, &wh, "Untitled - Notepad"
    SmoothMove Round(wx + ww / 2), Round(wy + wh / 2), 16
    Sleep 200
    Click Round(wx + ww / 2), Round(wy + wh / 2)
    Sleep 200
    ts := FormatTime(, "yyyy-MM-dd HH:mm:ss")
    SendText "=== Sentinel Sandbox Analysis ===`r`n"
    SendText "Time   : " . ts . "`r`n"
    SendText "Job    : " . JobId . "`r`n"
    SendText "Sample : " . SampleName . "`r`n"
    SendText "Status : Detonation in progress`r`n"
    SendText "Note   : ISOLATED ANALYSIS VM — FOR DEFENSIVE USE ONLY`r`n"
    SendText "================================`r`n"
    TakeShot "notepad"
    LogStep "OK", "Notepad annotated"
    Sleep 1500
    ; Close without saving
    WinClose "Untitled - Notepad"
    Sleep 500
    if WinExist("Notepad") {
        Send "!{F4}"
        Sleep 300
        if WinExist("Notepad") { Send "n" }
    }
    LogStep "OK", "Notepad closed"
} else {
    LogStep "Failed", "Notepad did not open"
}

; ══ Phase 5: Final visual ═════════════════════════════════════════════════════
SmoothMove cx, cy, 20
Sleep 300
TakeShot "final"
LogStep "OK", "AHK interaction complete"

ExitApp 0
