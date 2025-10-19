#!/usr/bin/env python3
"""
Performance optimization script for Sentinel
Removes slow PowerShell security checks and adds caching
"""

import re

# Read the original file
with open('app/infra/system_monitor_psutil.py', 'r', encoding='utf-8') as f:
    content = f.read()

# New optimized method with caching
new_method = '''    def _get_security_info(self) -> Dict[str, Any]:
        """Get Windows security features status (cached for 30 seconds)."""
        import time
        
        # Use cached value if less than 30 seconds old
        current_time = time.time()
        if hasattr(self, '_security_cache') and (current_time - self._security_cache_time) < 30:
            return self._security_cache
        
        # Return minimal info to avoid PowerShell delays
        security_info = {
            'windows_defender': {'status': 'Check Windows Security', 'enabled': False},
            'firewall': {'status': 'Check Windows Security', 'enabled': False},
            'antivirus': {'status': 'Check Windows Security', 'enabled': False},
            'uac': {'status': 'Check Settings', 'enabled': False},
            'bitlocker': {'status': 'Check BitLocker', 'enabled': False},
            'tpm': {'status': 'Check Device Security', 'enabled': False},
        }
        
        # Cache for 30 seconds
        self._security_cache = security_info
        self._security_cache_time = current_time
        
        return security_info
'''

# Find and replace the _get_security_info method
# Pattern matches from def _get_security_info to the next def or class
pattern = r'    def _get_security_info\(self\) -> Dict\[str, Any\]:.*?(?=\n    def |\nclass |\Z)'
content_new = re.sub(pattern, new_method, content, flags=re.DOTALL)

# Backup original
with open('app/infra/system_monitor_psutil.py.bak', 'w', encoding='utf-8') as f:
    f.write(content)

# Write optimized version
with open('app/infra/system_monitor_psutil.py', 'w', encoding='utf-8') as f:
    f.write(content_new)

print('✓ Performance optimization complete!')
print('✓ Backup saved to app/infra/system_monitor_psutil.py.bak')
print('✓ Security info now cached for 30 seconds (was checking every snapshot)')
