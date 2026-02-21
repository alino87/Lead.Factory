## LeadFactory Intelligence API

AI-powered B2B lead enrichment engine for fiber, infrastructure and data-center sales teams.

LeadFactory analyzes raw company text and extracts actionable buying signals and outreach angles using Claude AI.

---

## 🎯 Purpose

This API is built for high-value B2B environments where generic “growth signals” are not enough.

Instead of vague indicators, LeadFactory returns:

- Prioritized lead scoring
- Concrete buying triggers
- A strategic contact angle tailored to infrastructure / connectivity sales

Designed for:
- Fiber network providers
- Data center operators
- Backbone / connectivity vendors
- Infrastructure-focused sales teams

---

## 🔎 What It Returns

For any raw company text (About page, news article, funding report, etc.), the API extracts:

| Field | Description |
|--------|------------|
| `quality_score` | Lead priority (0–100) |
| `company_summary` | Concise description (max ~240 chars) |
| `buying_signal` | Specific trigger indicating infrastructure demand |
| `contact_angle` | Suggested strategic approach for outreach |
| `api_error` | System-level error (if applicable) |

The system never fabricates uncertain fields. If confidence is low, values are returned as `null`.

---

## ⚙️ Quick Start

### Requirements

- Docker
- Anthropic API Key
- Private API key for authentication

---

### Setup

1. Clone the repository

2. Create a `.env` file:
