import SwiftUI

struct WatchEditView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    let original: Watch?
    @State private var d = WatchDraft()
    @State private var loaded = false

    private let radii = [0, 5, 10, 20, 30, 50, 100, 150, 200]
    private let trusts = [0, 40, 50, 60, 70, 80]

    var body: some View {
        NavigationStack {
            Form {
                Section("Suche") {
                    TextField("Name, z. B. iPhone 13", text: $d.name)
                    TextField("Suchbegriff, z. B. iphone 13 128gb", text: $d.query)
                        .textInputAutocapitalization(.never)
                    Toggle("eBay", isOn: $d.ebay)
                    Toggle("Kleinanzeigen", isOn: $d.kleinanzeigen)
                }

                Section {
                    PriceField(title: "Mindestpreis", text: $d.minPrice)
                    PriceField(title: "Höchstpreis", text: $d.maxPrice)
                    PriceField(title: "Referenzpreis", text: $d.refPrice)
                } header: {
                    Text("Preis")
                } footer: {
                    Text("Referenzpreis = üblicher Marktpreis. Damit erkennt der Watcher Schnäppchen 🔥 und verdächtig billige Angebote.")
                }

                Section("Filter") {
                    Picker("Zustand", selection: $d.condition) {
                        Text("Egal").tag("egal")
                        Text("Neu").tag("neu")
                        Text("Gebraucht").tag("gebraucht")
                    }
                    .pickerStyle(.segmented)
                    if d.ebay {
                        Picker("eBay-Kaufart", selection: $d.buying) {
                            Text("Egal").tag("egal")
                            Text("Sofort-Kaufen").tag("sofort")
                            Text("Auktion").tag("auktion")
                        }
                    }
                    TextField("Ausschlusswörter (Komma-getrennt)", text: $d.exclude)
                        .textInputAutocapitalization(.never)
                }

                if d.kleinanzeigen {
                    Section {
                        Picker("Umkreis", selection: $d.radius) {
                            ForEach(radii, id: \.self) { r in
                                Text(r == 0 ? "Ganz Deutschland" : "\(r) km").tag(r)
                            }
                        }
                        if d.radius != 0 {
                            TextField("PLZ", text: $d.plz).keyboardType(.numberPad)
                        }
                        Toggle("Nur mit Versand", isOn: $d.shippingOnly)
                    } header: {
                        Text("Kleinanzeigen")
                    } footer: {
                        Text("Gräfenhainichen 06773 · Bitterfeld-Wolfen 06749")
                    }
                }

                Section {
                    Picker("Mindest-Vertrauen", selection: $d.minTrust) {
                        ForEach(trusts, id: \.self) { t in
                            Text(t == 0 ? "Standard (60)" : "\(t)").tag(t)
                        }
                    }
                    Toggle("Verdächtige trotzdem senden ⚠️", isOn: $d.sendSuspicious)
                    Toggle("Aktiv", isOn: $d.active)
                } header: {
                    Text("Seriosität")
                } footer: {
                    Text("Angebote unter dem Mindest-Vertrauen werden nicht gemeldet. Betrugs-Hinweise wie WhatsApp oder PayPal Freunde drücken den Score immer darunter.")
                }

                if let original {
                    Section {
                        Button(role: .destructive) {
                            Task {
                                if await state.delete(original) { dismiss() }
                            }
                        } label: {
                            HStack { Spacer(); Text("Suchauftrag löschen"); Spacer() }
                        }
                    }
                }
            }
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle(original == nil ? "Neuer Auftrag" : "Bearbeiten")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") {
                        Task {
                            if await state.save(d, originalName: original?.name) { dismiss() }
                        }
                    }
                    .bold()
                    .disabled(!d.isValid || state.busyText != nil)
                }
            }
            .overlay {
                if let text = state.busyText { BusyOverlay(text: text) }
            }
            .onAppear {
                guard !loaded else { return }
                if let original { d = WatchDraft(original) }
                loaded = true
            }
        }
    }
}

private struct PriceField: View {
    let title: String
    @Binding var text: String

    var body: some View {
        HStack {
            Text(title)
            Spacer()
            TextField("–", text: $text)
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.trailing)
                .frame(maxWidth: 120)
            Text("€").foregroundStyle(.secondary)
        }
    }
}
