# Sentinel Desktop Security Suite — User Manual

**Version:** 1.0.0  
**Release Date:** October 18, 2025  
**Status:** Production Release

---

## Welcome to Sentinel! 👋

Sentinel is your personal security assistant for Windows. Think of it as a guard dog for your computer—always watching, always protecting, and never sleeping. This manual will guide you through using Sentinel, whether you're a tech wizard or just getting started with computer security.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Understanding the Dashboard](#understanding-the-dashboard)
3. [Page-by-Page Guide](#page-by-page-guide)
4. [Common Tasks](#common-tasks)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)
7. [Getting Help](#getting-help)

---

## Getting Started

### What You'll Need

- **Computer:** Windows 10 or Windows 11
- **Python:** Version 3.10 or newer ([Download Python](https://www.python.org/downloads/))
- **Space:** About 200 MB of free disk space
- **Internet:** Optional (for VirusTotal checks)

### First-Time Setup (5 Minutes)

1. **Download Sentinel:**
   - Get the latest version from [GitHub Releases](https://github.com/mahmoudbadr238/graduationp/releases)
   - Unzip to `C:\Sentinel` (or any folder you prefer)

2. **Install Python Packages:**
   - Open PowerShell (right-click Start menu → Windows PowerShell)
   - Navigate to Sentinel folder: `cd C:\Sentinel`
   - Install dependencies: `pip install -r requirements.txt`

3. **Launch Sentinel:**
   - Double-click `run_as_admin.bat` (for full features)
   - **OR** run `python main.py` (for basic features)

4. **First Launch:**
   - Wait 3-5 seconds for Sentinel to load
   - You'll see the Dashboard with live system stats
   - That's it—you're protected! 🎉

### Optional Upgrades

**Want More Protection?** Enable these optional features:

**VirusTotal Integration** (Free, requires signup)
1. Go to [VirusTotal](https://www.virustotal.com/gui/join-us)
2. Sign up for a free account (takes 2 minutes)
3. Copy your API key from the profile page
4. Create a file named `.env` in Sentinel folder
5. Add this line: `VT_API_KEY=your_key_here`
6. Restart Sentinel → You'll see a green checkmark ✅ on the Dashboard

**Nmap Network Scanner** (Free)
1. Download Nmap from [nmap.org](https://nmap.org/download.html)
2. Install with default settings (takes 5 minutes)
3. Restart Sentinel → Network Scan feature is now active!

---

## Understanding the Dashboard

When you open Sentinel, you land on the **Dashboard** (Home screen). Here's what you see:

### Live Monitoring Panels

#### 🖥️ CPU Usage
Shows how hard your computer's brain (processor) is working right now.
- **Green (0-50%)**: All good, relaxing
- **Yellow (50-80%)**: Working hard
- **Red (80-100%)**: Overloaded, consider closing programs

#### 💾 Memory Usage
Shows how much RAM your computer is using.
- **Green (0-70%)**: Plenty of space
- **Yellow (70-85%)**: Getting full
- **Red (85-100%)**: Almost full, close unused apps

#### 🎮 GPU Usage
Shows if your graphics card is working (important for games/videos).
- Usually low (0-20%) when just browsing
- Spikes when playing games or editing videos

#### 🌐 Network I/O
Shows internet upload/download speed in KB/s.
- Green bars = downloading (incoming)
- Blue bars = uploading (outgoing)

### Status Chips (Top Right)

These colored badges show the status of features:

- 🟢 **Green:** Feature is active and working
- 🟠 **Orange:** Feature is disabled (not installed or not configured)
- 🔴 **Red:** Feature has an error

**Admin Status:**
- 🟢 "Running as Administrator" → Full features available
- 🟠 "Not Administrator" → Some features limited (Security event logs)

**VirusTotal:**
- 🟢 "VT Connected" → File scanning with cloud database
- 🟠 "VT API Key Missing" → Only local scanning

**Nmap:**
- 🟢 "Nmap Installed" → Network scanning available
- 🟠 "Nmap Not Installed" → Network scanning disabled

### Quick Actions

**🔍 Quick Scan** (30 seconds)
- Fast check of common threat locations
- Downloads folder, Temp files, Startup programs
- **When to use:** Daily, before opening suspicious files

**🌐 Network Scan**
- Check your home network for devices
- See what's connected to your WiFi
- **When to use:** New device appears, WiFi acting weird

---

## Page-by-Page Guide

### 1. Home (Dashboard)

**What it does:** Real-time overview of your computer's health.

**How to use:**
- Just watch! The charts update every second automatically.
- Click the status chips (Admin, VT, Nmap) to see more details.
- Use Quick Actions for fast security checks.

**Pro tip:** Leave Sentinel running in the background—it uses less than 2% CPU and 100 MB RAM.

---

### 2. Event Viewer 📋

**What it does:** Shows important events from Windows (errors, warnings, system changes).

**How to read events:**
- **🔴 Red (ERROR):** Something went wrong, might need attention
- **🟡 Yellow (WARNING):** Potential issue, keep an eye on it
- **🔵 Blue (INFO):** Just information, no action needed
- **🟢 Green (SUCCESS):** Good news, something worked!

**How to use:**
1. Look for patterns: Multiple errors from the same program? Might be a problem.
2. Use the filter buttons to show only errors or warnings.
3. Click **Refresh** to reload the latest events.

**Real Example:**
```
🔴 ERROR - Application - 10:43 AM
Event ID: 1000
Message: "Application crash: chrome.exe"
→ This means Chrome crashed. If it happens often, reinstall Chrome.
```

**When to check:**
- Computer acting weird (slow, freezing)
- After installing new software
- Once a week for peace of mind

---

### 3. System Snapshot 📸

**What it does:** Detailed information about your computer's hardware and software.

**Four Tabs:**

**Overview Tab:**
- Operating System (Windows 10/11)
- Computer name
- Total RAM and disk space
- **Use case:** Writing tech specs for selling your PC

**Hardware Tab:**
- CPU model and speed (e.g., "Intel Core i7-9700K @ 3.6 GHz")
- Number of cores (more = better multitasking)
- GPU model
- **Use case:** Checking if you can run a new game

**Network Tab:**
- All network adapters (WiFi, Ethernet, VPN)
- IP addresses
- Internet speed
- **Use case:** Troubleshooting internet connection

**Storage Tab:**
- All hard drives (C:\, D:\, etc.)
- Free space vs. used space
- **Use case:** Freeing up disk space before big downloads

**Pro tip:** Take screenshots of this page when calling tech support—they'll love you!

---

### 4. Scan History 🗂️

**What it does:** Shows all security scans you've run, stored in a local database.

**How to use:**
1. See past scan results (date, file name, threats found)
2. Click a row to see full details
3. Export to CSV (Excel) for record-keeping

**Columns explained:**
- **Timestamp:** When you ran the scan
- **Scan Type:** Quick (30s), Full (5min), or Deep (15min)
- **File Path:** What you scanned
- **Threats Found:** Number of suspicious items
- **Status:** Clean, Infected, or Error

**Export to Excel:**
1. Click **Export CSV** button (top right)
2. File saves to `Downloads/sentinel_scan_history_[timestamp].csv`
3. Open with Excel or Google Sheets

**Real Example:**
```
2025-10-18 14:23:45 | Quick Scan | C:\Users\YourName\Downloads\setup.exe | 2 threats | Infected
→ Delete setup.exe immediately! It contains malware.
```

---

### 5. Network Scan 🌐

**What it does:** Scans your home network to see all connected devices.

**Requirements:** Nmap must be installed (see Optional Upgrades).

**How to use:**
1. Enter target: `192.168.1.0/24` (scans your whole home network)
2. Choose profile:
   - **Safe Scan:** Fast, detects devices only
   - **Deep Scan:** Slower, finds open ports (security holes)
3. Click **Start Scan** (takes 1-3 minutes)
4. Results show:
   - IP addresses of devices
   - Device type (computer, phone, smart TV)
   - Open ports (red = potential security risk)

**Common Targets:**
- `192.168.1.0/24` - Typical home network
- `192.168.0.0/24` - Alternative home network
- `10.0.0.0/24` - Another common range
- `127.0.0.1` - Your own computer (for testing)

**Security Tips:**
- Unknown device? Change WiFi password immediately
- Open port 3389? Disable Remote Desktop if not needed
- Open port 445? Ensure Windows updates are current (prevents WannaCry)

**Pro tip:** Run once a month to spot intruders on your WiFi.

---

### 6. Scan Tool 🔍

**What it does:** Deep-dive security scan of specific files or folders.

**Three Scan Types:**

**Quick Scan (30 seconds):**
- Basic threat detection
- Uses pattern matching
- **Best for:** Daily downloads folder checks

**Full Scan (5 minutes):**
- Comprehensive analysis
- Checks file reputation (with VirusTotal)
- Analyzes behavior patterns
- **Best for:** New software before installing

**Deep Scan (15 minutes):**
- Everything from Full Scan PLUS:
- Rootkit detection
- Hidden process scanning
- Registry hijack checks
- **Best for:** Suspicious behavior, after malware removal

**How to use:**
1. Click a scan type tile (Quick/Full/Deep)
2. Click **Select File or Folder**
3. Browse to the suspicious file
4. Click **Start Scan**
5. Wait for results (toast notification appears)

**What do results mean?**
- **Clean:** No threats detected, safe to use
- **Suspicious:** Might be dangerous, get a second opinion
- **Infected:** Delete immediately, don't open!

**Real Example:**
```
Scanned: C:\Users\YourName\Downloads\game-crack.exe
Result: 12 threats detected
Recommendation: ❌ DELETE - This is ransomware disguised as a game crack
```

---

### 7. Data Loss Prevention 🛡️

**What it does:** Monitors sensitive file access and suspicious activity.

**Live Metrics:**

**File Operations:**
- Tracks read/write to important folders (Documents, Downloads)
- Spike = lots of activity (could be ransomware encrypting files)

**USB Activity:**
- Shows when USB drives are connected
- Warns if files are copied to USB (data theft prevention)

**Clipboard Activity:**
- Monitors copy/paste operations
- Detects password manager data copies

**Screenshot Detection:**
- Logs when Print Screen is pressed
- Helps track potential data exfiltration

**Sensitive File Access:**
- Monitors tax documents, medical records, banking files
- Alerts when unusual programs access these

**How to read:**
- **Green (0-10 events/min):** Normal activity
- **Yellow (10-50 events/min):** High activity, keep watching
- **Red (50+ events/min):** Potential ransomware, investigate!

**Pro tip:** If metrics spike while you're away from keyboard → possible malware running.

---

### 8. Settings ⚚

**What it does:** Customize Sentinel to your preferences.

**Theme Selector:**
- **Dark Mode:** Easy on eyes, saves battery (default)
- **Light Mode:** Traditional look, better in bright rooms
- **System:** Matches Windows theme automatically

**Other Settings (coming in v1.1.0):**
- Scan schedules (daily automatic scans)
- Email alerts (notify on threats)
- Quarantine management

**How to change theme:**
1. Click Settings (gear icon in sidebar)
2. Click theme dropdown
3. Select Dark / Light / System
4. Theme changes instantly (< 300ms)
5. Setting saves automatically—persists after restart

---

## Common Tasks

### Task 1: Scan a Downloaded File Before Opening

**Scenario:** You downloaded `installer.exe` from the internet. Is it safe?

**Steps:**
1. Go to **Scan Tool** (Ctrl+6)
2. Click **Full Scan** tile
3. Click **Select File or Folder**
4. Navigate to `Downloads` folder
5. Select `installer.exe`
6. Click **Start Scan**
7. Wait 5 minutes for results
8. **If Clean:** Open installer
9. **If Infected:** Delete immediately (Shift+Delete to skip Recycle Bin)

**Why Full Scan?** Uses VirusTotal to check against 70+ antivirus engines.

---

### Task 2: Check Why Computer is Slow

**Scenario:** Your computer feels sluggish today.

**Steps:**
1. Go to **Home** (Dashboard)
2. Check CPU Usage:
   - **High (>80%)?** Click chart → See which program is using CPU (Task Manager)
3. Check Memory Usage:
   - **High (>85%)?** Close unused browser tabs and programs
4. Check GPU Usage:
   - **High when idle?** Cryptominer malware? Run Deep Scan.
5. Go to **Event Viewer** (Ctrl+2)
6. Look for errors in last hour:
   - Application crashes? Reinstall that app.
   - Disk errors? Run `chkdsk C: /f` in Command Prompt (admin).

**Pro tip:** CPU/GPU both high when idle = likely cryptominer malware.

---

### Task 3: Find Unknown Devices on Your WiFi

**Scenario:** WiFi feels slow. Is someone leeching?

**Steps:**
1. Go to **Network Scan** (Ctrl+5)
2. Enter target: `192.168.1.0/24` (or check router label for range)
3. Select **Safe Scan**
4. Click **Start Scan** (takes 2 minutes)
5. Review results:
   - Recognize all devices by name/IP?
   - Unknown device? Note its IP address.
6. Log into router (usually `192.168.1.1` in browser)
7. Block unknown device by MAC address
8. Change WiFi password

**How to identify devices:**
- `192.168.1.1` - Usually your router
- `192.168.1.2-10` - Computers, laptops
- `192.168.1.50+` - Phones, smart TVs, IoT devices

---

### Task 4: Export Scan History for Insurance Claim

**Scenario:** Malware damaged your files. Insurance needs proof you scanned regularly.

**Steps:**
1. Go to **Scan History** (Ctrl+4)
2. Click **Export CSV** button (top right)
3. File saves to `Downloads/sentinel_scan_history_[date].csv`
4. Open in Excel:
   - Shows all scans with timestamps
   - Proves due diligence
5. Attach to insurance claim

**What they look for:**
- Regular scanning (weekly or daily)
- Scans before opening suspicious files
- Prompt action on infected files

---

### Task 5: Troubleshoot "Nmap Not Found" Error

**Scenario:** Network Scan shows orange "Nmap Not Installed" badge.

**Steps:**
1. Download Nmap: [nmap.org/download.html](https://nmap.org/download.html)
2. Run installer: `nmap-7.94-setup.exe`
3. Install with default options (includes WinPcap)
4. Restart Sentinel
5. Check Dashboard → Nmap badge should turn green ✅

**Still not working?**
1. Open PowerShell
2. Type: `nmap --version`
3. **If error:** Add Nmap to PATH:
   - Open Environment Variables (search in Start)
   - Edit `Path` variable
   - Add `C:\Program Files (x86)\Nmap`
   - Restart computer

---

## Troubleshooting

### Problem: Sentinel Won't Start

**Symptom:** Double-click `main.py`, nothing happens.

**Solutions:**
1. **Check Python installed:**
   - Open PowerShell
   - Type `python --version`
   - Should show Python 3.10 or newer
   - **If not:** Download from [python.org](https://www.python.org/downloads/)

2. **Install missing packages:**
   ```powershell
   cd C:\Sentinel
   pip install -r requirements.txt
   ```

3. **Check error message:**
   ```powershell
   python main.py
   # Read the error message and Google it
   ```

---

### Problem: "Not Running as Administrator" Warning

**Symptom:** Orange badge says "Not Admin" on Dashboard.

**Impact:**
- Event Viewer can't read Security logs
- Some network scans might fail

**Solution:**
- Right-click `run_as_admin.bat` → Run as Administrator
- **OR** Right-click `main.py` → Run as Administrator

**Why:** Windows protects sensitive logs from normal users.

---

### Problem: Live Charts Show 0%

**Symptom:** CPU/Memory/GPU charts are flat at 0%.

**Solutions:**
1. **Wait 5 seconds:** Charts update every 1 second, might still be loading.
2. **Check psutil installed:**
   ```powershell
   pip show psutil
   # Should show version 6.1.0 or newer
   ```
3. **Restart Sentinel:** Close completely, reopen.

---

### Problem: VirusTotal Always Says "API Key Missing"

**Symptom:** Orange badge on Dashboard, file scans show "VT unavailable".

**Solution:**
1. Get free API key: [virustotal.com/gui/join-us](https://www.virustotal.com/gui/join-us)
2. Copy key (looks like `a1b2c3d4e5f6...` 64 characters)
3. Create `.env` file in Sentinel folder (no name, just `.env`)
4. Add line: `VT_API_KEY=your_key_here`
5. Save file
6. Restart Sentinel
7. Dashboard badge should turn green ✅

**Note:** File must be named exactly `.env` (not `.env.txt`)

---

### Problem: Network Scan Takes Forever

**Symptom:** Scan running for 10+ minutes, no results.

**Solutions:**
1. **Check target:** `192.168.1.0/24` (not `192.168.1.0/16` which scans 65,000 IPs!)
2. **Use Safe Scan:** Deep Scan can take 15+ minutes for large networks
3. **Check firewall:** Might be blocking Nmap (temporarily disable for scan)
4. **Verify Nmap installed:** Dashboard badge should be green

---

### Problem: High CPU Usage (Sentinel Using 10%+)

**Symptom:** Task Manager shows `python.exe` using lots of CPU.

**Normal usage:**
- Idle: 1-2% CPU
- During scan: 5-10% CPU
- Live charts updating: 3-5% CPU

**Solutions:**
1. **Close other Python programs:** Might be conflicting
2. **Restart Sentinel:** Memory leak? (rare, but possible)
3. **Check for infinite loops:** If persists, report bug on GitHub

---

### Problem: Scan History Shows "0 scans loaded"

**Symptom:** Scan History page is empty, even though you've run scans.

**Explanation:** This is actually correct behavior on first install!
- Scans only save when using Scan Tool page
- Quick Scan button on Home doesn't save to history (it's a quick check)

**How to populate:**
1. Go to Scan Tool (Ctrl+6)
2. Run any scan type (Quick/Full/Deep)
3. Wait for completion
4. Go to Scan History (Ctrl+4)
5. Should now show 1 scan

---

## FAQ

### Q: Is Sentinel a replacement for Windows Defender?

**A:** No, Sentinel works alongside Windows Defender.
- **Windows Defender:** Real-time protection, always running
- **Sentinel:** On-demand scanning, monitoring, and analysis
- **Best practice:** Keep both enabled for maximum security

---

### Q: Does Sentinel send my data to the cloud?

**A:** Only if you enable VirusTotal.
- **Without VT:** 100% local, zero data leaves your PC
- **With VT:** Only file hashes (SHA256) sent, not actual files
- **Network Scan:** Local only, no cloud
- **Event Logs:** Local only, never uploaded

**Privacy guarantee:** No telemetry, no analytics, no user tracking.

---

### Q: Can I use Sentinel on multiple computers?

**A:** Yes! Free and unlimited.
- Copy Sentinel folder to each computer
- Each computer has its own scan history database
- Share VirusTotal API key across all (but watch rate limits: 4 requests/min free tier)

---

### Q: How much does Sentinel cost?

**A:** $0 - Completely free!
- Open source (GPL-3.0 license)
- No hidden fees, no premium versions
- VirusTotal API key is free (with rate limits)
- Nmap is free

**Optional paid upgrades:**
- VirusTotal Premium ($10/mo) - Higher rate limits, file upload
- Nmap (free, but donations appreciated)

---

### Q: What's the difference between Quick, Full, and Deep scans?

| Feature | Quick (30s) | Full (5min) | Deep (15min) |
|---------|-------------|-------------|--------------|
| **Pattern matching** | ✅ | ✅ | ✅ |
| **VirusTotal check** | ❌ | ✅ | ✅ |
| **Behavior analysis** | ❌ | ✅ | ✅ |
| **Rootkit detection** | ❌ | ❌ | ✅ |
| **Registry scan** | ❌ | ❌ | ✅ |
| **Best for** | Daily checks | New software | Malware removal |

**Pro tip:** Quick Scan daily, Full Scan weekly, Deep Scan only when suspicious.

---

### Q: Why does Sentinel need administrator privileges?

**A:** For full Event Viewer access.
- **Without admin:** Can read Application and System logs (90% of events)
- **With admin:** Also reads Security logs (login attempts, permission changes)

**You can run without admin** if you don't need Security logs.

---

### Q: Can Sentinel detect ransomware?

**A:** Yes, in two ways:
1. **Signature detection:** Recognizes known ransomware patterns
2. **Behavior monitoring:** Data Loss Prevention page shows spike in file operations (ransomware encrypting files)

**But:** Sentinel is reactive, not proactive.
- **Best practice:** Keep Windows Defender enabled (proactive real-time protection)
- Use Sentinel for analysis and verification

---

### Q: How do I uninstall Sentinel?

**A:** Just delete the folder!
1. Close Sentinel
2. Delete `C:\Sentinel` folder (or wherever you installed)
3. Database and settings auto-delete with folder
4. No registry entries to clean

**Optional:** If you installed Nmap just for Sentinel, uninstall from Control Panel → Programs.

---

### Q: Can I run Sentinel on a schedule (e.g., daily at 2 AM)?

**A:** Not yet in v1.0.0, but coming in v1.1.0!

**Current workaround:**
1. Create a Windows Task Scheduler entry
2. Run: `python main.py --scan-quick` (planned feature)
3. Set trigger: Daily at 2 AM

---

## Getting Help

### Free Support

**GitHub Issues:** [github.com/mahmoudbadr238/graduationp/issues](https://github.com/mahmoudbadr238/graduationp/issues)
- Report bugs
- Request features
- Ask questions
- Response time: 24-48 hours

**Documentation:**
- [README.md](../README.md) - Quick start guide
- [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) - VT + Nmap setup
- [QA_FINAL_REPORT.md](development/QA_FINAL_REPORT.md) - Technical testing details

### Community

**Discord** (coming soon): Real-time chat with other users

**Reddit** (unofficial): r/Sentinel_Security (community-created)

### Paid Support

**Not available yet.** For enterprise support, contact: [your-email@example.com]

---

## Quick Reference Card

**Keyboard Shortcuts:**
- `Ctrl+1` - Home (Dashboard)
- `Ctrl+2` - Event Viewer
- `Ctrl+3` - System Snapshot
- `Ctrl+4` - Scan History
- `Ctrl+5` - Network Scan
- `Ctrl+6` - Scan Tool
- `Ctrl+7` - Data Loss Prevention
- `Ctrl+8` - Settings
- `Esc` - Return to Home

**Status Colors:**
- 🟢 Green - Good, active, safe
- 🟡 Yellow/Orange - Warning, not configured, optional
- 🔴 Red - Error, danger, action needed

**Scan Recommendations:**
- **Daily:** Quick Scan (Downloads folder)
- **Weekly:** Full Scan (entire system)
- **Monthly:** Network Scan (check WiFi intruders)
- **As-needed:** Deep Scan (after malware infection)

---

## Final Tips

1. **Run as Administrator** for full features (right-click `run_as_admin.bat`)
2. **Get a VirusTotal API key** for best file scanning (free, 2 minutes)
3. **Install Nmap** for network security auditing (free, 5 minutes)
4. **Check Event Viewer** weekly for early warning signs
5. **Export Scan History** monthly for records/insurance
6. **Keep Windows updated** (Sentinel doesn't replace OS security patches)
7. **Trust your instincts** - If something feels suspicious, run a Deep Scan

---

**Remember:** Security is a journey, not a destination. Sentinel is your companion on that journey. Stay safe! 🛡️

---

*For technical documentation, see [README_BACKEND.md](README_BACKEND.md)*  
*For API integration, see [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md)*  
*For bug reports, visit [GitHub Issues](https://github.com/mahmoudbadr238/graduationp/issues)*

**Version:** 1.0.0  
**Last Updated:** October 18, 2025  
**License:** GPL-3.0
