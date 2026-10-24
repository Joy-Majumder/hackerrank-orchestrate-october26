import Foundation
import Vision

for path in CommandLine.arguments.dropFirst() {
    do {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        try VNImageRequestHandler(url: URL(fileURLWithPath: path), options: [:]).perform([request])
        let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        for line in lines {
            print("\(path)\t\(line.replacingOccurrences(of: "\t", with: " "))")
        }
    } catch {
        fputs("OCR failed for \(path): \(error)\n", stderr)
    }
}
