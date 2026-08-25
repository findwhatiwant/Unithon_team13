import Foundation
import RefinerCore

nonisolated(unsafe) var failures = 0

func check(_ name: String, _ condition: Bool) {
    if condition {
        print("  PASS  \(name)")
    } else {
        failures += 1
        print("  FAIL  \(name)")
    }
}

func checkThrows(
    _ name: String,
    _ expected: RefineError,
    _ body: () throws -> Void
) {
    do {
        try body()
        failures += 1
        print("  FAIL  \(name) (에러 없음)")
    } catch let error as RefineError {
        if error == expected {
            print("  PASS  \(name)")
        } else {
            failures += 1
            print("  FAIL  \(name) (다른 에러: \(error))")
        }
    } catch {
        failures += 1
        print("  FAIL  \(name) (예상치 못한 에러: \(error))")
    }
}

final class MockURLProtocol: URLProtocol {
    nonisolated(unsafe) static var handler: ((URLRequest) throws -> (HTTPURLResponse, Data))?
    nonisolated(unsafe) static var requestCount = 0

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        MockURLProtocol.requestCount += 1
        guard let handler = MockURLProtocol.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.unsupportedURL))
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}

    static func reset() {
        handler = nil
        requestCount = 0
    }

    static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    static func apiResponse(_ body: String, status: Int = 200) -> (HTTPURLResponse, Data) {
        let response = HTTPURLResponse(
            url: URL(string: "https://generativelanguage.googleapis.com")!,
            statusCode: status,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        return (response, Data(body.utf8))
    }
}

private func modelResponseBody(refinedText: String) -> String {
    let escaped = refinedText.replacingOccurrences(of: "\"", with: "\\\"")
    return """
    {"candidates":[{"content":{"parts":[{"text":"{\\"refined_text\\": \\"\(escaped)\\", \\"changes\\": []}"}]}}]}
    """
}

// MARK: - Prompts

func promptsTests() {
    print("[Prompts]")
    let polish = Prompts.buildUserPrompt(RefineRequest(text: "내일 3시 회의 잊지마"))
    check("교정 프롬프트에 원문 포함", polish.contains("내일 3시 회의 잊지마"))
    check("교정 지시 포함", polish.contains("맞춤법"))

    let tone = Prompts.buildUserPrompt(RefineRequest(text: "hello", mode: .tone, tone: .business))
    check("톤 라벨 포함", tone.contains("비즈니스"))
    check("어투 변환 지시 포함", tone.contains("어투와 표현만 바꾼다"))

    let summarize = Prompts.buildUserPrompt(RefineRequest(text: "긴 글", mode: .summarize))
    check("요약 지시 포함", summarize.contains("간결하게 줄인다"))

    let context = Prompts.buildUserPrompt(RefineRequest(text: "hello", context: "직속 상사에게 보내는 메시지"))
    check("상황 포함", context.contains("직속 상사에게 보내는 메시지"))

    let ordered = Prompts.buildUserPrompt(
        RefineRequest(text: "x", mode: .tone, tone: .casual, context: "친구에게")
    )
    func offset(of substring: String, in source: String) -> Int {
        guard let range = source.range(of: substring) else { return Int.max }
        return source.distance(from: source.startIndex, to: range.lowerBound)
    }
    let positions = [
        offset(of: "[작업]", in: ordered),
        offset(of: "[변환할 톤]", in: ordered),
        offset(of: "[상황]", in: ordered),
        offset(of: "[원본 메시지]", in: ordered),
    ]
    check("섹션 순서", positions == positions.sorted())
}

// MARK: - Validation

func validationTests() {
    print("[Validation]")
    checkThrows(
        "빈 텍스트 거부", .emptyText,
        { try RefineRequest(text: "   ").validate() }
    )
    checkThrows(
        "톤 미선택 거부", .toneRequired,
        { try RefineRequest(text: "안녕", mode: .tone).validate() }
    )
    do {
        try RefineRequest(text: "안녕", mode: .tone, tone: .formal).validate()
        print("  PASS  유효한 요청 통과")
    } catch {
        failures += 1
        print("  FAIL  유효한 요청 통과 (\(error))")
    }
}

// MARK: - ResultParser

