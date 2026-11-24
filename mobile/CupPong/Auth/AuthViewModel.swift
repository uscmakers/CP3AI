// xcode: set sdk=iOS

import Foundation
import Observation
import UIKit
import FirebaseCore
import FirebaseAuth
import GoogleSignIn

/// Who is using the app: nobody yet (show the login screen), a guest, or a Google account.
enum AuthState: Equatable {
    case signedOut
    case guest
    case signedIn(UserProfile)
}

/// The parts of the signed-in account the UI shows.
struct UserProfile: Equatable {
    var name: String?
    var email: String?
    var photoURL: URL?
}

/// Optional Google sign-in through Firebase. Guests stay entirely local.
@Observable
final class AuthViewModel {
    private(set) var state: AuthState = .signedOut
    private(set) var isSigningIn = false
    var errorMessage: String?

    private static let guestKey = "isGuest"
    private var listener: AuthStateDidChangeListenerHandle?

    /// False until a `GoogleService-Info.plist` with a `CLIENT_ID` is added to the app target;
    /// guest mode still works. Firebase only adds `CLIENT_ID` once Google sign-in is enabled.
    let isGoogleSignInAvailable: Bool

    init() {
        guard let path = Bundle.main.path(forResource: "GoogleService-Info", ofType: "plist"),
              let options = FirebaseOptions(contentsOfFile: path),
              let clientID = options.clientID else {
            isGoogleSignInAvailable = false
            state = UserDefaults.standard.bool(forKey: Self.guestKey) ? .guest : .signedOut
            return
        }
        isGoogleSignInAvailable = true

        if FirebaseApp.app() == nil { FirebaseApp.configure(options: options) }
        GIDSignIn.sharedInstance.configuration = GIDConfiguration(clientID: clientID)

        // Firebase restores the last signed-in user on launch and reports changes here.
        listener = Auth.auth().addStateDidChangeListener { [weak self] _, user in
            self?.update(for: user)
        }
    }

    deinit {
        if let listener { Auth.auth().removeStateDidChangeListener(listener) }
    }

    var isGuest: Bool { state == .guest }

    var profile: UserProfile? {
        if case .signedIn(let profile) = state { return profile }
        return nil
    }

    func continueAsGuest() {
        UserDefaults.standard.set(true, forKey: Self.guestKey)
        state = .guest
    }

    @MainActor
    func signInWithGoogle() async {
        guard isGoogleSignInAvailable, let presenter = UIApplication.shared.topViewController else { return }
        isSigningIn = true
        defer { isSigningIn = false }

        do {
            let result = try await GIDSignIn.sharedInstance.signIn(withPresenting: presenter)
            guard let idToken = result.user.idToken?.tokenString else {
                errorMessage = "Google didn't return an ID token. Please try again."
                return
            }
            let credential = GoogleAuthProvider.credential(
                withIDToken: idToken,
                accessToken: result.user.accessToken.tokenString
            )
            try await Auth.auth().signIn(with: credential)
            UserDefaults.standard.set(false, forKey: Self.guestKey)
        } catch let error as GIDSignInError where error.code == .canceled {
            // The user closed the Google sheet; nothing to report.
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func signOut() {
        UserDefaults.standard.set(false, forKey: Self.guestKey)
        if isGoogleSignInAvailable {
            GIDSignIn.sharedInstance.signOut()
            do {
                try Auth.auth().signOut()
            } catch {
                errorMessage = error.localizedDescription
                return
            }
        }
        state = .signedOut
    }

    /// Passes the Google sign-in redirect back to the SDK.
    func handle(_ url: URL) {
        guard isGoogleSignInAvailable else { return }
        GIDSignIn.sharedInstance.handle(url)
    }

    private func update(for user: User?) {
        if let user {
            state = .signedIn(UserProfile(name: user.displayName, email: user.email, photoURL: user.photoURL))
        } else {
            state = UserDefaults.standard.bool(forKey: Self.guestKey) ? .guest : .signedOut
        }
    }
}

private extension UIApplication {
    /// The view controller currently on screen, used to present the Google sign-in sheet.
    var topViewController: UIViewController? {
        let window = connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first { $0.isKeyWindow }
        var top = window?.rootViewController
        while let presented = top?.presentedViewController { top = presented }
        return top
    }
}
