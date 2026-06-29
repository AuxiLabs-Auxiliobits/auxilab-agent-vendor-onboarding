# SDD — Component 2: VendorGate AI ChatBot
**Product:** VendorGate  
**Entry Point:** `VendorAssistantChatBOT.py`  
**Version:** 1.0  
**Date:** 2026-06-28  

---

## Table of Contents
1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [UI Layout](#3-ui-layout)
4. [Application Linking (Left Column)](#4-application-linking-left-column)
5. [Status Card](#5-status-card)
6. [Chat Interface (Right Column)](#6-chat-interface-right-column)
7. [NLP Processing — Gemini Integration](#7-nlp-processing--gemini-integration)
8. [Context Building](#8-context-building)
9. [Conversation Management](#9-conversation-management)
10. [Quick-Question Chips](#10-quick-question-chips)
11. [Error Handling & Fallback](#11-error-handling--fallback)
12. [Session State](#12-session-state)
13. [Styling & Theming](#13-styling--theming)
14. [Data Flow](#14-data-flow)

---

## 1. Overview

The **VendorGate AI ChatBot** is a standalone, dark-themed conversational interface that allows vendors to query their onboarding status in natural language. It is powered by **Google Gemini 2.5 Flash** and injects the vendor's full application context into the system prompt, enabling context-aware, accurate answers without hallucination.

**Key capabilities:**
- Natural language understanding of onboarding status queries
- Real-time compliance score display
- Document checklist status
- Risk flag summary
- Context-grounded answers (no fabrication)
- Quick-question chips for common queries

**Does NOT require** the vendor to know the data model — they ask in plain English.

---

## 2. Architecture

```
VendorAssistantChatBOT.py
│
├── utils/data_manager.py         ← get_submission_by_id()
├── .env                          ← GEMINI_API_KEY
│
├── get_gemini_key()              ← reads env + st.secrets fallback
├── build_context(sub)            ← serializes submission to text block
├── ask_gemini(api_key, sys_prompt, history, user_msg)  ← LLM call
├── pill(status)                  ← styled HTML status badge
└── fmt_md(text)                  ← converts **bold**/**`code`** to HTML
```

**LLM:** `google-genai` Python SDK (`genai.Client.models.generate_content`)  
**Model:** Configurable via `GEMINI_MODEL` env var (default: `gemini-2.5-flash`)

---

## 3. UI Layout

```
┌──────────────────────────────────────────────────────────────┐
│  🤖 VendorGate AI Assistant        [● Live]                  │
│  Natural language queries about your vendor onboarding       │
└──────────────────────────────────────────────────────────────┘

┌───────────────────────┬──────────────────────────────────────┐
│  LEFT (1x)            │  RIGHT (1.85x)                       │
│                       │                                      │
│  🔗 Link Application  │  💬 AI Assistant Chat                │
│  [Reference Code   ]  │  ┌────────────────────────────────┐  │
│  [Link Application→]  │  │  🤖 VendorGate Assistant ● live│  │
│                       │  └────────────────────────────────┘  │
│  ┌─────────────────┐  │  ┌────────────────────────────────┐  │
│  │ Status Card     │  │  │  Chat message area (h=440px)   │  │
│  │ Company name    │  │  │  [user bubbles / bot bubbles]  │  │
│  │ Ref code        │  │  └────────────────────────────────┘  │
│  │ Status badge    │  │                                      │
│  │ Score bar       │  │  💡 Quick questions                  │
│  │ Doc checklist   │  │  [What is my status?][Missing docs?] │
│  │ Risk banner     │  │  [Checks failed?][Next steps?]       │
│  │ [Refresh][Unlink]  │  [Score?][Risk flags?]               │
│  └─────────────────┘  │                                      │
│                       │  [Type your question...    ] [Send➤] │
└───────────────────────┴──────────────────────────────────────┘
│  🔒 Secure · Powered by Gemini 2.5 Flash                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Application Linking (Left Column)

### Lookup Form
```python
with st.form("link_form"):
    ref_input = st.text_input("Reference Code", placeholder="e.g. VND-2026-00001")
    submitted = st.form_submit_button("Link Application →")
```

### Lookup Logic
1. `get_submission_by_id(ref_input.strip())` queries `data/submissions.csv`
2. If found:
   - Sets `st.session_state.bot_sub`, `bot_sub_id`, `bot_linked = True`
   - Creates welcome message in `bot_msgs`
   - Triggers `st.rerun()`
3. If not found: `st.error("❌ Reference ... not found")`

### Welcome Message (auto-generated on link)
```
👋 Hello, {contact_name}! I've loaded your application for {legal_name} (Ref: {ref}).
Your current status is {status} with a compliance score of {score}%.
Ask me anything about your submission...
```

---

## 5. Status Card

Rendered below the link form when an application is linked.

### Sections

| Section | Data source | Visual |
|---|---|---|
| Company name | `sub["legal_name"]` | Large bold white text |
| Reference code | `sub["submission_id"]` | Monospace, muted |
| Status badge | `sub["status"]` | Coloured pill (see pill function) |
| Compliance score | `sub["overall_score"]` | Progress bar with colour coding |
| Document checklist | `w9_filename`, `coi_filename`, etc. | ✅/❌ per document |
| Timestamps | `created_at`, `updated_at` | Formatted date strings |
| Risk banner | `sub["risk_flags"]` | Amber (issues) or Green (clean) |

### Score Bar Colour Logic
```python
bar_color = "#4ade80" if score >= 80 else "#fbbf24" if score >= 50 else "#f87171"
# Green   ≥ 80%
# Amber  50–79%
# Red    < 50%
```

### Status Pill Colour Map
```python
"Approved"             → green pill   ✅
"Awaiting human review"→ amber pill   ⏳
"Action Required"      → orange pill  ⚠️
"Processing"           → blue pill    🔄
"Rejected"             → red pill     ❌
```

### Refresh / Unlink Buttons
- **Refresh** — re-fetches submission from `data_manager`, updates session state
- **Unlink** — clears all `bot_*` session state keys, resets to empty state

---

## 6. Chat Interface (Right Column)

### Chat Top Bar
Always visible. Shows:
- Bot avatar (🤖) + "VendorGate Assistant" + green live dot
- Context label: either "Context loaded: {company}" or "Link an application first"

### Message Area
Scrollable container (`height=440px`).

**Bot messages** — left-aligned, dark blue bubble, 🤖 avatar, timestamp below  
**User messages** — right-aligned, purple gradient bubble, timestamp below

**Empty state** — shown when no messages: dashed border card with instructions

### Message Rendering
Bot message content passes through `fmt_md()`:
```python
# **bold** → <strong>bold</strong>
# `code`   → <code style="...">code</code>
# \n       → <br>
```

---

## 7. NLP Processing — Gemini Integration

### `ask_gemini()` function

```python
def ask_gemini(api_key, system_prompt, history, user_msg) -> str:
    client = genai.Client(api_key=api_key)
    
    # Build multi-turn content
    contents = []
    for m in history:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_msg)]))
    
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,        # slight creativity for helpfulness
            max_output_tokens=1024  # concise answers
        )
    )
    return resp.text.strip()
```

**Temperature 0.4** — balances factual accuracy with natural, helpful language.  
**`system_instruction`** — separates the system prompt from the conversation turns (Gemini API native feature).

### API Key Resolution
```python
def get_gemini_key():
    # 1. Check environment variable (loaded from .env via load_dotenv)
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    # 2. Check Streamlit secrets
    try:
        return st.secrets["GEMINI_API_KEY"]
    except:
        return None
```

---

## 8. Context Building

### `build_context(sub)` function

Serializes the full submission record into a plain-text block injected into the Gemini system prompt. This is the key mechanism ensuring **context-grounded, non-hallucinated answers**.

**Context sections:**
```
=== VENDOR ONBOARDING APPLICATION CONTEXT ===
Submission: VND-2026-00001
Company: Alpha Ventures LLC
Status: Awaiting human review
Overall Score: 87.4%
Risk Recommendation: approve
Registered: 2026-06-28

--- DOCUMENTS UPLOADED ---
W-9 Tax Form: ✓ Uploaded (w9Form.pdf)
COI: ✓ Uploaded (COI.pdf)
Bank Letter: ✓ Uploaded (bankLetter.pdf)
Questionnaire: ✓ Uploaded (questionnaire.pdf)
Company Reg: ✗ Missing

--- DOCUMENT SCORES ---
W-9: 95.0%
COI: 80.0%
Bank: 60.0%
Questionnaire: 88.0%
Company Reg: 0.0%

--- RISK FLAGS ---
HIGH:
  • Missing mandatory document: Company Registration Document
MEDIUM:
  • Cross-document consistency check failed (Rule 7...)

--- CONSISTENCY CHECKS ---
✓ PASS | Rule 1: W-9 Legal Name vs COI: Similarity 85%...
✗ FAIL | Rule 7: Questionnaire Beneficiary vs Bank: Missing data

--- REVIEWER NOTES ---
(if any reviewer_comments are set)

===================================
```

### System Prompt Rules
```
- Only use data from the provided context. Never fabricate scores, dates, or statuses.
- Be concise (under 200 words unless detail is requested).
- Use bullet points and bold.
- If outside context, say so and suggest contacting procurement team.
- Be warm and helpful — the vendor is trying to complete their registration.
- Today's date: {datetime.now()}.
```

---

## 9. Conversation Management

### History Trimming
Only the last **20 message turns** are sent to the API to keep token usage bounded:
```python
history = [{"role": m["role"], "content": m["content"]}
           for m in st.session_state.bot_msgs[:-1][-20:]]
```

### Message Schema
Each message in `st.session_state.bot_msgs`:
```python
{
    "role": "user" | "assistant",
    "content": "...",
    "ts": "14:35"   # HH:MM timestamp for display
}
```

### Clear Chat
Button renders if `bot_msgs` is non-empty. Clears the list and calls `st.rerun()`.

---

## 10. Quick-Question Chips

Six pre-defined questions rendered as clickable buttons in a 3×2 grid:

| Chip | Typical Response |
|---|---|
| "What is my current status?" | Current status + what it means |
| "What documents are missing?" | List of missing docs with upload instructions |
| "What checks failed?" | List of failed consistency rules with details |
| "What are my next steps?" | Action-oriented guidance based on status |
| "Explain my compliance score" | Breakdown of score components |
| "Are there any risk flags?" | High/medium risk items listed clearly |

Clicking a chip sets `quick_trigger` → processed identically to a typed message.

---

## 11. Error Handling & Fallback

| Scenario | Behaviour |
|---|---|
| No API key configured | Bot replies with styled error message explaining how to set `GEMINI_API_KEY` |
| Quota exceeded (429) | `ask_gemini()` returns error string; displayed as bot message |
| Network error / 503 | Same error string fallback |
| Submission not found | `st.error()` shown in the link form; chat remains disabled |
| Application unlinked | Chat input disabled; placeholder text instructs to link first |

---

## 12. Session State

| Key | Type | Description |
|---|---|---|
| `bot_msgs` | `list[dict]` | Full conversation history |
| `bot_sub_id` | `str` | Linked reference code |
| `bot_sub` | `dict \| None` | Loaded submission record |
| `bot_linked` | `bool` | Whether an application is linked |

Initialized at page load:
```python
for k, v in [("bot_msgs", []), ("bot_sub_id", ""), ("bot_sub", None), ("bot_linked", False)]:
    if k not in st.session_state:
        st.session_state[k] = v
```

---

## 13. Styling & Theming

The ChatBot uses its own **dark theme** (independent of the shared `style_utils.py`):

| Element | Style |
|---|---|
| App background | `#0D1B2E` (deep navy) |
| Input fields | `#1E2D45` bg, `#F1F5F9` text, `#334155` border |
| Buttons | `linear-gradient(135deg, #6366f1, #8b5cf6)` (indigo-violet) |
| User bubbles | Indigo gradient pill |
| Bot bubbles | `#1E2D45` dark card |
| Score bar | Dynamic: green / amber / red |
| Status pills | Colour-coded per status |
| Hero banner | Dark card with gradient accent |

Font: **Outfit** (Google Fonts) — consistent with main portal.

---

## 14. Data Flow

```
Vendor enters reference code
         │
         ▼
get_submission_by_id() → data/submissions.csv
         │
         ▼
Submission loaded into st.session_state.bot_sub
         │
         ▼
Status card rendered + welcome message generated
         │
Vendor types question (or clicks quick chip)
         │
         ▼
build_context(sub) → plain-text context block
         │
         ▼
ask_gemini(api_key, system_prompt+context, history[-20], user_msg)
         │
         ├── Google Gemini API (gemini-2.5-flash)
         │   temperature=0.4, max_tokens=1024
         │
         ▼
Response appended to bot_msgs → st.rerun() → rendered in chat area
```
