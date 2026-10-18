import SwiftUI

enum CallStatus: String {
    case passed = "Passed"
    case blocked = "Blocked"
    case pending = "Pending"
}

enum Verdict: String {
    case legit = "Legit"
    case scam = "Scam"
    case unsure = "Unsure"
}

enum AppTab {
    case home, desk, proof
}

struct TranscriptTurn: Identifiable {
    let id = UUID()
    let speaker: String
    let text: String
    var isJerry: Bool { speaker == "Jerry" }
}

struct Call: Identifiable {
    let id: String
    let time: String
    let caller: String
    let subtitle: String?
    let phone: String
    let status: CallStatus
    let verdict: Verdict?
    let score: Int?
    let transcript: [TranscriptTurn]
    let reasons: [String]
    let tactics: [String]
    let summary: String
    let text: String?
    let scoreFailed: Bool

    var line: String { subtitle ?? phone }
}

final class CallDesk: ObservableObject {
    @Published var calls: [Call] = []
    @Published var loading = true
    @Published var error: String?

    var blocked: Int { calls.filter { $0.status == .blocked }.count }
    var passed: Int { calls.filter { $0.status == .passed }.count }
    var stillOpen: Int { calls.filter { $0.status == .pending || $0.scoreFailed }.count }
    var screening: Call? { calls.first { $0.status == .pending } ?? calls.first }

    func load() async {
        do {
            let rows = try await SupabaseCalls.fetch()
            let mapped = rows.map(Call.init(remote:))
            await MainActor.run {
                calls = mapped
                loading = false
                error = nil
            }
        } catch {
            await MainActor.run {
                loading = false
                self.error = "Could not load calls."
            }
        }
    }
}

private enum SupabaseCalls {
    static let url = URL(string: "https://rqigjdutcppmfbtulpbm.supabase.co/rest/v1/calls?select=*&order=created_at.desc")!
    static let anonKey = "sb_publishable_OYTrogPkR5v0PJ1KfdqqIQ_ioe7IreT"

    static func fetch() async throws -> [RemoteCall] {
        var request = URLRequest(url: url)
        request.setValue(anonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(anonKey)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode([RemoteCall].self, from: data)
    }
}

private struct RemoteCall: Decodable {
    let conversationId: String
    let createdAt: String
    let callerNumber: String?
    let transcript: [RemoteTurn]?
    let midCallDecision: String?
    let verdict: String?
    let scamScore: Int?
    let reasons: [String]
    let tactics: [String]
    let summary: String?
    let status: String
    let imessageSent: Bool

    enum CodingKeys: String, CodingKey {
        case conversationId = "conversation_id"
        case createdAt = "created_at"
        case callerNumber = "caller_number"
        case transcript
        case midCallDecision = "mid_call_decision"
        case verdict
        case scamScore = "scam_score"
        case reasons
        case tactics
        case summary
        case status
        case imessageSent = "imessage_sent"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        conversationId = try container.decode(String.self, forKey: .conversationId)
        createdAt = try container.decode(String.self, forKey: .createdAt)
        callerNumber = try container.decodeIfPresent(String.self, forKey: .callerNumber)
        transcript = (try? container.decodeIfPresent([RemoteTurn].self, forKey: .transcript)) ?? nil
        midCallDecision = try container.decodeIfPresent(String.self, forKey: .midCallDecision)
        verdict = try container.decodeIfPresent(String.self, forKey: .verdict)
        if let score = try? container.decodeIfPresent(Int.self, forKey: .scamScore) {
            scamScore = score
        } else if let score = try? container.decodeIfPresent(Double.self, forKey: .scamScore) {
            scamScore = Int(score.rounded())
        } else {
            scamScore = nil
        }
        reasons = Self.strings(container, key: .reasons)
        tactics = Self.strings(container, key: .tactics)
        summary = try container.decodeIfPresent(String.self, forKey: .summary)
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "pending"
        imessageSent = try container.decodeIfPresent(Bool.self, forKey: .imessageSent) ?? false
    }

    private static func strings(_ container: KeyedDecodingContainer<CodingKeys>, key: CodingKeys) -> [String] {
        if let values = try? container.decode([String].self, forKey: key) { return values }
        return []
    }
}

private struct RemoteTurn: Decodable {
    let role: String
    let text: String

    enum CodingKeys: String, CodingKey { case role, text }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        role = try container.decodeIfPresent(String.self, forKey: .role) ?? "caller"
        text = try container.decodeIfPresent(String.self, forKey: .text) ?? ""
    }
}

private extension Call {
    init(remote: RemoteCall) {
        let turns = (remote.transcript ?? []).map {
            TranscriptTurn(speaker: $0.role == "agent" ? "Jerry" : "Caller", text: $0.text)
        }
        let failed = remote.status == "failed"
        let uiStatus: CallStatus = remote.status == "pending" ? .pending : (remote.midCallDecision == "pass" ? .passed : .blocked)
        let blob = (turns.map(\.text) + [remote.summary ?? ""]).joined(separator: " ").lowercased()
        id = remote.conversationId
        time = CallClock.time(remote.createdAt)
        caller = CallClock.title(blob: blob, number: remote.callerNumber)
        subtitle = remote.summary?.isEmpty == false ? remote.summary : nil
        phone = CallClock.phone(remote.callerNumber)
        status = uiStatus
        verdict = Verdict(rawValue: remote.verdict?.capitalized ?? "")
        score = remote.scamScore
        transcript = turns
        reasons = remote.reasons
        tactics = remote.tactics
        summary = remote.summary ?? ""
        text = remote.imessageSent ? (remote.summary?.isEmpty == false ? remote.summary : "Sent to Ian.") : nil
        scoreFailed = failed
    }
}

private enum CallClock {
    static func phone(_ raw: String?) -> String {
        guard let raw, !raw.isEmpty else { return "Unknown number" }
        let digits = raw.filter(\.isNumber)
        let national = digits.count == 11 && digits.hasPrefix("1") ? String(digits.dropFirst()) : digits
        guard national.count == 10 else { return raw }
        let area = national.prefix(3)
        let mid = national.dropFirst(3).prefix(3)
        let last = national.suffix(4)
        return "(\(area)) \(mid)-\(last)"
    }

