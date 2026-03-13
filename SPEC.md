# SPEC.md — MALIN v0.1 (Evidence-Driven Office Agent)

Version: 0.1
Datum: 2026-02-22
Zielgruppe: CTO / Dev-Team / Claude Code Orchestrator
Plattform: Mac + Windows (Docker-first), später Hetzner (Single-Tenant pro Kunde)

---

## 1) Produkt-Ziel (v0.1)

MALIN ist ein **Evidence-Driven Office Agent**, der Dokumente (PDF/Fotos/E-Mail-Anhänge) verarbeitet, daraus **Entwürfe (Draft Actions)** erzeugt und nach **menschlicher Freigabe** Aktionen ausführt.

**Core Loop (Definition von "fertig"):**

1. Input (Upload oder E-Mail) → Document entsteht
2. OCR → ocr_spans (Text + Bounding Boxes)
3. Intelligence (LLM) → Draft Actions mit Evidence (span_ids)
4. Review UI (Focus Stream) → Approve/Edit/Reject
5. Execution (nach Approve) → Kalender (ICS) + Exporte + Drafts (z. B. E-Mail-Entwürfe)
6. Audit/Receipt → jederzeit beweisbar

**Nicht-Ziel (v0.1):**

- Kein automatisches Versenden von E-Mails
- Keine automatische Zahlungsausführung
- Keine automatische Vertragskündigung/Steuerübermittlung
- Keine komplexe Multi-Tenant-SaaS Architektur (Start: Single-Tenant pro Kunde, aber Tenant-ID sauber modelliert)

---

## 2) Rechtliche Leitplanken (Must)

**Grundsatz:** MALIN ist Copilot, keine rechts-/steuerberatende Instanz.

### 2.1 Human-in-the-Loop Pflicht

- Jede "bindende" Handlung ist **nur Entwurf** bis ein Mensch freigibt.
- Execution darf **nur** bei `status == APPROVED` erfolgen (Backend-Guard).

### 2.2 Automatisierung (v0.1 erlaubte Ausführung nach Freigabe)

✅ Nach APPROVE darf MALIN:

- Kalendertermin erstellen (v0.1: ICS export, v0.2: Google/M365)
- Erinnerungen setzen (ICS alarms)
- Exportdateien erzeugen: SEPA XML / DATEV-Vorerfassung / ZIP-Export

❌ MALIN darf NICHT selbstständig:

- Zahlungen ausführen
- E-Mails verschicken (nur Draft)
- Kündigungen versenden (nur Draft)
- Steuererklärungen/UStVA übermitteln (nur Export/Vorerfassung)

### 2.3 Transparenz / Evidence

Jedes extrahierte Feld muss auf **OCR-Spans** verweisen:

- `span_id` Pflicht für wichtige Felder (Frist, Betrag, IBAN, Vertragspartner).
- Ohne Evidence → Draft landet in `NEEDS_REVIEW` mit `error_code`.

---

## 3) Architektur (Monorepo, Docker-first, Cross-OS)

### 3.1 Tech Stack (v0.1)

- Backend: FastAPI
- Worker: Celery (oder RQ) + Redis
- DB: Postgres
- Storage: S3-kompatibel (MinIO lokal)
- OCR: Azure Document Intelligence (empfohlen) oder Textract; v0.1 zusätzlich `mock` Provider
- UI: Streamlit (v0.1) — Focus Stream; Next.js optional v0.2
- LLM: Claude API (JSON-only, deterministic)

### 3.2 Repo Struktur (konventionell)

Root:

- `docker-compose.yml` (Quelle der Wahrheit für Mac/Windows)
- `scripts/` mit `*.sh` + `*.ps1`
- `.gitattributes` (LF) + `.env.example` (keine Secrets)

---

## 4) Module (v0.1) — als Draft-Schemas

**Wichtig:** Alle Module existieren in v0.1 als **Draft Generation + Review**.
Execution gibt es v0.1 nur für Kalender (ICS) + Exporte.

### 4.1 Module Liste

MALIN unterstützt folgende Module als Klassifikation + Draft-Typen:

1) **POST/INBOX (Input Layer)**
   - Upload & Email-Ingest
   - Dokumentklassifikation (doc_type)

2) **INVOICE (Buchhaltung/Vorerfassung)**
   - Rechnung erkennen, Betrag/IBAN/Fälligkeit extrahieren
   - Drafts: PAYMENT_EXPORT, DATEV_EXPORT (Vorerfassung)

3) **CONTRACT (Vertragsmanager)**
   - Laufzeit/Kündigungsfristen/Kosten extrahieren
   - Drafts: CALENDAR (Kündigungsfrist), REPLY_EMAIL (Kündigungsentwurf)

