import SwiftUI

struct WatchListView: View {
    @EnvironmentObject var state: AppState
    @State private var editing: EditTarget?
    @State private var confirmDelete: Watch?

    struct EditTarget: Identifiable {
        let id = UUID()
        let watch: Watch?
    }

    var body: some View {
        NavigationStack {
            Group {
                if state.watches.isEmpty && !state.loading {
                    EmptyState { editing = EditTarget(watch: nil) }
                } else {
                    List {
                        ForEach(state.watches) { w in
                            Button { editing = EditTarget(watch: w) } label: { WatchRow(watch: w) }
                                .buttonStyle(.plain)
                                .swipeActions(edge: .trailing) {
                                    Button(role: .destructive) { confirmDelete = w } label: {
                                        Label("Löschen", systemImage: "trash")
                                    }
                                    Button { Task { await state.toggleActive(w) } } label: {
                                        Label(w.isActive ? "Pause" : "Start",
                                              systemImage: w.isActive ? "pause.fill" : "play.fill")
                                    }
                                    .tint(w.isActive ? .orange : .green)
                                }
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .refreshable { await state.refresh() }
            .navigationTitle("Suchaufträge")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { editing = EditTarget(watch: nil) } label: {
                        Image(systemName: "plus.circle.fill").font(.title3)
                    }
                }
                ToolbarItem(placement: .navigationBarLeading) {
                    if state.loading { ProgressView() }
                }
            }
            .sheet(item: $editing) { target in
                WatchEditView(original: target.watch)
                    .environmentObject(state)
            }
            .confirmationDialog("Suchauftrag löschen?", isPresented: Binding(
                get: { confirmDelete != nil }, set: { if !$0 { confirmDelete = nil } }
            ), titleVisibility: .visible) {
                Button("Löschen", role: .destructive) {
                    if let w = confirmDelete { Task { _ = await state.delete(w) } }
                }
            } message: {
                Text(confirmDelete?.name ?? "")
            }
        }
    }
}

struct WatchRow: View {
    let watch: Watch

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(watch.isActive ? Color.green : Color.secondary.opacity(0.4))
                .frame(width: 10, height: 10)
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(watch.name).font(.headline)
                    if !watch.isActive {
                        Text("pausiert").font(.caption2.bold())
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(Capsule().fill(Color.secondary.opacity(0.15)))
                    }
                }
                Text(watch.query).font(.subheadline).foregroundStyle(.secondary)
                HStack(spacing: 6) {
                    ForEach(watch.sources, id: \.self) { s in
                        SourceChip(source: s)
                    }
                    Text(watch.priceLabel).font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer()
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }
}

struct SourceChip: View {
    let source: String

    var body: some View {
        let isEbay = source == "ebay"
        Text(isEbay ? "eBay" : "Kleinanzeigen")
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 7).padding(.vertical, 2)
            .foregroundStyle(isEbay ? Color.blue : Color.green)
            .background(Capsule().fill((isEbay ? Color.blue : Color.green).opacity(0.12)))
    }
}

private struct EmptyState: View {
    let add: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "binoculars").font(.system(size: 48)).foregroundStyle(.tint)
            Text("Noch keine Suchaufträge").font(.title3.bold())
            Text("Lege deinen ersten Auftrag an. Beim ersten Lauf werden vorhandene Angebote nur gemerkt, danach meldet der Watcher nur neue.")
                .multilineTextAlignment(.center).foregroundStyle(.secondary)
            Button(action: add) {
                Label("Suchauftrag anlegen", systemImage: "plus").bold()
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
