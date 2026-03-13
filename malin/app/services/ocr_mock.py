"""
Mock OCR Provider — SPEC §3.1 (v0.1 mock provider).

Generates synthetic OCR spans for testing the full pipeline
without an actual OCR service. In production, swap with
Azure Document Intelligence or Textract.
"""

import uuid
from datetime import datetime

from malin.app.models.tables import OcrSpan


def generate_mock_spans(document_id: uuid.UUID, filename: str) -> list[OcrSpan]:
    """
    Generate realistic mock OCR spans for a document.
    These simulate what Azure Document Intelligence would return.
    """
    # Simulate typical German business letter spans
    mock_texts = [
        {"page": 0, "text": "Finanzamt München", "bbox": [50, 50, 200, 20]},
        {"page": 0, "text": "Steuernummer: 143/123/45678", "bbox": [50, 80, 250, 20]},
        {"page": 0, "text": "Aktenzeichen: AZ-2026-0042", "bbox": [50, 110, 250, 20]},
        {"page": 0, "text": f"Betreff: Umsatzsteuervoranmeldung Q1 2026", "bbox": [50, 150, 400, 20]},
        {"page": 0, "text": "Sehr geehrte Damen und Herren,", "bbox": [50, 200, 300, 20]},
        {"page": 0, "text": "bitte reichen Sie Ihre Umsatzsteuervoranmeldung", "bbox": [50, 230, 400, 20]},
        {"page": 0, "text": "für das erste Quartal 2026 ein.", "bbox": [50, 260, 350, 20]},
        {"page": 0, "text": "Frist: 10.04.2026", "bbox": [50, 300, 200, 20]},
        {"page": 0, "text": "Betrag: 2.450,00 EUR", "bbox": [50, 330, 200, 20]},
        {"page": 0, "text": "IBAN: DE89 3704 0044 0532 0130 00", "bbox": [50, 360, 300, 20]},
        {"page": 0, "text": "Mit freundlichen Grüßen", "bbox": [50, 420, 250, 20]},
        {"page": 0, "text": filename, "bbox": [50, 460, 300, 20]},
    ]

    spans = []
    for m in mock_texts:
        spans.append(OcrSpan(
            document_id=document_id,
            page=m["page"],
            text=m["text"],
            bbox=m["bbox"],
        ))
    return spans