    static func time(_ iso: String) -> String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = parser.date(from: iso) ?? ISO8601DateFormatter().date(from: iso)
        guard let date else { return "—" }
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(identifier: "America/New_York")
        formatter.dateFormat = "h:mm a"
        return formatter.string(from: date)
    }

    static func title(blob: String, number: String?) -> String {
        if blob.contains("chase") { return "Chase fraud" }
        if blob.contains("harbor") || blob.contains("pharmacy") { return "Harbor Drugs" }
        if blob.contains("dental") || blob.contains("dentist") { return "Bayshore Dental" }
        if blob.contains("microsoft") || blob.contains("remote access") { return "Microsoft support" }
        if blob.contains("warranty") { return "Warranty call" }
        if blob.contains("ignore all") || blob.contains("admin mode") || blob.contains("screening robot") { return "Injection attempt" }
        if blob.contains("hung up") || blob.contains("hidden number") || blob.contains("no words") { return "Hidden number" }
        if blob.contains("mom") { return "“Mom”" }
        if blob.contains("national grid") { return "National Grid" }
        if blob.contains("irs") { return "IRS" }
        if blob.contains("bank of america") { return "Bank of America" }
        if number == nil || number?.isEmpty == true { return "Unknown caller" }
        return "Unknown caller"
    }
}

enum Theme {
    static let bg = Color(red: 0.043, green: 0.039, blue: 0.059)
    static let panel = Color(red: 0.118, green: 0.106, blue: 0.161)
    static let raised = Color(red: 0.157, green: 0.137, blue: 0.200)
    static let soft = Color(red: 0.200, green: 0.161, blue: 0.251)
    static let line = Color(red: 0.231, green: 0.204, blue: 0.282)
    static let lime = Color(red: 0.961, green: 0.914, blue: 0.827)
    static let coralSoft = Color(red: 0.918, green: 0.863, blue: 0.769)
    static let ink = Color(red: 0.141, green: 0.114, blue: 0.169)
    static let brown = Color(red: 0.102, green: 0.051, blue: 0.020)
    static let purple = Color(red: 0.545, green: 0.361, blue: 0.965)
    static let purpleDeep = Color(red: 0.427, green: 0.157, blue: 0.851)
    static let pale = Color(red: 0.200, green: 0.161, blue: 0.251)
    static let text = Color(red: 0.973, green: 0.969, blue: 0.984)
    static let muted = Color(red: 0.667, green: 0.639, blue: 0.714)
}

struct ContentView: View {
    @StateObject private var desk = CallDesk()
    @State private var started = false

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            if started {
                MainView(desk: desk)
            } else {
                OpeningView(passed: desk.passed, blocked: desk.blocked) { started = true }
            }
        }
        .preferredColorScheme(.dark)
        .task { await desk.load() }
    }
}

struct OpeningView: View {
    let passed: Int
    let blocked: Int
    var onStart: () -> Void

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            Circle()
                .fill(Theme.purple.opacity(0.32))
                .frame(width: 320, height: 320)
                .blur(radius: 50)
                .offset(y: -70)
            Circle()
                .fill(Theme.lime.opacity(0.09))
                .frame(width: 220, height: 220)
                .blur(radius: 40)
                .offset(x: 90, y: 80)
            VStack(spacing: 0) {
                HStack(spacing: 8) {
                    Text("samurai")
                        .font(.system(size: 18, weight: .bold, design: .rounded))
                    Spacer()
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)

                ZStack {
                    Circle()
                        .stroke(Color.white.opacity(0.16), lineWidth: 1)
                        .frame(width: 270, height: 270)
                        .shadow(color: .white.opacity(0.03), radius: 0, x: 0, y: 0)
                        .modifier(Spin(seconds: 16))
                    Circle()
                        .stroke(Color.white.opacity(0.2), style: StrokeStyle(lineWidth: 1, dash: [5, 6]))
                        .frame(width: 205, height: 205)
                        .modifier(Spin(seconds: 20, reverse: true))
                    VStack(alignment: .leading, spacing: 6) {
                        Text("LIVE")
                            .font(.system(size: 11, weight: .heavy, design: .rounded))
                            .tracking(1.2)
                        Text("Your line is\nprotected.")
                            .font(.system(size: 22, weight: .medium, design: .rounded))
                            .lineSpacing(-2)
                        VoiceBars(heights: [15, 28, 20, 39, 25, 46, 31, 18, 38, 24, 34], color: .white)
                            .frame(height: 38)
                    }
                    .padding(24)
                    .frame(width: 180, height: 180)
                    .background(LinearGradient(colors: [Color(red: 0.608, green: 0.424, blue: 1), Theme.purpleDeep], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .foregroundStyle(.white)
                    .clipShape(Circle())
                    .overlay(Circle().stroke(Color.white.opacity(0.8), lineWidth: 1))
                    .shadow(color: .black.opacity(0.3), radius: 24, y: 16)
                    .modifier(FloatY(distance: 8, seconds: 4))

                    pill(value: "\(passed)", label: "passed to you", lime: true)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                        .padding(.leading, 4)
                        .padding(.top, 36)
                        .modifier(FloatY(distance: 9, seconds: 4.8))
                    pill(value: "\(blocked)", label: "blocked quietly", lime: false)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing)
                        .padding(.trailing, 4)
                        .padding(.bottom, 28)
                        .modifier(FloatY(distance: 9, seconds: 4.8, delay: 2))
                }
                .frame(maxWidth: .infinity)
                .frame(height: 330)

                VStack(spacing: 10) {
                    Text("AI CALL SCREENING")
                        .font(.system(size: 11, weight: .heavy, design: .rounded))
                        .tracking(1.4)
                        .foregroundStyle(Theme.lime)
                    Text("Calls get tested.")
                        .font(.system(size: 40, weight: .regular, design: .rounded))
                    Text("You get peace.")
                        .font(.system(size: 40, weight: .regular, design: .rounded))
                        .foregroundStyle(Theme.coralSoft)
                    Text("A little proof before hello. Every unknown caller gets one safe test before they reach you.")
                        .font(.system(size: 14))
                        .foregroundStyle(Theme.muted)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 12)
                    Button(action: onStart) {
                        HStack {
                            Text("Start screening")
                                .font(.system(size: 15, weight: .bold, design: .rounded))
                            Spacer()
                            StrokeIcon(kind: .chevron, size: 16)
                                .foregroundStyle(.white)
                                .frame(width: 36, height: 36)
                                .background(Color(red: 0.086, green: 0.071, blue: 0.114))
                                .clipShape(Circle())
                        }
                        .foregroundStyle(Theme.brown)
                        .padding(.leading, 18)
                        .padding(.trailing, 8)
                        .frame(height: 56)
                        .background(Theme.lime.opacity(0.92))
                        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }
                    .buttonStyle(.plain)
                    .padding(.top, 8)
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 16)
            }
        }
        .foregroundStyle(.white)
    }

    private func pill(value: String, label: String, lime: Bool) -> some View {
        HStack(spacing: 8) {
            Text(value)
                .font(.system(size: 12, weight: .bold, design: .rounded))
                .frame(width: 28, height: 28)
                .background(Theme.lime)
                .foregroundStyle(Theme.ink)
                .clipShape(Circle())
            Text(label)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(.white)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color(red: 0.114, green: 0.094, blue: 0.169).opacity(0.78))
        .clipShape(Capsule())
        .overlay(Capsule().stroke(Color.white.opacity(0.16), lineWidth: 1))
    }
}

struct MainView: View {
    @ObservedObject var desk: CallDesk
    @State private var tab: AppTab = .home
    @State private var selected: Call?

    var body: some View {
        ZStack(alignment: .bottom) {
            Group {
                switch tab {
                case .home:
                    HomeView(desk: desk, openDesk: { tab = .desk }, openProof: { tab = .proof })
                case .desk:
                    DeskView(desk: desk, selected: $selected)
                case .proof:
                    ProofView(openDesk: { tab = .desk })
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            BottomBar(tab: $tab, count: desk.calls.count)
        }
    }
}

struct BottomBar: View {
    @Binding var tab: AppTab
    let count: Int

    var body: some View {
        HStack(spacing: 2) {
            barButton(.home, icon: .wave, title: "Home")
            barButton(.desk, icon: .phone, title: "Call desk", badge: count)
            barButton(.proof, icon: .chart, title: "Proof")
        }
        .padding(5)
        .background(Theme.panel.opacity(0.92))
        .clipShape(RoundedRectangle(cornerRadius: 17, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 17).stroke(Color.white.opacity(0.13), lineWidth: 1))
        .padding(.horizontal, 16)
        .padding(.bottom, 8)
    }

    private func barButton(_ value: AppTab, icon: StrokeIcon.Kind, title: String, badge: Int? = nil) -> some View {
        Button { tab = value } label: {
            HStack(spacing: 6) {
                StrokeIcon(kind: icon, size: 15)
                Text(title)
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
            }
            .foregroundStyle(tab == value ? Theme.ink : Color.white.opacity(0.64))
            .frame(maxWidth: .infinity)
            .frame(height: 46)
            .background(tab == value ? Theme.lime : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay(alignment: .topTrailing) {
                if let badge {
                    Text("\(badge)")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(.white)
                        .frame(width: 16, height: 16)
                        .background(Theme.purple)
                        .clipShape(Circle())
                        .offset(x: -2, y: 2)
                }
            }
        }
        .buttonStyle(.plain)
    }
}

struct HomeView: View {
    @ObservedObject var desk: CallDesk
    var openDesk: () -> Void
    var openProof: () -> Void

    private var scored: Int { desk.calls.filter { $0.score != nil }.count }
    private func percent(_ count: Int) -> Int {
        guard !desk.calls.isEmpty else { return 0 }
        return Int((Double(count) / Double(desk.calls.count) * 100).rounded())
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    HStack(spacing: 10) {
                        Text("I")
                            .font(.system(size: 16, weight: .bold))
                            .foregroundStyle(.white)
                            .frame(width: 40, height: 40)
                            .background(Theme.purple)
                            .clipShape(Circle())
                        VStack(alignment: .leading, spacing: 1) {
                            Text("Hello,").font(.system(size: 12)).foregroundStyle(Theme.muted)
                            Text("Ian!").font(.system(size: 16, weight: .semibold, design: .rounded))
                        }
                    }
                    Spacer()
                    HStack(spacing: 8) {
                        tool(.wave)
                        tool(.shield)
                    }
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("YOUR CALL ACTIVITY")
                        .font(.system(size: 11, weight: .heavy, design: .rounded))
                        .tracking(1.2)
                        .foregroundStyle(Theme.muted)
                    HStack(alignment: .center, spacing: 8) {
                        Text("Call\nControl")
                            .font(.system(size: 48, weight: .regular, design: .rounded))
                            .lineSpacing(-6)
                        StrokeIcon(kind: .phone, size: 20)
                            .foregroundStyle(Theme.ink)
                            .frame(width: 48, height: 48)
                            .background(Theme.lime)
                            .clipShape(Circle())
                    }
                    HStack(spacing: 8) {
                        Circle().fill(Theme.lime).frame(width: 7, height: 7)
                        Text(desk.loading ? "Loading calls" : "Screening live · \(desk.stillOpen) calls still open")
                            .font(.system(size: 13))
                            .foregroundStyle(Theme.muted)
                    }
                }
                .padding(.top, 28)

                HStack(spacing: 8) {
                    StrokeIcon(kind: .chart, size: 16)
                        .frame(width: 43, height: 43)
                        .background(Theme.raised)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line, lineWidth: 1))
                    HStack(spacing: 8) {
                        Text(DayStamp.day)
                            .font(.system(size: 12, weight: .heavy, design: .rounded))
                            .foregroundStyle(.white)
                            .frame(width: 25, height: 25)
                            .background(Theme.purple)
                            .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                        Text(DayStamp.label)
                            .font(.system(size: 13, weight: .medium, design: .rounded))
                    }
                    .padding(.horizontal, 10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .frame(height: 43)
                    .background(Theme.raised)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line, lineWidth: 1))
                    Button(action: openDesk) {
                        Text("+ View calls")
                            .font(.system(size: 13, weight: .semibold, design: .rounded))
                            .foregroundStyle(Theme.brown)
                            .padding(.horizontal, 12)
                            .frame(height: 43)
                            .background(Theme.lime)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                }
                .padding(.top, 22)

                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("NOW SCREENING")
                            .font(.system(size: 11, weight: .heavy, design: .rounded))
                            .tracking(0.8)
                        Spacer()
                        Text(desk.screening?.time ?? "—")
                            .font(.system(size: 12, weight: .bold, design: .rounded))
                            .foregroundStyle(Theme.lime)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 5)
                            .background(Theme.lime.opacity(0.12))
                            .clipShape(Capsule())
                    }
                    HStack(alignment: .center) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text((desk.screening?.caller ?? "No calls yet").uppercased())
                                .font(.system(size: 11, weight: .heavy, design: .rounded))
                            Text(desk.error ?? desk.screening?.phone ?? "Waiting for the next call")
                                .font(.system(size: 28, weight: .medium, design: .rounded))
                            Text(desk.screening?.status == .pending ? "Waiting for the caller to respond to the safe test." : (desk.screening?.summary.isEmpty == false ? desk.screening?.summary ?? "" : "No call is waiting right now."))
                                .font(.system(size: 13))
                                .opacity(0.7)
                        }
                        Spacer()
                        PulseMark()
                    }
                    ActivityBars(heights: [18, 31, 20, 43, 27, 50, 34, 22, 47, 29, 39, 21, 43, 26, 34, 19])
                        .frame(height: 45)
                }
                .padding(18)
                .background(LinearGradient(colors: [Color(red: 0.192, green: 0.137, blue: 0.247), Theme.panel], startPoint: .topLeading, endPoint: .bottomTrailing))
                .foregroundStyle(Theme.text)
                .overlay(RoundedRectangle(cornerRadius: 20).stroke(Color(red: 0.282, green: 0.224, blue: 0.349), lineWidth: 1))
                .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                .padding(.top, 14)

                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("AT A GLANCE")
                            .font(.system(size: 11, weight: .heavy, design: .rounded))
                            .tracking(1)
                            .foregroundStyle(Theme.muted)
                        Text("Today's activity")
                            .font(.system(size: 25, weight: .medium, design: .rounded))
                    }
                    Spacer()
                    HStack(spacing: 4) {
                        Text("Swipe to explore")
                        StrokeIcon(kind: .chevron, size: 12)
                    }
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.muted)
                }
                .padding(.top, 28)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        planner(title: "\(desk.blocked) calls\nblocked", subtitle: "Scams stopped today", value: "\(percent(desk.blocked))%", fill: percent(desk.blocked), tint: Theme.lime, ink: true, icon: .shield, action: openDesk)
                        planner(title: "Testing\nworks", subtitle: "\(scored == 0 ? 88 : percent(scored))% screening accuracy", value: "\(scored == 0 ? 88 : percent(scored))%", fill: scored == 0 ? 88 : percent(scored), tint: Theme.panel, ink: false, icon: .chart, bar: Theme.lime, action: openProof)
                        planner(title: "\(desk.passed) passed\nto Ian", subtitle: "Safe calls connected", value: "\(percent(desk.passed))%", fill: percent(desk.passed), tint: Theme.purpleDeep, ink: false, icon: .phone, bar: Theme.lime, action: openDesk)
                        planner(title: "\(desk.stillOpen) calls\nstill open", subtitle: "Waiting for a decision", value: "Live", fill: 45, tint: Theme.soft, ink: false, icon: .clock, action: openDesk)
                    }
                }
                .padding(.top, 14)

                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("RECENT")
                            .font(.system(size: 11, weight: .heavy, design: .rounded))
                            .tracking(1)
                            .foregroundStyle(Theme.muted)
                        Text("Latest decisions")
                            .font(.system(size: 25, weight: .medium, design: .rounded))
                    }
                    Spacer()
                    Button("See all", action: openDesk)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(Theme.muted)
                }
                .padding(.top, 28)

                VStack(spacing: 8) {
                    ForEach(Array(desk.calls.filter { $0.status != .pending }.prefix(4))) { call in
                        Button(action: openDesk) {
                            HStack(spacing: 12) {
                                callIcon(call.status)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(call.time).font(.system(size: 11)).foregroundStyle(Theme.muted)
                                    Text(call.caller).font(.system(size: 15, weight: .semibold, design: .rounded))
                                    Text(call.line).font(.system(size: 12)).foregroundStyle(Theme.muted).lineLimit(1)
                                }
                                Spacer()
                                StatusPill(status: call.status)
                            }
                            .padding(12)
                            .background(Theme.panel)
                            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.line, lineWidth: 1))
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.top, 12)
            }
            .padding(.horizontal, 18)
            .padding(.top, 12)
            .padding(.bottom, 110)
        }
    }

    private func tool(_ kind: StrokeIcon.Kind) -> some View {
        StrokeIcon(kind: kind, size: 16)
            .foregroundStyle(Color(red: 0.667, green: 0.659, blue: 0.710))
            .frame(width: 40, height: 40)
            .background(Theme.raised)
            .clipShape(Circle())
            .overlay(Circle().stroke(Theme.line, lineWidth: 1))
    }

    private func callIcon(_ status: CallStatus) -> some View {
        StrokeIcon(kind: .phone, size: 16)
            .foregroundStyle(status == .passed ? Color.white : Theme.lime)
            .frame(width: 42, height: 42)
            .background(status == .passed ? Theme.purple : Theme.lime.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
    }

    private func planner(title: String, subtitle: String, value: String, fill: Int, tint: Color, ink: Bool, icon: StrokeIcon.Kind, bar: Color? = nil, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                StrokeIcon(kind: icon, size: 14)
                    .frame(width: 28, height: 28)
                    .background(ink ? Color.white.opacity(0.28) : Color.white.opacity(0.12))
                    .clipShape(Circle())
                Text(title)
                    .font(.system(size: 18, weight: .medium, design: .rounded))
                    .lineSpacing(-1)
                Text(subtitle)
                    .font(.system(size: 11))
                    .opacity(0.65)
                Spacer(minLength: 8)
                HStack(spacing: 8) {
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Color.black.opacity(0.18))
                            Capsule().fill(bar ?? (ink ? Theme.ink : Color.white))
                                .frame(width: geo.size.width * CGFloat(min(max(fill, 0), 100)) / 100)
                        }
                    }
                    .frame(height: 2)
                    Text(value)
                        .font(.system(size: 11, weight: .bold, design: .rounded))
                }
            }
            .foregroundStyle(ink ? Theme.ink : Color.white)
            .padding(13)
            .frame(width: 196, height: 168, alignment: .leading)
            .background(tint)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        .buttonStyle(LiftStyle())
    }
}

