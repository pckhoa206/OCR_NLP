#!/usr/bin/env swift
import Foundation
import PDFKit
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

// MARK: - Manifest Models

struct ValidRange: Decodable {
    let book_page_start: Int
    let book_page_end: Int
    let pdf_page_start: Int
    let pdf_page_end: Int
    let step: Int
    let parity: String?
    let valid_pdf_page_count: Int?
    let description: String?
}

struct BookEntry: Decodable {
    let book_id: String
    let code: String
    let deliverable_dir: String
    let source_dir: String
    let title: String
    let pdf_filename: String
    let total_pdf_pages: Int
    let valid_range: ValidRange
    let excluded_pdf_pages_in_valid_range: [Int]?
    let pilot_pages: [Int]
}

struct BookManifest: Decodable {
    let project: String
    let version: String
    let books: [String: BookEntry]
}

// MARK: - CLI Options

enum ExtractionMode {
    case pilot
    case all
}

struct CLIOptions {
    var mode: ExtractionMode = .pilot
    var bookFilter: String? = nil
    var dpi: CGFloat = 216.0 // 3.0x standard 72 DPI points
    var manifestPath: String = "config/book_manifest.json"
    var force: Bool = false
}

func parseArgs() -> CLIOptions {
    var opts = CLIOptions()
    let args = Array(CommandLine.arguments.dropFirst())
    var i = 0
    while i < args.count {
        let arg = args[i]
        switch arg {
        case "--pilot":
            opts.mode = .pilot
        case "--all", "--all-valid":
            opts.mode = .all
        case "--force":
            opts.force = true
        case "--book":
            if i + 1 < args.count {
                opts.bookFilter = args[i + 1].uppercased()
                i += 1
            }
        case "--dpi":
            if i + 1 < args.count, let val = Double(args[i + 1]), val > 0 {
                opts.dpi = CGFloat(val)
                i += 1
            }
        case "--manifest":
            if i + 1 < args.count {
                opts.manifestPath = args[i + 1]
                i += 1
            }
        default:
            break
        }
        i += 1
    }
    return opts
}

// MARK: - PDF Page Rendering

func resolvePDFURL(filename: String, workspaceRoot: URL) -> URL? {
    let directURL = workspaceRoot.appendingPathComponent(filename)
    if FileManager.default.fileExists(atPath: directURL.path) {
        return directURL
    }
    // Fallback: match by Unicode NFC/NFD normalized filename in workspaceRoot
    let targetNFC = filename.precomposedStringWithCanonicalMapping
    if let items = try? FileManager.default.contentsOfDirectory(at: workspaceRoot, includingPropertiesForKeys: nil) {
        for item in items {
            if item.lastPathComponent.precomposedStringWithCanonicalMapping == targetNFC {
                return item
            }
        }
    }
    return nil
}

func isExistingNonEmptyFile(at url: URL) -> Bool {
    guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
          let fileSize = attrs[.size] as? NSNumber else {
        return false
    }
    return fileSize.int64Value > 0
}

func renderPageToPNG(page: PDFPage, destinationURL: URL, dpi: CGFloat) -> Bool {
    let scale = dpi / 72.0
    let box: PDFDisplayBox = .mediaBox
    let pageRect = page.bounds(for: box)
    let rotation = page.rotation
    
    let isRotated90Or270 = (rotation == 90 || rotation == 270)
    let effectiveWidth = isRotated90Or270 ? pageRect.height : pageRect.width
    let effectiveHeight = isRotated90Or270 ? pageRect.width : pageRect.height
    
    let width = max(1, Int(ceil(effectiveWidth * scale)))
    let height = max(1, Int(ceil(effectiveHeight * scale)))
    
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    let bitmapInfo = CGImageAlphaInfo.noneSkipLast.rawValue
    
    guard let context = CGContext(
        data: nil,
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: colorSpace,
        bitmapInfo: bitmapInfo
    ) else {
        fputs("Error: Failed to create CGContext (\(width)x\(height))\n", stderr)
        return false
    }
    
    context.interpolationQuality = .high
    context.setFillColor(red: 1.0, green: 1.0, blue: 1.0, alpha: 1.0)
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    
    context.saveGState()
    context.scaleBy(x: scale, y: scale)
    page.draw(with: box, to: context)
    context.restoreGState()
    
    guard let cgImage = context.makeImage() else {
        fputs("Error: Failed to create CGImage from context\n", stderr)
        return false
    }
    
    let pngType = UTType.png.identifier as CFString
    guard let destination = CGImageDestinationCreateWithURL(destinationURL as CFURL, pngType, 1, nil) else {
        fputs("Error: Failed to create CGImageDestination at \(destinationURL.path)\n", stderr)
        return false
    }
    
    CGImageDestinationAddImage(destination, cgImage, nil)
    return CGImageDestinationFinalize(destination)
}

