import SwiftUI

struct SetupView: View {
    @EnvironmentObject var state: AppState
    @State private var owner = ""
    @State private var repo = ""
    @State private var token = ""
    @State private var connecting = false

    private let tokenURL = URL(string: "https://github.com/settings/personal-access-tokens/new")!

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 10) {
                        Image(systemName: "magnifyingglass.circle.fill")
                            .font(.system(size: 44)).foregroundStyle(.tint)
                        Text("Watcher verbinden").font(.title2.bold())
                        Text("Die App steuert deinen Watcher über GitHub. Dafür brauchst du einmalig einen Zugangsschlüssel (Token).")
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 6)
                }

                Section("So erstellst du den Token") {
                    Step(n: 1, text: "Unten auf „Token erstellen“ tippen und bei GitHub anmelden.")
                    Step(n: 2, text: "Name z. B. „Watcher App“, Ablauf: 1 Jahr.")
                    Step(n: 3, text: "Repository access → Only select repositories → \(repo.isEmpty ? "dein Watcher-Repo" : repo).")
                    Step(n: 4, text: "Permissions → Repository: Actions „Read and write“, Contents „Read and write“, Issues „Read and write“.")
                    Step(n: 5, text: "Generate token → kopieren → hier einfügen.")
                    Link(destination: tokenURL) {
                        Label("Token erstellen", systemImage: "arrow.up.right.square")
                    }
                }

                Section("Repository") {
                    TextField("Besitzer", text: $owner)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                    TextField("Repo-Name", text: $repo)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                }

                Section {
                    SecureField("github_pat_…", text: $token)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                } header: {
                    Text("Token")
                } footer: {
                    Text("Wird nur im Schlüsselbund dieses iPhones gespeichert und nur an api.github.com gesendet.")
                }

                Section {
                    Button {
                        connecting = true
                        Task {
                            _ = await state.connect(owner: owner, repo: repo, token: token)
                            connecting = false
                        }
                    } label: {
                        HStack {
                            Spacer()
                            if connecting { ProgressView() } else { Text("Verbinden").bold() }
                            Spacer()
                        }
                    }
                    .disabled(token.trimmed.isEmpty || owner.trimmed.isEmpty || repo.trimmed.isEmpty || connecting)
                }
            }
            .navigationTitle("Einrichtung")
            .onAppear {
                owner = state.owner
                repo = state.repo
            }
        }
    }
}

private struct Step: View {
    let n: Int
    let text: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text("\(n)")
                .font(.caption.bold()).foregroundStyle(.white)
                .frame(width: 20, height: 20)
                .background(Circle().fill(Color.accentColor))
            Text(text).font(.subheadline)
        }
    }
}
