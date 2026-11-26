import SwiftUI

struct FoundView: View {
    @EnvironmentObject var state: AppState
    @State private var mode = 0          // 0 = Neu, 1 = Behalten
    @State private var filter = ""

    private func filtered(_ items: [FoundItem]) -> [FoundItem] {
        filter.isEmpty ? items : items.filter { $0.watch == filter }
    }

    private func names(_ items: [FoundItem]) -> [String] {
        var seen = Set<String>()
        return items.map(\.watch).filter { seen.insert($0).inserted }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 10) {
                Picker("", selection: $mode) {
                    Text("Neu (\(state.freshFound.count))").tag(0)
                    Text("Behalten (\(state.keptFound.count))").tag(1)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .onChange(of: mode) { _ in filter = "" }

                let base = mode == 0 ? state.freshFound : state.keptFound
                if names(base).count > 1 {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            FilterChip(title: "Alle", on: filter.isEmpty) { filter = "" }
                            ForEach(names(base), id: \.self) { n in
                                FilterChip(title: n, on: filter == n) { filter = n }
                            }
                        }
                        .padding(.horizontal)
                    }
                }

                if mode == 0 {
                    SwipeDeck(items: filtered(base))
                } else {
                    KeptList(items: filtered(base))
                }

                if state.syncOff {
                    Text("Sortierung nur auf diesem iPhone gespeichert. Für Abgleich mit der Web-App: Token-Recht „Contents → Read and write“.")
                        .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        .padding(.horizontal)
                }
            }
            .padding(.top, 6)
            .navigationTitle("Funde")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { Task { await state.refreshFound() } } label: { Image(systemName: "arrow.clockwise") }
                }
            }
            .task {
                state.loadLocalDecisions()
                await state.refreshFound()
                state.markFoundSeen()
            }
        }
    }
}

// MARK: Karten-Stapel (links = behalten, rechts = löschen)
private struct SwipeDeck: View {
    @EnvironmentObject var state: AppState
    @Environment(\.openURL) private var openURL
    let items: [FoundItem]
    @State private var offset: CGSize = .zero
    @State private var flying = false

    var body: some View {
        if items.isEmpty {
            VStack(spacing: 12) {
                Spacer()
                Image(systemName: "checkmark.seal").font(.system(size: 46)).foregroundStyle(.tint)
                Text("Alles sortiert").font(.title3.bold())
                Text("Neue Angebote erscheinen hier, sobald der Watcher etwas meldet, auch wenn eine Push-Nachricht nicht ankommt.")
                    .multilineTextAlignment(.center).foregroundStyle(.secondary)
                if !state.undoStack.isEmpty {
                    Button { state.undo() } label: { Label("Rückgängig", systemImage: "arrow.uturn.backward") }
                        .buttonStyle(.bordered)
                }
                Spacer()
            }
            .padding(32)
        } else {
            VStack(spacing: 14) {
                ZStack {
                    if items.count > 1 {
                        OfferCard(item: items[1])
                            .scaleEffect(0.95).offset(y: 12).opacity(0.7)
                    }
                    OfferCard(item: items[0], dragX: offset.width)
                        .offset(x: offset.width, y: offset.height * 0.2)
                        .rotationEffect(.degrees(Double(offset.width) / 18))
                        .gesture(
                            DragGesture(minimumDistance: 8)
                                .onChanged { offset = $0.translation }
                                .onEnded { v in
                                    if v.translation.width < -100 { fly(keep: true) }
                                    else if v.translation.width > 100 { fly(keep: false) }
                                    else { withAnimation(.spring()) { offset = .zero } }
                                }
                        )
                        .onTapGesture {
                            if let url = URL(string: items[0].url) { openURL(url) }
                        }
                        .id(items[0].key)
                }
                .padding(.horizontal)

                HStack(spacing: 26) {
                    RoundButton(icon: "checkmark", color: .green, size: 64) { fly(keep: true) }
                    RoundButton(icon: "arrow.uturn.backward", color: .secondary, size: 48) { state.undo() }
                        .disabled(state.undoStack.isEmpty)
                        .opacity(state.undoStack.isEmpty ? 0.35 : 1)
                    RoundButton(icon: "xmark", color: .red, size: 64) { fly(keep: false) }
                }
                Text("Antippen = Angebot öffnen · ← links = behalten · rechts = löschen →\n\(items.count) offen")
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(.bottom, 8)
        }
    }

    private func fly(keep: Bool) {
        guard !flying, let item = items.first else { return }
        flying = true
        withAnimation(.easeOut(duration: 0.25)) {
            offset = CGSize(width: keep ? -600 : 600, height: 0)
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
            state.decide(item, keep: keep)
            offset = .zero
            flying = false
        }
    }
}

private struct OfferCard: View {
    let item: FoundItem
    var dragX: CGFloat = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            AsyncImage(url: item.image.flatMap(URL.init(string:))) { img in
                img.resizable().scaledToFill()
            } placeholder: {
                ZStack {
                    Color.secondary.opacity(0.12)
                    Image(systemName: "bag").font(.largeTitle).foregroundStyle(.secondary)
                }
            }
            .frame(height: 230)
            .frame(maxWidth: .infinity)
            .clipped()