func pagesToExtract(for book: BookEntry, mode: ExtractionMode) -> [Int] {
    switch mode {
    case .pilot:
        return book.pilot_pages.sorted()
    case .all:
        let excluded = Set(book.excluded_pdf_pages_in_valid_range ?? [])
        let start = book.valid_range.pdf_page_start
        let end = book.valid_range.pdf_page_end
        let step = max(1, book.valid_range.step)
        var pages: [Int] = []
        var p = start
        while p <= end {
            if !excluded.contains(p) {
                pages.append(p)
            }
            p += step
        }
        return pages
    }
}

// MARK: - Main Execution

let options = parseArgs()
let workspaceRoot = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let manifestURL = workspaceRoot.appendingPathComponent(options.manifestPath)

guard let manifestData = try? Data(contentsOf: manifestURL) else {
    fputs("Error: Could not read manifest at \(manifestURL.path)\n", stderr)
    exit(1)
}

let decoder = JSONDecoder()
guard let manifest = try? decoder.decode(BookManifest.self, from: manifestData) else {
    fputs("Error: Could not decode JSON manifest at \(manifestURL.path)\n", stderr)
    exit(1)
}

let bookOrder = ["HVTT", "TVLT2", "TLTVN"]
var totalExtracted = 0
var totalSkipped = 0
var totalFailed = 0

for key in bookOrder {
    if let filter = options.bookFilter, filter != key {
        continue
    }
    guard let book = manifest.books[key] else {
        fputs("Warning: Book key \(key) not found in manifest\n", stderr)
        continue
    }
    
    guard let pdfURL = resolvePDFURL(filename: book.pdf_filename, workspaceRoot: workspaceRoot) else {
        fputs("Error: PDF file not found for \(key): \(book.pdf_filename)\n", stderr)
        totalFailed += 1
        continue
    }
    
    guard let pdfDoc = PDFDocument(url: pdfURL) else {
        fputs("Error: Failed to open PDFDocument at \(pdfURL.path)\n", stderr)
        totalFailed += 1
        continue
    }
    
    let outDirURL = workspaceRoot.appendingPathComponent(book.source_dir)
    do {
        try FileManager.default.createDirectory(at: outDirURL, withIntermediateDirectories: true)
    } catch {
        fputs("Error: Failed to create output directory \(outDirURL.path): \(error)\n", stderr)
        totalFailed += 1
        continue
    }
    
    let targetPages = pagesToExtract(for: book, mode: options.mode)
    let totalForBook = targetPages.count
    print("[\(book.book_id)] Extracting \(totalForBook) pages (\(options.mode == .pilot ? "pilot" : "all-valid")) from '\(book.title)' (PDF pages: \(pdfDoc.pageCount))...")
    fflush(stdout)
    
    for (idx, pdfPageNum) in targetPages.enumerated() {
        autoreleasepool {
            let fileName = String(format: "%04d.png", pdfPageNum)
            let fileURL = outDirURL.appendingPathComponent(fileName)
            let progressCount = idx + 1
            let shouldLogProgress = (options.mode == .pilot) || (progressCount == 1) || (progressCount == totalForBook) || (progressCount % 50 == 0)
            
            if !options.force && isExistingNonEmptyFile(at: fileURL) {
                totalSkipped += 1
                if shouldLogProgress {
                    print("  [\(progressCount)/\(totalForBook)] Skipped existing \(book.source_dir)/\(fileName)")
                    fflush(stdout)
                }
                return
            }
            
            let pageIndex = pdfPageNum - 1 // PDFKit is 0-indexed
            guard pageIndex >= 0 && pageIndex < pdfDoc.pageCount,
                  let page = pdfDoc.page(at: pageIndex) else {
                fputs("  [!] Page \(pdfPageNum) out of bounds for \(book.book_id)\n", stderr)
                totalFailed += 1
                return
            }
            
            if renderPageToPNG(page: page, destinationURL: fileURL, dpi: options.dpi) {
                totalExtracted += 1
                if shouldLogProgress {
                    print("  [\(progressCount)/\(totalForBook)] Saved \(book.source_dir)/\(fileName)")
                    fflush(stdout)
                }
            } else {
                fputs("  [!] Failed to render \(book.source_dir)/\(fileName)\n", stderr)
                totalFailed += 1
            }
        }
    }
}

print("Done. Extracted \(totalExtracted) PNG page(s), skipped \(totalSkipped) existing page(s), \(totalFailed) failure(s).")
fflush(stdout)
if totalFailed > 0 {
    exit(1)
}
