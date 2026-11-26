import Foundation

/// Ein Suchauftrag, wie ihn der Bot in watches.json schreibt.
struct Watch: Codable, Identifiable, Equatable {
    var id: String { name.lowercased() }
    var name: String
    var query: String
    var sources: [String]
    var minPrice: Double?
    var maxPrice: Double?
    var refPrice: Double?
    var condition: String?
    var buying: String?
    var plz: String?
    var radius: Int?
    var shippingOnly: Bool?
    var exclude: [String]?
    var minTrust: Int?
    var sendSuspicious: Bool?
    var active: Bool?
    var aiHint: String?

    var isActive: Bool { active ?? true }

    var sourcesLabel: String {
        sources.map { $0 == "ebay" ? "eBay" : "Kleinanzeigen" }.joined(separator: " · ")
    }

    var priceLabel: String {
        switch (minPrice, maxPrice) {
        case let (lo?, hi?): return "\(Fmt.euro(lo)) – \(Fmt.euro(hi))"
        case let (lo?, nil): return "ab \(Fmt.euro(lo))"
        case let (nil, hi?): return "bis \(Fmt.euro(hi))"
        default: return "jeder Preis"
        }
    }
}

struct WatchList: Codable {
    var watches: [Watch]
}

/// Bearbeitbare Formular-Werte (alles als Text, der Bot prüft und wandelt um).
struct WatchDraft: Equatable {
    var name = ""
    var query = ""
    var ebay = true
    var kleinanzeigen = true
    var minPrice = ""
    var maxPrice = ""
    var refPrice = ""
    var condition = "egal"        // egal | neu | gebraucht
    var buying = "egal"           // egal | sofort | auktion
    var plz = "06773"
    var radius = 50               // 0 = ganz Deutschland
    var shippingOnly = false
    var exclude = ""
    var minTrust = 0              // 0 = Standard
    var sendSuspicious = false
    var active = true
    var aiHint = ""

    init() {}

    init(_ w: Watch) {
        name = w.name
        query = w.query
        ebay = w.sources.contains("ebay")
        kleinanzeigen = w.sources.contains("kleinanzeigen")
        minPrice = Fmt.plain(w.minPrice)
        maxPrice = Fmt.plain(w.maxPrice)
        refPrice = Fmt.plain(w.refPrice)
        condition = w.condition ?? "egal"
        buying = w.buying ?? "egal"
        plz = w.plz ?? ""
        radius = w.plz == nil ? 0 : (w.radius ?? 0)
        shippingOnly = w.shippingOnly ?? false
        exclude = (w.exclude ?? []).joined(separator: ", ")
        minTrust = w.minTrust ?? 0
        sendSuspicious = w.sendSuspicious ?? false
        active = w.isActive
        aiHint = w.aiHint ?? ""
    }

    var isValid: Bool {
        !name.trimmed.isEmpty && !query.trimmed.isEmpty && (ebay || kleinanzeigen)
    }

    /// Text im Format des GitHub-Issue-Formulars (wird vom Bot ausgewertet).
    var issueBody: String {
        func field(_ label: String, _ value: String) -> String {
            let v = value.trimmed
            return "### \(label)\n\n\(v.isEmpty ? "_No response_" : v)\n\n"
        }
        func box(_ on: Bool, _ label: String) -> String { "- [\(on ? "X" : " ")] \(label)" }
        let radiusText = radius == 0 ? "ganz Deutschland" : "\(radius) km"
        let buyText = buying == "sofort" ? "Sofort-Kaufen" : buying == "auktion" ? "Auktion" : "egal"
        let trustText = minTrust == 0 ? "Standard (60)" : "\(minTrust)"
        var s = ""
        s += field("Name des Suchauftrags", name)
        s += field("Suchbegriff", query)
        s += "### Quellen\n\n\(box(ebay, "eBay"))\n\(box(kleinanzeigen, "Kleinanzeigen"))\n\n"
        s += field("Mindestpreis (€)", minPrice)
        s += field("Höchstpreis (€)", maxPrice)
        s += field("Referenzpreis (€)", refPrice)
        s += field("Zustand", condition)
        s += field("Kaufart (nur eBay)", buyText)
        s += field("PLZ (nur Kleinanzeigen)", radius == 0 ? "" : plz)
        s += field("Umkreis (nur Kleinanzeigen)", radiusText)
        s += "### Versand\n\n\(box(shippingOnly, "Nur Angebote mit Versand (Kleinanzeigen)"))\n\n"
        s += field("Ausschlusswörter", exclude)
        s += field("Genauer Wunsch (für die KI-Prüfung)",
                   aiHint.components(separatedBy: .whitespacesAndNewlines).filter { !$0.isEmpty }.joined(separator: " "))
        s += field("Mindest-Vertrauen", trustText)
        s += "### Optionen\n\n\(box(sendSuspicious, "Verdächtige Angebote trotzdem senden (⚠️)"))\n\(box(!active, "Suchauftrag pausieren"))\n"
        return s
    }
}