4) **CRM (Kommunikation/CRM-Light)**
   - Kontakt/Anfrage erkennen
   - Drafts: REPLY_EMAIL, CALENDAR (Follow-up)

5) **AUTHORITY (Behörden/Fristen) — Speerspitze v0.1**
   - Absender, Frist, Aufgabe, Risiko extrahieren
   - Drafts: CALENDAR, REPLY_EMAIL (Antwortentwurf)

6) **ARCHIVE (Dokumentenarchiv + Smart Search)**
   - Tags, Gegenpartei, Doc-Type
   - Drafts: TAGGING (optional), Search Index intern

7) **SPEND (Ausgabenoptimierung)**
   - Muster/Abos/Anomalien (heuristisch + LLM)
   - Drafts: SPEND_REPORT (Report Draft)

---

## 5) Datenmodell (DB) — "Draft is Law"

### 5.1 Tabellen (Minimal v0.1)

#### tenants

- `tenant_id` (uuid)
- `name`
- `status` (ACTIVE, SUSPENDED)
- `plan` (FREE, STARTER, BUSINESS, ENTERPRISE) — gating v0.1
- `created_at`

#### users

- `user_id` (uuid)
- `tenant_id`
- `email`
- `role` (ADMIN, REVIEWER, VIEWER)
- `created_at`

#### documents

- `document_id` (uuid)
- `tenant_id`
- `source` (UPLOAD, EMAIL)
- `filename`, `mime_type`, `size_bytes`, `sha256`
- `storage_key` (S3 path)
- `status` (UPLOADED, OCR_DONE, INTELLIGENCE_DONE, NEEDS_ATTENTION)
- `doc_type` (AUTHORITY, INVOICE, CONTRACT, CRM, GENERAL)
- `created_at`

#### ocr_spans

- `span_id` (uuid / string)
- `document_id`
- `page` (int)
- `bbox` (json: [x, y, w, h])
- `text` (string)
- `created_at`

#### drafts (versioned)

- `draft_id` (uuid)
- `version_group_id` (uuid) — gruppiert Versionen
- `version` (int) — KI=1, User edit =2+
- `tenant_id`
- `document_id`
- `module_type` (enum)
- `action_type` (enum)
- `payload` (jsonb)
- `confidence` (jsonb) — field->0..1
- `evidence` (jsonb array) — {field, span_id}
- `status` (DRAFT, NEEDS_REVIEW, APPROVED, REJECTED, EXECUTED, ARCHIVED)
- `review_required` (bool)
- `error_code` (nullable string)
- `locked_at` (timestamp nullable)
- `created_at`

#### audit_logs (append-only)

- `audit_id` (uuid)
- `tenant_id`
- `draft_id`
- `actor_type` (SYSTEM, USER)
- `actor_id` (nullable)
- `action` (CREATE_DRAFT, UPDATE_DRAFT, APPROVE, REJECT, EXECUTE, ERROR)
- `before_payload` (jsonb nullable)
- `after_payload` (jsonb nullable)
- `diff` (jsonb nullable) — field-level changes
- `ip` (nullable)
- `user_agent` (nullable)
- `created_at`

#### executions (receipts)

- `execution_id` (uuid)
- `tenant_id`
- `draft_id`
- `execution_type` (CALENDAR_ICS, SEPA_EXPORT, DATEV_EXPORT, ZIP_EXPORT)
- `receipt` (jsonb) — e.g. hashes, filenames, ids
- `executed_by` (user_id nullable)
- `executed_at`

### 5.2 Status State Machine (Backend Guard)

Allowed transitions:

- DRAFT → APPROVED / REJECTED
- NEEDS_REVIEW → APPROVED / REJECTED
- APPROVED → EXECUTED
- EXECUTED → ARCHIVED

**Hard rule (service layer):**

- `execute_action()` darf nur, wenn `status == APPROVED`, sonst `IllegalStateError`.

---

## 6) Error Handling (Graceful Degradation)

MALIN darf niemals beim Pilot "500 Internal Server Error" als Default zeigen.

### 6.1 Standard Error Codes

- `OCR_MISSING`
- `LLM_PARSE`
- `SPAN_MISMATCH`
- `LLM_RATE_LIMIT`
- `LLM_AUTH`
- `LLM_TIMEOUT`
- `EXECUTION_FAILED`
- `ILLEGAL_STATE`

### 6.2 Verhalten

- Bei LLM Problemen: Draft wird angelegt als `NEEDS_REVIEW` + `error_code`, UI zeigt "KI konnte nicht sicher extrahieren".
- Bei span mismatch: Draft wird verworfen oder als NEEDS_REVIEW angelegt ohne payload.
- Bei Execution: Fehlgeschlagene Execution schreibt receipt + audit log, Draft bleibt APPROVED oder wechselt zu NEEDS_REVIEW (Policy).

