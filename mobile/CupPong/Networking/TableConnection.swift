import Foundation
import Observation

/// WebSocket link to the table server. Keeps the latest game state the server
/// sent and reconnects on its own until `disconnect()` is called.
@MainActor
@Observable
final class TableConnection {
    enum Status: Equatable {
        /// Not using a table: the app plays locally.
        case disconnected
        case connecting
        case connected
        /// The link dropped or couldn't open; retrying.
        case reconnecting(String)
    }

    static let defaultPort = 8765

    private(set) var status: Status = .disconnected
    /// Latest state from the server. Kept while reconnecting so the screen
    /// doesn't jump back to the local game; cleared on `disconnect()`.
    private(set) var snapshot: TableSnapshot?
    /// Last error the server reported for a command, for the UI to show.
    var serverError: String?

    private(set) var url: URL?

    /// True when the user chose to play with a table, connected or not.
    var isActive: Bool { url != nil }

    private let session = URLSession(configuration: .default)
    private var socket: URLSessionWebSocketTask?
    private var runTask: Task<Void, Never>?

    /// Turns what the user typed ("unoq.local", "192.168.1.20:8765",
    /// "ws://host:port/path") into a WebSocket URL.
    static func url(from address: String) -> URL? {
        let trimmed = address.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        let withScheme = trimmed.contains("://") ? trimmed : "ws://\(trimmed)"
        guard var components = URLComponents(string: withScheme),
              let scheme = components.scheme?.lowercased(), scheme == "ws" || scheme == "wss",
              let host = components.host, !host.isEmpty
        else { return nil }

        if components.port == nil { components.port = defaultPort }
        if components.path.isEmpty { components.path = "/" }
        return components.url
    }

    func connect(to url: URL) {
        disconnect()
        self.url = url
        status = .connecting
        runTask = Task { [weak self] in await self?.run(url) }
    }

    func disconnect() {
        url = nil
        runTask?.cancel()
        runTask = nil
        socket?.cancel(with: .goingAway, reason: nil)
        socket = nil
        snapshot = nil
        serverError = nil
        status = .disconnected
    }

    /// Sends a command. Failures show up as `serverError`; the server
    /// answers with a new state or an error message.
    func send(_ command: ClientCommand) {
        guard let socket, status == .connected else {
            serverError = "Not connected to the table."
            return
        }
        Task {
            do {
                try await socket.send(.string(command.encoded()))
            } catch {
                serverError = "Couldn't reach the table: \(error.localizedDescription)"
            }
        }
    }

    // MARK: - Connection loop

    private func run(_ url: URL) async {
        var attempt = 0

        while !Task.isCancelled {
            let socket = session.webSocketTask(with: url)
            self.socket = socket
            socket.resume()

            do {
                // The server sends the state as soon as a client connects,
                // so the first message also confirms the handshake.
                while !Task.isCancelled {
                    let message = try await socket.receive()
                    if status != .connected {
                        status = .connected
                        attempt = 0
                    }
                    handle(message)
                }
            } catch {
                socket.cancel(with: .goingAway, reason: nil)
                guard !Task.isCancelled else { return }
                status = .reconnecting(Self.describe(error))
            }

            // Back off 1, 2, 4, then 5 seconds between attempts.
            attempt += 1
            let delay = min(5.0, pow(2.0, Double(attempt - 1)))
            try? await Task.sleep(for: .seconds(delay))
        }
    }

    private func handle(_ message: URLSessionWebSocketTask.Message) {
        let data: Data
        switch message {
        case .string(let text): data = Data(text.utf8)
        case .data(let bytes): data = bytes
        @unknown default: return
        }

        do {
            switch try ServerMessage.decode(data) {
            case .state(let snapshot): self.snapshot = snapshot
            case .error(let message): serverError = message
            case .unknown: break
            }
        } catch {
            serverError = "The table sent a message the app couldn't read."
        }
    }

    private static func describe(_ error: Error) -> String {
        let nsError = error as NSError
        if nsError.domain == NSURLErrorDomain {
            switch nsError.code {
            case NSURLErrorCannotFindHost, NSURLErrorDNSLookupFailed: return "Table not found"
            case NSURLErrorCannotConnectToHost: return "Table isn't accepting connections"
            case NSURLErrorTimedOut: return "Timed out"
            case NSURLErrorNotConnectedToInternet: return "No network"
            default: break
            }
        }
        return "Connection lost"
    }
}
