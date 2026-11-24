import SwiftUI

/// Sheet for connecting to the table server, or going back to local play.
struct TableConnectView: View {
    let table: TableConnection

    @AppStorage("tableAddress") private var address = "unoq.local"
    @Environment(\.dismiss) private var dismiss
    @FocusState private var addressFocused: Bool

    private var url: URL? { TableConnection.url(from: address) }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("unoq.local or 192.168.1.20", text: $address)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($addressFocused)
                        .submitLabel(.go)
                        .onSubmit(connect)
                        .disabled(table.isActive)
                } header: {
                    Text("Table address")
                } footer: {
                    Text("The game server on the Arduino UNO Q. Your phone must be on the same Wi-Fi. Port \(String(TableConnection.defaultPort)) is used unless you add one, like host:9000.")
                }

                if table.isActive {
                    Section("Status") {
                        LabeledContent("Table") {
                            TableStatusLabel(status: table.status)
                        }
                        if let url = table.url {
                            LabeledContent("Address", value: url.absoluteString)
                        }
                    }
                }

                Section {
                    if table.isActive {
                        Button("Disconnect and Play Locally", role: .destructive) {
                            table.disconnect()
                        }
                    } else {
                        Button("Connect", action: connect)
                            .disabled(url == nil)
                    }
                } footer: {
                    if !table.isActive {
                        Text("While connected, the table runs the game: the camera reports hits and the gantry moves the cups. This screen follows along.")
                    }
                }
            }
            .navigationTitle("Table")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .presentationDragIndicator(.visible)
    }

    private func connect() {
        guard let url else { return }
        addressFocused = false
        table.connect(to: url)
    }
}

/// Connection state as a colored dot and short text.
struct TableStatusLabel: View {
    let status: TableConnection.Status

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(text)
        }
        .accessibilityElement(children: .combine)
    }

    private var text: String {
        switch status {
        case .disconnected: "Not connected"
        case .connecting: "Connecting…"
        case .connected: "Connected"
        case .reconnecting(let reason): "\(reason). Retrying…"
        }
    }

    private var color: Color {
        switch status {
        case .disconnected: .secondary
        case .connecting, .reconnecting: .orange
        case .connected: .green
        }
    }
}

#Preview {
    TableConnectView(table: TableConnection())
}