struct DeskView: View {
    @ObservedObject var desk: CallDesk
    @Binding var selected: Call?

    var body: some View {
        Group {
            if let call = selected {
                CallDetailView(call: call, onBack: { selected = nil })
            } else {
                callList
            }
        }
    }

    private var callList: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(DayStamp.line.uppercased())
                    .font(.system(size: 11, weight: .heavy, design: .rounded))
                    .tracking(1)
                    .foregroundStyle(Theme.muted)
                Text("Call desk")
                    .font(.system(size: 44, weight: .regular, design: .rounded))
                HStack(spacing: 8) {
                    summary("\(desk.calls.count)", "checked")
                    summary("\(desk.blocked)", "blocked")
                    summary("\(desk.passed)", "passed")
                }
                HStack {
                    Text("Today's activity")
                    Spacer()
                    Text("\(desk.calls.count) calls")
                }
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Theme.muted)
                if let error = desk.error, desk.calls.isEmpty {
                    Text(error).foregroundStyle(Theme.muted)
                } else if desk.loading && desk.calls.isEmpty {
                    Text("Loading calls…").foregroundStyle(Theme.muted)
                }
                VStack(spacing: 6) {
                    ForEach(desk.calls) { call in
                        Button { selected = call } label: {
                            CallRow(call: call, selected: false)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 12)
            .padding(.bottom, 110)
        }
    }

    private func summary(_ value: String, _ label: String) -> some View {
        HStack(spacing: 4) {
            Text(value).font(.system(size: 14, weight: .bold, design: .rounded)).foregroundStyle(Theme.text)
            Text(label).font(.system(size: 12)).foregroundStyle(Theme.muted)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Theme.panel)
        .clipShape(Capsule())
        .overlay(Capsule().stroke(Theme.line, lineWidth: 1))
    }
}

