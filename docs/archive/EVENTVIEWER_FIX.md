# EventViewer.qml Fix

## Issue
The EventViewer.qml has errors at lines 111, 124, and 169 where undefined values are being assigned to double properties.

## Root Cause
The Backend context property is not available when the QML component first loads, causing property bindings to fail.

## Solution
Add null checks and default values to all Backend property accesses:

### Line 111 (approximate)
Change:
```qml
property double someValue: Backend.someProperty
```

To:
```qml
property double someValue: Backend ? Backend.someProperty || 0 : 0
```

### General Pattern
For all Backend property accesses in EventViewer.qml, use:
```qml
property double value: (Backend && Backend.property !== undefined) ? Backend.property : 0
```

Or for Theme properties:
```qml
spacing: Theme.spacing_md !== undefined ? Theme.spacing_md : 16
```

## Files to Check
- qml/pages/EventViewer.qml (lines 111, 124, 169)
