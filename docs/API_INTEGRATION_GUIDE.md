# API Integration Guide - Sentinel Security Suite

## Overview
Sentinel supports optional integrations with external security tools to enhance threat detection capabilities. Both integrations are **completely optional** - the core application works without them.

---

## VirusTotal Integration

### What is VirusTotal?
VirusTotal is a free online service that analyzes files and URLs for viruses, worms, trojans, and other malicious content using 70+ antivirus engines.

### Setup Instructions

#### Step 1: Create Free Account
1. Visit https://www.virustotal.com/gui/join-us
2. Sign up with email (Google/GitHub auth supported)
3. Confirm email address

#### Step 2: Get API Key
1. Log in to VirusTotal
2. Navigate to your profile (top-right corner)
3. Go to **API Key** section
4. Copy your 64-character API key

#### Step 3: Configure Sentinel
1. Navigate to Sentinel project root directory
2. Create `.env` file (copy from `.env.example`)
3. Add your API key:
   ```env
   VT_API_KEY=your_64_character_api_key_here
   ```
4. Restart Sentinel

### Verification
1. Open Sentinel
2. Go to **Scan Tool** page
3. Status should show: ✅ **VirusTotal: Enabled**
4. Try scanning a test file (e.g., `notepad.exe`)

### Free Tier Limits
- **4 requests per minute**
- **500 requests per day**
- **15-second cool-down** enforced by Sentinel

### Features Enabled
When VirusTotal is configured, you can:
- ✅ Scan individual files for malware
- ✅ Check URLs for phishing/malware
- ✅ View threat intelligence reports
- ✅ See detection rates from 70+ AV engines
- ✅ Access historical scan data

### Troubleshooting

**"VirusTotal API key required" error:**
- Ensure `.env` file exists in project root
- Check API key has no extra spaces or quotes
- Verify key is 64 characters long
- Restart Sentinel after adding key

**"Rate limit exceeded" error:**
- Free tier: Wait 15 seconds between scans
- Upgrade to Premium API for higher limits
- Check daily quota (500 requests/day)

**"HTTP 403 Forbidden" error:**
- API key may be invalid or expired
- Generate new key from VirusTotal dashboard
- Update `.env` file with new key

---

## Nmap Integration

### What is Nmap?
Nmap (Network Mapper) is a free, open-source tool for network discovery and security auditing. It's used to scan networks and discover connected devices, open ports, and running services.

### Setup Instructions

#### Step 1: Download Nmap
**Windows:**
1. Visit https://nmap.org/download.html
2. Download `nmap-{version}-setup.exe`
3. Run installer

**Important:** During installation, check the box:
```
☑ Add Nmap to system PATH
```

#### Step 2: Verify Installation
Open PowerShell/Command Prompt and run:
```powershell
nmap --version
```

Expected output:
```
Nmap version 7.94 ( https://nmap.org )
Platform: i686-pc-windows-windows
Compiled with: nmap-liblua-5.4.6 ...
```

#### Step 3: Configure Sentinel (if needed)
If Nmap is **not** in system PATH, add to `.env`:
```env
NMAP_PATH=C:\Program Files (x86)\Nmap\nmap.exe
```

#### Step 4: Restart Sentinel
Close and reopen Sentinel. The app will auto-detect Nmap.

### Verification
1. Open Sentinel
2. Go to **Network Scan** page
3. Status should show: ✅ **Nmap: Available**
4. Enter target: `127.0.0.1` (localhost)
5. Click **Start Scan**

### Common Targets
- **Single host:** `192.168.1.1`
- **Subnet:** `192.168.1.0/24` (scans 192.168.1.1-254)
- **Range:** `10.0.0.1-50`
- **Localhost:** `127.0.0.1` (safe test)

### Scan Modes

**Quick Scan (Fast):**
- Scans top 100 most common ports
- Completes in 5-30 seconds
- Good for quick network overview

**Full Scan (Comprehensive):**
- Service version detection (`-sV`)
- All 65,535 ports
- Takes 5-15 minutes
- Detailed service information

### Safety Notes
⚠️ **Only scan networks you own or have permission to scan.**
- Scanning unauthorized networks is **illegal** in most countries
- Some ISPs may flag aggressive scans
- Use **Quick Scan** for home networks
- Test with `127.0.0.1` first