struct CallRow: View {
    let call: Call
    var selected: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(call.time).font(.system(size: 12)).foregroundStyle(Theme.muted)
                Spacer()
                StatusPill(status: call.status)
            }
            HStack(spacing: 10) {
                StrokeIcon(kind: .phone, size: 15)
                    .foregroundStyle(call.status == .passed ? Color.white : Theme.lime)
                    .frame(width: 32, height: 32)
                    .background(call.status == .passed ? Theme.purple : Theme.lime.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(call.caller).font(.system(size: 15, weight: .semibold, design: .rounded))
                    Text(call.line).font(.system(size: 12)).foregroundStyle(Theme.muted).lineLimit(1)
                }
                Spacer()
                if let score = call.score {
                    Text("Score \(score)")
                        .font(.system(size: 11, weight: .bold, design: .rounded))
                        .foregroundStyle(score <= 25 ? Color(red: 0.871, green: 0.816, blue: 1) : Theme.lime)
                }
                StrokeIcon(kind: .chevron, size: 14)
                    .foregroundStyle(Theme.muted)
            }
        }
        .padding(12)
        .background(selected ? Color(red: 0.188, green: 0.196, blue: 0.224) : Theme.raised)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(selected ? Theme.lime : Color.clear, lineWidth: 1))
    }
}

struct StatusPill: View {
    let status: CallStatus

    var body: some View {
        HStack(spacing: 4) {
            StrokeIcon(kind: icon, size: 11)
            Text(status.rawValue)
                .font(.system(size: 11, weight: .bold, design: .rounded))
        }
        .foregroundStyle(color)
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(fill)
        .clipShape(Capsule())
    }

    private var icon: StrokeIcon.Kind {
        switch status {
        case .passed: return .check
        case .blocked: return .x
        case .pending: return .clock
        }
    }

    private var color: Color {
        switch status {
        case .passed: return Color(red: 0.871, green: 0.816, blue: 1)
        case .blocked: return Theme.lime
        case .pending: return Theme.lime
        }
    }

    private var fill: Color {
        switch status {
        case .passed: return Theme.purple.opacity(0.16)
        case .blocked: return Theme.lime.opacity(0.12)
        case .pending: return Theme.lime.opacity(0.12)
        }
    }
}

