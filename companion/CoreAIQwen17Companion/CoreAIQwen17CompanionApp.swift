// SPDX-License-Identifier: BSD-3-Clause
// Copyright 2026 massif-01

import CoreAILanguageModels
import CryptoKit
import Foundation
import FoundationModels
import Observation
import OSLog
import SwiftUI
import UIKit

@main
struct CoreAIQwen17CompanionApp: App {
  var body: some Scene {
    WindowGroup {
      CompanionView()
    }
  }
}

private struct GenerationResult: Sendable {
  let content: String
  let inputTokens: Int
  let cachedInputTokens: Int
  let outputTokens: Int
  let reasoningTokens: Int
  let timeToFirstTokenSeconds: Double
  let totalSeconds: Double
}

private enum CompanionError: LocalizedError {
  case modelNotLoaded
  case missingResourceDirectory
  case missingModelBundle(String)
  case invalidCompiledAsset(String)
  case noStreamSnapshots
  case smokeMismatch(String)
  case contextOverflow(Int)
  case tracePrerequisiteMismatch(String)

  var errorDescription: String? {
    switch self {
    case .modelNotLoaded:
      "Load the model before sending a prompt."
    case .missingResourceDirectory:
      "The app resource directory is unavailable."
    case .missingModelBundle(let name):
      "Missing model resource folder: \(name)"
    case .invalidCompiledAsset(let name):
      "The compiled h16p asset is missing or has the wrong sourceHash: \(name)"
    case .noStreamSnapshots:
      "The response stream ended without producing a snapshot."
    case .smokeMismatch(let content):
      "Deterministic smoke expected COREAI-OK, received: \(content)"
    case .contextOverflow(let tokens):
      "The request used \(tokens) tokens, exceeding the locked 4096-token context."
    case .tracePrerequisiteMismatch(let content):
      "The trace prerequisite request returned an unexpected response: \(content)"
    }
  }
}

@MainActor
@Observable
final class CompanionState {
  var status = "Not loaded"
  var prompt =
    "Explain in two sentences why on-device inference helps protect private data. /no_think"
  var output = ""
  var metrics = ""
  var isBusy = false

  private let modelBundleName = "qwen3_1_7b_w8_4k_ios"
  private let compiledModelName = "qwen3_1_7b_coreai_ane_w8_4k.h16p.aimodelc"
  private let expectedSourceHash =
    "5e885ec407f1b2690df5098d38b1bed4a3e66f4352c859fb2bb79666bc0aef73"
  private let publicArtifactRepository = "massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p"
  private let publicArtifactRevision = "466ebe2e5cec125fa113ea71503add41bba581a8"
  private let coreAISourceRevision = "04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a"
  private let traceInstructions =
    "Follow the user's request exactly. Return only the requested answer and no reasoning."
  private let traceSmokePrompt = "Reply with exactly COREAI-OK and no other text. /no_think"
  private let traceWarmupPrompt = "Reply with exactly COREAI-WARMUP-OK and no other text. /no_think"
  private let traceMeasuredPrompt =
    "Reply with exactly PUBLIC-W8-TRACE-OK and no other text. /no_think"
  private static let traceSubsystem = "io.massif.qwen3.coreai.trace-confirmation"
  private static let traceCategory = "inference"
  private static let traceIntervalName: StaticString = "PUBLIC_W8_TRACE_CONFIRMATION_V1"
  private static let traceLog = OSLog(
    subsystem: traceSubsystem,
    category: traceCategory
  )
  private static let traceLogger = Logger(
    subsystem: traceSubsystem,
    category: traceCategory
  )
  private var model: CoreAILanguageModel?
  private var session: LanguageModelSession?
  private var loadedSourceHash: String?

  func loadModel() async {
    guard !isBusy else { return }
    guard model == nil else {
      status = "Ready"
      return
    }
    isBusy = true
    defer { isBusy = false }
    status = "Loading"
    output = ""
    metrics = ""

    do {
      guard let resources = Bundle.main.resourceURL else {
        throw CompanionError.missingResourceDirectory
      }
      let modelURL = resources.appending(path: modelBundleName, directoryHint: .isDirectory)
      guard FileManager.default.fileExists(atPath: modelURL.path) else {
        throw CompanionError.missingModelBundle(modelBundleName)
      }

      let sourceHash = try validateCompiledAsset(in: modelURL)
      let started = ContinuousClock.now
      let loadedModel = try await CoreAILanguageModel(
        resourcesAt: modelURL,
        mode: .eager,
        kvCacheStrategy: .fixedSize
      )
      let loadSeconds = started.duration(to: .now).seconds
      model = loadedModel
      loadedSourceHash = sourceHash
      session = LanguageModelSession(
        model: loadedModel,
        instructions: "Follow the user's request and return only the requested answer."
      )
      status = "Ready"
      metrics = String(
        format: "load=%.3fs estimatedDiskBytes=%lld sourceHash=%@", loadSeconds,
        loadedModel.estimatedSizeOnDiskBytes ?? -1,
        String(sourceHash.prefix(12)))
      print(String(format: "COREAI_COMPANION_LOAD_PASS seconds=%.3f", loadSeconds))
    } catch {
      status = "Load failed"
      output = String(reflecting: error)
      print("COREAI_COMPANION_LOAD_FAIL error=\(String(reflecting: error))")
    }
  }