func parserTests() {
    print("[ResultParser]")
    do {
        let result = try ResultParser.parse(#"{"refined_text": "다듬어진 메시지", "changes": ["오타 수정"]}"#)
        check("정상 JSON 파싱", result.refinedText == "다듬어진 메시지" && result.changes == ["오타 수정"])
    } catch {
        failures += 1
        print("  FAIL  정상 JSON 파싱 (\(error))")
    }

    do {
        let result = try ResultParser.parse("```json\n{\"refined_text\": \"결과\", \"changes\": []}\n```")
        check("마크다운 펜스 제거", result.refinedText == "결과")
    } catch {
        failures += 1
        print("  FAIL  마크다운 펜스 제거 (\(error))")
    }

    do {
        let result = try ResultParser.parse(#"{"refined_text": "결과"}"#)
        check("changes 기본값 빈 배열", result.changes.isEmpty)
    } catch {
        failures += 1
        print("  FAIL  changes 기본값 빈 배열 (\(error))")
    }

    do {
        let result = try ResultParser.parse(
            #"{"refined_text": "못 갈 것 같아요", "changes": [{"original": "못갈거같아요", "corrected": "못 갈 것 같아요", "reason": "띄어쓰기 교정", "extra": 1}, "문장 정리"]}"#
        )
        check(
            "구조화 changes 표시 문자열 변환",
            result.changes == ["못갈거같아요 → 못 갈 것 같아요", "문장 정리"]
        )
    } catch {
        failures += 1
        print("  FAIL  구조화 changes 표시 문자열 변환 (\(error))")
    }

    checkThrows(
        "refined_text 누락 거부", .parsingFailed("refined_text 누락"),
        { try ResultParser.parse(#"{"changes": []}"#) }
    )
    checkThrows(
        "빈 결과 거부", .emptyResult,
        { try ResultParser.parse(#"{"refined_text": "   "}"#) }
    )
    checkThrows(
        "JSON 아님 거부", .parsingFailed("JSON이 아닌 응답"),
        { try ResultParser.parse("not json at all") }
    )
}

// MARK: - GeminiClient

func clientTests() async {
    print("[GeminiClient]")

    do {
        MockURLProtocol.reset()
        MockURLProtocol.handler = { _ in
            MockURLProtocol.apiResponse(modelResponseBody(refinedText: "다듬어진 문장"))
        }
        let client = GeminiClient(apiKey: "test-key", maxRetries: 0, session: MockURLProtocol.makeSession())
        let result = try await client.refine(RefineRequest(text: "원본"))
        check("성공 시 파싱 결과 반환", result.refinedText == "다듬어진 문장")
    } catch {
        failures += 1
        print("  FAIL  성공 시 파싱 결과 반환 (\(error))")
    }

    do {
        MockURLProtocol.reset()
        var capturedPath: String?
        MockURLProtocol.handler = { request in
            capturedPath = request.url?.absoluteString
            return MockURLProtocol.apiResponse(modelResponseBody(refinedText: "ok"))
        }
        let client = GeminiClient(apiKey: "test-key", maxRetries: 0, session: MockURLProtocol.makeSession())
        _ = try await client.refine(RefineRequest(text: "원본"))
        check(
            "엔드포인트 경로 확인",
            capturedPath == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
        )
    } catch {
        failures += 1
        print("  FAIL  엔드포인트 경로 확인 (\(error))")
    }

    do {
        MockURLProtocol.reset()
        MockURLProtocol.handler = { _ in
            MockURLProtocol.apiResponse(#"{"error":{"code":429,"message":"quota"}}"#, status: 429)
        }
        let client = GeminiClient(apiKey: "test-key", maxRetries: 0, session: MockURLProtocol.makeSession())
        _ = try await client.refine(RefineRequest(text: "원본"))
        failures += 1
        print("  FAIL  429 rateLimited 에러 (에러 없음)")
    } catch RefineError.rateLimited {
        print("  PASS  429 rateLimited 에러")
    } catch {
        failures += 1
        print("  FAIL  429 rateLimited 에러 (\(error))")
    }

    do {
        MockURLProtocol.reset()
        MockURLProtocol.handler = { _ in
            MockURLProtocol.apiResponse(
                #"{"candidates":[{"content":{"parts":[{"text":"not json"}]}}]"#
            )
        }
        let client = GeminiClient(apiKey: "test-key", maxRetries: 2, session: MockURLProtocol.makeSession())
        do {
            _ = try await client.refine(RefineRequest(text: "원본"))
            failures += 1
            print("  FAIL  파싱 실패 재시도 없음 (에러 없음)")
        } catch {
            check("파싱 실패 재시도 없음", MockURLProtocol.requestCount == 1)
        }
    } catch {
        failures += 1
        print("  FAIL  파싱 실패 재시도 없음 (\(error))")
    }

    do {
        MockURLProtocol.reset()
        MockURLProtocol.handler = { _ in
            MockURLProtocol.apiResponse(#"{"error":{"code":500,"message":"boom"}}"#, status: 500)
        }
        let client = GeminiClient(apiKey: "test-key", maxRetries: 2, session: MockURLProtocol.makeSession())
        do {
            _ = try await client.refine(RefineRequest(text: "원본"))
            failures += 1
            print("  FAIL  서버 오류 최대 재시도 (에러 없음)")
        } catch {
            check("서버 오류 최대 재시도", MockURLProtocol.requestCount == 3)
        }
    } catch {
        failures += 1
        print("  FAIL  서버 오류 최대 재시도 (\(error))")
    }

    do {
        MockURLProtocol.reset()
        let client = GeminiClient(apiKey: "test-key", maxRetries: 0, session: MockURLProtocol.makeSession())
        do {
            _ = try await client.refine(RefineRequest(text: "", mode: .polish))
            failures += 1
            print("  FAIL  유효성 검사가 네트워크 호출 전 (에러 없음)")
        } catch RefineError.emptyText {
            check("유효성 검사가 네트워크 호출 전", MockURLProtocol.requestCount == 0)
        } catch {
            failures += 1
            print("  FAIL  유효성 검사가 네트워크 호출 전 (\(error))")
        }
    } catch {
        failures += 1
        print("  FAIL  유효성 검사가 네트워크 호출 전 (\(error))")
    }
}

// MARK: - ViewModel

@MainActor
func viewModelTests() async {
    print("[ViewModel]")

    final class FakeService: RefiningService {
        let result: Result<RefineResult, Error>
        init(result: Result<RefineResult, Error>) { self.result = result }
        func refine(_ request: RefineRequest) async throws -> RefineResult {
            try result.get()
        }
    }

    do {
        let vm = RefineViewModel(service: FakeService(result: .success(RefineResult(refinedText: "결과"))))
        vm.input = "원본"
        await vm.refine()
        check("성공 시 결과 설정", vm.result?.refinedText == "결과" && vm.errorMessage == nil && !vm.isLoading)
    } catch {
        failures += 1
        print("  FAIL  성공 시 결과 설정 (\(error))")
    }

    do {
        let vm = RefineViewModel(service: FakeService(result: .failure(RefineError.rateLimited)))
        vm.input = "원본"
        await vm.refine()
        check("실패 시 에러 메시지", vm.result == nil && vm.errorMessage == RefineError.rateLimited.message)
    } catch {
        failures += 1
        print("  FAIL  실패 시 에러 메시지 (\(error))")
    }

    do {
        let vm = RefineViewModel(service: FakeService(result: .success(RefineResult(refinedText: "x"))))
        vm.input = "  "
        await vm.refine()
        check("빈 입력 유효성 메시지", vm.errorMessage == RefineError.emptyText.message)
    } catch {
        failures += 1
        print("  FAIL  빈 입력 유효성 메시지 (\(error))")
    }

    do {
        let vm = RefineViewModel(service: FakeService(result: .success(RefineResult(refinedText: "x"))))
        vm.mode = .tone
        vm.tone = nil
        check("톤 모드 기본값 formal", vm.tone == .formal)
    } catch {
        failures += 1
        print("  FAIL  톤 모드 기본값 formal (\(error))")
    }
}

await promptsTests()
await validationTests()
await parserTests()
await clientTests()
await viewModelTests()

print("")
if failures == 0 {
    print("모든 테스트 통과")
} else {
    print("\(failures)개 테스트 실패")
    exit(1)
}