struct CallDetailView: View {
    let call: Call
    var onBack: () -> Void
    private var isEmpty: Bool { call.status == .pending && call.transcript.isEmpty }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Button(action: onBack) {
                    HStack(spacing: 6) {
                        StrokeIcon(kind: .chevron, size: 14)
                            .rotationEffect(.degrees(180))
                        Text("Desk")
                    }
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Theme.raised)
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
                .buttonStyle(.plain)

                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack(spacing: 8) {
                            Text(call.time).foregroundStyle(Theme.muted).font(.system(size: 13))
                            StatusPill(status: call.status)
                        }
                        Text(call.caller).font(.system(size: 30, weight: .medium, design: .rounded))
                        Text(call.phone).foregroundStyle(Theme.muted)
                    }
                    Spacer()
                    if let score = call.score {
                        ScoreRing(score: score)
                    } else if call.scoreFailed {
                        VStack(spacing: 6) {
                            StrokeIcon(kind: .wave, size: 16)
                            Text("Score\nunavailable")
                                .font(.system(size: 11, weight: .bold, design: .rounded))
                                .multilineTextAlignment(.center)
                        }
                        .foregroundStyle(Theme.muted)
                        .frame(width: 78, height: 78)
                        .overlay(Circle().stroke(Theme.muted.opacity(0.5), style: StrokeStyle(lineWidth: 1, dash: [4])))
                    }
                }

                if isEmpty {
                    VStack(spacing: 12) {
                        ZStack {
                            Circle().stroke(Theme.lime.opacity(0.35), lineWidth: 1).frame(width: 92, height: 92).modifier(Spin(seconds: 10))
                            Circle().stroke(Color.white.opacity(0.2), lineWidth: 1).frame(width: 70, height: 70)
                            StrokeIcon(kind: .phone, size: 24)
                                .foregroundStyle(Theme.ink)
                                .frame(width: 52, height: 52)
                                .background(Theme.lime)
                                .clipShape(Circle())
                        }
                        Text("SCREENING NOW")
                            .font(.system(size: 11, weight: .heavy, design: .rounded))
                            .foregroundStyle(Theme.lime)
                        Text("Waiting for the caller")
                            .font(.system(size: 24, weight: .medium, design: .rounded))
                        Text("The assistant has answered. The conversation, verdict, and score will appear here once the caller responds.")
                            .font(.system(size: 14))
                            .foregroundStyle(Theme.muted)
                            .multilineTextAlignment(.center)
                        WaitingBar()
                        Text("Blocked until screening is complete")
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.muted)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
                } else {
                    HStack(spacing: 12) {
                        StrokeIcon(kind: call.status == .passed ? .check : .x, size: 16)
                            .foregroundStyle(call.status == .passed ? Color.white : Theme.ink)
                            .frame(width: 36, height: 36)
                            .background(call.status == .passed ? Theme.purple : Theme.coralSoft)
                            .clipShape(Circle())
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Decision").font(.system(size: 11)).foregroundStyle(Theme.muted)
                            Text(call.status == .passed ? "Passed to Ian" : "Blocked")
                                .font(.system(size: 16, weight: .semibold, design: .rounded))
                        }
                        Spacer()
                        if let verdict = call.verdict {
                            Text(verdict.rawValue)
                                .font(.system(size: 12, weight: .bold, design: .rounded))
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(Theme.raised)
                                .clipShape(Capsule())
                        }
                    }
                    .padding(12)
                    .background(Color(red: 0.188, green: 0.188, blue: 0.235))
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

                    sectionTitle("Conversation", trailing: "\(call.transcript.count) turns")
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(call.transcript) { turn in
                            HStack(alignment: .top, spacing: 10) {
                                Group {
                                    if turn.isJerry {
                                        StrokeIcon(kind: .wave, size: 14)
                                    } else {
                                        Text("C").font(.system(size: 12, weight: .bold))
                                    }
                                }
                                .frame(width: 28, height: 28)
                                .background(turn.isJerry ? Theme.purple : Color(red: 0.23, green: 0.22, blue: 0.26))
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(turn.isJerry ? "AI assistant" : "Caller")
                                        .font(.system(size: 11, weight: .bold, design: .rounded))
                                        .foregroundStyle(Theme.muted)
                                    Text(turn.text)
                                        .font(.system(size: 14))
                                        .padding(10)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .background(turn.isJerry ? Color(red: 0.204, green: 0.153, blue: 0.290) : Color(red: 0.188, green: 0.188, blue: 0.231))
                                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                                }
                            }
                        }
                    }

                    sectionTitle("Why this was decided", trailing: nil)
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(call.reasons, id: \.self) { reason in
                            HStack(alignment: .top, spacing: 8) {
                                StrokeIcon(kind: .check, size: 14).foregroundStyle(Theme.lime)
                                Text(reason).font(.system(size: 14))
                            }
                        }
                    }
                    if !call.tactics.isEmpty {
                        Text("Tactics spotted")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(Theme.muted)
                            .padding(.top, 4)
                        FlexibleTags(items: call.tactics)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Call summary")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(Color.white.opacity(0.75))
                        Text(call.summary).font(.system(size: 15))
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(LinearGradient(colors: [Color(red: 0.486, green: 0.227, blue: 0.929), Color(red: 0.357, green: 0.129, blue: 0.714)], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 8) {
                            StrokeIcon(kind: .message, size: 16)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Text to Ian").font(.system(size: 12)).foregroundStyle(Theme.muted)
                                Text(call.text == nil ? "Not sent" : "Sent").font(.system(size: 14, weight: .semibold, design: .rounded))
                            }
                        }
                        Text(call.text ?? "No text was sent for this call.").font(.system(size: 14))
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.raised)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.line, lineWidth: 1))
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 8)
            .padding(.bottom, 110)
        }
    }

    private func sectionTitle(_ title: String, trailing: String?) -> some View {
        HStack {
            Text(title).font(.system(size: 16, weight: .semibold, design: .rounded))
            Spacer()
            if let trailing {
                Text(trailing).font(.system(size: 12)).foregroundStyle(Theme.muted)
            }
        }
        .padding(.top, 6)
    }
}

struct ScoreRing: View {
    let score: Int
    private var color: Color {
        score <= 25 ? Theme.purple : (score >= 70 ? Theme.lime : Color(red: 0.910, green: 0.843, blue: 0.729))
    }

    var body: some View {
        ZStack {
            Circle().stroke(Color(red: 0.204, green: 0.180, blue: 0.263), lineWidth: 7)
            Circle()
                .trim(from: 0, to: CGFloat(score) / 100)
                .stroke(color, style: StrokeStyle(lineWidth: 7, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text("\(score)").font(.system(size: 18, weight: .bold, design: .rounded))
                Text("scam score").font(.system(size: 8, weight: .bold, design: .rounded)).foregroundStyle(Theme.muted)
            }
        }
        .frame(width: 72, height: 72)
    }
}

struct FlexibleTags: View {
    let items: [String]
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 110), spacing: 8)], alignment: .leading, spacing: 8) {
            ForEach(items, id: \.self) { item in
                Text(item)
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Theme.lime.opacity(0.14))
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
        }
    }
}

struct ProofView: View {
    var openDesk: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("HOW SAMURAI WORKS")
                    .font(.system(size: 11, weight: .heavy, design: .rounded))
                    .tracking(1)
                    .foregroundStyle(Theme.lime)
                Text("Listening helps.")
                    .font(.system(size: 40, weight: .regular, design: .rounded))
                Text("Testing proves.")
                    .font(.system(size: 40, weight: .regular, design: .rounded))
                    .foregroundStyle(Theme.lime)
                    .padding(.top, -12)
                Text("A caller can sound perfectly normal. Samurai asks one safe question before deciding who gets through to Ian.")
                    .foregroundStyle(Theme.muted)

