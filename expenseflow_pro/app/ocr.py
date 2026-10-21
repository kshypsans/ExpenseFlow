"""Receipt OCR and heuristic field extraction.

Tesseract is the OCR engine. Pillow/OpenCV preprocessing and multiple Tesseract
page-segmentation modes improve resilience to phone photos and scanned receipts.
The output is always intended for user review, never silent financial automation.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path


def _load_pages(path):
    """Yield PIL images from a supported image or PDF file."""
    from PIL import Image, ImageOps
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise RuntimeError("PDF support is missing. Install the project requirements and try again.") from exc
        document = fitz.open(path)
        try:
            for page_number in range(min(3, document.page_count)):
                page = document.load_page(page_number)
                pix = page.get_pixmap(matrix=fitz.Matrix(2.4, 2.4), alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                yield ImageOps.exif_transpose(image)
        finally:
            document.close()
    else:
        with Image.open(path) as source:
            yield ImageOps.exif_transpose(source.copy())


def _preprocess_variants(image):
    """Return several OCR-friendly views without modifying the uploaded original."""
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    import io

    image = image.convert("RGB")
    # Keep OCR text large enough for Tesseract; avoid wasting time on huge camera images.
    max_side = 2600
    if max(image.size) > max_side:
        ratio = max_side / max(image.size)
        image = image.resize((int(image.width * ratio), int(image.height * ratio)), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    if min(gray.size) < 1200:
        scale = min(2.0, 1200 / max(1, min(gray.size)))
        gray = gray.resize((int(gray.width * scale), int(gray.height * scale)), Image.Resampling.LANCZOS)

    variants = [gray, ImageEnhance.Contrast(gray).enhance(1.8), ImageEnhance.Sharpness(gray).enhance(2.0)]
    # Adaptive thresholding is particularly useful for uneven lighting. OpenCV is a
    # declared dependency, but keep a Pillow-only fallback for constrained installs.
    try:
        import cv2
        import numpy as np
        array = np.array(gray)
        denoised = cv2.fastNlMeansDenoising(array, None, 10, 7, 21)
        adaptive = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 31, 11)
        variants.append(Image.fromarray(adaptive))
        _, otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(Image.fromarray(otsu))
    except Exception:
        variants.append(gray.point(lambda pixel: 255 if pixel > 165 else 0))
    return variants


def extract_text(path):
    """OCR one image/PDF using multiple preprocessing and layout strategies."""
    try:
        import pytesseract
        from PIL import Image  # noqa: F401 - verifies Pillow availability
        configured_tesseract = os.environ.get("TESSERACT_CMD", "").strip()
        if configured_tesseract:
            pytesseract.pytesseract.tesseract_cmd = configured_tesseract
    except ImportError:
        return "", "OCR packages are missing. Run: py -m pip install -r requirements.txt"
    try:
        all_text = []
        for page in _load_pages(path):
            candidates = []
            for image in _preprocess_variants(page):
                for psm in (6, 4, 11):
                    try:
                        result = pytesseract.image_to_data(
                            image, config=f"--oem 3 --psm {psm}",
                            output_type=pytesseract.Output.DICT,
                        )
                        lines, words, weighted_conf, total_weight = {}, [], 0.0, 0
                        for idx, (word, confidence) in enumerate(zip(result.get("text", []), result.get("conf", []))):
                            word = (word or "").strip()
                            try:
                                conf = float(confidence)
                            except (ValueError, TypeError):
                                conf = -1
                            if word and conf >= 0:
                                words.append(word)
                                weighted_conf += conf * max(1, len(word))
                                total_weight += max(1, len(word))
                                key = (result.get("block_num", [0])[idx], result.get("par_num", [0])[idx], result.get("line_num", [idx])[idx])
                                lines.setdefault(key, []).append(word)
                        line_text = "\n".join(" ".join(parts) for parts in lines.values()).strip()
                        score = (weighted_conf / total_weight if total_weight else 0) + min(len(line_text), 1800) / 180
                        if line_text:
                            candidates.append((score, line_text))
                    except Exception:
                        continue
            if candidates:
                # Favor readable, well-populated results; preserve line structure for parsing.
                best = max(candidates, key=lambda item: item[0])[1]
                all_text.append(best)
        text = "\n\n--- Next page ---\n\n".join(all_text).strip()
        if not text:
            return "", "No readable text was detected. Try a sharper, brighter photo or enter the details manually."
        return text, None
    except RuntimeError as exc:
        return "", str(exc)
    except Exception:
        return "", "Tesseract could not process this file. Check that Tesseract OCR is installed and on PATH, then try a clearer receipt."


MONEY_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:₹|Rs\.?|INR|USD|\$|€|£|GBP)?\s*"
    r"([-+]?(?:\d{1,3}(?:[, ]\d{3})+|\d{1,8})(?:\.\d{1,2})?)(?!\d)", re.I
)
TOTAL_RE = re.compile(
    r"\b(grand\s*total|total\s*due|amount\s*due|net\s*payable|invoice\s*total|bill\s*total|net\s*total|total|balance\s*due|amount\s*payable|payable)\b",
    re.I,
)


def _money_values(line):
    values = []
    for match in MONEY_RE.finditer(line):
        raw = match.group(1).replace(",", "").replace(" ", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if 0 <= value < 100_000_000:
            values.append(value)
    return values


def parse_receipt(text):
    lines = [re.sub(r"\s+", " ", line).strip(" |\t") for line in text.splitlines() if line.strip()]
    # Ignore generic OCR debris when selecting the likely merchant line.
    noise = re.compile(r"(receipt|tax invoice|invoice no|gstin|phone|tel:|date:|cashier|thank you|www\.|http)", re.I)
    vendor = next((line[:120] for line in lines[:10]
                   if len(re.sub(r"[^A-Za-z]", "", line)) >= 3 and not noise.search(line)),
                  "Unknown vendor")

    amount = 0.0
    # Search total labels first. Some receipts put the label and value on adjacent lines.
    for index, line in enumerate(lines):
        if TOTAL_RE.search(line):
            candidates = _money_values(line)
            if not candidates and index + 1 < len(lines):
                candidates = _money_values(lines[index + 1])
            if candidates:
                # Total lines commonly contain subtotal/tax plus final amount: use last number.
                amount = candidates[-1]
                break
    if amount == 0:
        candidates = []
        for line in lines:
            values = _money_values(line)
            # Exclude dates, telephone numbers, and likely item codes.
            if len(values) == 1 and not re.search(r"\b(?:phone|mobile|tel|gstin|zip|postal)\b", line, re.I):
                candidates.extend(v for v in values if v > 0)
        if candidates:
            amount = max(candidates)

    expense_date = date.today().isoformat()
    date_patterns = [
        (r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", ("%Y-%m-%d",)),
        (r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b", ("%d-%m-%Y", "%m-%d-%Y")),
        (r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})\b", ("%d %B %Y", "%d %b %Y")),
        (r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(20\d{2})\b", ("%B %d %Y", "%b %d %Y")),
    ]
    for pattern, formats in date_patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        raw = match.group(0).replace("/", "-").replace(".", "-")
        for fmt in formats:
            try:
                expense_date = datetime.strptime(raw, fmt).date().isoformat()
                return {"vendor": vendor, "amount": amount, "expense_date": expense_date}
            except ValueError:
                pass
    return {"vendor": vendor, "amount": amount, "expense_date": expense_date}


def suggest_category(text, vendor=""):
    sample = (text + " " + vendor).lower()
    rules = {
        "Food": ("restaurant", "cafe", "coffee", "pizza", "grocery", "supermarket", "bakery", "food", "swiggy", "zomato", "dining", "dominos", "mcdonald"),
        "Travel": ("uber", "ola", "taxi", "metro", "railway", "flight", "fuel", "petrol", "parking", "rapido", "irctc", "airlines"),
        "Shopping": ("amazon", "flipkart", "mall", "clothing", "fashion", "store", "retail", "mart"),
        "Bills": ("electricity", "internet", "water bill", "mobile recharge", "utility", "broadband", "gas bill"),
        "Health": ("pharmacy", "medical", "hospital", "clinic", "chemist", "diagnostic", "doctor"),
        "Office": ("stationery", "office", "printer", "software", "supplies"),
    }
    for category, keywords in rules.items():
        if any(keyword in sample for keyword in keywords):
            return category
    return "Other"
