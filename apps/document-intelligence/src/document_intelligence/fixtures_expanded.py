"""Expanded synthetic fixture set for the document-intelligence live sample.

Next-round item 3: adds seven born-digital, non-sensitive synthetic documents
(in the same fictional Northstar/Acme/Example universe as the committed
fixtures) plus their per-page reference analyses. The committed fixtures and
``evaluations/references.json`` are never edited; a script merges the
committed cases with :data:`EXPANDED_CASES` into a new references file under
a new dataset revision.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_intelligence.fixtures import render_pdf

# Reference content for the seven new documents, same schema as the committed
# evaluations/references.json cases. Evidence strings are exact substrings of
# the rendered page lines so the resolver can match them verbatim.
EXPANDED_CASES: list[dict[str, Any]] = [
    {
        "case_id": "invoice",
        "file": "expanded/invoice.pdf",
        "pages": [
            {
                "page": 1,
                "key_points": [
                    {
                        "text": "The invoice is billed to Harborview Logistics.",
                        "evidence": ["BILL TO: Harborview Logistics"],
                    },
                    {
                        "text": "Payment is due within thirty days of issue.",
                        "evidence": ["Payment is due within thirty days of issue."],
                    },
                ],
                "entities": [
                    {
                        "text": "Harborview Logistics",
                        "name": "Harborview Logistics",
                        "type": "organization",
                        "evidence": "BILL TO: Harborview Logistics",
                    },
                    {
                        "text": "2025-04-02",
                        "name": "2025-04-02",
                        "type": "date",
                        "evidence": "ISSUED: 2025-04-02",
                    },
                ],
                "topics": [
                    {
                        "label": "billing",
                        "aliases": ["billing", "invoicing", "accounts receivable", "payment"],
                    }
                ],
                "questions": [
                    {
                        "question": "Who is the invoice billed to?",
                        "answer": "The invoice is billed to Harborview Logistics.",
                        "citations": ["BILL TO: Harborview Logistics"],
                    }
                ],
            }
        ],
    },
    {
        "case_id": "minutes",
        "file": "expanded/minutes.pdf",
        "pages": [
            {
                "page": 1,
                "key_points": [
                    {
                        "text": "The rollout moves to the second week of April.",
                        "evidence": ["The rollout moves to the second week of April."],
                    },
                    {
                        "text": "The vendor review concludes on schedule.",
                        "evidence": ["The vendor review concludes on schedule."],
                    },
                ],
                "entities": [
                    {
                        "text": "Dana Example",
                        "name": "Dana Example",
                        "type": "person",
                        "evidence": "ATTENDEE: Dana Example",
                    },
                    {
                        "text": "Priya Example",
                        "name": "Priya Example",
                        "type": "person",
                        "evidence": "ATTENDEE: Priya Example",
                    },
                    {
                        "text": "2025-03-18",
                        "name": "2025-03-18",
                        "type": "date",
                        "evidence": "DATE: 2025-03-18",
                    },
                ],
                "topics": [
                    {
                        "label": "project management",
                        "aliases": ["project management", "meetings", "rollout planning"],
                    }
                ],
                "questions": [
                    {
                        "question": "When does the rollout move?",
                        "answer": "The rollout moves to the second week of April.",
                        "citations": ["The rollout moves to the second week of April."],
                    }
                ],
            }
        ],
    },
    {
        "case_id": "spec-sheet",
        "file": "expanded/spec-sheet.pdf",
        "pages": [
            {
                "page": 1,
                "key_points": [
                    {
                        "text": "The Relay Module X-2 meets the industrial temperature range.",
                        "evidence": ["The module meets the industrial temperature range."],
                    },
                    {
                        "text": "Compliance testing completed in 2025-02.",
                        "evidence": ["Compliance testing completed in 2025-02."],
                    },
                ],
                "entities": [
                    {
                        "text": "Relay Module X-2",
                        "name": "Relay Module X-2",
                        "type": "equipment",
                        "evidence": "COMPONENT: Relay Module X-2",
                    },
                    {
                        "text": "Acme Components Ltd",
                        "name": "Acme Components Ltd",
                        "type": "organization",
                        "evidence": "MANUFACTURER: Acme Components Ltd",
                    },
                    {
                        "text": "2025-02",
                        "name": "2025-02",
                        "type": "date",
                        "evidence": "Compliance testing completed in 2025-02.",
                    },
                ],
                "topics": [
                    {
                        "label": "hardware specifications",
                        "aliases": [
                            "hardware specifications",
                            "component specifications",
                            "industrial components",
                        ],
                    }
                ],
                "questions": [
                    {
                        "question": "Who manufactures the Relay Module X-2?",
                        "answer": "Acme Components Ltd manufactures the Relay Module X-2.",
                        "citations": ["MANUFACTURER: Acme Components Ltd"],
                    }
                ],
            }
        ],
    },
    {
        "case_id": "manifest",
        "file": "expanded/manifest.pdf",
        "pages": [
            {
                "page": 1,
                "key_points": [
                    {
                        "text": "The consignment cleared customs inspection.",
                        "evidence": ["The consignment cleared customs inspection."],
                    },
                    {
                        "text": "The cargo consists of sealed instrument cases.",
                        "evidence": ["CARGO: Sealed instrument cases"],
                    },
                ],
                "entities": [
                    {
                        "text": "Rotterdam Depot",
                        "name": "Rotterdam Depot",
                        "type": "location",
                        "evidence": "ORIGIN: Rotterdam Depot",
                    },
                    {
                        "text": "Northstar Depot",
                        "name": "Northstar Depot",
                        "type": "organization",
                        "evidence": "DESTINATION: Northstar Depot",
                    },
                ],
                "topics": [
                    {
                        "label": "logistics",
                        "aliases": ["logistics", "shipping", "freight", "supply chain"],
                    }
                ],
                "questions": [
                    {
                        "question": "Where does the consignment originate?",
                        "answer": "The consignment originates at Rotterdam Depot.",
                        "citations": ["ORIGIN: Rotterdam Depot"],
                    }
                ],
            }
        ],
    },
    {
        "case_id": "protocol",
        "file": "expanded/protocol.pdf",
        "pages": [
            {
                "page": 1,
                "key_points": [
                    {
                        "text": "The spectrometer is calibrated before each run.",
                        "evidence": ["STEP 1: Calibrate the spectrometer before each run."],
                    },
                    {
                        "text": "The blank reading is recorded as step two.",
                        "evidence": ["STEP 2: Record the blank reading."],
                    },
                ],
                "entities": [
                    {
                        "text": "Example Lab",
                        "name": "Example Lab",
                        "type": "organization",
                        "evidence": "PREPARED BY: Example Lab",
                    },
                    {
                        "text": "spectrometer",
                        "name": "spectrometer",
                        "type": "equipment",
                        "evidence": "STEP 1: Calibrate the spectrometer before each run.",
                    },
                    {
                        "text": "2025-01",
                        "name": "2025-01",
                        "type": "date",
                        "evidence": "The protocol was reviewed in 2025-01.",
                    },
                ],
                "topics": [
                    {
                        "label": "laboratory procedures",
                        "aliases": ["laboratory procedures", "scientific protocols", "calibration"],
                    }
                ],
                "questions": [
                    {
                        "question": "What is the first step of the protocol?",
                        "answer": (
                            "The first step is to calibrate the spectrometer before each run."
                        ),
                        "citations": ["STEP 1: Calibrate the spectrometer before each run."],
                    }
                ],
            }
        ],
    },
    {
        "case_id": "memo",
        "file": "expanded/memo.pdf",
        "pages": [
            {
                "page": 1,
                "key_points": [
                    {
                        "text": "The April release has a code freeze.",
                        "evidence": ["SUBJECT: Code freeze for the April release"],
                    },
                    {
                        "text": "All feature branches merge before the freeze.",
                        "evidence": ["All feature branches merge before the freeze."],
                    },
                ],
                "entities": [
                    {
                        "text": "Dana Example",
                        "name": "Dana Example",
                        "type": "person",
                        "evidence": "FROM: Dana Example",
                    },
                    {
                        "text": "2025-02-27",
                        "name": "2025-02-27",
                        "type": "date",
                        "evidence": "DATE: 2025-02-27",
                    },
                ],
                "topics": [
                    {
                        "label": "release management",
                        "aliases": ["release management", "code freeze", "engineering process"],
                    }
                ],
                "questions": [
                    {
                        "question": "What is the subject of the memo?",
                        "answer": "The subject is the code freeze for the April release.",
                        "citations": ["SUBJECT: Code freeze for the April release"],
                    }
                ],
            }
        ],
    },
    {
        "case_id": "incident",
        "file": "expanded/incident.pdf",
        "pages": [
            {
                "page": 1,
                "key_points": [
                    {
                        "text": "A conveyor belt stalled during the night shift.",
                        "evidence": ["A conveyor belt stalled during the night shift."],
                    },
                    {
                        "text": "No injuries were reported.",
                        "evidence": ["No injuries were reported."],
                    },
                ],
                "entities": [
                    {
                        "text": "2025-03-05",
                        "name": "2025-03-05",
                        "type": "date",
                        "evidence": "REPORTED: 2025-03-05",
                    },
                    {
                        "text": "Dock 4, Northstar Depot",
                        "name": "Dock 4, Northstar Depot",
                        "type": "location",
                        "evidence": "LOCATION: Dock 4, Northstar Depot",
                    },
                    {
                        "text": "conveyor belt",
                        "name": "conveyor belt",
                        "type": "equipment",
                        "evidence": "A conveyor belt stalled during the night shift.",
                    },
                ],
                "topics": [
                    {
                        "label": "incident reporting",
                        "aliases": ["incident reporting", "safety", "operational incidents"],
                    },
                    {
                        "label": "warehouse operations",
                        "aliases": ["warehouse operations", "dock operations", "maintenance"],
                    },
                ],
                "questions": [
                    {
                        "question": "Were any injuries reported?",
                        "answer": "No injuries were reported.",
                        "citations": ["No injuries were reported."],
                    }
                ],
            }
        ],
    },
]

# Rendered lines must match the evidence strings above exactly.
EXPANDED_DOCUMENTS: dict[str, list[str]] = {
    "invoice.pdf": [
        "INVOICE",
        "ISSUED: 2025-04-02",
        "BILL TO: Harborview Logistics",
        "AMOUNT DUE: $1,280.00",
        "Payment is due within thirty days of issue.",
    ],
    "minutes.pdf": [
        "MEETING MINUTES",
        "DATE: 2025-03-18",
        "ATTENDEE: Dana Example",
        "ATTENDEE: Priya Example",
        "DECISIONS",
        "The rollout moves to the second week of April.",
        "The vendor review concludes on schedule.",
    ],
    "spec-sheet.pdf": [
        "COMPONENT SPECIFICATION",
        "COMPONENT: Relay Module X-2",
        "MANUFACTURER: Acme Components Ltd",
        "OPERATING TEMPERATURE: -20C to 85C",
        "The module meets the industrial temperature range.",
        "Compliance testing completed in 2025-02.",
    ],
    "manifest.pdf": [
        "SHIPPING MANIFEST",
        "ORIGIN: Rotterdam Depot",
        "DESTINATION: Northstar Depot",
        "CARGO: Sealed instrument cases",
        "The consignment cleared customs inspection.",
    ],
    "protocol.pdf": [
        "LABORATORY PROTOCOL",
        "PREPARED BY: Example Lab",
        "STEP 1: Calibrate the spectrometer before each run.",
        "STEP 2: Record the blank reading.",
        "The protocol was reviewed in 2025-01.",
    ],
    "memo.pdf": [
        "INTERNAL MEMORANDUM",
        "TO: All Engineering Staff",
        "FROM: Dana Example",
        "DATE: 2025-02-27",
        "SUBJECT: Code freeze for the April release",
        "All feature branches merge before the freeze.",
    ],
    "incident.pdf": [
        "INCIDENT REPORT",
        "REPORTED: 2025-03-05",
        "LOCATION: Dock 4, Northstar Depot",
        "A conveyor belt stalled during the night shift.",
        "No injuries were reported.",
        "Maintenance cleared the fault by 06:00.",
    ],
}


def write_expanded_fixture_set(root: Path) -> None:
    """Write the seven expanded PDFs under ``root/expanded/``."""
    out = root / "expanded"
    out.mkdir(parents=True, exist_ok=True)
    for index, (name, lines) in enumerate(EXPANDED_DOCUMENTS.items()):
        (out / name).write_bytes(render_pdf(lines, layout=index + 1))
