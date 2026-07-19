// SPDX-License-Identifier: BSD-3-Clause
// Copyright 2026 massif-01

import CoreAILanguageModels
import Foundation
import FoundationModels
import Observation
import SwiftUI

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
  private let compiledModelName = "qwen3_1_7b_w8_4k_ios.h16p.aimodelc"
  private var model: CoreAILanguageModel?
  private var session: LanguageModelSession?

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

  func unloadModel() {
    model?.unload()
    model = nil
    session = nil
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
      let result = try await Self.generate(session: session, prompt: requestPrompt)
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
      !sourceHash.isEmpty
    else {
      throw CompanionError.invalidCompiledAsset(compiledModelName)
    }
    return sourceHash
  }

  private nonisolated static func generate(
    session: LanguageModelSession,
    prompt: String
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
      options: GenerationOptions(temperature: 0, maximumResponseTokens: 256)
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
