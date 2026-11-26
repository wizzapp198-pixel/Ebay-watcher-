import SwiftUI

struct FoundView: View {
    @EnvironmentObject var state: AppState
    @State private var filter = ""
    @State private var lastSeen = ""

    private var names: [String] {
        var seen = Set<String>()
        return state.found.map(\.watch).filter { seen.insert($0).inserted }
    }

    private var items: [FoundItem] {
        filter.isEmpty ? state.found : state.found.filter { $0.watch == filter }
    }

    var body: some View {
        NavigationStack {
            Group {
                if state.found.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "tray").font(.system(size: 46)).foregroundStyle(.tint)
                        Text("Noch keine Funde").font(.title3.bold())
                        Text("Hier erscheinen alle Angebote, die der Watcher gemeldet hat, auch wenn eine Push-Nachricht nicht ankommt.")
                            .multilineTextAlignment(.center).foregroundStyle(.secondary)
                    }
                    .padding(32)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        if names.count > 1 {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 8) {
                                    FilterChip(title: "Alle", on: filter.isEmpty) { filter = "" }
                                    ForEach(names, id: \.self) { n in
                                        FilterChip(title: n, on: filter == n) { filter = n }
                                    }
                                }
                                .padding(.vertical, 4)
                            }
                            .listRowInsets(EdgeInsets(top: 0, leading: 16, bottom: 0, trailing: 16))
                            .listRowBackground(Color.clear)
                        }
                        Section {
                            ForEach(items) { item in
                                if let url = URL(string: item.url) {
                                    Link(destination: url) {
                                        FoundRow(item: item, isNew: !lastSeen.isEmpty && item.foundAt > lastSeen)
                                    }
                                    .foregroundStyle(.primary)
                                }
                            }
                        } footer: {
                            Text("Antippen öffnet das Angebot. Gespeichert werden die letzten 300 Funde.")
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .refreshable { await state.refreshFound() }
            .navigationTitle("Funde")
            .task {
                lastSeen = state.foundSeen
                await state.refreshFound()
                state.markFoundSeen()
            }
        }
    }
}

private struct FilterChip: View {
    let title: String
    let on: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline)
                .padding(.horizontal, 12).padding(.vertical, 6)
                .foregroundStyle(on ? Color.white : Color.primary)
                .background(Capsule().fill(on ? Color.accentColor : Color(.secondarySystemGroupedBackground)))
        }
        .buttonStyle(.plain)
    }
}

struct FoundRow: View {
    let item: FoundItem
    let isNew: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            AsyncImage(url: item.image.flatMap(URL.init(string:))) { img in
                img.resizable().scaledToFill()
            } placeholder: {
                Color.secondary.opacity(0.12)
            }
            .frame(width: 60, height: 60)
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))

            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    if isNew { Circle().fill(Color.blue).frame(width: 8, height: 8) }
                    Text(item.badge + item.title).font(.subheadline.weight(.semibold)).lineLimit(2)
                }
                Text(item.priceLabel).font(.headline)
                HStack(spacing: 6) {
                    SourceChip(source: item.source)
                    Text("\(item.watch) · \(Fmt.relative(item.date))")
                        .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                }
                if let reasons = item.reasons, !reasons.isEmpty {
                    Text((item.score.map { "Vertrauen \($0) · " } ?? "") + reasons)
                        .font(.caption).foregroundStyle(.secondary).lineLimit(2)
                }
            }
        }
        .padding(.vertical, 4)
    }
}
