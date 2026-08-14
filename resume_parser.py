import io
import re

import pdfplumber

CERT_KEYWORDS = [
    "RN", "LPN", "BSN", "CPC", "CCS", "CCS-P", "CIC", "COC", "CRC",
    "CPMA", "RHIT", "RHIA", "CDIP", "CCDS", "CPHQ", "CPB",
]


def extract_text(file_bytes: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return file_bytes.decode("utf-8", errors="replace")


def _extract_candidate_name(text: str, filename: str) -> str:
    match = re.search(r"^Name:\s*(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return filename


def _extract_years_experience(text: str) -> float | None:
    matches = re.findall(
        r"(\d+(?:\.\d+)?)\+?\s*years?(?:\s+of)?\s+(?:relevant\s+)?experience",
        text,
        re.IGNORECASE,
    )
    if not matches:
        return None
    return max(float(m) for m in matches)


def _extract_graduation_year(text: str) -> int | None:
    match = re.search(
        r"(?:graduated|graduation)\D{0,20}((?:19|20)\d{2})", text, re.IGNORECASE
    )
    return int(match.group(1)) if match else None


def _extract_school(text: str) -> str | None:
    match = re.search(
        r"University of (?:[A-Z][\w]*\s*){1,4}|"
        r"(?:[A-Z][\w]*\s+){1,4}(?:University|College|Institute)",
        text,
    )
    return match.group(0).strip() if match else None


def _extract_certifications(text: str) -> list[str]:
    return [
        cert
        for cert in CERT_KEYWORDS
        if re.search(rf"\b{re.escape(cert)}\b(?!-)", text)
    ]


def _extract_employment_gap_months(text: str) -> int | None:
    match = re.search(r"employment gap\D{0,20}(\d+)\s*months?", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_resume(file_bytes: bytes, filename: str) -> dict:
    text = extract_text(file_bytes, filename)
    return {
        "filename": filename,
        "candidate_name": _extract_candidate_name(text, filename),
        "raw_text": text,
        "certifications": _extract_certifications(text),
        "years_experience": _extract_years_experience(text),
        "graduation_year": _extract_graduation_year(text),
        "school": _extract_school(text),
        "employment_gap_months": _extract_employment_gap_months(text),
    }