  func runDeterministicSmoke() async {
    prompt = "Reply with exactly COREAI-OK and no other text. /no_think"
    await send(expectExact: "COREAI-OK")
  }

  func sendPrompt() async {
    await send(expectExact: nil)
  }

  /// Runs the preregistered ANE trace confirmation sequence. Session creation,
  /// a deterministic smoke test, and warm-up all precede the owned signpost
  /// interval. Exactly one measured generation request is made inside it.
  func runPublicW8TraceConfirmation() async {
    guard !isBusy else { return }
    isBusy = true
    defer { isBusy = false }
    status = "Preparing trace confirmation"
    output = ""
    metrics = ""

    let runUUID = UUID()
    let pid = ProcessInfo.processInfo.processIdentifier
    recordTraceEvent(
      "prerequisites_begin",
      runUUID: runUUID,
      fields: traceEnvironmentFields(pid: pid)
    )

    do {
      guard let model, let sourceHash = loadedSourceHash else {
        throw CompanionError.modelNotLoaded
      }
      guard sourceHash == expectedSourceHash else {
        throw CompanionError.invalidCompiledAsset(compiledModelName)
      }

      // This dedicated session is created before both the warm-up and the
      // measured interval so no session setup is included in the trace window.
      let prerequisiteSession = LanguageModelSession(
        model: model,
        instructions: traceInstructions
      )
      let smoke = try await Self.generate(
        session: prerequisiteSession,
        prompt: traceSmokePrompt,
        maximumResponseTokens: 16
      )
      try requireExactTraceResponse(smoke.content, expected: "COREAI-OK")
      var smokeFields = generationFields(smoke)
      smokeFields["pid"] = pid
      smokeFields["wall_clock_utc"] = Self.utcTimestamp()
      recordTraceEvent(
        "smoke_complete",
        runUUID: runUUID,
        fields: smokeFields
      )

      let warmup = try await Self.generate(
        session: prerequisiteSession,
        prompt: traceWarmupPrompt,
        maximumResponseTokens: 16
      )
      try requireExactTraceResponse(warmup.content, expected: "COREAI-WARMUP-OK")
      var warmupFields = generationFields(warmup)
      warmupFields["pid"] = pid
      warmupFields["wall_clock_utc"] = Self.utcTimestamp()
      recordTraceEvent(
        "warmup_complete",
        runUUID: runUUID,
        fields: warmupFields
      )

      // Keep the measured prompt independent of the smoke/warm-up conversation
      // while still creating its session before the owned interval.
      let measuredSession = LanguageModelSession(
        model: model,
        instructions: traceInstructions
      )
      recordTraceEvent(
        "measured_session_ready",
        runUUID: runUUID,
        fields: [
          "pid": pid,
          "wall_clock_utc": Self.utcTimestamp(),
        ]
      )

      status = "Trace confirmation running"
      let signpostID = OSSignpostID(log: Self.traceLog)
      let promptSHA256 = Self.sha256(traceMeasuredPrompt)
      let startedAt = Self.utcTimestamp()
      recordTraceEvent(
        "measured_request_begin",
        runUUID: runUUID,
        fields: [
          "pid": pid,
          "prompt_sha256": promptSHA256,
          "wall_clock_utc": startedAt,
        ]
      )
      os_signpost(
        .begin,
        log: Self.traceLog,
        name: Self.traceIntervalName,
        signpostID: signpostID,
        "run_uuid=%{public}@ pid=%{public}d terminal=%{public}@",
        runUUID.uuidString as NSString,
        pid,
        "started" as NSString
      )

      do {
        let result = try await Self.generate(
          session: measuredSession,
          prompt: traceMeasuredPrompt,
          maximumResponseTokens: 64
        )
        os_signpost(
          .end,
          log: Self.traceLog,
          name: Self.traceIntervalName,
          signpostID: signpostID,
          "run_uuid=%{public}@ pid=%{public}d terminal=%{public}@ input_tokens=%{public}d emitted_tokens=%{public}d",
          runUUID.uuidString as NSString,
          pid,
          "completed" as NSString,
          result.inputTokens,
          result.outputTokens
        )
        let endedAt = Self.utcTimestamp()
        var fields = generationFields(result)
        fields["pid"] = pid
        fields["prompt_sha256"] = promptSHA256
        fields["terminal_state"] = "completed"
        fields["wall_clock_utc"] = endedAt
        recordTraceEvent("measured_request_end", runUUID: runUUID, fields: fields)

        output = result.content
        metrics = String(
          format: "run=%@ input=%d emitted=%d total=%.3fs",
          String(runUUID.uuidString.prefix(8)),
          result.inputTokens,
          result.outputTokens,
          result.totalSeconds
        )
        status = "Trace confirmation complete"
      } catch {
        os_signpost(
          .end,
          log: Self.traceLog,
          name: Self.traceIntervalName,
          signpostID: signpostID,
          "run_uuid=%{public}@ pid=%{public}d terminal=%{public}@",
          runUUID.uuidString as NSString,
          pid,
          "error" as NSString
        )
        let endedAt = Self.utcTimestamp()
        recordTraceEvent(
          "measured_request_end",
          runUUID: runUUID,
          fields: [
            "pid": pid,
            "prompt_sha256": promptSHA256,
            "terminal_state": "error",
            "wall_clock_utc": endedAt,
          ]
        )
        throw error
      }
    } catch {
      status = "Trace confirmation failed"
      output = String(reflecting: error)
    }
  }

