import Foundation
import SwiftUI

@MainActor
final class AppState: ObservableObject {
    @AppStorage("owner") var owner = "wizzapp198-pixel"
    @AppStorage("repo") var repo = "Ebay-watcher-"
    @Published var token: String = Keychain.load("token") ?? ""

    @Published var watches: [Watch] = []
    @Published var runs: [WorkflowRun] = []
    @Published var found: [FoundItem] = []
    @AppStorage("foundSeen") var foundSeen = ""
    @Published var branch = ""
    @Published var repoURL = ""
    @Published var isPrivate = false
    @Published var loading = false
    @Published var busyText: String?
    @Published var alert: AlertMessage?

    struct AlertMessage: Identifiable {
        let id = UUID()
        let title: String
        let text: String
    }

    var isConfigured: Bool { !token.isEmpty }
    var client: GitHubClient { GitHubClient(owner: owner.trimmed, repo: repo.trimmed, token: token) }

    // MARK: Einrichtung
    func connect(owner: String, repo: String, token: String) async -> Bool {
        let c = GitHubClient(owner: owner.trimmed, repo: repo.trimmed, token: token.trimmed)
        do {
            let info = try await c.repoInfo()
            self.owner = owner.trimmed
            self.repo = repo.trimmed
            self.token = token.trimmed
            Keychain.save(self.token, key: "token")
            branch = info.defaultBranch
            await refresh()
            return true
        } catch {
            show("Verbindung fehlgeschlagen", error)
            return false
        }
    }

    func signOut() {
        Keychain.delete("token")
        token = ""
        watches = []
        runs = []
        branch = ""
    }

    // MARK: Laden
    func refresh() async {
        guard isConfigured else { return }
        loading = true
        defer { loading = false }
        do {
            let info = try await client.repoInfo()
            branch = info.defaultBranch
            repoURL = info.htmlUrl
            isPrivate = info.isPrivate
            let c = client
            let b = branch
            async let w = c.watches(branch: b)
            async let r = c.runs()
            async let f = c.found()
            watches = try await w
            runs = (try? await r) ?? []
            found = (try? await f) ?? found
        } catch {
            show("Laden fehlgeschlagen", error)
        }
    }

    func refreshFound() async {
        guard isConfigured else { return }
        do { found = try await client.found() } catch { show("Funde laden fehlgeschlagen", error) }
    }

    func markFoundSeen() {
        if let newest = found.first?.foundAt { foundSeen = newest }
    }

    func refreshRuns() async {
        guard isConfigured else { return }
        if let r = try? await client.runs() { runs = r }
    }

    // MARK: Suchaufträge
    /// Legt an/ändert über das Issue-Formular. Gibt true bei Erfolg zurück.
    func save(_ draft: WatchDraft, originalName: String?) async -> Bool {
        let ok = await submit(title: "[Suchauftrag] \(draft.name.trimmed)", body: draft.issueBody,
                              busy: "Wird übernommen …")
        if ok, let old = originalName, old.lowercased() != draft.name.trimmed.lowercased() {
            _ = await submit(title: "[Löschen] \(old)", body: "### Name des Suchauftrags\n\n\(old)\n",
                             busy: "Alter Name wird entfernt …", silent: true)
        }
        if ok { await reloadWatchesSoon() }
        return ok
    }

    func delete(_ watch: Watch) async -> Bool {
        let ok = await submit(title: "[Löschen] \(watch.name)",
                              body: "### Name des Suchauftrags\n\n\(watch.name)\n", busy: "Wird gelöscht …")
        if ok {
            watches.removeAll { $0.id == watch.id }
            await reloadWatchesSoon()
        }
        return ok
    }

    func toggleActive(_ watch: Watch) async {
        var d = WatchDraft(watch)
        d.active.toggle()
        _ = await save(d, originalName: nil)
    }

    private func submit(title: String, body: String, busy: String, silent: Bool = false) async -> Bool {
        busyText = busy
        defer { busyText = nil }
        do {
            let number = try await client.createIssue(title: title, body: body)
            // Auf die Antwort des Bots warten (meist 15–40 s)
            for _ in 0..<40 {
                try await Task.sleep(nanoseconds: 4_000_000_000)
                if let reply = try await client.botReply(issue: number) {
                    let ok = !reply.hasPrefix("❌")
                    if !silent || !ok {
                        alert = AlertMessage(title: ok ? "Erledigt" : "Nicht übernommen",
                                             text: Self.clean(reply))
                    }
                    return ok
                }
            }
            alert = AlertMessage(title: "Noch in Bearbeitung",
                                 text: "Der Bot hat noch nicht geantwortet. Bitte gleich aktualisieren.")
            return false
        } catch {
            show("Fehler", error)
            return false
        }
    }

    private func reloadWatchesSoon() async {
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        if let w = try? await client.watches(branch: branch) { watches = w }
    }

    /// Kürzt die Bot-Antwort für die Anzeige (YAML-Block entfernen, Markdown vereinfachen).
    static func clean(_ text: String) -> String {
        var t = text
        if let r = t.range(of: "```") { t = String(t[..<r.lowerBound]) }
        return t.replacingOccurrences(of: "**", with: "").trimmed
    }

    // MARK: Aktionen
    func runNow(testPush: Bool) async {
        busyText = testPush ? "Test-Push wird gestartet …" : "Suche wird gestartet …"
        defer { busyText = nil }
        do {
            if branch.isEmpty { branch = try await client.repoInfo().defaultBranch }
            try await client.dispatch(branch: branch, inputs: testPush ? ["test_push": "true"] : [:])
            alert = AlertMessage(title: "Gestartet",
                                 text: testPush ? "In ca. 1 Minute sollte der Test-Push ankommen."
                                                : "Der Lauf startet in wenigen Sekunden.")
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            await refreshRuns()
        } catch {
            show("Start fehlgeschlagen", error)
        }
    }

    private func show(_ title: String, _ error: Error) {
        alert = AlertMessage(title: title, text: error.localizedDescription)
    }
}
