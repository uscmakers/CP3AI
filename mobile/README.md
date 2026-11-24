# Cup Pong iOS App

A SwiftUI prototype for the automated cup pong project. It shows the current cup formation, lets players mark cups as hit, suggests when a rerack makes sense, and previews and applies a new formation.

It runs in two modes:

- **Local** (default): the app keeps the game on the phone and players tap cups to mark hits.
- **Table**: the app connects over Wi-Fi to the game server on the Arduino UNO Q. The server runs the game: the camera reports hits, the gantry moves cups, and the app shows the live state. Players can still mark a missed hit, rearrange, or start a new rack from the app.

## Connecting to the table

1. Tap the antenna button in the top-right of the main screen.
2. Enter the table's address, for example `unoq.local` or `192.168.1.20`. Port 8765 is used unless you add one (`host:9000`).
3. Tap **Connect**. The header shows the connection status. If the link drops, the app keeps the last state on screen and retries on its own.
4. To go back to local play, open the same screen and tap **Disconnect and Play Locally**.

The first time, iOS asks for permission to find devices on the local network. Allow it, or the app can't reach the table.

The message format is in [`docs/websocket-protocol.md`](../docs/websocket-protocol.md).

### Trying it without the table

`tools/mock_table_server.py` imitates the table server (Python 3, no packages needed). It fakes the gantry with a short delay and lets you type commands as if you were the camera:

```sh
python3 tools/mock_table_server.py
```

Then type `hit 3`, `rearrange`, `reset` or `state`. In the simulator, connect to `127.0.0.1`. On an iPhone, connect to your Mac's IP address. Both must be on the same Wi-Fi.

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
├── Networking/
│   ├── TableConnection.swift WebSocket link to the table server, with reconnect
│   └── TableMessages.swift   Messages to and from the server
├── ViewModels/
│   └── GameViewModel.swift   Game state: local, or the table's state in table mode
└── Views/
    ├── GameView.swift        Main screen
    ├── RearrangeView.swift   Formation picker / preview sheet
    ├── TableConnectView.swift  Connect to / disconnect from the table
    └── Components/           CupView, FormationView, FormationCard, RerackBanner, Card
tools/
└── mock_table_server.py      Stand-in table server for testing
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