  func unloadModel() {
    model?.unload()
    model = nil
    session = nil
    loadedSourceHash = nil
    status = "Not loaded"
    metrics = ""
    print("COREAI_COMPANION_UNLOAD")
  }

  private func send(expectExact: String?) async {
    guard !isBusy else { return }
    isBusy = true
    defer { isBusy = false }
    status = "Generating"
    output = ""
    metrics = ""

    do {
      guard let session else { throw CompanionError.modelNotLoaded }
      let requestPrompt = prompt
      let result = try await Self.generate(
        session: session,
        prompt: requestPrompt,
        maximumResponseTokens: 256
      )
      let totalTokens = result.inputTokens + result.outputTokens
      guard totalTokens <= 4096 else {
        throw CompanionError.contextOverflow(totalTokens)
      }
      if let expectExact,
        result.content.trimmingCharacters(in: .whitespacesAndNewlines) != expectExact
      {
        throw CompanionError.smokeMismatch(result.content)
      }

      output = result.content
      metrics = String(
        format: "input=%d cached=%d output=%d reasoning=%d ttft=%.3fs total=%.3fs",
        result.inputTokens,
        result.cachedInputTokens,
        result.outputTokens,
        result.reasoningTokens,
        result.timeToFirstTokenSeconds,
        result.totalSeconds
      )
      status = expectExact == nil ? "Complete" : "Smoke passed"
      print(
        String(
          format:
            "COREAI_COMPANION_RESPONSE_PASS mode=%@ input=%d cached=%d output=%d reasoning=%d ttft=%.3f total=%.3f",
          expectExact == nil ? "interactive" : "deterministic_smoke",
          result.inputTokens,
          result.cachedInputTokens,
          result.outputTokens,
          result.reasoningTokens,
          result.timeToFirstTokenSeconds,
          result.totalSeconds
        ))
    } catch {
      status = "Generation failed"
      output = String(reflecting: error)
      print("COREAI_COMPANION_RESPONSE_FAIL error=\(String(reflecting: error))")
    }
  }

  private func validateCompiledAsset(in modelURL: URL) throws -> String {
    let compiledURL = modelURL.appending(path: compiledModelName, directoryHint: .isDirectory)
    let mainURL = compiledURL.appending(path: "main-h16p.mlirb")
    let metadataURL = compiledURL.appending(path: "metadata.json")
    guard FileManager.default.fileExists(atPath: mainURL.path),
      let data = try? Data(contentsOf: metadataURL),
      let metadata = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
      let sourceHash = metadata["sourceHash"] as? String,
      sourceHash.lowercased() == expectedSourceHash
    else {
      throw CompanionError.invalidCompiledAsset(compiledModelName)
    }
    return sourceHash.lowercased()
  }

