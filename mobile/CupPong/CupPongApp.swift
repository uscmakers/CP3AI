// xcode: set sdk=iOS

import SwiftUI

@main
struct CupPongApp: App {
    var body: some Scene {
        WindowGroup {
            GameView()
                .preferredColorScheme(.light)
        }
    }
}