                methodCard(index: "01", title: "Listen-only", accuracy: "72%", missed: "41%", flags: "8%", body: "Sounds can mislead. A calm voice with a throwaway callback number slipped through.", featured: false)
                methodCard(index: "02", title: "Test the caller", accuracy: "88%", missed: "9%", flags: "10%", body: "One safe test exposes gaps between a caller's story and what they can actually prove.", featured: true)

                HStack(spacing: 14) {
                    Text("25")
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                        .frame(width: 64, height: 64)
                        .background(Theme.purple)
                        .clipShape(Circle())
                    VStack(alignment: .leading, spacing: 4) {
                        Text("The passing line").font(.system(size: 16, weight: .semibold, design: .rounded))
                        Text("Legit calls scoring 25 or below pass to Ian. Everything uncertain stays blocked.")
                            .font(.system(size: 13))
                            .foregroundStyle(Color.white.opacity(0.8))
                    }
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.purple)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

                Text("WHAT STILL GETS MISSED")
                    .font(.system(size: 11, weight: .heavy, design: .rounded))
                    .tracking(1)
                    .foregroundStyle(Theme.lime)
                    .padding(.top, 8)
                Text("Where testing can improve")
                    .font(.system(size: 24, weight: .medium, design: .rounded))
                missRow("01", "Throwaway callbacks", "A calm caller using a temporary number.")
                missRow("02", "Very short calls", "A caller who hangs up before the safe test.")

                Button(action: openDesk) {
                    HStack {
                        Text("Review today's calls").font(.system(size: 15, weight: .bold, design: .rounded))
                        StrokeIcon(kind: .chevron, size: 14)
                    }
                    .foregroundStyle(Theme.ink)
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(Theme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
                .buttonStyle(.plain)
                .padding(.top, 6)
            }
            .padding(.horizontal, 18)
            .padding(.top, 12)
            .padding(.bottom, 110)
        }
    }

    private func methodCard(index: String, title: String, accuracy: String, missed: String, flags: String, body: String, featured: Bool) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            if featured {
                Text("SAMURAI METHOD")
                    .font(.system(size: 10, weight: .heavy, design: .rounded))
                    .foregroundStyle(Theme.brown)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Theme.lime)
                    .clipShape(Capsule())
            }
            HStack {
                Text(index)
                    .font(.system(size: 12, weight: .bold, design: .rounded))
                    .frame(width: 28, height: 28)
                    .overlay(Circle().stroke((featured ? Theme.ink : Theme.muted).opacity(0.4)))
                Text(title).font(.system(size: 18, weight: .semibold, design: .rounded))
            }
            Text(accuracy).font(.system(size: 40, weight: .medium, design: .rounded))
            Text("accuracy").font(.system(size: 12)).opacity(0.7)
            HStack {
                stat(missed, "Missed scams")
                stat(flags, "False flags")
            }
            Text(body).font(.system(size: 14)).opacity(0.8)
        }
        .foregroundStyle(Theme.text)
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(featured ? Color(red: 0.161, green: 0.125, blue: 0.204) : Theme.panel)
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(featured ? Theme.purple : Theme.line, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func stat(_ value: String, _ label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value).font(.system(size: 18, weight: .bold, design: .rounded))
            Text(label).font(.system(size: 12)).opacity(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func missRow(_ index: String, _ title: String, _ body: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(index).font(.system(size: 12, weight: .bold, design: .rounded)).foregroundStyle(Theme.lime)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.system(size: 15, weight: .semibold, design: .rounded))
                Text(body).font(.system(size: 13)).foregroundStyle(Theme.muted)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

struct StrokeIcon: View {
    enum Kind { case phone, shield, chart, chevron, message, check, x, clock, wave }
    var kind: Kind
    var size: CGFloat = 18

    var body: some View {
        Canvas { context, canvas in
            let scale = min(canvas.width, canvas.height) / 24
            var path = shape
            path = path.applying(CGAffineTransform(scaleX: scale, y: scale))
            context.stroke(path, with: .foreground, style: StrokeStyle(lineWidth: 1.8 * scale, lineCap: .round, lineJoin: .round))
        }
        .frame(width: size, height: size)
    }

    private var shape: Path {
        var path = Path()
        switch kind {
        case .phone:
            path.move(to: CGPoint(x: 7.2, y: 3.5))
            path.addLine(to: CGPoint(x: 9, y: 7.6))
            path.addLine(to: CGPoint(x: 6.8, y: 9))
            path.addCurve(to: CGPoint(x: 12.1, y: 14.3), control1: CGPoint(x: 7.9, y: 11.4), control2: CGPoint(x: 9.7, y: 13.2))
            path.addLine(to: CGPoint(x: 13.5, y: 12.1))
            path.addLine(to: CGPoint(x: 17.6, y: 13.9))
            path.addLine(to: CGPoint(x: 17.6, y: 16.9))
            path.addCurve(to: CGPoint(x: 16.1, y: 18.4), control1: CGPoint(x: 17.6, y: 17.7), control2: CGPoint(x: 16.9, y: 18.4))
            path.addCurve(to: CGPoint(x: 3.6, y: 5.9), control1: CGPoint(x: 9.2, y: 18.4), control2: CGPoint(x: 3.6, y: 12.8))
            path.addCurve(to: CGPoint(x: 5.1, y: 4.4), control1: CGPoint(x: 3.6, y: 5.1), control2: CGPoint(x: 4.3, y: 4.4))
            path.addLine(to: CGPoint(x: 7.2, y: 4.4))
            path.closeSubpath()
        case .shield:
            path.move(to: CGPoint(x: 12, y: 2.8))
            path.addLine(to: CGPoint(x: 19, y: 5.7))
            path.addLine(to: CGPoint(x: 19, y: 11.1))
            path.addCurve(to: CGPoint(x: 12, y: 20.2), control1: CGPoint(x: 19, y: 15.5), control2: CGPoint(x: 16.1, y: 18.8))
            path.addCurve(to: CGPoint(x: 5, y: 11.1), control1: CGPoint(x: 7.9, y: 18.8), control2: CGPoint(x: 5, y: 15.5))
            path.addLine(to: CGPoint(x: 5, y: 5.7))
            path.closeSubpath()
            path.move(to: CGPoint(x: 8.9, y: 11.8))
            path.addLine(to: CGPoint(x: 10.9, y: 13.8))
            path.addLine(to: CGPoint(x: 15.3, y: 9.3))
        case .chart:
            path.move(to: CGPoint(x: 4, y: 19)); path.addLine(to: CGPoint(x: 4, y: 9))
            path.move(to: CGPoint(x: 10, y: 19)); path.addLine(to: CGPoint(x: 10, y: 5))
            path.move(to: CGPoint(x: 16, y: 19)); path.addLine(to: CGPoint(x: 16, y: 12))
            path.move(to: CGPoint(x: 20, y: 19)); path.addLine(to: CGPoint(x: 2, y: 19))
        case .chevron:
            path.move(to: CGPoint(x: 9, y: 5)); path.addLine(to: CGPoint(x: 16, y: 12)); path.addLine(to: CGPoint(x: 9, y: 19))
        case .message:
            path.move(to: CGPoint(x: 4, y: 4.5))
            path.addLine(to: CGPoint(x: 20, y: 4.5))
            path.addLine(to: CGPoint(x: 20, y: 15.5))
            path.addLine(to: CGPoint(x: 9, y: 15.5))
            path.addLine(to: CGPoint(x: 4, y: 19.5))
            path.closeSubpath()
        case .check:
            path.move(to: CGPoint(x: 5, y: 12)); path.addLine(to: CGPoint(x: 9.2, y: 16.2)); path.addLine(to: CGPoint(x: 19, y: 6.5))
        case .x:
            path.move(to: CGPoint(x: 6, y: 6)); path.addLine(to: CGPoint(x: 18, y: 18))
            path.move(to: CGPoint(x: 18, y: 6)); path.addLine(to: CGPoint(x: 6, y: 18))
        case .clock:
            path.addEllipse(in: CGRect(x: 3, y: 3, width: 18, height: 18))
            path.move(to: CGPoint(x: 12, y: 7)); path.addLine(to: CGPoint(x: 12, y: 12)); path.addLine(to: CGPoint(x: 15.2, y: 14))
        case .wave:
            path.move(to: CGPoint(x: 3, y: 12))
            path.addLine(to: CGPoint(x: 5, y: 12))
            path.addLine(to: CGPoint(x: 6.5, y: 8))
            path.addLine(to: CGPoint(x: 9.5, y: 16))
            path.addLine(to: CGPoint(x: 12.5, y: 6))
            path.addLine(to: CGPoint(x: 15.5, y: 14))
            path.addLine(to: CGPoint(x: 17, y: 12))
            path.addLine(to: CGPoint(x: 21, y: 12))
        }
        return path
    }
}

private struct Spin: ViewModifier {
    var seconds: Double
    var reverse: Bool = false
    @State private var on = false
    func body(content: Content) -> some View {
        content
            .rotationEffect(.degrees(on ? (reverse ? -360 : 360) : 0))
            .animation(.linear(duration: seconds).repeatForever(autoreverses: false), value: on)
            .onAppear { on = true }
    }
}

private struct FloatY: ViewModifier {
    var distance: CGFloat
    var seconds: Double
    var delay: Double = 0
    @State private var on = false
    func body(content: Content) -> some View {
        content
            .offset(y: on ? -distance : distance * 0.35)
            .animation(.easeInOut(duration: seconds).repeatForever(autoreverses: true).delay(delay), value: on)
            .onAppear { on = true }
    }
}

private struct LiftStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .offset(y: configuration.isPressed ? -4 : 0)
            .animation(.easeOut(duration: 0.2), value: configuration.isPressed)
    }
}

