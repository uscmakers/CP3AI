# Cup Pong iOS App

A SwiftUI prototype for the automated cup pong project. It shows the current cup formation, lets players mark cups as hit, suggests when a rerack makes sense, and previews and applies a new formation.

The app keeps all game state locally on the device. It doesn't talk to the gantry, the Arduino, or the computer vision system yet.

## Requirements

- macOS with **Xcode 16 or later**
- iOS 17+ (iPhone simulator or device)

Xcode downloads the Swift packages (Firebase Auth and Google Sign-In) automatically the first time you open the project.

## Google sign-in setup (optional)

The app runs without this. Until it's set up, the login screen only offers **Continue as Guest**.

1. In the [Firebase console](https://console.firebase.google.com), create a project (or open the team's), then add an **iOS app** with bundle ID `org.uscmakers.CupPong`.
2. In Firebase, go to **Authentication → Sign-in method**, enable **Google**, choose a support email, and click **Save**.
3. Only after that, go to **Project settings → General → Your apps**, download `GoogleService-Info.plist`, and drag it into the `CupPong/` folder in Xcode (check the **CupPong** target). It must contain `CLIENT_ID` and `REVERSED_CLIENT_ID`. If it doesn't, Google sign-in wasn't enabled yet when you downloaded it.
4. Open `GoogleService-Info.plist`, copy the `REVERSED_CLIENT_ID` value, and paste it in place of `com.googleusercontent.apps.REPLACE_WITH_YOUR_CLIENT_ID` in `CupPong/Info.plist`. Google sign-in uses this URL scheme to return to the app.

## Run in Xcode

1. Open `CupPong.xcodeproj`.
2. Choose the **CupPong** scheme and an iPhone simulator (for example, iPhone 16 Pro) from the toolbar.
3. Press **⌘R** to build and run.

### Running on a physical iPhone

1. Connect your iPhone and select it as the run destination.
2. In the **CupPong** target, open **Signing & Capabilities** and select your Team. If the bundle ID `org.uscmakers.CupPong` is already taken, change it to something unique.
3. Press **⌘R**. The first time, you may need to trust the developer profile on the phone under **Settings → General → VPN & Device Management**.

## Run from the command line

From this `mobile/` folder:

```sh
# Build for the simulator
xcodebuild -project CupPong.xcodeproj -scheme CupPong \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
  -derivedDataPath build build

# Boot a simulator, install, and launch
open -a Simulator
xcrun simctl boot "iPhone 16 Pro" 2>/dev/null
xcrun simctl install booted build/Build/Products/Debug-iphonesimulator/CupPong.app
xcrun simctl launch booted org.uscmakers.CupPong
```

Run `xcrun simctl list devices available` to see which simulators you have, and swap in a different device name if needed.

## Using the app

1. The app starts with the standard 10-cup triangle (4-3-2-1).
2. Tap a cup to mark it as hit. It becomes a dashed outline. Tap the outline to restore the cup if you tapped by mistake.
3. When the remaining cups match a rerack formation, a **Rerack available** card appears.
4. Tap **Rearrange** to see the formations for the current cup count, select one to preview it, and confirm.
5. Each game allows only **one** rearrangement. Tap the reset button (↺) in the top-right to start a new rack.

## Project structure

```
CupPong/
├── CupPongApp.swift          App entry point
├── Models/
│   ├── Formation.swift       Formation definitions (FormationLibrary)
│   ├── Cup.swift             Cup model
│   └── RerackRules.swift     When to suggest a rerack + rearrangement limit
├── ViewModels/
│   └── GameViewModel.swift   Game state: cups, formation, rearrangements used
└── Views/
    ├── GameView.swift        Main screen
    ├── RearrangeView.swift   Formation picker / preview sheet
    └── Components/           CupView, FormationView, FormationCard, RerackBanner, Card
```

## Formations and rules

Formations match `rack_layouts` in `../software/layouts.py`, using the same IDs and coordinates in cup diameters:

| Cups | Formation | ID |
|------|-----------|----|
| 10 | Triangle (4-3-2-1) | `triangle_10` |
| 6 | Triangle (3-2-1) | `triangle_6` |
| 5 | Backpack | `backpack_kid_5` |
| 3 | Triangle (2-1) | `triangle_3` |
| 2 | Vertical | `vertical_2` |

- **To add a formation:** define it in `FormationLibrary` in `Models/Formation.swift` and add it to `all`. Add it to `software/layouts.py` too so the gantry planner and the app stay in sync.
- **To change the rerack rules:** edit `RerackRules` in `Models/RerackRules.swift`. `suggestedCounts` sets the cup counts that trigger a suggestion, and `maxRearrangements` sets the per-game limit. Both mirror `REARRANGE_FORMATIONS` and `MAX_REARRANGEMENTS` in `software/motion_viewer.py`.

The Xcode project uses folder-synced groups, so any new `.swift` file added under `CupPong/` is picked up automatically.