---

## 7) Endpoints (Backend)

### 7.1 Auth / Tenant

- `GET /health`
- `GET /me`
- Header: `X-TENANT-KEY` (v0.1 API key auth)

### 7.2 Documents

- `POST /documents/upload`
- `GET /documents` (Inbox)
- `GET /documents/{id}`
- `GET /documents/{id}/download`
- `POST /documents/{id}/process` (enqueue OCR + Intelligence)

### 7.3 OCR

- `POST /documents/{id}/ocr/run`
- `GET /documents/{id}/spans`
- `POST /documents/{id}/spans/resolve` (span_id → text/bbox)

### 7.4 Intelligence

- `POST /intelligence/run/{document_id}` (async)
- (optional) `GET /intelligence/status/{document_id}`

### 7.5 Drafts

- `GET /drafts?document_id=...`
- `POST /drafts/{id}/approve`
- `POST /drafts/{id}/reject`
- `POST /drafts/{id}/edit` (creates new version)
- `GET /drafts/{version_group_id}/history`

### 7.6 Execution (v0.1)

- `POST /drafts/{id}/execute/calendar_ics` → returns `.ics` + execution receipt
- `POST /drafts/{id}/execute/sepa_export` → returns xml + receipt (optional v0.1)
- `POST /drafts/{id}/execute/datev_export` → returns zip/csv + receipt (optional v0.1)

### 7.7 Usage / Billing (Scaffold v0.1)

- `GET /usage`
- `POST /billing/checkout` (optional)
- `POST /billing/webhook` (optional)
- Plan gating: processing endpoints return 402 if tenant inactive.

---

## 8) UI (Focus Stream) — v0.1 Streamlit

### 8.1 Screens

- Inbox (documents)
- Document Detail / Focus Stream:
  - Left: PDF viewer (iframe/embedded)
  - Right: Draft cards
- Draft History (versions + audit)
- Settings (tenant key, mailbox status placeholder, usage)

### 8.2 Evidence UX (Must)

- Klick auf Draft-Feld → zeigt Evidence (page + bbox + span text).
- "Soft Lock" (Must für kritische Felder):
  - Approve ist erst aktiv, nachdem Evidence für kritische Felder mindestens einmal fokussiert wurde:
    - `due_date`, `amount`, `iban`, `notice_deadline`

---

## 9) LLM Prompting (Evidence-Driven)

### 9.1 Grundregeln

- Output ONLY valid JSON
- No markdown, no explanations, no extra keys
- If unsure: use null
- Use span_ids only (no invented evidence)

### 9.2 Prompt Inputs

- Document metadata
- OCR spans (oder komprimiert: relevant spans)

**Hinweis:** Für Performance darf das System vorher heuristisch "candidate spans" auswählen.

### 9.3 Validation

- Jeder `span_id` muss in `ocr_spans` existieren
- Jeder extrahierte Key muss im Schema stehen
- confidence ∈ [0..1]

---

## 10) Cross-Platform Anforderungen (Mac + Windows)

- `docker compose up --build` muss ohne Anpassungen laufen
- Keine OS-spezifischen Pfade in compose (nur named volumes)
- Scripts: bash + PowerShell
- `.gitattributes` erzwingt LF
- Worker läuft im Container (keine fork Annahmen)

---

## 11) Security (v0.1 minimal, aber sauber)

- Secrets nur über `.env` (nie commit)
- API keys pro Tenant
- Rate limiting (basic) auf processing endpoints
- Logs ohne Dokumentinhalte (PII safe), nur IDs + error codes
- Storage: signed URLs oder backend streaming (auth)

---

## 12) Definition of Done (DoD) — MALIN v0.1

MALIN v0.1 ist "fertig", wenn:

1. Upload & Email-Ingest erzeugen Documents
2. OCR erzeugt spans mit bbox (oder mock spans) und persistiert
3. Intelligence erzeugt Draft Actions mit evidence span_ids
4. UI zeigt Focus Stream: PDF + Drafts + Evidence
5. Approve erzeugt Execution (ICS export) + Receipt + Audit entry
6. Edit erzeugt neue Draft Version + Audit diff
7. Fehler werden als NEEDS_REVIEW + error_code abgebildet (kein Standard-500)
8. Läuft identisch auf Mac & Windows via Docker Compose

---

## 13) Roadmap (nur als Kontext, nicht v0.1)

v0.2:

- Google Calendar OAuth / Microsoft Graph
- Next.js UI + echte bbox overlays
- Stripe Billing voll (Invoices, customer portal)
- OCR provider hardening
- Multi-tenant RLS optional (oder weiter Single-Tenant pro Kunde)
