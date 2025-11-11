#!/usr/bin/env python3
"""
QML Static Linter for Responsiveness
Flags:
- Hard-coded width/height without Layout.* or implicitWidth/Height
- Anchor conflicts (anchors.fill + individual anchors)
- Text without wrapMode on shrinkable containers
- Fixed font pixel sizes (should use Theme tokens)
"""

import sys
import re
from pathlib import Path
from typing import List, Tuple, Dict

class QMLLinter:
    def __init__(self):
        self.violations = []
        self.files_checked = 0
        self.qml_root = Path(__file__).parent.parent / 'qml'
        
    def lint_all(self):
        """Scan all QML files"""
        if not self.qml_root.exists():
            print(f"Error: QML root not found at {self.qml_root}")
            return False
            
        for qml_file in self.qml_root.rglob('*.qml'):
            self.lint_file(qml_file)
            
        self._print_report()
        return len(self.violations) == 0
        
    def lint_file(self, filepath: Path):
        """Lint a single QML file"""
        self.files_checked += 1
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return
            
        # Check for violations
        self._check_fixed_dimensions(filepath, lines)
        self._check_anchor_conflicts(filepath, lines)
        self._check_text_wrapping(filepath, lines)
        self._check_fixed_fonts(filepath, lines)
        
    def _check_fixed_dimensions(self, filepath: Path, lines: List[str]):
        """Flag hard-coded width/height without Layout or implicitWidth"""
        in_control = False
        control_type = None
        brace_depth = 0
        
        for i, line in enumerate(lines, 1):
            # Skip comments and strings
            if line.strip().startswith('//') or not line.strip():
                continue
                
            # Detect control definitions
            if re.search(r'\b(Rectangle|Item|Label|Button|Text|ComboBox|TextField)\s*\{', line):
                in_control = True
                control_type = re.search(r'\b(\w+)\s*\{', line).group(1)
                brace_depth = 1
                continue
                
            if in_control:
                brace_depth += line.count('{') - line.count('}')
                if brace_depth <= 0:
                    in_control = False
                    control_type = None
                    continue
                    
                # Check for fixed width/height in controls (but skip images)
                if control_type not in ['Image', 'Icon']:
                    width_match = re.search(r'^\s*width:\s*(\d+)', line)
                    height_match = re.search(r'^\s*height:\s*(\d+)', line)
                    
                    if width_match or height_match:
                        # Check if Layout.* or implicitWidth nearby (within next 3 lines)
                        context = '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])
                        has_layout = 'Layout.' in context
                        has_implicit = 'implicitWidth' in context or 'implicitHeight' in context
                        
                        if not (has_layout or has_implicit):
                            dim = 'width' if width_match else 'height'
                            value = width_match.group(1) if width_match else height_match.group(1)
                            self.violations.append({
                                'file': filepath,
                                'line': i,
                                'severity': 'warning',
                                'message': f"Hard-coded {dim}: {value}px without Layout.* or implicit* on {control_type}",
                                'fix': f"Use Layout.preferred{dim.capitalize()}: {value}; Layout.minimum{dim.capitalize()}: 200; or compute relative to Theme"
                            })
                            
    def _check_anchor_conflicts(self, filepath: Path, lines: List[str]):
        """Flag anchors.fill + individual anchors"""
        for i, line in enumerate(lines, 1):
            if re.search(r'anchors\.fill\s*:\s*parent', line):
                # Check surrounding context for individual anchors
                context_start = max(0, i - 3)
                context_end = min(len(lines), i + 3)
                context = '\n'.join(lines[context_start:context_end])
                
                if re.search(r'anchors\.(top|bottom|left|right|centerIn|baseline)', context):
                    self.violations.append({
                        'file': filepath,
                        'line': i,
                        'severity': 'error',
                        'message': f"Anchor conflict: anchors.fill: parent mixed with individual anchor directives",
                        'fix': f"Remove anchors.fill; use ColumnLayout/RowLayout with Layout.fillWidth/Height instead"
                    })
                    
    def _check_text_wrapping(self, filepath: Path, lines: List[str]):
        """Flag Text elements without wrapMode on shrinkable containers"""
        for i, line in enumerate(lines, 1):
            if re.search(r'\bText\s*\{', line):
                # Check surrounding lines (up to 20 lines for full Text element)
                context_end = min(len(lines), i + 20)
                text_block = '\n'.join(lines[i-1:context_end])
                
                # Find closing brace
                brace_count = text_block.count('{') - text_block.count('}')
                for j in range(context_end, min(len(lines), context_end + 30)):
                    if lines[j].count('}') > lines[j].count('{'):
                        text_block = '\n'.join(lines[i-1:j+1])
                        break
                        
                # Check if has fixed width OR is in scrollable container
                has_wrap = 'wrapMode' in text_block
                has_fixed_width = re.search(r'width:\s*\d+', text_block)
                is_in_layout = any(x in text_block for x in ['ColumnLayout', 'RowLayout', 'GridLayout'])
                
                if not has_wrap and (has_fixed_width or is_in_layout):
                    # Check if has elide
                    has_elide = 'elide' in text_block
                    
                    self.violations.append({
                        'file': filepath,
                        'line': i,
                        'severity': 'warning',
                        'message': f"Text without wrapMode in container (may clip on narrow widths)",
                        'fix': f"Add: wrapMode: Text.WordWrap" + (f"; elide: Text.ElideRight" if not has_elide else "")
                    })
                    
    def _check_fixed_fonts(self, filepath: Path, lines: List[str]):
        """Flag hard-coded font pixel sizes"""
        for i, line in enumerate(lines, 1):
            # Skip Theme definitions
            if 'Theme.qml' in str(filepath) or 'theme' in str(filepath):
                continue
                
            # Look for font.pixelSize with hard-coded numbers
            match = re.search(r'font\.pixelSize:\s*(\d+)', line)
            if match:
                value = int(match.group(1))
                # Flag if it looks arbitrary (not Theme.typography.*)
                if not re.search(r'Theme\.typography', line) and value > 8 and value < 64:
                    self.violations.append({
                        'file': filepath,
                        'line': i,
                        'severity': 'warning',
                        'message': f"Hard-coded font size: {value}px (should use Theme tokens)",
                        'fix': f"Use Theme.typography.*.size or compute relative to Theme.base"
                    })
                    
    def _print_report(self):
        """Print formatted violation report"""
        if not self.violations:
            print(f"\n[PASS] All {self.files_checked} QML files are responsive!")
            print("="*60)
            return
            
        print(f"\n{'='*60}")
        print(f"QML LINTER REPORT")
        print(f"{'='*60}")
        print(f"Files checked: {self.files_checked}")
        print(f"Violations found: {len(self.violations)}")
        print(f"{'='*60}\n")
        
        # Group by severity
        errors = [v for v in self.violations if v['severity'] == 'error']
        warnings = [v for v in self.violations if v['severity'] == 'warning']
        
        if errors:
            print(f"ERRORS ({len(errors)}):")
            for v in errors:
                self._print_violation(v)
                
        if warnings:
            print(f"\nWARNINGS ({len(warnings)}):")
            for v in warnings:
                self._print_violation(v)
                
        print(f"\n{'='*60}")
        print(f"Result: {'PASS' if not errors else 'FAIL (fix errors first)'}")
        print(f"{'='*60}\n")
        
    def _print_violation(self, v: Dict):
        """Print a single violation"""
        rel_path = v['file'].relative_to(self.qml_root.parent) if v['file'].is_relative_to(self.qml_root.parent) else v['file']
        print(f"  {v['file'].name}:{v['line']}")
        print(f"    {v['message']}")
        print(f"    Fix: {v['fix']}\n")


def main():
    linter = QMLLinter()
    success = linter.lint_all()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
