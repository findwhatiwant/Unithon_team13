import Foundation

/// 앱 실행 시 Python 백엔드(refiner-api)를 자동으로 띄우고, 앱이 직접 띄운 경우에만 종료한다.
///
/// - 이미 127.0.0.1:8000에서 서버가 살아있으면 재사용 (수동으로 켠 서버는 건드리지 않음)
/// - `.venv`가 없으면 server.sh의 ensure_env와 동일하게 생성·설치를 시도한다
/// - 로그/PID 파일은 server.sh와 동일한 경로를 쓴다 (/tmp/magicnote-server.{log,pid})
final class ServerManager {
    static let shared = ServerManager()

    enum Status: Equatable {
        case idle
        case preparing      // 헬스체크·venv 준비 중
        case starting       // 프로세스 스폰 후 readiness 대기
        case reused         // 이미 실행 중이던 외부 서버 재사용
        case running        // 앱이 직접 스폰한 서버
        case remote         // apiBaseURL이 클라우드 — 로컬 스폰 불필요
        case failed(String)
    }

    private(set) var status: Status = .idle
    private var process: Process?
    private(set) var ownsProcess = false

    private let port = 8000
    private let pidFile = "/tmp/magicnote-server.pid"
    private let logFile = "/tmp/magicnote-server.log"

    private var healthURL: URL {
        URL(string: "http://127.0.0.1:\(port)/health")!
    }

    private let queue = DispatchQueue(label: "com.unithon.magicnote.server", qos: .utility)

    // MARK: - 진입점 (앱 런치/종료)

    /// 앱 시작 시 호출 — 백그라운드에서 서버 확보. 메인 스레드를 막지 않는다.
    func bootstrap() {
        queue.async { [weak self] in
            self?.startIfNeeded()
        }
    }

    /// 앱 종료 시 호출 — 우리가 스폰한 프로세스만 정리.
    func shutdown() {
        guard ownsProcess, let process, process.isRunning else { return }
        process.terminate()
        for _ in 0..<20 {
            if !process.isRunning { break }
            Thread.sleep(forTimeInterval: 0.1)
        }
        if process.isRunning {
            kill(process.processIdentifier, SIGKILL)
        }
        try? FileManager.default.removeItem(atPath: pidFile)
    }

    // MARK: - 시작 절차

    private func startIfNeeded() {
        // apiBaseURL이 localhost가 아니면 클라우드 배포 모드 — 로컬 서버를 띄우지 않는다
        if isRemoteMode() {
            status = .remote
            return
        }

        setStatus(.preparing)

        if isServerHealthy(timeout: 2) {
            status = .reused
            return
        }

        guard let projectDir = resolveProjectDir() else {
            setStatus(.failed("프로젝트 디렉토리를 찾지 못했습니다. 'defaults write com.unithon.team13.MagicNote serverProjectDir <경로>'로 지정하세요."))
            return
        }

        guard prepareVenv(projectDir) else {
            setStatus(.failed("Python 가상환경 준비 실패 — \(projectDir)/.venv"))
            return
        }

        spawnServer(projectDir: projectDir)

        setStatus(.starting)
        if waitUntilReady(timeout: 15) {
            status = .running
        } else {
            shutdown()
            setStatus(.failed("서버가 15초 내에 준비되지 않았습니다 — tail /tmp/magicnote-server.log"))
        }
    }

    private func setStatus(_ newStatus: Status) {
        DispatchQueue.main.async { [weak self] in
            self?.status = newStatus
        }
    }

    private func isRemoteMode() -> Bool {
        guard let raw = UserDefaults.standard.string(forKey: "apiBaseURL"),
              !raw.isEmpty,
              let url = URL(string: raw),
              let host = url.host else { return false }
        return host != "127.0.0.1" && host != "localhost"
    }

    // MARK: - 헬스체크

    private func isServerHealthy(timeout: TimeInterval) -> Bool {
        guard let data = httpGet(healthURL, timeout: timeout) else { return false }
        return String(data: data, encoding: .utf8)?.contains("\"ok\":true") == true
    }

