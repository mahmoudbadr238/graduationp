#Requires AutoHotkey v2.0
; ============================================================================
; Sentinel Sandbox — AHK Detonation Helper
; Companion to run.ps1: handles visible sample launch, UAC acceptance,
; installer/dialog button clicking, and human-like mouse simulation.
;
; Usage (called by sandbox_controller.py or run.ps1):
;   AutoHotkey64.exe detonate.ahk <SamplePath> <OutDir> <MonitorSeconds>
;
; Phases:
;   1  Desktop sweep           — smooth mouse arcs to defeat sandbox detection
;   2  Launch sample            — via ShellRun with visible window
;   3  UAC auto-accept          — watches for consent.exe / UAC dialogs
;   4  Dialog/installer clicker — finds and clicks common buttons every 2 s
;   5  Periodic mouse jitter    — random micro-movements during monitoring
;   6  Final screenshot + exit
;
; All actions logged to <OutDir>\ahk_steps.jsonl
; ============================================================================

#SingleInstance Force
SetTitleMatchMode 2
CoordMode "Mouse", "Screen"
SendMode "Event"

; ─── Arguments ───────────────────────────────────────────────────────────────
SamplePath     := A_Args.Length >= 1 ? A_Args[1] : ""
OutDir         := A_Args.Length >= 2 ? A_Args[2] : "C:\Sandbox\out"
MonitorSeconds := A_Args.Length >= 3 ? Integer(A_Args[3]) : 60
SampleName     := SubStr(SamplePath, InStr(SamplePath, "\",, 0) + 1)
StepsFile      := OutDir . "\ahk_steps.jsonl"
ShotsDir       := OutDir . "\shots"

; Ensure output directories exist
try DirCreate ShotsDir

; ─── Helpers ─────────────────────────────────────────────────────────────────

LogStep(status, msg) {
    global StepsFile
    t    := FormatTime(, "yyyy-MM-dd HH:mm:ss")
    line := '{"time":"' . t . '","status":"' . status . '","source":"ahk_detonate","message":"' . StrReplace(msg, '"', "'") . '"}'
    try FileAppend line "`n", StepsFile, "UTF-8"
}

; Smooth cursor movement — Bézier-like interpolation between current pos and target
SmoothMove(tx, ty, steps := 20) {
    MouseGetPos &cx, &cy
    Loop steps {
        frac := A_Index / steps
        ; Ease-in-out cubic for more human-like motion
        frac := frac < 0.5 ? 4 * frac ** 3 : 1 - (-2 * frac + 2) ** 3 / 2
        MouseMove Round(cx + (tx - cx) * frac), Round(cy + (ty - cy) * frac), 0
        Sleep 14
    }
}

; Random mouse jitter — small offset from current position
JitterMouse(maxDx := 35, maxDy := 25) {
    MouseGetPos &cx, &cy
    W := A_ScreenWidth
    H := A_ScreenHeight
    dx := Random(-maxDx, maxDx)
    dy := Random(-maxDy, maxDy)
    nx := Max(10, Min(W - 10, cx + dx))
    ny := Max(10, Min(H - 10, cy + dy))
    SmoothMove nx, ny, 8
}

; Take a screenshot via .NET (same approach as run_ui.ahk)
TakeShot(label := "") {
    global ShotsDir
    p := ShotsDir . "\det_" . (label != "" ? label . "_" : "") . A_TickCount . ".png"
    cmd := 'powershell.exe -NoP -NonI -Command "'
         . 'Add-Type -An System.Windows.Forms,System.Drawing;'
         . '$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;'
         . '$i=[System.Drawing.Bitmap]::new($b.W,$b.H);'
         . '$g=[System.Drawing.Graphics]::FromImage($i);'
         . '$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);'
         . '$i.Save(''' . p . ''',[System.Drawing.Imaging.ImageFormat]::Png)"'
    try RunWait cmd,, "Hide"
}

; ─── Phase 1: Desktop Sweep ─────────────────────────────────────────────────
LogStep "Running", "Phase 1: Desktop sweep (anti-sandbox evasion)"

W := A_ScreenWidth
H := A_ScreenHeight
cx := Round(W / 2)
cy := Round(H / 2)

; Move cursor through a natural-looking pattern
SmoothMove cx, cy, 28
Sleep 200
SmoothMove Round(W * 0.12), Round(H * 0.12), 22
Sleep 150
SmoothMove Round(W * 0.88), Round(H * 0.12), 22
Sleep 150
SmoothMove Round(W * 0.88), Round(H * 0.85), 22
Sleep 150
SmoothMove Round(W * 0.12), Round(H * 0.85), 22
Sleep 150
SmoothMove cx, cy, 22

; Quick taskbar hover
SmoothMove 24, H - 16, 16
Sleep 400
SmoothMove W - 90, H - 16, 18
Sleep 300
SmoothMove cx, cy, 18

LogStep "OK", "Phase 1 complete — desktop sweep done"
TakeShot "sweep"

; ─── Phase 2: Launch Sample ──────────────────────────────────────────────────
launched := false

if (SamplePath != "") {
    LogStep "Running", "Phase 2: Launching sample — " . SampleName

    ; Method A: Direct ShellRun (most reliable for Session 1 visibility)
    try {
        Run SamplePath,, "Normal", &samplePID
        Sleep 1500
        launched := true
        LogStep "OK", "Sample launched via Run, PID=" . samplePID
        TakeShot "launched"
    } catch as e1 {
        LogStep "Failed", "Direct Run failed: " . e1.Message . " — trying Win+R fallback"

        ; Method B: Win+R dialog
        Send "#r"
        if WinWait("Run",, 5) {
            WinActivate "Run"
            Sleep 500
            Send "^a"
            Sleep 80
            Send "{Delete}"
            Sleep 80
            SendText SamplePath
            Sleep 600
            TakeShot "run-dialog"
            Send "{Enter}"
            Sleep 1500
            launched := true
            LogStep "OK", "Sample launched via Win+R"
            TakeShot "launched-winr"
        } else {
            LogStep "Failed", "Win+R dialog did not appear"
        }
    }
} else {
    LogStep "Running", "Phase 2: No sample path — monitoring only"
}

; ─── Phase 3 + 4 + 5: UAC Accept + Dialog Clicker + Mouse Jitter ────────────
; All three run in the monitoring loop for the configured duration.
; AHK handles window matching natively, which is faster and more reliable
; than .NET UIAutomation for button clicking.

; Button text patterns we will accept/click (case-insensitive)
acceptBtns := [
    "Yes", "&Yes", "OK", "Next", "I Agree", "Accept", "Install",
    "Continue", "Allow", "Agree", "Run", "Apply", "Proceed",
    "Confirm", "Finish", "Open", "Extract", "Setup", "Start",
    "Got it", "Skip", "Execute", "Launch", "Unzip"
]

; UAC-specific window titles/classes to handle
uacTitles := ["User Account Control", "Windows Security"]

LogStep "Running", "Phase 3-5: Monitoring loop (" . MonitorSeconds . "s) — UAC + dialogs + jitter"

deadline := A_TickCount + MonitorSeconds * 1000
loopIdx  := 0

while (A_TickCount < deadline) {

    loopIdx++

    ; ── UAC prompt handling ───────────────────────────────────────────────
    ; consent.exe runs the UAC dialog on the secure desktop. If
    ; PromptOnSecureDesktop=0 (required for automation), the dialog appears
    ; on the normal desktop and we can interact with it.
    for _, uacTitle in uacTitles {
        if WinExist(uacTitle) {
            try {
                WinActivate uacTitle
                Sleep 400
                ; Try clicking "Yes" button (standard UAC elevation prompt)
                try ControlClick "Button1", uacTitle  ; "Yes" is typically Button1
                catch {
                    ; Fallback: send Alt+Y (Yes accelerator)
                    Send "!y"
                }
                Sleep 800
                LogStep "OK", "UAC prompt accepted: " . uacTitle
                TakeShot "uac-accepted"
            }
        }
    }

    ; ── Generic dialog/installer button clicker ──────────────────────────
    ; Every 2 seconds, scan all visible windows for matching button text
    if (Mod(loopIdx, 1) == 0) {
        for _, btnText in acceptBtns {
            ; Use ControlGet to find buttons across all windows
            ; Focus on windows that are NOT the desktop or explorer
            try {
                ; Find any window containing this button text
                for hwnd in WinGetList() {
                    try {
                        wTitle := WinGetTitle(hwnd)
                        ; Skip desktop, taskbar, and Sentinel's own windows
                        if (wTitle == "" || wTitle == "Program Manager" || InStr(wTitle, "Sentinel"))
                            continue

                        ; Look for button controls matching our accept list
                        try {
                            ctrls := WinGetControls(hwnd)
                            if (!IsObject(ctrls))
                                continue
                            for _, ctrl in ctrls {
                                if (InStr(ctrl, "Button")) {
                                    try {
                                        ctrlText := ControlGetText(ctrl, hwnd)
                                        if (ctrlText != "" && InStr(ctrlText, btnText)) {
                                            ControlClick ctrl, hwnd
                                            Sleep 500
                                            LogStep "OK", "Clicked button '" . ctrlText . "' in '" . wTitle . "'"
                                            TakeShot "click-" . A_Index
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    ; ── Periodic mouse jitter (every ~4 seconds) ────────────────────────
    if (Mod(loopIdx, 2) == 0) {
        JitterMouse 30, 20
    }

    Sleep 2000
}

LogStep "OK", "Monitoring loop complete"

; ─── Phase 6: Final Screenshot + Exit ────────────────────────────────────────
SmoothMove cx, cy, 16
Sleep 300
TakeShot "final"
LogStep "OK", "AHK detonation helper finished"

ExitApp 0