            VStack(alignment: .leading, spacing: 6) {
                Text(item.badge + item.title).font(.title3.bold()).lineLimit(2)
                Text(item.priceLabel).font(.title2.weight(.heavy))
                HStack(spacing: 6) {
                    SourceChip(source: item.source)
                    Text([item.watch, Fmt.relative(item.date), item.location].compactMap { $0 }.joined(separator: " · "))
                        .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                }
                if let reasons = item.reasons, !reasons.isEmpty {
                    Text((item.score.map { "Vertrauen \($0) · " } ?? "") + reasons)
                        .font(.caption).foregroundStyle(.secondary).lineLimit(3)
                }
            }
            .padding(16)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: 430)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .shadow(color: .black.opacity(0.12), radius: 12, y: 4)
        .overlay(alignment: .topLeading) {
            Stamp(text: "BEHALTEN", color: .green, angle: -12).opacity(Double(max(0, min(1, -dragX / 90))))
                .padding(20)
        }
        .overlay(alignment: .topTrailing) {
            Stamp(text: "LÖSCHEN", color: .red, angle: 12).opacity(Double(max(0, min(1, dragX / 90))))
                .padding(20)
        }
    }
}

private struct Stamp: View {
    let text: String
    let color: Color
    let angle: Double

    var body: some View {
        Text(text)
            .font(.title2.weight(.heavy))
            .foregroundStyle(color)
            .padding(.horizontal, 12).padding(.vertical, 4)
            .background(Color.white.opacity(0.85))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(color, lineWidth: 4))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .rotationEffect(.degrees(angle))
    }
}

private struct RoundButton: View {
    let icon: String
    let color: Color
    let size: CGFloat
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: size * 0.4, weight: .bold))
                .foregroundStyle(color)
                .frame(width: size, height: size)
                .background(Circle().fill(Color(.secondarySystemGroupedBackground)))
                .shadow(color: .black.opacity(0.15), radius: 6, y: 3)
        }
        .buttonStyle(.plain)
    }
}

// MARK: Behaltene Angebote
private struct KeptList: View {
    @EnvironmentObject var state: AppState
    let items: [FoundItem]

    var body: some View {
        if items.isEmpty {
            VStack(spacing: 12) {
                Spacer()
                Image(systemName: "star").font(.system(size: 46)).foregroundStyle(.tint)
                Text("Noch nichts behalten").font(.title3.bold())
                Text("Wische unter „Neu“ ein Angebot nach links, um es hier zu speichern.")
                    .multilineTextAlignment(.center).foregroundStyle(.secondary)
                Spacer()
            }
            .padding(32)
        } else {
            List {
                Section {
                    ForEach(items) { item in
                        if let url = URL(string: item.url) {
                            Link(destination: url) { FoundRow(item: item, isNew: false) }
                                .foregroundStyle(.primary)
                                .swipeActions(edge: .trailing) {
                                    Button(role: .destructive) { state.decide(item, keep: false) } label: {
                                        Label("Löschen", systemImage: "trash")
                                    }
                                }
                        }
                    }
                } footer: {
                    Text("Antippen öffnet das Angebot, nach links wischen löscht es.")
                }
            }
            .listStyle(.insetGrouped)
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
            }
        }
        .padding(.vertical, 4)
    }
}
