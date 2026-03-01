# VMware Sandbox Lab Setup

This document covers the VMware Workstation integration used by Sentinel's `Sandbox Lab` page.

## Host Requirements

1. Install VMware Workstation on the Windows host.
2. Confirm `vmrun.exe` exists at:
   - `C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe`
3. Create or choose a Windows 10 guest VM.
4. Install VMware Tools inside the guest.
5. Create a clean snapshot named `Clean Base`.

## Guest Requirements

Inside the guest VM:

1. Create `C:\Sandbox\in`
2. Create `C:\Sandbox\out`
3. Place the detonation runner at `C:\Sandbox\run.ps1`
4. Place the URL opener at `C:\Sandbox\open_url.ps1`
5. Create a guest user account that VMware `vmrun` can authenticate with

Sentinel expects the guest runner to write the final detonation report to:

- `C:\Sandbox\out\report.json`

## .env Configuration

Copy `.env.example` to `.env` and configure these values:

```env
SANDBOX_VMRUN=C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe
SANDBOX_VMX=D:\vm\windows10\Windows 10 x64.vmx
SANDBOX_SNAPSHOT=Clean Base
SANDBOX_GUEST_USER=guestuser
SANDBOX_GUEST_PASS=guestpassword
SANDBOX_HOST_RESULTS_DIR=C:\SentinelSandbox\results
SANDBOX_HOST_FRAMES_DIR=C:\SentinelSandbox\frames
```

Do not commit `.env`.

## How Sentinel Uses VMware

For each detonation run, Sentinel:

1. Reverts the VM to `Clean Base`
2. Starts the VM with `vmrun start ... nogui`
3. Copies the host sample into `C:\Sandbox\in` (file mode only)
4. Executes `powershell.exe -ExecutionPolicy Bypass -File C:\Sandbox\run.ps1 ...`
5. Polls for `C:\Sandbox\out\report.json`
6. Copies the report back to the host and parses it
7. Saves `report.json`, `meta.json`, and all captured frames in `run_<timestamp>`
8. Exports `proof.gif`
9. Exports `proof.mp4` when `ffmpeg` is installed
10. Reverts the VM again for cleanup

Live view uses `vmrun captureScreen` on a 400-700ms timer and stores proof frames in each run folder so the user can replay the session after the VM is reset.

## Using Sandbox Lab From The UI

1. Launch Sentinel.
2. Open `Sandbox Lab` from the sidebar.
3. Verify the page reports host integration as configured.
4. Choose a file (or switch to URL mode and enter a URL).
5. Adjust monitor seconds / network / kill options.
6. Click `Run`.
7. Watch the live view and real-time proof timeline.
8. After completion, use:
   - `Open Run Folder`
   - `Open Proof Media`
   - `Copy AI Prompt`
9. Toggle `Replay` and scrub through saved frames with the slider.

## Media Export Notes

- GIF export uses `imageio` and is included in Sentinel's Python dependencies.
- MP4 export requires `ffmpeg` in `PATH`.
- If `ffmpeg` is missing, Sentinel still exports `proof.gif` and records a clear UI message.

## Failure Modes

- If `vmrun.exe` is missing, the feature stays disabled and shows a clear message.
- If the VMX path is wrong, the page stays disabled until corrected.
- If guest credentials are missing, VM power controls still work, but file/URL detonation is blocked.
- If the snapshot name is wrong, `Reset Snapshot` shows the available snapshots in the error message when VMware returns them.
- If `report.json` is never created, Sentinel still preserves the timeline and captured frames, then resets the VM.
- If `captureScreen` fails intermittently, Sentinel logs a non-fatal timeline step and continues the run.
