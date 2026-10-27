# Reference: iOS Simulator & Mobile Automation

Origin: conorluddy/ios-simulator-skill  
License: MIT  

## Mobile Testing & Verification

1. **Simulator CLI (`xcrun simctl`)**:
   - Boot device: `xcrun simctl boot <device-id>`
   - Install build: `xcrun simctl install booted <path/to/app>`
   - Launch app: `xcrun simctl launch booted <bundle-identifier>`
   - Capture screenshot: `xcrun simctl io booted screenshot <output.png>`
2. **Touch Targets on Mobile**:
   - Minimum tap target: 44×44pt.
   - Safe areas: Respect `safeAreaInsets` (notch, dynamic island, home indicator bar).
