# app/ai/event_id_knowledge.py
"""
Local knowledge base for common Windows Event IDs.

This provides instant, accurate explanations for well-known Windows events
without needing AI inference. No network calls, no external dependencies.

The knowledge base is derived from Microsoft documentation but stored locally
as simple Python data structures for fast lookup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class EventKnowledge:
    """Structured knowledge about a Windows event."""
    
    title: str                  # Short summary (max ~60 chars)
    severity: str               # "Safe", "Minor", "Warning", "Critical"
    what_happened: str          # 1-2 sentences in plain language
    what_you_can_do: str        # 1-3 bullet-style sentences
    tech_notes: Optional[str] = None  # Optional technical detail


# Key: (source, event_id) OR ("*", event_id) for generic/any-source matches
EVENT_KB: Dict[Tuple[str, int], EventKnowledge] = {
    # =========================================================================
    # APPLICATION EVENTS
    # =========================================================================
    
    ("Application", 1000): EventKnowledge(
        title="Application error occurred",
        severity="Warning",
        what_happened=(
            "A program on your computer crashed or had an error. "
            "Windows recorded this so you can troubleshoot if needed."
        ),
        what_you_can_do=(
            "If the app is still working, no action needed. "
            "If it keeps crashing, try updating or reinstalling the app."
        ),
        tech_notes="Windows Error Reporting: Application Error (Event ID 1000)."
    ),
    
    ("Application", 1001): EventKnowledge(
        title="Error report sent to Microsoft",
        severity="Safe",
        what_happened=(
            "Windows sent an error report to help Microsoft improve their software. "
            "This is a normal follow-up to an earlier crash or problem."
        ),
        what_you_can_do=(
            "No action needed. This just confirms an error report was sent."
        ),
        tech_notes="Windows Error Reporting follow-up event."
    ),
    
    ("Application", 1002): EventKnowledge(
        title="Application stopped responding",
        severity="Warning",
        what_happened=(
            "A program froze or stopped responding for a while. "
            "Windows detected this and recorded it."
        ),
        what_you_can_do=(
            "If it happens rarely, you can ignore it. "
            "If it happens often with the same app, try updating or reinstalling that app."
        ),
        tech_notes="Windows Error Reporting: Application Hang (Event ID 1002)."
    ),
    
    ("Application", 1005): EventKnowledge(
        title="Application restart required",
        severity="Minor",
        what_happened="An application needs to be restarted to complete an operation.",
        what_you_can_do="Restart the application when convenient.",
        tech_notes="Windows Error Reporting: Restart required."
    ),
    
    ("Application", 1008): EventKnowledge(
        title="Application crash dump saved",
        severity="Minor",
        what_happened=(
            "An application crashed and Windows saved diagnostic information. "
            "This helps developers fix the problem."
        ),
        what_you_can_do=(
            "If the app keeps crashing, try updating or reinstalling it."
        ),
        tech_notes="Windows Error Reporting: Crash dump created."
    ),
    
    ("Application", 1026): EventKnowledge(
        title=".NET application error",
        severity="Warning",
        what_happened=(
            "A program built with .NET technology had an error. "
            "This is common and usually not serious."
        ),
        what_you_can_do=(
            "If the app still works, no action needed. "
            "If it keeps failing, try updating the app or reinstalling .NET."
        ),
        tech_notes=".NET Runtime error event."
    ),
    
    ("Application", 1033): EventKnowledge(
        title="Application installed successfully",
        severity="Safe",
        what_happened="A program was installed on your computer.",
        what_you_can_do="No action needed.",
        tech_notes="MsiInstaller: Installation success."
    ),
    
    ("Application", 1034): EventKnowledge(
        title="Application removed successfully",
        severity="Safe",
        what_happened="A program was uninstalled from your computer.",
        what_you_can_do="No action needed.",
        tech_notes="MsiInstaller: Removal success."
    ),
    
    ("Application", 1040): EventKnowledge(
        title="Application install/update started",
        severity="Safe",
        what_happened="Windows Installer started installing or updating a program.",
        what_you_can_do="No action needed.",
        tech_notes="MsiInstaller: Install started."
    ),
    
    ("Application", 1042): EventKnowledge(
        title="Application install/update finished",
        severity="Safe",
        what_happened="Windows Installer finished its work.",
        what_you_can_do="No action needed.",
        tech_notes="MsiInstaller: Install ended."
    ),
    
    ("Application", 11707): EventKnowledge(
        title="Software installation successful",
        severity="Safe",
        what_happened="A program was installed successfully on your computer.",
        what_you_can_do="No action needed.",
        tech_notes="MsiInstaller: Product install success."
    ),
    
    ("Application", 11708): EventKnowledge(
        title="Software installation failed",
        severity="Warning",
        what_happened="A program installation failed. It may not work properly.",
        what_you_can_do="Try running the installer again as Administrator.",
        tech_notes="MsiInstaller: Product install failure."
    ),
    
    ("Application", 11724): EventKnowledge(
        title="Software removed successfully",
        severity="Safe",
        what_happened="A program was completely removed from your computer.",
        what_you_can_do="No action needed.",
        tech_notes="MsiInstaller: Product removal success."
    ),
    
    # =========================================================================
    # ESENT (Database Engine) - very common
    # =========================================================================
    
    ("Application", 102): EventKnowledge(
        title="Database instance started",
        severity="Safe",
        what_happened="A Windows database component started. Normal operation.",
        what_you_can_do="No action needed.",
        tech_notes="ESENT: Instance started."
    ),
    
    ("Application", 103): EventKnowledge(
        title="Database instance stopped",
        severity="Safe",
        what_happened="A Windows database component stopped. Normal operation.",
        what_you_can_do="No action needed.",
        tech_notes="ESENT: Instance stopped."
    ),
    
    ("Application", 326): EventKnowledge(
        title="Database attached",
        severity="Safe",
        what_happened="A Windows database was opened. Normal operation.",
        what_you_can_do="No action needed.",
        tech_notes="ESENT: Database attached."
    ),
    
    ("Application", 327): EventKnowledge(
        title="Database detached",
        severity="Safe",
        what_happened="A Windows database was closed. Normal operation.",
        what_you_can_do="No action needed.",
        tech_notes="ESENT: Database detached."
    ),
    
    # =========================================================================
    # VSS (Volume Shadow Copy) - backups
    # =========================================================================
    
    ("Application", 8224): EventKnowledge(
        title="Backup in progress",
        severity="Safe",
        what_happened="Windows is creating a backup or restore point.",
        what_you_can_do="No action needed. Let it complete.",
        tech_notes="VSS: Writer in use."
    ),
    
    # =========================================================================
    # SYSTEM EVENTS - Startup/Shutdown
    # =========================================================================
    
    ("*", 6005): EventKnowledge(
        title="Windows started",
        severity="Safe",
        what_happened=(
            "Windows started the Event Log service, which means your computer just booted up. "
            "This is completely normal."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Event log service startup marker."
    ),
    
    ("*", 6006): EventKnowledge(
        title="Windows shut down normally",
        severity="Safe",
        what_happened=(
            "Windows shut down the Event Log service properly. "
            "This means your computer was turned off or restarted normally."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Event log service shutdown marker."
    ),
    
    ("*", 6008): EventKnowledge(
        title="Unexpected shutdown detected",
        severity="Warning",
        what_happened=(
            "Windows detected that your computer was not shut down properly last time. "
            "This could be from a power outage, holding the power button, or a crash."
        ),
        what_you_can_do=(
            "If you lost power or forced a shutdown, no worries. "
            "If this happens often without explanation, have your computer checked."
        ),
        tech_notes="Unexpected shutdown event (dirty shutdown)."
    ),
    
    ("*", 6009): EventKnowledge(
        title="Windows version information",
        severity="Safe",
        what_happened=(
            "Windows recorded its version information at startup. "
            "This is just a reference log entry."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Windows version logged at boot time."
    ),
    
    ("System", 1074): EventKnowledge(
        title="System restart or shutdown initiated",
        severity="Safe",
        what_happened=(
            "Someone or something requested a restart or shutdown of your computer. "
            "This is normal when you restart Windows or install updates."
        ),
        what_you_can_do="No action needed unless it was unexpected.",
        tech_notes="User-initiated restart/shutdown event."
    ),
    
    ("System", 1076): EventKnowledge(
        title="Unexpected shutdown reason recorded",
        severity="Minor",
        what_happened=(
            "Windows recorded why the last shutdown was unexpected. "
            "Someone may have filled out the Shutdown Event Tracker."
        ),
        what_you_can_do="No action needed. This is informational.",
        tech_notes="Shutdown Event Tracker reason."
    ),
    
    # =========================================================================
    # SYSTEM EVENTS - Services
    # =========================================================================
    
    ("System", 7000): EventKnowledge(
        title="A service failed to start",
        severity="Warning",
        what_happened=(
            "A Windows service tried to start but couldn't. "
            "Some features might not work until this is fixed."
        ),
        what_you_can_do=(
            "If everything seems fine, you can ignore this. "
            "If something isn't working, try restarting your computer. "
            "Check Windows Update for fixes."
        ),
        tech_notes="Service Control Manager: Service start failure."
    ),
    
    ("System", 7001): EventKnowledge(
        title="A service depends on another that failed",
        severity="Warning",
        what_happened=(
            "A service couldn't start because another service it needs didn't start. "
            "This is like a chain reaction from another problem."
        ),
        what_you_can_do=(
            "Look for another error about the original service that failed. "
            "Restarting your computer often fixes this."
        ),
        tech_notes="Service Control Manager: Dependency failure."
    ),
    
    ("System", 7034): EventKnowledge(
        title="A service stopped unexpectedly",
        severity="Warning",
        what_happened=(
            "A Windows service crashed or stopped running unexpectedly. "
            "Windows may try to restart it automatically."
        ),
        what_you_can_do=(
            "If the service restarted and things work fine, no worries. "
            "If you notice problems, restart your computer."
        ),
        tech_notes="Service Control Manager: Unexpected service termination."
    ),
    
    ("System", 7036): EventKnowledge(
        title="Service status changed",
        severity="Safe",
        what_happened=(
            "A Windows service started or stopped. "
            "This is normal and happens all the time."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Service Control Manager: Service state change."
    ),
    
    ("System", 7040): EventKnowledge(
        title="Service startup type changed",
        severity="Safe",
        what_happened=(
            "The way a service starts was changed (automatic, manual, disabled). "
            "This could be from an update or a settings change."
        ),
        what_you_can_do="No action needed unless you didn't make this change.",
        tech_notes="Service Control Manager: Start type modification."
    ),
    
    # =========================================================================
    # SYSTEM EVENTS - DCOM / Permissions
    # =========================================================================
    
    ("System", 10016): EventKnowledge(
        title="DCOM permissions issue",
        severity="Minor",
        what_happened=(
            "A Windows component tried to do something it doesn't have full permission for. "
            "This is very common and usually doesn't cause any real problems."
        ),
        what_you_can_do=(
            "If everything is working fine, you can safely ignore this. "
            "These are often caused by Windows itself and are harmless."
        ),
        tech_notes="DistributedCOM permission error; very common on consumer Windows."
    ),
    
    # =========================================================================
    # SYSTEM EVENTS - Time
    # =========================================================================
    
    ("System", 1): EventKnowledge(
        title="System time changed",
        severity="Safe",
        what_happened=(
            "Your computer's clock was adjusted. "
            "This often happens when Windows syncs with an internet time server."
        ),
        what_you_can_do="No action needed. This is normal.",
        tech_notes="Kernel-General: System time change."
    ),
    
    ("*", 37): EventKnowledge(
        title="Time synchronized",
        severity="Safe",
        what_happened=(
            "Windows synchronized your computer's clock with an internet time server. "
            "This keeps your clock accurate."
        ),
        what_you_can_do="No action needed. This is a good thing!",
        tech_notes="Windows Time service sync event."
    ),
    
    # =========================================================================
    # SECURITY EVENTS - Logon/Logoff
    # =========================================================================
    
    ("Security", 4624): EventKnowledge(
        title="User logged in successfully",
        severity="Safe",
        what_happened=(
            "Someone successfully logged into your computer. "
            "This happens every time you sign in."
        ),
        what_you_can_do="No action needed if it was you.",
        tech_notes="Successful logon event."
    ),
    
    ("Security", 4625): EventKnowledge(
        title="Failed login attempt",
        severity="Warning",
        what_happened=(
            "Someone tried to log in but entered the wrong password or username. "
            "This could be you mistyping, or someone else trying to access your computer."
        ),
        what_you_can_do=(
            "If you mistyped your password, no worries. "
            "If you see many failed attempts you didn't make, change your password."
        ),
        tech_notes="Failed logon event."
    ),
    
    ("Security", 4634): EventKnowledge(
        title="User logged off",
        severity="Safe",
        what_happened="Someone logged out of your computer. This is normal.",
        what_you_can_do="No action needed.",
        tech_notes="Logoff event."
    ),
    
    ("Security", 4648): EventKnowledge(
        title="Login with explicit credentials",
        severity="Safe",
        what_happened=(
            "A program or service logged in using specific credentials. "
            "This is common for network drives or scheduled tasks."
        ),
        what_you_can_do="No action needed if you recognize the activity.",
        tech_notes="Explicit credential logon."
    ),
    
    ("Security", 4672): EventKnowledge(
        title="Special privileges assigned",
        severity="Safe",
        what_happened=(
            "An administrator or system account was granted special permissions. "
            "This is normal when you use admin features."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Special privileges assigned to new logon."
    ),
    
    # =========================================================================
    # SECURITY EVENTS - Process
    # =========================================================================
    
    ("Security", 4688): EventKnowledge(
        title="New program started",
        severity="Safe",
        what_happened="A program was launched on your computer. This happens constantly.",
        what_you_can_do="No action needed. This is normal activity logging.",
        tech_notes="Process creation audit event."
    ),
    
    ("Security", 4689): EventKnowledge(
        title="Program closed",
        severity="Safe",
        what_happened="A program finished running and closed. This is completely normal.",
        what_you_can_do="No action needed.",
        tech_notes="Process exit audit event."
    ),
    
    # =========================================================================
    # SECURITY EVENTS - Firewall
    # =========================================================================
    
    ("Security", 5152): EventKnowledge(
        title="Network connection blocked",
        severity="Safe",
        what_happened=(
            "Windows Firewall blocked a network connection. "
            "This is the firewall doing its job to protect you."
        ),
        what_you_can_do=(
            "No action needed. If an app isn't working, you may need to allow it through the firewall."
        ),
        tech_notes="Windows Filtering Platform packet drop."
    ),
    
    ("Security", 5156): EventKnowledge(
        title="Network connection allowed",
        severity="Safe",
        what_happened=(
            "Windows Firewall allowed a network connection. "
            "This is normal network activity."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Windows Filtering Platform connection permit."
    ),
    
    # =========================================================================
    # WINDOWS DEFENDER / SECURITY CENTER
    # =========================================================================
    
    ("*", 1116): EventKnowledge(
        title="Windows Defender detected something",
        severity="Warning",
        what_happened=(
            "Windows Defender found a potentially unwanted or dangerous file. "
            "It may have already taken action to protect you."
        ),
        what_you_can_do=(
            "Open Windows Security to see what was found. "
            "Usually Defender handles it automatically."
        ),
        tech_notes="Microsoft Defender Antivirus detection event."
    ),
    
    ("*", 1117): EventKnowledge(
        title="Windows Defender took action",
        severity="Safe",
        what_happened=(
            "Windows Defender took action against a threat. "
            "It may have quarantined, removed, or blocked something suspicious."
        ),
        what_you_can_do=(
            "Open Windows Security to see details. "
            "The threat has likely been handled."
        ),
        tech_notes="Microsoft Defender Antivirus action event."
    ),
    
    ("*", 1150): EventKnowledge(
        title="Windows Defender service started",
        severity="Safe",
        what_happened="Windows Defender started up. Your computer is being protected.",
        what_you_can_do="No action needed. This is good!",
        tech_notes="Microsoft Defender Antivirus service start."
    ),
    
    ("*", 2000): EventKnowledge(
        title="Windows Defender definitions updated",
        severity="Safe",
        what_happened=(
            "Windows Defender updated its virus definitions. "
            "This helps it detect the latest threats."
        ),
        what_you_can_do="No action needed. Updates are good!",
        tech_notes="Microsoft Defender Antivirus signature update."
    ),
    
    ("*", 2001): EventKnowledge(
        title="Windows Defender update failed",
        severity="Warning",
        what_happened=(
            "Windows Defender couldn't update its virus definitions. "
            "Your protection might be slightly outdated."
        ),
        what_you_can_do=(
            "Try running Windows Update. "
            "Open Windows Security and click 'Check for updates'."
        ),
        tech_notes="Microsoft Defender Antivirus signature update failure."
    ),
    
    # =========================================================================
    # WINDOWS UPDATE
    # =========================================================================
    
    ("*", 19): EventKnowledge(
        title="Windows Update installed successfully",
        severity="Safe",
        what_happened="A Windows update was installed. Your system is up to date!",
        what_you_can_do="No action needed. You may need to restart if prompted.",
        tech_notes="Windows Update Agent: Installation success."
    ),
    
    ("*", 20): EventKnowledge(
        title="Windows Update installation failed",
        severity="Warning",
        what_happened=(
            "A Windows update couldn't be installed. "
            "Windows will usually try again later."
        ),
        what_you_can_do=(
            "Try running Windows Update again. "
            "Make sure you have enough disk space. "
            "Restart and try again."
        ),
        tech_notes="Windows Update Agent: Installation failure."
    ),
    
    ("*", 43): EventKnowledge(
        title="Windows Update download started",
        severity="Safe",
        what_happened="Windows is downloading updates. This is normal.",
        what_you_can_do="No action needed. Updates will install when ready.",
        tech_notes="Windows Update Agent: Download started."
    ),
    
    # =========================================================================
    # DISK / STORAGE
    # =========================================================================
    
    ("*", 7): EventKnowledge(
        title="Disk error detected",
        severity="Critical",
        what_happened=(
            "Windows detected a problem reading or writing to a disk. "
            "This could mean your hard drive is having issues."
        ),
        what_you_can_do=(
            "Back up your important files immediately. "
            "Run the built-in disk check tool: Right-click the drive, Properties, Tools, Check. "
            "Consider getting the drive checked by a professional."
        ),
        tech_notes="Disk: Block error or bad sector."
    ),
    
    ("*", 11): EventKnowledge(
        title="Disk controller error",
        severity="Warning",
        what_happened=(
            "Windows had trouble communicating with a disk. "
            "This could be a temporary glitch or a hardware issue."
        ),
        what_you_can_do=(
            "If it happens once, probably fine. "
            "If it keeps happening, check your disk cables and consider backing up your data."
        ),
        tech_notes="Disk: Controller error."
    ),
    
    ("*", 51): EventKnowledge(
        title="Disk write error",
        severity="Warning",
        what_happened=(
            "Windows had trouble writing data to a disk. "
            "This could be temporary or indicate a disk problem."
        ),
        what_you_can_do=(
            "If it happens rarely, probably fine. "
            "If frequent, back up your data and check the disk."
        ),
        tech_notes="Disk: Paging write failure."
    ),
    
    # =========================================================================
    # POWER
    # =========================================================================
    
    ("*", 41): EventKnowledge(
        title="System rebooted without clean shutdown",
        severity="Warning",
        what_happened=(
            "Your computer restarted without shutting down properly. "
            "This could be from a crash, power loss, or forced restart."
        ),
        what_you_can_do=(
            "If you had a power outage or held the power button, that explains it. "
            "If it happens randomly, your computer may need to be checked."
        ),
        tech_notes="Kernel-Power: Bugcheck or unexpected reboot."
    ),
    
    ("*", 42): EventKnowledge(
        title="System entering sleep mode",
        severity="Safe",
        what_happened="Your computer is going to sleep. This is normal.",
        what_you_can_do="No action needed.",
        tech_notes="Kernel-Power: Sleep transition."
    ),
    
    ("*", 107): EventKnowledge(
        title="System resumed from sleep",
        severity="Safe",
        what_happened="Your computer woke up from sleep mode. This is normal.",
        what_you_can_do="No action needed.",
        tech_notes="Kernel-Power: Resume from sleep."
    ),
    
    # =========================================================================
    # DNS / NAME RESOLUTION
    # =========================================================================
    
    ("*", 1014): EventKnowledge(
        title="DNS lookup timed out",
        severity="Minor",
        what_happened=(
            "Your computer tried to look up a website address but it took too long. "
            "This is usually a temporary network hiccup."
        ),
        what_you_can_do=(
            "If your internet is working, ignore this. "
            "If browsing is slow, try restarting your router."
        ),
        tech_notes="DNS Client: Name resolution timeout."
    ),
    
    # =========================================================================
    # DCOM / COM+ ERRORS
    # =========================================================================
    
    ("*", 10010): EventKnowledge(
        title="Program didn't respond in time",
        severity="Minor",
        what_happened=(
            "A Windows component tried to start something but it didn't respond quickly enough. "
            "This usually doesn't cause any real problems."
        ),
        what_you_can_do=(
            "If everything is working, ignore this. "
            "These messages are common and usually harmless."
        ),
        tech_notes="DCOM: Server did not register within timeout."
    ),
    
    ("*", 10317): EventKnowledge(
        title="DCOM activation issue",
        severity="Minor",
        what_happened=(
            "A Windows component had a minor issue starting up. "
            "Windows usually handles this automatically."
        ),
        what_you_can_do="No action needed. This is typically harmless.",
        tech_notes="DCOM: Activation failure (usually cosmetic)."
    ),
    
    # =========================================================================
    # MICROSOFT OFFICE / APPLICATIONS
    # =========================================================================
    
    ("*", 16384): EventKnowledge(
        title="Application started or status update",
        severity="Safe",
        what_happened=(
            "An application logged some status information. "
            "This is normal operational logging."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Application informational event."
    ),
    
    ("*", 16394): EventKnowledge(
        title="Application status logged",
        severity="Safe",
        what_happened=(
            "An application recorded a routine status update. "
            "This is normal behavior."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Application status event."
    ),
    
    # =========================================================================
    # WINDOWS PERFORMANCE / WMI
    # =========================================================================
    
    ("*", 1801): EventKnowledge(
        title="Performance data collection",
        severity="Safe",
        what_happened=(
            "Windows collected some performance data. "
            "This helps Windows run efficiently."
        ),
        what_you_can_do="No action needed.",
        tech_notes="WMI/Performance counter event."
    ),
    
    ("*", 5858): EventKnowledge(
        title="WMI activity recorded",
        severity="Safe",
        what_happened=(
            "Windows Management Instrumentation (WMI) did some work. "
            "This is normal system monitoring activity."
        ),
        what_you_can_do="No action needed.",
        tech_notes="WMI-Activity event."
    ),
    
    ("*", 5857): EventKnowledge(
        title="WMI provider loaded",
        severity="Safe",
        what_happened="A Windows management component was loaded. This is normal.",
        what_you_can_do="No action needed.",
        tech_notes="WMI-Activity: Provider loaded."
    ),
    
    # =========================================================================
    # TASK SCHEDULER
    # =========================================================================
    
    ("*", 100): EventKnowledge(
        title="Scheduled task started",
        severity="Safe",
        what_happened="A scheduled task started running. This is normal.",
        what_you_can_do="No action needed.",
        tech_notes="Task Scheduler: Task started."
    ),
    
    ("*", 101): EventKnowledge(
        title="Scheduled task failed to start",
        severity="Warning",
        what_happened=(
            "A scheduled task couldn't start. "
            "This might affect automatic maintenance or updates."
        ),
        what_you_can_do=(
            "If you notice something not running, check Task Scheduler. "
            "Usually Windows handles this automatically."
        ),
        tech_notes="Task Scheduler: Task start failure."
    ),
    
    ("*", 102): EventKnowledge(
        title="Scheduled task completed",
        severity="Safe",
        what_happened="A scheduled task finished running. This is normal.",
        what_you_can_do="No action needed.",
        tech_notes="Task Scheduler: Task completed."
    ),
    
    ("*", 110): EventKnowledge(
        title="Scheduled task triggered",
        severity="Safe",
        what_happened="A scheduled task was triggered to run. This is normal.",
        what_you_can_do="No action needed.",
        tech_notes="Task Scheduler: Task triggered."
    ),
    
    ("*", 129): EventKnowledge(
        title="Scheduled task process created",
        severity="Safe",
        what_happened="The Task Scheduler started a process for a task. Normal operation.",
        what_you_can_do="No action needed.",
        tech_notes="Task Scheduler: Process created."
    ),
    
    ("*", 200): EventKnowledge(
        title="Scheduled task action started",
        severity="Safe",
        what_happened="A scheduled task action began executing. Normal operation.",
        what_you_can_do="No action needed.",
        tech_notes="Task Scheduler: Action started."
    ),
    
    ("*", 201): EventKnowledge(
        title="Scheduled task action completed",
        severity="Safe",
        what_happened="A scheduled task action finished. Normal operation.",
        what_you_can_do="No action needed.",
        tech_notes="Task Scheduler: Action completed."
    ),
    
    # =========================================================================
    # PRINT / SPOOLER
    # =========================================================================
    
    ("*", 307): EventKnowledge(
        title="Document printed",
        severity="Safe",
        what_happened="A document was sent to a printer. Normal printing activity.",
        what_you_can_do="No action needed.",
        tech_notes="Print Spooler: Document printed."
    ),
    
    ("*", 805): EventKnowledge(
        title="Printer added or removed",
        severity="Safe",
        what_happened="A printer was added or removed from your system.",
        what_you_can_do="No action needed if you made this change.",
        tech_notes="Print Spooler: Printer change."
    ),
    
    # =========================================================================
    # BITS (Background Intelligent Transfer Service)
    # =========================================================================
    
    ("*", 3): EventKnowledge(
        title="Background download started",
        severity="Safe",
        what_happened=(
            "Windows started a background download. "
            "This is often Windows Update or app updates."
        ),
        what_you_can_do="No action needed. Downloads help keep your system updated.",
        tech_notes="BITS: Transfer job started."
    ),
    
    ("*", 4): EventKnowledge(
        title="Background download completed",
        severity="Safe",
        what_happened="A background download finished successfully.",
        what_you_can_do="No action needed.",
        tech_notes="BITS: Transfer job completed."
    ),
    
    ("*", 5): EventKnowledge(
        title="Background download cancelled",
        severity="Safe",
        what_happened="A background download was cancelled.",
        what_you_can_do="No action needed.",
        tech_notes="BITS: Transfer job cancelled."
    ),
    
    # =========================================================================
    # USER PROFILE
    # =========================================================================
    
    ("*", 1530): EventKnowledge(
        title="User profile loaded slowly",
        severity="Minor",
        what_happened=(
            "Loading your user profile took longer than expected. "
            "This can happen if you have many programs starting up."
        ),
        what_you_can_do=(
            "Consider removing some startup programs. "
            "Check Task Manager > Startup tab."
        ),
        tech_notes="User Profile Service: Slow profile load."
    ),
    
    ("*", 1531): EventKnowledge(
        title="User profile backup created",
        severity="Safe",
        what_happened="Windows created a backup of your user profile. This is protective.",
        what_you_can_do="No action needed.",
        tech_notes="User Profile Service: Profile backup."
    ),
    
    # =========================================================================
    # CERTIFICATE / CRYPTO
    # =========================================================================
    
    ("*", 4107): EventKnowledge(
        title="Certificate error",
        severity="Warning",
        what_happened=(
            "Windows encountered an issue with a security certificate. "
            "This might affect secure connections."
        ),
        what_you_can_do=(
            "If websites work fine, ignore this. "
            "If you see certificate warnings in browsers, check your system date/time."
        ),
        tech_notes="CAPI2: Certificate validation issue."
    ),
    
    ("*", 11): EventKnowledge(
        title="Certificate auto-update",
        severity="Safe",
        what_happened="Windows updated its certificate store. This keeps you secure.",
        what_you_can_do="No action needed.",
        tech_notes="CAPI2: Certificate update."
    ),
    
    # =========================================================================
    # GROUP POLICY
    # =========================================================================
    
    ("*", 1500): EventKnowledge(
        title="Group Policy applied",
        severity="Safe",
        what_happened=(
            "Windows applied Group Policy settings. "
            "This is normal on work computers or domain-joined PCs."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Group Policy: Policy applied."
    ),
    
    ("*", 1501): EventKnowledge(
        title="Group Policy applied successfully",
        severity="Safe",
        what_happened="Computer policy was applied successfully.",
        what_you_can_do="No action needed.",
        tech_notes="Group Policy: Computer policy success."
    ),
    
    ("*", 1502): EventKnowledge(
        title="User Group Policy applied",
        severity="Safe",
        what_happened="User policy settings were applied successfully.",
        what_you_can_do="No action needed.",
        tech_notes="Group Policy: User policy success."
    ),
    
    # =========================================================================
    # SEARCH INDEXER
    # =========================================================================
    
    ("*", 3028): EventKnowledge(
        title="Search indexing activity",
        severity="Safe",
        what_happened=(
            "Windows Search is indexing files to make searches faster. "
            "This is normal background activity."
        ),
        what_you_can_do="No action needed.",
        tech_notes="Windows Search: Indexing activity."
    ),
    
    ("*", 3036): EventKnowledge(
        title="Search index optimization",
        severity="Safe",
        what_happened="Windows is optimizing its search index for better performance.",
        what_you_can_do="No action needed.",
        tech_notes="Windows Search: Index optimization."
    ),
    
    # =========================================================================
    # NETWORK
    # =========================================================================
    
    ("*", 4000): EventKnowledge(
        title="Network adapter connected",
        severity="Safe",
        what_happened="A network adapter connected to a network. This is normal.",
        what_you_can_do="No action needed.",
        tech_notes="WLAN/LAN connect event."
    ),
    
    ("*", 4001): EventKnowledge(
        title="Network adapter disconnected",
        severity="Safe",
        what_happened="A network adapter disconnected from a network. This is normal.",
        what_you_can_do="No action needed if you unplugged or moved away from Wi-Fi.",
        tech_notes="WLAN/LAN disconnect event."
    ),
    
    ("*", 10000): EventKnowledge(
        title="Network connection successful",
        severity="Safe",
        what_happened="Your computer connected to a network. Internet should be working!",
        what_you_can_do="No action needed.",
        tech_notes="WLAN connection event."
    ),
    
    ("*", 10001): EventKnowledge(
        title="Network connection failed",
        severity="Warning",
        what_happened="Your computer couldn't connect to a network.",
        what_you_can_do=(
            "Check your Wi-Fi password. "
            "Make sure you're in range. "
            "Try restarting your router."
        ),
        tech_notes="WLAN connection failure."
    ),
    
    # =========================================================================
    # USER ACCOUNT CONTROL (UAC)
    # =========================================================================
    
    ("*", 4673): EventKnowledge(
        title="Privileged service called",
        severity="Safe",
        what_happened=(
            "A program used a special Windows feature that requires elevated permissions. "
            "This is normal for many administrative tools."
        ),
        what_you_can_do="No action needed unless you see suspicious activity.",
        tech_notes="Audit: Privileged service called."
    ),
    
    ("*", 4670): EventKnowledge(
        title="Object permissions changed",
        severity="Safe",
        what_happened="Permissions on a file or folder were changed. This is often normal.",
        what_you_can_do="No action needed if you made the change.",
        tech_notes="Audit: Object permissions modified."
    ),
}


def lookup_event_knowledge(source: str, event_id: int) -> Optional[EventKnowledge]:
    """
    Look up knowledge for a specific event.
    
    Args:
        source: Event source (e.g., "System", "Application", "Security")
        event_id: The Windows Event ID
        
    Returns:
        EventKnowledge if found, None otherwise.
        First checks for exact (source, event_id) match,
        then falls back to generic ("*", event_id) match.
    """
    # Normalize source
    source = (source or "").strip()
    
    # Try exact match first
    key = (source, event_id)
    if key in EVENT_KB:
        return EVENT_KB[key]
    
    # Try generic match (any source)
    generic_key = ("*", event_id)
    return EVENT_KB.get(generic_key)


def get_friendly_title(source: str, event_id: int, fallback: str = "") -> str:
    """
    Get a friendly title for an event, or return fallback if not in KB.
    
    This is useful for the event list display.
    """
    kb = lookup_event_knowledge(source, event_id)
    if kb:
        return kb.title
    return fallback
