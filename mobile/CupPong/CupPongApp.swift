// xcode: set sdk=iOS

import SwiftUI

@main
struct CupPongApp: App {
    @State private var auth = AuthViewModel()

    var body: some Scene {
        WindowGroup {
            Group {
                if auth.state == .signedOut {
                    LoginView()
                } else {
                    GameView()
                }
            }
            .environment(auth)
            .animation(.easeInOut(duration: 0.25), value: auth.state)
            .onOpenURL { auth.handle($0) }
            .preferredColorScheme(.light)
        }
    }
}