  private nonisolated static func generate(
    session: LanguageModelSession,
    prompt: String,
    maximumResponseTokens: Int
  ) async throws -> GenerationResult {
    let started = ContinuousClock.now
    var firstSnapshotAt: ContinuousClock.Instant?
    var content = ""
    var inputTokens = 0
    var cachedInputTokens = 0
    var outputTokens = 0
    var reasoningTokens = 0
    var snapshotCount = 0

    let stream = session.streamResponse(
      to: prompt,
      options: GenerationOptions(
        temperature: 0,
        maximumResponseTokens: maximumResponseTokens
      )
    )
    for try await snapshot in stream {
      snapshotCount += 1
      if firstSnapshotAt == nil {
        firstSnapshotAt = .now
      }
      content = snapshot.content
      inputTokens = snapshot.usage.input.totalTokenCount
      cachedInputTokens = snapshot.usage.input.cachedTokenCount
      outputTokens = snapshot.usage.output.totalTokenCount
      reasoningTokens = snapshot.usage.output.reasoningTokenCount
    }

    guard snapshotCount > 0, let firstSnapshotAt else {
      throw CompanionError.noStreamSnapshots
    }
    let ended = ContinuousClock.now
    return GenerationResult(
      content: content,
      inputTokens: inputTokens,
      cachedInputTokens: cachedInputTokens,
      outputTokens: outputTokens,
      reasoningTokens: reasoningTokens,
      timeToFirstTokenSeconds: started.duration(to: firstSnapshotAt).seconds,
      totalSeconds: started.duration(to: ended).seconds
    )
  }

  private func requireExactTraceResponse(_ content: String, expected: String) throws {
    guard content.trimmingCharacters(in: .whitespacesAndNewlines) == expected else {
      throw CompanionError.tracePrerequisiteMismatch(content)
    }
  }

  private func generationFields(_ result: GenerationResult) -> [String: Any] {
    [
      "cached_input_tokens": result.cachedInputTokens,
      "emitted_tokens": result.outputTokens,
      "input_tokens": result.inputTokens,
      "reasoning_tokens": result.reasoningTokens,
      "time_to_first_token_seconds": result.timeToFirstTokenSeconds,
      "total_seconds": result.totalSeconds,
    ]
  }

  private func traceEnvironmentFields(pid: Int32) -> [String: Any] {
    let process = ProcessInfo.processInfo
    return [
      "app_bundle_identifier": Bundle.main.bundleIdentifier ?? NSNull(),
      "app_executable_sha256": Self.currentExecutableSHA256(),
      "artifact_repository": publicArtifactRepository,
      "artifact_revision": publicArtifactRevision,
      "artifact_source_hash": loadedSourceHash ?? NSNull(),
      "coreai_source_revision": coreAISourceRevision,
      "device_identifier_class": Self.deviceIdentifierClass(),
      "device_model": Self.deviceModelName(),
      "low_power_mode_enabled": process.isLowPowerModeEnabled,
      "os_build": Self.systemControlString("kern.osversion"),
      "os_version": UIDevice.current.systemVersion,
      "pid": pid,
      "thermal_state": Self.thermalStateName(process.thermalState),
      "wall_clock_utc": Self.utcTimestamp(),
    ]
  }

