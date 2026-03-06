; Sentinel Sandbox Visible Interaction — AutoHotkey v2
; ─────────────────────────────────────────────────────
; Usage (called by run_sandbox_ui.ps1):
;   AutoHotkey64.exe sandbox_ui.ahk <SamplePath> <JobDir> <MonitorSeconds>
;
; PURPOSE: Perform visible, safe GUI interactions inside the sandbox guest
; to demonstrate that analysis is active.  DEFENSIVE-ONLY — no evasion.
;
; Requires AutoHotkey v2.0+

#Requires AutoHotkey v2.0
SingleInstance Force

; ── Arguments ──────────────────────────────────────────────────────────────
SamplePath    := A_Args.Length >= 1 ? A_Args[1] : ""
JobDir        := A_Args.Length >= 2 ? A_Args[2] : A_Temp
MonitorSecs   := A_Args.Length >= 3 ? Integer(A_Args[3]) : 30
SampleName    := RegExReplace(SamplePath, ".*[\\/]", "")

; ── Helpers ─────────────────────────────────────────────────────────────────
LogFile := JobDir . "\steps.jsonl"

LogStep(status, msg) {
    global LogFile
    ts  := FormatTime(A_Now, "HH:mm:ss")
    ; Escape double-quotes for compact JSON
    safeMsg := StrReplace(msg, '"', "'")
    line := '{"time":"' . ts . '","status":"' . status . '","message":"[AHK] ' . safeMsg . '"}'
    try FileAppend(line . "`n", LogFile)
}

; ── Setup ───────────────────────────────────────────────────────────────────
SendMode "Input"
SetMouseDelay 15
SetWinDelay   100
CoordMode "Mouse", "Screen"

LogStep("Running", "AHK interaction sequence started  sample=" . SampleName)

; ── Get screen dimensions ───────────────────────────────────────────────────
screenW := SysGet(0)   ; SM_CXSCREEN
screenH := SysGet(1)   ; SM_CYSCREEN
cx      := screenW // 2
cy      := screenH // 2

; ── 1) Smooth mouse move to centre ──────────────────────────────────────────
LogStep("Running", "Moving mouse to screen centre")

MouseGetPos &startX, &startY

steps := 25
Loop steps {
    nx := startX + (cx - startX) * A_Index // steps
    ny := startY + (cy - startY) * A_Index // steps
    MouseMove nx, ny, 0
    Sleep 20
}
Sleep 300
LogStep("OK", "Mouse at centre (" . cx . ", " . cy . ")")

; ── 2) Demonstrate mouse sweep ───────────────────────────────────────────────
LogStep("Running", "Performing visible mouse sweep")
points := [[cx - 200, cy - 100], [cx + 200, cy - 100],
           [cx + 200, cy + 100], [cx - 200, cy + 100], [cx, cy]]
for pt in points {
    MouseMove pt[1], pt[2], 25
    Sleep 120
}
LogStep("OK", "Mouse sweep complete")

; ── 3) Open Notepad with analysis banner ────────────────────────────────────
LogStep("Running", "Opening Notepad for visible analysis annotation")
notepadPid := Run("notepad.exe", , "Normal")
Sleep 2000

; Find and activate the Notepad window
if WinWait("ahk_class Notepad", , 8) {
    WinActivate()
    Sleep 500
    LogStep("OK", "Notepad window activated")

    analysisText :=
        "╔══════════════════════════════════════════╗`n"
        . "║      SENTINEL SANDBOX ANALYSIS           ║`n"
        . "╚══════════════════════════════════════════╝`n"
        . "`n"
        . "Job ID  : " . JobDir . "`n"
        . "Sample  : " . SampleName . "`n"
        . "Monitor : " . MonitorSecs . " seconds`n"
        . "Status  : Detonating sample…`n"
        . "`n"
        . "This window confirms the sandbox is running`n"
        . "in the active interactive desktop session.`n"

    SendText analysisText
    Sleep 800
    LogStep("OK", "Analysis annotation typed into Notepad")
} else {
    LogStep("Failed", "Notepad window did not appear within 8s — skipping annotation")
}

; ── 4) Move mouse to task-bar area then back ─────────────────────────────────
LogStep("Running", "Moving mouse towards task-bar")
MouseMove cx, screenH - 15, 30
Sleep 500
MouseMove cx, cy - 50, 25
Sleep 300
LogStep("OK", "Taskbar hover complete")

; ── 5) Close Notepad (Alt+F4, discard) ──────────────────────────────────────
if WinExist("ahk_class Notepad") {
    WinActivate "ahk_class Notepad"
    Sleep 200
    Send "!{F4}"
    Sleep 600
    ; Dismiss "Save?" dialog if it appeared
    if WinExist("Notepad ahk_class #32770") {
        Send "!n"   ; No
        Sleep 300
    }
    LogStep("OK", "Notepad closed")
}

; ── Done ─────────────────────────────────────────────────────────────────────
LogStep("OK", "AHK interaction sequence finished successfully")
ExitApp 0
