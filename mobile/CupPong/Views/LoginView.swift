import SwiftUI

/// First screen: sign in with Google or skip and play as a guest.
struct LoginView: View {
    @Environment(AuthViewModel.self) private var auth

    var body: some View {
        @Bindable var auth = auth

        VStack(spacing: 24) {
            Spacer()

            VStack(spacing: 12) {
                Image(systemName: "basketball.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(Color.accentColor)
                Text("Cup Pong")
                    .font(.system(size: 40, weight: .semibold, design: .rounded))
                Text("Sign in to save your profile, or jump straight in.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            Spacer()

            VStack(spacing: 12) {
                Button {
                    Task { await auth.signInWithGoogle() }
                } label: {
                    HStack(spacing: 10) {
                        if auth.isSigningIn {
                            ProgressView()
                        } else {
                            Image(systemName: "g.circle.fill")
                        }
                        Text("Sign in with Google")
                    }
                    .font(.body.weight(.semibold))
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .buttonBorderShape(.roundedRectangle(radius: 14))
                .disabled(!auth.isGoogleSignInAvailable || auth.isSigningIn)

                Button {
                    auth.continueAsGuest()
                } label: {
                    Text("Continue as Guest")
                        .font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
                .buttonBorderShape(.roundedRectangle(radius: 14))
                .disabled(auth.isSigningIn)

                if !auth.isGoogleSignInAvailable {
                    Text("Google sign-in isn't set up yet. Add a GoogleService-Info.plist that includes CLIENT_ID to enable it.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.bottom, 24)
        .background(Color(.systemGroupedBackground))
        .alert("Sign-in failed", isPresented: Binding(
            get: { auth.errorMessage != nil },
            set: { if !$0 { auth.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(auth.errorMessage ?? "")
        }
    }
}

#Preview {
    LoginView()
        .environment(AuthViewModel())
}
