"""macOS native OCR using Vision framework — zero external dependencies.

Uses a tiny Swift helper that calls VNRecognizeTextRequest.
This is faster and more accurate for Chinese text than Tesseract,
and doesn't require any downloads since Vision is built into macOS.
"""

import subprocess
import tempfile
import os

SWIFT_HELPER = r'''
import Vision
import Foundation
import AppKit

let args = CommandLine.arguments
guard args.count >= 2 else {
    print("USAGE: ocr_helper <image_path>")
    exit(1)
}

let imagePath = args[1]
guard let img = NSImage(contentsOfFile: imagePath),
      let cgImg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("ERROR: Cannot load image")
    exit(1)
}

let semaphore = DispatchSemaphore(value: 0)
var resultText = ""

let request = VNRecognizeTextRequest { (request, error) in
    defer { semaphore.signal() }
    guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
    resultText = observations
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: "\n")
}

request.recognitionLevel = .accurate
request.recognitionLanguages = ["zh-Hans", "en-US"]
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImg, options: [:])
try? handler.perform([request])

semaphore.wait()
print(resultText)
'''

_HELPER_PATH = None


def _get_helper_path() -> str:
    """Compile the Swift helper once and cache the path."""
    global _HELPER_PATH
    if _HELPER_PATH and os.path.exists(_HELPER_PATH):
        return _HELPER_PATH

    # Write Swift source to temp file
    swift_src = tempfile.mktemp(suffix=".swift")
    with open(swift_src, "w") as f:
        f.write(SWIFT_HELPER)

    # Compile
    binary = os.path.join(tempfile.gettempdir(), "douyin_ocr_helper")
    result = subprocess.run(
        ["swiftc", swift_src, "-o", binary],
        capture_output=True, text=True
    )

    os.unlink(swift_src)  # Clean up source

    if result.returncode != 0:
        raise RuntimeError(f"Swift compile failed: {result.stderr}")

    _HELPER_PATH = binary
    return binary


def ocr_image(image_path: str) -> str:
    """Run OCR on an image file using macOS Vision framework.

    Args:
        image_path: Path to PNG or JPEG file

    Returns:
        Extracted text (Chinese + English)
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    helper = _get_helper_path()
    result = subprocess.run(
        [helper, image_path],
        capture_output=True, text=True, timeout=30
    )

    if result.returncode != 0:
        raise RuntimeError(f"OCR failed: {result.stderr}")

    return result.stdout.strip()


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Run OCR on image bytes. Writes to temp file first."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(image_bytes)
        tmp_path = f.name

    try:
        return ocr_image(tmp_path)
    finally:
        os.unlink(tmp_path)
