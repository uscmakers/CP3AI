import Foundation

// Messages exchanged with the table server.
// The format is described in docs/websocket-protocol.md.

/// Full game state sent by the server. Coordinates are in millimeters.
struct TableSnapshot: Decodable, Equatable {
    struct Cup: Decodable, Equatable {
        let id: Int
        /// "active" (in play) or "parked" (hit and moved to a parking slot).
        let status: String
        let xMm: Double
        let yMm: Double
        let slotId: String?
        let formationIndex: Int?

        var isActive: Bool { status == "active" }
    }

    /// A position of the current formation, filled or not.
    struct Spot: Decodable, Equatable {
        let index: Int
        let xMm: Double
        let yMm: Double
        /// The cup in this spot, or the cup that was last there.
        let cupId: Int?
    }

    let version: Int
    let formation: String
    let startFormation: String
    let gameStarted: Bool
    let busy: Bool
    let remaining: Int
    let rearrangementsLeft: Int
    let rearrangeOption: String?
    let cupDiameterMm: Double
    let cups: [Cup]
    /// Optional: without it the app draws only the active cups.
    let spots: [Spot]?
}

enum ServerMessage: Equatable {
    case state(TableSnapshot)
    case error(String)
    /// A message type this version of the app doesn't know.
    case unknown(String)

    private struct Envelope: Decodable {
        let type: String
        let message: String?
    }

    static func decode(_ data: Data) throws -> ServerMessage {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase

        let envelope = try decoder.decode(Envelope.self, from: data)
        switch envelope.type {
        case "state":
            return .state(try decoder.decode(TableSnapshot.self, from: data))
        case "error":
            return .error(envelope.message ?? "The table reported an error.")
        default:
            return .unknown(envelope.type)
        }
    }
}

enum ClientCommand: Equatable {
    /// Manually mark a cup as hit (for a hit the camera missed).
    case cupHit(cupID: Int)
    case rearrange(formationID: String)
    case reset
    case getState

    func encoded() throws -> String {
        var object: [String: Any]
        switch self {
        case .cupHit(let cupID): object = ["type": "cup_hit", "cup_id": cupID]
        case .rearrange(let formationID): object = ["type": "rearrange", "formation": formationID]
        case .reset: object = ["type": "reset"]
        case .getState: object = ["type": "get_state"]
        }
        let data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        return String(decoding: data, as: UTF8.self)
    }
}
