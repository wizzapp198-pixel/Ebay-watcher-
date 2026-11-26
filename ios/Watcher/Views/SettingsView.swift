import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var state: AppState
    @State private var confirmSignOut = false

    private var repoBase: String { "https://github.com/\(state.owner)/\(state.repo)" }

    var body: some View {
        NavigationStack {
            List {
                Section("Verbunden mit") {
                    LabeledContent("Repository", value: "\(state.owner)/\(state.repo)")
                    LabeledContent("Branch", value: state.branch.isEmpty ? "–" : state.branch)
                    LabeledContent("Sichtbarkeit", value: state.isPrivate ? "privat" : "öffentlich")
                }

                Section("Links") {
                    LinkRow(title: "Repository öffnen", url: repoBase)
                    LinkRow(title: "Actions (Läufe & Logs)", url: repoBase + "/actions")
                    LinkRow(title: "Secrets bearbeiten", url: repoBase + "/settings/secrets/actions")
                    LinkRow(title: "Anleitung (README)", url: repoBase + "#readme")
                }

                Section {
                    Button("Token entfernen / neu verbinden", role: .destructive) { confirmSignOut = true }
                } footer: {
                    Text("Watcher 1.0 · Die App speichert nur den Token (Schlüsselbund) und den Repo-Namen.")
                }
            }
            .navigationTitle("Einstellungen")
            .confirmationDialog("Token vom iPhone entfernen?", isPresented: $confirmSignOut, titleVisibility: .visible) {
                Button("Entfernen", role: .destructive) { state.signOut() }
            }
        }
    }
}

private struct LinkRow: View {
    let title: String
    let url: String

    var body: some View {
        if let u = URL(string: url) {
            Link(destination: u) {
                HStack {
                    Text(title)
                    Spacer()
                    Image(systemName: "arrow.up.right").font(.caption).foregroundStyle(.tertiary)
                }
            }
            .foregroundStyle(.primary)
        }
    }
}
