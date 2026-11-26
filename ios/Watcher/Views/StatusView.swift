import SwiftUI

struct StatusView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 12) {
                        ActionTile(title: "Jetzt suchen", icon: "bolt.fill", color: .accentColor) {
                            Task { await state.runNow(testPush: false) }
                        }
                        ActionTile(title: "Test-Push", icon: "bell.badge.fill", color: .orange) {
                            Task { await state.runNow(testPush: true) }
                        }
                    }
                    .listRowInsets(EdgeInsets())
                    .listRowBackground(Color.clear)
                }

                Section {
                    if let last = state.runs.first {
                        LabeledContent("Letzter Lauf", value: Fmt.relative(last.date))
                        LabeledContent("Ergebnis") { RunBadge(run: last) }
                    }
                    LabeledContent("Intervall", value: state.isPrivate ? "alle 30 Min." : "laut Workflow")
                    LabeledContent("Aktive Aufträge", value: "\(state.watches.filter(\.isActive).count)")
                } header: {
                    Text("Überblick")
                } footer: {
                    Text("GitHub startet geplante Läufe oft einige Minuten verspätet.")
                }

                Section("Letzte Läufe") {
                    if state.runs.isEmpty {
                        Text("Noch keine Läufe").foregroundStyle(.secondary)
                    }
                    ForEach(state.runs) { run in
                        if let url = URL(string: run.htmlUrl) {
                            Link(destination: url) {
                                HStack {
                                    RunBadge(run: run)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("#\(run.runNumber) · \(run.eventLabel)").font(.subheadline)
                                        Text(Fmt.relative(run.date)).font(.caption).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    Image(systemName: "arrow.up.right").font(.caption).foregroundStyle(.tertiary)
                                }
                            }
                            .foregroundStyle(.primary)
                        }
                    }
                }
            }
            .refreshable { await state.refresh() }
            .navigationTitle("Status")
        }
    }
}

private struct ActionTile: View {
    let title: String
    let icon: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon).font(.title2)
                Text(title).font(.subheadline.bold())
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 18)
            .foregroundStyle(.white)
            .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(color.gradient))
        }
        .buttonStyle(.plain)
    }
}

struct RunBadge: View {
    let run: WorkflowRun

    var body: some View {
        let (icon, color, text): (String, Color, String) = {
            if run.status != "completed" { return ("clock.fill", .blue, "läuft") }
            switch run.conclusion {
            case "success": return ("checkmark.circle.fill", .green, "OK")
            case "failure": return ("xmark.octagon.fill", .red, "Fehler")
            case "cancelled": return ("minus.circle.fill", .secondary, "abgebrochen")
            default: return ("questionmark.circle.fill", .secondary, run.conclusion ?? "?")
            }
        }()
        Label(text, systemImage: icon)
            .font(.caption.bold())
            .foregroundStyle(color)
    }
}
