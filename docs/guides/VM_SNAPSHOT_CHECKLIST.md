# VMware Guest Snapshot Configuration Checklist

> **Purpose**: Ensure the VMware guest VM is properly configured before taking
> the "Clean Base" snapshot used by Sentinel's sandbox detonation pipeline.
> All items below must be verified — missing any one can cause Session 0
> isolation (invisible execution) or failed UI automation.

---

## 1. User Session & Auto-Login

| Setting | How to configure | Why |
|---------|-----------------|-----|
| **Auto-login enabled** | `netplwiz` → uncheck *"Users must enter a username and password to use this computer"* → set user & password | vmrun cannot type at a lock screen; the desktop must be active at boot |
| **No screen lock / screensaver** | Settings → Personalization → Lock screen → Screen timeout = **Never**; Screen saver = **None** | Prevents the desktop from locking during long analysis runs |
| **Password never expires** | `net accounts /maxpwage:unlimited` (or Local Security Policy) | Avoids expiration breaking auto-login |

## 2. UAC (User Account Control)

| Setting | Registry path | Value | Why |
|---------|--------------|-------|-----|
| **PromptOnSecureDesktop = 0** | `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System` → `PromptOnSecureDesktop` | `0` (DWORD) | When set to 1, UAC runs on a separate secure desktop that automation cannot reach |
| **ConsentPromptBehaviorAdmin** | Same key → `ConsentPromptBehaviorAdmin` | `0` = no prompt (recommended) or `5` = standard prompt | `0` completely silences UAC; `5` shows the prompt but our AHK/UIA clicker can handle it |
| **EnableLUA** | Same key → `EnableLUA` | `1` (keep enabled) | Disabling UAC entirely (`0`) hides elevation behavior malware may rely on |

**Quick command (run as admin in guest):**
```powershell
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v PromptOnSecureDesktop /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f
```

## 3. VMware Tools

| Item | Check |
|------|-------|
| **VMware Tools installed** | `vmtoolsd.exe` is running (`Get-Process vmtoolsd`) |
| **VMware Tools version** | Should be current; update via VM → Install VMware Tools |
| **Shared folders** | Not required — Sentinel uses `vmrun copyFileFromHostToGuest` |

## 4. PowerShell Execution Policy

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope LocalMachine -Force
```

This is **required** — `run.ps1` and all guest scripts need unrestricted execution.

## 5. Windows Defender / Antivirus

| Setting | How |
|---------|-----|
| **Real-time protection OFF** | Settings → Windows Security → Virus & threat → Real-time protection → **Off** |
| **Tamper protection OFF** | Same page → Tamper protection → **Off** (must be done first) |
| **Exclusion (alternative)** | Add `C:\Sandbox\` to exclusions if you prefer to keep Defender on |
| **Cloud-delivered protection OFF** | Prevents samples from being uploaded to Microsoft |

**Quick command:**
```powershell
Set-MpPreference -DisableRealtimeMonitoring $true
Set-MpPreference -DisableBehaviorMonitoring $true
Set-MpPreference -DisableIOAVProtection $true
Add-MpPreference -ExclusionPath "C:\Sandbox"
```

> **Note**: On Windows 10 2004+, Tamper Protection may re-enable Defender.
> Disable it via the GUI first, then run the commands.

## 6. Directory Structure

Create the standard Sentinel sandbox directories:

```powershell
New-Item -ItemType Directory -Force -Path "C:\Sandbox\in"
New-Item -ItemType Directory -Force -Path "C:\Sandbox\out"
New-Item -ItemType Directory -Force -Path "C:\Sandbox\out\shots"
New-Item -ItemType Directory -Force -Path "C:\Sandbox\tools"
```

## 7. Display & Resolution

| Setting | Value | Why |
|---------|-------|-----|
| **Screen resolution** | ≥ 1024×768 (1280×720 recommended) | Screenshots need reasonable resolution; some malware checks resolution |
| **Color depth** | 32-bit | Standard for screenshot capture |
| **DPI scaling** | 100% | Avoids coordinate offset issues in UI automation |

## 8. Optional: AutoHotkey v2

If using the AHK detonation helper (`detonate.ahk`) for smoother UI interaction:

1. Download AutoHotkey v2 from https://www.autohotkey.com/
2. Install to default path: `C:\Program Files\AutoHotkey\v2\`
3. Verify: `"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" --help`

> AHK is **optional** — the PowerShell UIA button-clicker in `run.ps1` works
> without it. AHK provides more human-like mouse movement and faster dialog
> interaction.

## 9. Network

| Setting | Value | Why |
|---------|-------|-----|
| **Network adapter** | NAT or Host-only | NAT allows C2 callbacks for analysis; Host-only is safer |
| **DNS resolution** | Must work initially | `run.ps1` captures DNS queries then optionally disables the adapter |

## 10. Miscellaneous

| Setting | How | Why |
|---------|-----|-----|
| **Windows Update OFF** | Settings → Update → Pause updates | Prevents restarts and background CPU usage during analysis |
| **Notifications OFF** | Settings → System → Notifications → **Off** | Notification popups can interfere with UI automation |
| **Firewall** | Keep ON (default) | `run.ps1` monitors network connections; firewall doesn't block outbound by default |
| **Time zone** | Set to match expected malware target | Some malware checks timezone for geo-targeting |

---

## Taking the Snapshot

After configuring all of the above:

1. **Boot the VM** and verify auto-login works (desktop appears without interaction)
2. **Open Task Manager** → verify `vmtoolsd.exe` and `explorer.exe` are running
3. Run the verification script:
   ```powershell
   # Quick check from inside the guest
   query user                                          # Should show "Active" session
   Get-Process explorer, vmtoolsd -ErrorAction Stop    # Both must be running
   (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System").PromptOnSecureDesktop  # Should be 0
   Get-ExecutionPolicy -Scope LocalMachine             # Should be Bypass
   Test-Path "C:\Sandbox\in","C:\Sandbox\out"          # Both True
   ```
4. **Shut down the VM cleanly** (Start → Shut down)
5. In VMware Workstation: **VM → Snapshot → Take Snapshot**
   - Name: `Clean Base`
   - Description: `Sentinel sandbox base — auto-login, UAC dimmed, Defender off, PS Bypass, AHK v2`

> **Important**: Sentinel's pipeline reverts to this snapshot before every analysis
> run. Any configuration change requires taking a new snapshot.
