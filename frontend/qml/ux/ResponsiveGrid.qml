import QtQuick
import QtQuick.Layouts

/**
 * Responsive Grid Layout
 * Automatically computes columns based on container width and minimum card width
 * 
 * Usage:
 *   ResponsiveGrid {
 *       minCardWidth: 280
 *       hSpacing: Theme.spacing_m
 *       vSpacing: Theme.spacing_l
 *       
 *       Card { }
 *       Card { }
 *       Card { }
 *   }
 */
GridLayout {
    id: grid
    
    // Configure these properties
    property int minCardWidth: 280   // Minimum width per card/column
    property int hSpacing: 16        // Horizontal spacing
    property int vSpacing: 16        // Vertical spacing
    
    columns: Math.max(1, Math.floor(width / (minCardWidth + hSpacing)))
    columnSpacing: hSpacing
    rowSpacing: vSpacing
    
    // All children get equal width
    children: {
        let result = []
        for (let i = 0; i < grid.children.length; i++) {
            let child = grid.children[i]
            if (child === this) continue  // Skip the grid itself
            result.push(child)
        }
        return result
    }
    
    // Ensure items fill grid uniformly
    Repeater {
        model: grid.columns
        delegate: Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
