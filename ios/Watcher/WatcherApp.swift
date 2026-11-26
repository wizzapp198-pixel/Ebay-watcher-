import SwiftUI

@main
struct WatcherApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(state)
        }
    }
}

struct RootView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        Group {
            if state.isConfigured {
                TabView {
                    WatchListView()
                        .tabItem { Label("Aufträge", systemImage: "magnifyingglass") }
                    StatusView()
                        .tabItem { Label("Status", systemImage: "waveform.path.ecg") }
                    SettingsView()
                        .tabItem { Label("Einstellungen", systemImage: "gearshape") }
                }
                .task { await state.refresh() }
            } else {
                SetupView()
            }
        }
        .overlay {
            if let text = state.busyText {
                BusyOverlay(text: text)
            }
        }
        .alert(item: $state.alert) { a in
            Alert(title: Text(a.title), message: Text(a.text), dismissButton: .default(Text("OK")))
        }
    }
}

struct BusyOverlay: View {
    let text: String

    var body: some View {
        ZStack {
            Color.black.opacity(0.25).ignoresSafeArea()
            VStack(spacing: 14) {
                ProgressView().controlSize(.large)
                Text(text).font(.headline)
                Text("GitHub übernimmt das gerade, dauert meist unter einer Minute.")
                    .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(24)
            .frame(maxWidth: 280)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
        .transition(.opacity)
    }
}
