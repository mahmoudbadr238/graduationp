# Sentinel Features & Workflows

This document provides technical depth on the core security workflows and features implemented in Sentinel.

---

## 1. Multi-Engine Scan Center

The Scan Center is not a simple ClamAV wrapper. It is an 11-stage pipeline that combines static analysis, heuristics, and external integrations to form a Next-Gen AV (NGAV) approach.

### The 11-Stage Pipeline
1. **Validation & Access:** Verifies file existence, read permissions, and size constraints.
2. **Hashing:** Computes SHA-256 and MD5 hashes simultaneously.
3. **PE Static Analysis:** For Windows executables, uses `pefile` to extract imports/exports, verify section entropy (detecting packers), and flag suspicious API calls (e.g., `VirtualAllocEx`, `SetWindowsHookEx`).
4. **String Extraction:** Extracts up to 200 meaningful ASCII/Unicode strings.
5. **Groq AI NGAV:** Formats the static indicators into a specialized prompt for the Groq LLM, requesting a structured JSON verdict based on behavioral indicators.
6. **ClamAV:** If the local ClamAV daemon/scanner is installed, it queries the signature database.
7. **Signature Verification:** Checks Windows Authenticode signatures to verify publisher trust.
8. **IOC Extraction:** Uses Regex to extract embedded IPs, domains, and URLs.
9. **Deterministic Scoring:** Aggregates findings into a final 0-100 score. *Crucially, the final enforcement decision relies on this deterministic score, preventing AI hallucinations from causing false-positive quarantines.*
10. **Sandbox Detonation:** (Windows Only) Triggers the VMware integration if configured.
11. **Report Generation:** Saves the aggregated JSON report to the SQLite history repository.

---

## 2. Dynamic Sandbox Lab (Windows Only)

The Sandbox Lab provides live malware detonation without relying on cloud APIs.

**Workflow:**
1. **VM Revert:** Uses `vmrun` to restore the target VMware Workstation VM to a known-clean snapshot (e.g., "Clean Base").
2. **File Injection:** Copies the target malware into the guest filesystem.
3. **Execution & Telemetry:** Executes the malware via a hidden PowerShell script inside the guest. 
4. **Visual Capture:** Simultaneously captures high-resolution desktop screenshots from the host every 500ms using `imageio` and `ffmpeg`, stitching them into a live preview for the Sentinel UI.
5. **Delta Analysis:** The guest script monitors process creation, file modifications, and network connections. Upon timeout, it outputs a `summary.json` delta which is pulled back to the host and parsed by the UI.

---

## 3. Real-Time Protection (RTP)

Sentinel actively monitors newly spawned processes to intercept threats before execution finishes.

**Platform Implementations:**
- **Windows (WMI Watcher):** Sentinel subscribes to the WMI event class `Win32_Process.__InstanceCreation`. This provides asynchronous, low-overhead notifications when a new PID is created.
- **Linux (Process Polling):** Due to the lack of a universal WMI equivalent (without writing a custom eBPF/Kernel module), Sentinel implements a highly optimized user-space polling loop using `psutil`. It maintains a known-PID set and diffs it every few milliseconds.

**Enforcement:**
When a new process is detected, the executable path is passed to the static scanner. Based on the configured policy, Sentinel can actively `TerminateProcess` / `kill -9` the malicious PID and log a `ThreatEvent`.

---

## 4. Hardware Telemetry & GPU Monitoring

Sentinel bypasses heavy vendor suites (like AMD ROCm) in favor of lightweight, direct OS queries.

**Data Sources:**
- **NVIDIA:** Uses `nvidia-ml-py` (NVML) as the primary source. If NVML fails, it falls back to parsing `nvidia-smi` CLI output.
- **AMD (Windows):** Uses the `pyadl` SDK.
- **AMD / Intel (Linux):** Reads directly from `/sys/class/drm/cardN/device/hwmon/` to get temperature, power, and fan RPM without external dependencies. 
- **Hybrid Laptops:** Implements a 3-layer detection logic on Linux to find powered-off discrete GPUs (via `lspci` bus scanning) that proprietary drivers might hide to save power.

---

## 5. Security Posture Assessment

Sentinel aggregates disparate OS security settings into a single "Health Dashboard".

**Linux Posture Checks:**
- **Firewall:** Automatically detects and queries `ufw`, `firewalld`, `iptables`, or `nftables`.
- **MAC (Mandatory Access Control):** Checks if AppArmor (`aa-status`) or SELinux (`getenforce`) is actively enforcing policies.
- **Secure Boot:** Queries `mokutil --sb-state`.
- **Disk Encryption:** Traverses block devices using `lsblk` to identify LUKS encryption on root/home partitions.

**Windows Posture Checks:**
- **Defender:** Queries WMI/PowerShell for Real-Time Protection and Signature age.
- **UAC:** Checks registry keys for User Account Control levels. 
- **Firewall:** Checks the state of the Domain, Private, and Public profiles.

---

## 6. Forensics: File Shredding & Carving

- **Secure Delete (3-Pass):** Overwrites the target file with random bytes, random bytes again, and finally zeros. To thwart MFT (Master File Table) or ext4 directory recovery, it renames the file to a random string before issuing the final `unlink()`.
- **File Carving:** A sector-by-sector raw disk scanner that looks for magic file headers (e.g., `\xFF\xD8\xFF` for JPEG). It can recover deleted files from raw block devices without relying on the OS file system.
