import SwiftUI

/// Toolbar avatar: the Google profile photo when signed in, a default silhouette otherwise.
/// Tapping it opens account actions.
struct ProfileButton: View {
    @Environment(AuthViewModel.self) private var auth

    var body: some View {
        Menu {
            if let profile = auth.profile {
                Section {
                    Text(profile.name ?? "Signed in")
                    if let email = profile.email {
                        Text(email)
                    }
                }
                Button("Sign Out", systemImage: "rectangle.portrait.and.arrow.right", role: .destructive) {
                    auth.signOut()
                }
            } else {
                Section("Playing as Guest") {
                    if auth.isGoogleSignInAvailable {
                        Button("Sign in with Google", systemImage: "person.crop.circle.badge.plus") {
                            Task { await auth.signInWithGoogle() }
                        }
                    }
                    Button("Exit Guest Mode", systemImage: "rectangle.portrait.and.arrow.right") {
                        auth.signOut()
                    }
                }
            }
        } label: {
            ProfileAvatar(photoURL: auth.profile?.photoURL)
                .frame(width: 32, height: 32)
        }
        .accessibilityLabel("Profile")
    }
}

/// Circular profile picture that falls back to a default avatar.
struct ProfileAvatar: View {
    var photoURL: URL?

    var body: some View {
        Group {
            if let photoURL {
                AsyncImage(url: photoURL) { phase in
                    if let image = phase.image {
                        image.resizable().scaledToFill()
                    } else {
                        placeholder
                    }
                }
            } else {
                placeholder
            }
        }
        .clipShape(Circle())
        .overlay(Circle().strokeBorder(Color.primary.opacity(0.07), lineWidth: 1))
    }

    private var placeholder: some View {
        Image(systemName: "person.crop.circle.fill")
            .resizable()
            .scaledToFit()
            .foregroundStyle(.secondary)
    }
}

#Preview {
    HStack(spacing: 16) {
        ProfileAvatar(photoURL: nil)
        ProfileAvatar(photoURL: URL(string: "https://example.com/missing.png"))
    }
    .frame(height: 32)
}