### Features Enabled
With Nmap installed:
- ✅ Discover devices on local network
- ✅ Find open ports and services
- ✅ Detect potential vulnerabilities
- ✅ Map network topology
- ✅ Save scan results to database

### Troubleshooting

**"Nmap not found" error:**
- Verify Nmap is in system PATH:
  ```powershell
  where nmap
  ```
- If not found, add to PATH or set `NMAP_PATH` in `.env`
- Restart Sentinel after PATH changes

**"Scan timed out" error:**
- Large subnets (e.g., /16) can take 30+ minutes
- Use Quick Scan mode for faster results
- Scan smaller ranges (e.g., /24 instead of /16)

**"Permission denied" error:**
- Some scan types require administrator privileges
- Right-click Sentinel → **Run as Administrator**
- Or use `run_as_admin.bat` script

---

## Advanced Configuration

### Environment Variables Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VT_API_KEY` | String | Empty | VirusTotal API key (64 chars) |
| `NMAP_PATH` | Path | `nmap` | Full path to nmap.exe |
| `OFFLINE_ONLY` | Boolean | `false` | Disable all external APIs |
| `DB_PATH` | Path | `~/.sentinel/` | SQLite database location |
| `LOG_LEVEL` | String | `INFO` | Logging verbosity |

### Example `.env` File
```env
# Production configuration
VT_API_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
NMAP_PATH=C:\Tools\nmap\nmap.exe
OFFLINE_ONLY=false
LOG_LEVEL=INFO
```

### Disabling Integrations
To temporarily disable without removing keys:
```env
OFFLINE_ONLY=true
```

This will:
- Disable VirusTotal file/URL scanning
- Disable network scanning
- Keep local features working (monitoring, event viewer, etc.)

---

## Security Best Practices

### API Key Management
1. ✅ **Never commit `.env` to Git**
   - `.env` is in `.gitignore` by default
   - Use `.env.example` for templates

2. ✅ **Rotate keys periodically**
   - Generate new VT API key every 6 months
   - Update `.env` file

3. ✅ **Use environment-specific keys**
   - Development: Use test API key
   - Production: Use dedicated key

### Network Scanning Ethics
1. ✅ **Only scan owned networks**
2. ✅ **Get written permission** for client networks
3. ✅ **Use Quick Scan** in shared environments
4. ❌ **Never scan**: Public Wi-Fi, work networks (without approval), ISP networks

---

## Rate Limiting & Performance

### VirusTotal
Sentinel automatically enforces:
- **15-second cool-down** between requests
- **Progress indicators** during scans
- **Queue system** for multiple files
- **Error handling** for HTTP 429 (rate limit)

### Nmap
Sentinel uses sensible defaults:
- **Quick Scan:** `-F -T4` (fast timing, top 100 ports)
- **Full Scan:** `-sV -T3` (normal timing, service detection)
- **Timeout:** 5 minutes maximum per scan
- **Background execution:** Scans run in separate thread

---

## FAQ

**Q: Can I use Sentinel without API integrations?**  
A: Yes! Core features (system monitoring, event viewer, system snapshot) work without any external APIs.

**Q: Are API keys stored securely?**  
A: Keys are stored in `.env` file (not in source code). File should have restricted permissions (user-read only).

**Q: Does VirusTotal store my scanned files?**  
A: Yes, VirusTotal keeps submitted files for analysis. **Don't scan sensitive/confidential files**.

**Q: Will network scanning affect my internet speed?**  
A: Minimal impact. Quick Scans use low bandwidth (~1-5 MB). Full Scans may use more during service detection.

**Q: Can I use a different network scanner?**  
A: Currently Nmap only. Future versions may support Masscan, Zmap.

**Q: How do I upgrade VirusTotal to Premium?**  
A: Visit https://www.virustotal.com/gui/user/{username}/apikey and subscribe. Higher rate limits apply automatically.

---

## Getting Help

- **Documentation:** https://github.com/mahmoudbadr238/graduationp/wiki
- **Issues:** https://github.com/mahmoudbadr238/graduationp/issues
- **VirusTotal Support:** https://support.virustotal.com/
- **Nmap Docs:** https://nmap.org/docs.html

---

**Last Updated:** October 18, 2025  
**Version:** 1.0.0