  private func recordTraceEvent(
    _ event: String,
    runUUID: UUID,
    fields: [String: Any]
  ) {
    guard let allowedFields = traceAllowedFields(event: event, fields: fields),
      Set(fields.keys) == allowedFields
    else {
      assertionFailure("Trace event fields differ from the public allowlist")
      return
    }
    var record = fields
    record["event"] = event
    record["run_uuid"] = runUUID.uuidString.lowercased()
    record["schema"] = "public-w8-trace-confirmation-app-record-v2"
    guard JSONSerialization.isValidJSONObject(record),
      let data = try? JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]),
      let json = String(data: data, encoding: .utf8)
    else {
      assertionFailure("Trace record could not be serialized")
      return
    }
    Self.traceLogger.notice("ANE_TRACE_V2_JSON=\(json, privacy: .public)")
  }

  private func traceAllowedFields(
    event: String,
    fields: [String: Any]
  ) -> Set<String>? {
    let generationFields: Set<String> = [
      "cached_input_tokens",
      "emitted_tokens",
      "input_tokens",
      "reasoning_tokens",
      "time_to_first_token_seconds",
      "total_seconds",
    ]
    switch event {
    case "prerequisites_begin":
      return [
        "app_bundle_identifier",
        "app_executable_sha256",
        "artifact_repository",
        "artifact_revision",
        "artifact_source_hash",
        "coreai_source_revision",
        "device_identifier_class",
        "device_model",
        "low_power_mode_enabled",
        "os_build",
        "os_version",
        "pid",
        "thermal_state",
        "wall_clock_utc",
      ]
    case "smoke_complete", "warmup_complete":
      return generationFields.union(["pid", "wall_clock_utc"])
    case "measured_session_ready":
      return ["pid", "wall_clock_utc"]
    case "measured_request_begin":
      return ["pid", "prompt_sha256", "wall_clock_utc"]
    case "measured_request_end":
      let common: Set<String> = [
        "pid", "prompt_sha256", "terminal_state", "wall_clock_utc",
      ]
      if fields["terminal_state"] as? String == "completed" {
        return generationFields.union(common)
      }
      if fields["terminal_state"] as? String == "error" {
        return common
      }
      return nil
    default:
      return nil
    }
  }

  private nonisolated static func sha256(_ value: String) -> String {
    SHA256.hash(data: Data(value.utf8)).map { String(format: "%02x", $0) }.joined()
  }

  private nonisolated static func currentExecutableSHA256() -> String {
    guard let path = Bundle.main.executablePath,
      let handle = FileHandle(forReadingAtPath: path)
    else {
      return "unavailable"
    }
    defer { try? handle.close() }
    var hasher = SHA256()
    while true {
      let data = handle.readData(ofLength: 1024 * 1024)
      if data.isEmpty { break }
      hasher.update(data: data)
    }
    return hasher.finalize().map { String(format: "%02x", $0) }.joined()
  }

  private nonisolated static func utcTimestamp() -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    formatter.timeZone = TimeZone(secondsFromGMT: 0)
    return formatter.string(from: Date())
  }

  private nonisolated static func thermalStateName(
    _ state: ProcessInfo.ThermalState
  ) -> String {
    switch state {
    case .nominal: "nominal"
    case .fair: "fair"
    case .serious: "serious"
    case .critical: "critical"
    @unknown default: "unknown"
    }
  }

  private nonisolated static func deviceIdentifierClass() -> String {
    var systemInfo = utsname()
    guard uname(&systemInfo) == 0 else { return "unknown" }
    var machine = systemInfo.machine
    let capacity = MemoryLayout.size(ofValue: machine)
    return withUnsafePointer(to: &machine) { pointer in
      pointer.withMemoryRebound(
        to: UInt8.self,
        capacity: capacity
      ) { bytes in
        let buffer = UnsafeBufferPointer(start: bytes, count: capacity)
        let count = buffer.firstIndex(of: 0) ?? capacity
        return String(decoding: buffer.prefix(count), as: UTF8.self)
      }
    }
  }

  private static func deviceModelName() -> String {
    switch deviceIdentifierClass() {
    case "iPhone16,1": "iPhone 15 Pro"
    default: UIDevice.current.model
    }
  }

  private nonisolated static func systemControlString(_ name: String) -> String {
    var size = 0
    guard sysctlbyname(name, nil, &size, nil, 0) == 0, size > 0 else {
      return "unknown"
    }
    var value = [CChar](repeating: 0, count: size)
    guard sysctlbyname(name, &value, &size, nil, 0) == 0 else {
      return "unknown"
    }
    let bytes = value.prefix { $0 != 0 }.map { UInt8(bitPattern: $0) }
    return String(decoding: bytes, as: UTF8.self)
  }
}

extension Duration {
  fileprivate var seconds: Double {
    let components = self.components
    return Double(components.seconds) + Double(components.attoseconds) / 1e18
  }
}

private struct CompanionView: View {
  @State private var state = CompanionState()

  var body: some View {
    NavigationStack {
      Form {
        Section("Model") {
          Text(state.status)
          if !state.metrics.isEmpty {
            Text(state.metrics)
              .font(.footnote.monospacedDigit())
              .textSelection(.enabled)
          }
          HStack {
            Button("Load model") {
              Task { await state.loadModel() }
            }
            Button("Unload") {
              state.unloadModel()
            }
          }
          .disabled(state.isBusy)
        }

        Section("Prompt") {
          TextEditor(text: $state.prompt)
            .frame(minHeight: 120)
          Button("Run deterministic smoke") {
            Task { await state.runDeterministicSmoke() }
          }
          .disabled(state.isBusy)
          Button("Send") {
            Task { await state.sendPrompt() }
          }
          .buttonStyle(.borderedProminent)
          .disabled(state.isBusy || state.prompt.isEmpty)
          Button("Run public W8 trace confirmation") {
            Task { await state.runPublicW8TraceConfirmation() }
          }
          .disabled(state.isBusy)
        }

        Section("Output") {
          Text(state.output.isEmpty ? "No response yet" : state.output)
            .textSelection(.enabled)
        }
      }
      .navigationTitle("Qwen3-1.7B · Core AI")
    }
  }
}
