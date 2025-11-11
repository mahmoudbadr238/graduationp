#!/usr/bin/env python3
"""
Auto-fix script for common QML responsiveness violations.
Applies targeted fixes to high-impact components and pages.
"""

import re
from pathlib import Path

def fix_text_wrapping(content, filename):
    """Add wrapMode to Text elements that lack it in layouts"""
    # Only fix Text elements not already having wrapMode
    # Look for Text { ... } blocks
    pattern = r'(\s+)Text\s*\{([^}]*?)(?<!wrapMode[^}]*)\s*(Layout\.|anchors\.fill|implicitWidth)'
    
    def add_wrap(match):
        indent = match.group(1)
        text_content = match.group(2)
        next_prop = match.group(3)
        
        # Don't add if already has wrapMode
        if 'wrapMode' in text_content:
            return match.group(0)
            
        # Add wrapMode before the next property
        wrap_mode = f"wrapMode: Text.WordWrap\n{indent}"
        return f"{indent}Text {{{text_content}{wrap_mode}{next_prop}"
    
    return re.sub(pattern, add_wrap, content, flags=re.DOTALL)

def fix_hard_coded_fonts(content, filename):
    """Replace hard-coded font.pixelSize with Theme tokens"""
    # Skip Theme.qml and theme files
    if 'Theme' in filename or 'theme' in filename:
        return content
    
    replacements = [
        (r'font\.pixelSize:\s*32(?!\d)', 'font.pixelSize: Theme.typography.h1.size'),
        (r'font\.pixelSize:\s*28(?!\d)', 'font.pixelSize: Theme.typography.h2.size'),
        (r'font\.pixelSize:\s*24(?!\d)', 'font.pixelSize: Theme.typography.h2.size'),
        (r'font\.pixelSize:\s*20(?!\d)', 'font.pixelSize: Theme.typography.h3.size'),
        (r'font\.pixelSize:\s*18(?!\d)', 'font.pixelSize: Theme.typography.h4.size'),
        (r'font\.pixelSize:\s*16(?!\d)', 'font.pixelSize: Theme.typography.bodyLarge.size'),
        (r'font\.pixelSize:\s*15(?!\d)', 'font.pixelSize: Theme.typography.body.size'),
        (r'font\.pixelSize:\s*14(?!\d)', 'font.pixelSize: Theme.typography.body.size'),
        (r'font\.pixelSize:\s*13(?!\d)', 'font.pixelSize: Theme.typography.bodySmall.size'),
        (r'font\.pixelSize:\s*12(?!\d)', 'font.pixelSize: Theme.typography.bodySmall.size'),
        (r'font\.pixelSize:\s*11(?!\d)', 'font.pixelSize: Theme.typography.caption.size'),
        (r'font\.pixelSize:\s*10(?!\d)', 'font.pixelSize: Theme.typography.caption.size'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    return content

def fix_icon_sizes(content, filename):
    """Replace hard-coded icon pixel sizes with Theme tokens"""
    replacements = [
        # 24px icons
        (r'(?<![a-zA-Z])(?<![\d])width:\s*24(?!\d)[\s\n]*(?=\n\s*height:\s*24)', 
         'Layout.preferredWidth: Theme.size_md\n        Layout.preferredHeight: Theme.size_md'),
        (r'(?<![a-zA-Z])(?<![\d])height:\s*24(?!\d)', 'Layout.preferredHeight: Theme.size_md'),
        # 32px icons
        (r'(?<![a-zA-Z])(?<![\d])width:\s*32(?!\d)', 'Layout.preferredWidth: Theme.size_lg'),
        (r'(?<![a-zA-Z])(?<![\d])height:\s*32(?!\d)', 'Layout.preferredHeight: Theme.size_lg'),
        # 48px icons
        (r'(?<![a-zA-Z])(?<![\d])width:\s*48(?!\d)', 'Layout.preferredWidth: Theme.size_xl'),
        (r'(?<![a-zA-Z])(?<![\d])height:\s*48(?!\d)', 'Layout.preferredHeight: Theme.size_xl'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    return content

def apply_fixes(qml_root):
    """Apply fixes to all QML files"""
    fixes_applied = {}
    qml_files = list(qml_root.rglob('*.qml'))
    
    print(f"Applying fixes to {len(qml_files)} QML files...\n")
    
    for qml_file in qml_files:
        try:
            with open(qml_file, 'r', encoding='utf-8') as f:
                original = f.read()
            
            modified = original
            fix_count = 0
            
            # Apply fixes
            before = len(re.findall(r'font\.pixelSize:\s*\d+', modified))
            modified = fix_hard_coded_fonts(modified, qml_file.name)
            after = len(re.findall(r'font\.pixelSize:\s*\d+', modified))
            if after < before:
                fix_count += (before - after)
                fixes_applied[qml_file.name] = fixes_applied.get(qml_file.name, 0) + (before - after)
            
            # Check if modified
            if modified != original:
                with open(qml_file, 'w', encoding='utf-8') as f:
                    f.write(modified)
                print(f"  ✓ {qml_file.name}: {fix_count} fixes applied")
            
        except Exception as e:
            print(f"  ✗ Error processing {qml_file.name}: {e}")
    
    return fixes_applied

if __name__ == '__main__':
    qml_root = Path(__file__).parent.parent / 'qml'
    if qml_root.exists():
        fixes = apply_fixes(qml_root)
        print(f"\n✓ Total: {sum(fixes.values())} fixes applied across {len(fixes)} files")
    else:
        print(f"Error: QML root not found at {qml_root}")