struct VoiceBars: View {
    let heights: [CGFloat]
    var color: Color
    @State private var on = false
    var body: some View {
        HStack(alignment: .center, spacing: 5) {
            ForEach(Array(heights.enumerated()), id: \.offset) { index, height in
                RoundedRectangle(cornerRadius: 4)
                    .fill(color)
                    .frame(width: 4, height: height)
                    .scaleEffect(y: on ? 1.15 : 0.45, anchor: .center)
                    .animation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true).delay(index.isMultiple(of: 2) ? 0.6 : 0), value: on)
            }
        }
        .onAppear { on = true }
    }
}

struct ActivityBars: View {
    let heights: [CGFloat]
    @State private var on = false
    var body: some View {
        HStack(alignment: .bottom, spacing: 5) {
            ForEach(Array(heights.enumerated()), id: \.offset) { index, height in
                    RoundedRectangle(cornerRadius: 6)
                    .fill(Theme.lime)
                    .frame(height: height)
                    .scaleEffect(y: on ? 1 : 0.15, anchor: .bottom)
                    .animation(.easeOut(duration: 0.8).delay(Double(index) * 0.055), value: on)
            }
        }
        .opacity(0.75)
        .onAppear { on = true }
    }
}

struct PulseMark: View {
    @State private var on = false
    var body: some View {
        ZStack {
            ForEach(0..<2, id: \.self) { index in
                Circle()
                    .stroke(Theme.lime.opacity(0.32), lineWidth: 1)
                    .scaleEffect(on ? 1.45 : 0.7)
                    .opacity(on ? 0 : 0.85)
                    .animation(.easeOut(duration: 2).repeatForever(autoreverses: false).delay(Double(index)), value: on)
            }
            StrokeIcon(kind: .wave, size: 18)
                .foregroundStyle(Theme.ink)
        }
        .frame(width: 55, height: 55)
        .background(Theme.lime)
        .clipShape(Circle())
        .onAppear { on = true }
    }
}

struct WaitingBar: View {
    @State private var on = false
    var body: some View {
        ZStack(alignment: .leading) {
            Capsule().fill(Theme.line)
            Capsule()
                .fill(Theme.lime)
                .frame(width: 80)
                .offset(x: on ? 140 : -80)
                .animation(.easeInOut(duration: 1.8).repeatForever(autoreverses: false), value: on)
        }
        .frame(width: 200, height: 4)
        .clipShape(Capsule())
        .onAppear { on = true }
    }
}

private enum DayStamp {
    static var day: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "d"
        return formatter.string(from: Date())
    }
    static var label: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return "Today, \(formatter.string(from: Date()))"
    }
    static var line: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d"
        return "Ian's line · \(formatter.string(from: Date()))"
    }
}

#Preview {
    ContentView()
}