/// Ein gemeldetes Angebot (found.json auf Branch watcher-data).
struct FoundItem: Decodable, Identifiable {
    var id: String { key }
    let key: String
    let source: String
    let title: String
    let price: Double?
    let priceNegotiable: Bool?
    let url: String
    let image: String?
    let location: String?
    let watch: String
    let score: Int?
    let reasons: String?
    let kind: String?
    let foundAt: String

    var date: Date? { ISO8601DateFormatter().date(from: foundAt) }

    var priceLabel: String {
        guard let price else { return "Preis k. A." }
        return Fmt.euro(price) + ((priceNegotiable ?? false) ? " VB" : "")
    }

    var badge: String {
        switch kind {
        case "bargain": return "🔥 "
        case "suspicious": return "⚠️ "
        default: return ""
        }
    }
}

struct FoundList: Decodable {
    let found: [FoundItem]
}

/// Sortier-Entscheidungen (decisions.json auf Branch watcher-data), Wert = Zeitpunkt in ms.
struct Decisions: Codable, Equatable {
    var kept: [String: Double] = [:]
    var deleted: [String: Double] = [:]

    func merged(with other: Decisions) -> Decisions {
        var out = Decisions(kept: kept.merging(other.kept) { max($0, $1) },
                            deleted: deleted.merging(other.deleted) { max($0, $1) })
        for (k, t) in out.kept {
            if let d = out.deleted[k] {
                if d > t { out.kept[k] = nil } else { out.deleted[k] = nil }
            }
        }
        return out
    }
}

struct ContentFile: Decodable {
    let sha: String
    let content: String
}

struct ContentPutResponse: Decodable {
    struct C: Decodable { let sha: String }
    let content: C
}

struct RepoInfo: Decodable {
    let defaultBranch: String
    let isPrivate: Bool
    let htmlUrl: String

    enum CodingKeys: String, CodingKey {
        case defaultBranch, htmlUrl
        case isPrivate = "private"
    }
}

struct WorkflowRun: Decodable, Identifiable {
    let id: Int
    let runNumber: Int
    let status: String
    let conclusion: String?
    let event: String
    let createdAt: String
    let htmlUrl: String

    var date: Date? { ISO8601DateFormatter().date(from: createdAt) }

    var eventLabel: String {
        switch event {
        case "schedule": return "Zeitplan"
        case "workflow_dispatch": return "Manuell"
        default: return event
        }
    }
}

struct RunsResponse: Decodable {
    let workflowRuns: [WorkflowRun]
}

struct IssueRef: Decodable {
    let number: Int
}

struct IssueComment: Decodable {
    struct User: Decodable { let login: String }
    let body: String
    let user: User
}

enum Fmt {
    static func euro(_ v: Double) -> String {
        let f = NumberFormatter()
        f.locale = Locale(identifier: "de_DE")
        f.numberStyle = .currency
        f.currencyCode = "EUR"
        f.maximumFractionDigits = v == v.rounded() ? 0 : 2
        return f.string(from: NSNumber(value: v)) ?? "\(v) €"
    }

    static func plain(_ v: Double?) -> String {
        guard let v else { return "" }
        if v == v.rounded() { return String(Int(v)) }
        return String(v).replacingOccurrences(of: ".", with: ",")
    }

    static func relative(_ d: Date?) -> String {
        guard let d else { return "" }
        let f = RelativeDateTimeFormatter()
        f.locale = Locale(identifier: "de_DE")
        f.unitsStyle = .full
        return f.localizedString(for: d, relativeTo: Date())
    }
}

extension String {
    var trimmed: String { trimmingCharacters(in: .whitespacesAndNewlines) }
}
