import Foundation

struct APIError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

/// Minimaler GitHub-REST-Client. Spricht nur mit api.github.com.
struct GitHubClient: Sendable {
    let owner: String
    let repo: String
    let token: String

    private var base: String { "https://api.github.com/repos/\(owner)/\(repo)" }

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    private func request(_ path: String, method: String = "GET", body: [String: Any]? = nil,
                         accept: String = "application/vnd.github+json") async throws -> Data {
        guard let url = URL(string: base + path) else { throw APIError(message: "Ungültige Adresse") }
        var req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 25)
        req.httpMethod = method
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.setValue(accept, forHTTPHeaderField: "Accept")
        req.setValue("2022-11-28", forHTTPHeaderField: "X-GitHub-Api-Version")
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: req)
        } catch {
            throw APIError(message: "Keine Verbindung: \(error.localizedDescription)")
        }
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        switch code {
        case 200...299: return data
        case 401: throw APIError(message: "Token ungültig oder abgelaufen.")
        case 403: throw APIError(message: "Keine Berechtigung. Token-Rechte prüfen (Contents, Issues, Actions).")
        case 404: throw APIError(message: "Nicht gefunden. Repo-Name und Token-Zugriff prüfen.")
        default:
            let text = String(data: data, encoding: .utf8) ?? ""
            throw APIError(message: "GitHub-Fehler \(code): \(text.prefix(160))")
        }
    }

    func repoInfo() async throws -> RepoInfo {
        let data = try await request("")
        return try Self.decoder.decode(RepoInfo.self, from: data)
    }

    func watches(branch: String) async throws -> [Watch] {
        let ref = branch.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? branch
        do {
            let data = try await request("/contents/watches.json?ref=\(ref)",
                                         accept: "application/vnd.github.raw+json")
            return try Self.decoder.decode(WatchList.self, from: data).watches
        } catch let e as APIError where e.message.hasPrefix("Nicht gefunden") {
            return []
        }
    }

    func runs() async throws -> [WorkflowRun] {
        let data = try await request("/actions/workflows/watch.yml/runs?per_page=15")
        return try Self.decoder.decode(RunsResponse.self, from: data).workflowRuns
    }

    func createIssue(title: String, body: String) async throws -> Int {
        let data = try await request("/issues", method: "POST", body: ["title": title, "body": body])
        return try Self.decoder.decode(IssueRef.self, from: data).number
    }

    func botReply(issue: Int) async throws -> String? {
        let data = try await request("/issues/\(issue)/comments")
        let comments = try Self.decoder.decode([IssueComment].self, from: data)
        return comments.last(where: { $0.user.login == "github-actions[bot]" })?.body
    }

    func dispatch(branch: String, inputs: [String: String]) async throws {
        _ = try await request("/actions/workflows/watch.yml/dispatches", method: "POST",
                              body: ["ref": branch, "inputs": inputs])
    }
}