    private func waitUntilReady(timeout: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if isServerHealthy(timeout: 2) { return true }
            Thread.sleep(forTimeInterval: 0.5)
        }
        return false
    }

    private func httpGet(_ url: URL, timeout: TimeInterval) -> Data? {
        var request = URLRequest(url: url)
        request.timeoutInterval = timeout

        var result: Data?
        let semaphore = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: request) { data, response, _ in
            if let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) {
                result = data
            }
            semaphore.signal()
        }.resume()
        _ = semaphore.wait(timeout: .now() + timeout + 1)
        return result
    }

    // MARK: - 경로 탐색

    private func resolveProjectDir() -> String? {
        var candidates: [String] = []

        // 사용자 지정 오버라이드 최우선
        if let custom = UserDefaults.standard.string(forKey: "serverProjectDir") {
            candidates.append(custom)
        }
        // 흔한 체크아웃 위치
        let home = NSHomeDirectory()
        candidates.append(contentsOf: [
            "\(home)/programming/Unithon",
            "\(home)/Developer/Unithon",
            "\(home)/Unithon",
        ])

        return candidates.first { dir in
            FileManager.default.fileExists(atPath: "\(dir)/pyproject.toml")
        }
    }

    // MARK: - 가상환경 준비 (server.sh의 ensure_env 이식)

    private func prepareVenv(_ projectDir: String) -> Bool {
        appendLog("--- MagicNote 앱에서 서버 시작 시도 ---\n")

        let venvPython = "\(projectDir)/.venv/bin/python"
        if !FileManager.default.fileExists(atPath: venvPython) {
            run("/usr/bin/python3", arguments: ["-m", "venv", ".venv"], cwd: projectDir)
        }
        guard FileManager.default.fileExists(atPath: venvPython) else { return false }

        // 필수 패키지 확인 → 없으면 설치
        if !run(venvPython, arguments: ["-c", "import fastapi, uvicorn"], cwd: projectDir) {
            return run("\(projectDir)/.venv/bin/pip", arguments: ["install", "-q", "-e", ".[dev]"], cwd: projectDir)
                && run(venvPython, arguments: ["-c", "import fastapi, uvicorn"], cwd: projectDir)
        }
        return true
    }

    // MARK: - 서버 스폰

    private func spawnServer(projectDir: String) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "\(projectDir)/.venv/bin/python")
        process.arguments = [
            "-m", "uvicorn", "refiner.server:app",
            "--host", "127.0.0.1", "--port", String(port),
        ]
        process.currentDirectoryURL = URL(fileURLWithPath: projectDir)

        if let log = FileHandle(forWritingAtPath: logFile) {
            _ = try? log.seekToEnd()
            process.standardOutput = log
            process.standardError = log
        }

        process.terminationHandler = { [weak self] proc in
            guard let self, self.process === proc else { return }
            DispatchQueue.main.async {
                if self.status == .running || self.status == .starting {
                    self.status = .failed("서버 프로세스가 종료되었습니다 (code \(proc.terminationStatus))")
                }
            }
        }

        do {
            try process.run()
        } catch {
            setStatus(.failed("서버 실행 실패: \(error.localizedDescription)"))
            return
        }

        self.process = process
        ownsProcess = true
        try? "\(process.processIdentifier)\n".write(toFile: pidFile, atomically: true, encoding: .utf8)
    }

    // MARK: - 프로세스 유틸

    @discardableResult
    private func run(_ executablePath: String, arguments: [String], cwd: String) -> Bool {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executablePath)
        process.arguments = arguments
        process.currentDirectoryURL = URL(fileURLWithPath: cwd)

        if let log = FileHandle(forWritingAtPath: logFile) {
            _ = try? log.seekToEnd()
            process.standardOutput = log
            process.standardError = log
        }

        do {
            try process.run()
        } catch {
            appendLog("[ServerManager] 실행 실패: \(executablePath) \(arguments.joined(separator: " ")) — \(error)\n")
            return false
        }
        process.waitUntilExit()
        return process.terminationStatus == 0
    }

    private func appendLog(_ message: String) {
        if let handle = FileHandle(forWritingAtPath: logFile) {
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: Data(message.utf8))
            try? handle.close()
        }
    }
}
