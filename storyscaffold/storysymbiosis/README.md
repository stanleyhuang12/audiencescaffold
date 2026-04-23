# StorySymbiosis

Always-on-top Electron panel with four AI audience agents. They observe your screen every 60 seconds and raise a speech bubble when they have something to say. Clicking an agent opens a full-screen talk panel with their comment, a real-world cultural artifact reference sourced live from the web, and a three-button feedback widget. Works across **any creative environment** — design tools, browsers, code editors, document editors, whiteboards, terminals, and more.

Powered by **Google Gemini 2.0 Flash** for vision analysis, comment generation, and artifact search (via Gemini Google Search grounding).

## Project Structure

```
storysymbiosis/
├── package.json
├── CLAUDE.md               # Research project context doc
├── src/
│   ├── main.js             # Electron main process
│   ├── preload.js          # IPC bridge (exposes api.* to renderer)
│   └── renderer/
│       └── index.html      # Panel UI (agents, talk panel, export)
└── backend/
    ├── main.py             # FastAPI server
    ├── vlm.py              # Vision → state description (Gemini)
    ├── audience.py         # Comment & artifact generation (Gemini + Search grounding)
    ├── session.py          # Session state, logging, CSV/JSON export
    ├── personas.json       # Agent definitions
    └── requirements.txt    # Python dependencies
```

## Setup

### Prerequisites
- **Node.js** ≥ 18
- **Python** ≥ 3.11
- A **Google Gemini API key** — get one at https://aistudio.google.com/apikey

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
GEMINI_API_KEY=your-key-here uvicorn main:app --reload --port 8000
```

### 2. Electron panel

```bash
npm install
npm start
```

**macOS**: grant Screen Recording permission on first launch (System Settings → Privacy & Security → Screen Recording).

## Usage

- Panel floats bottom-right, always on top. Drag the titlebar to reposition.
- A **20-second warmup delay** runs on launch before the first capture fires.
- Speech bubbles (animated dots) appear on agent cards when they have a thought — at most 1–2 agents speak per cycle.
- Click a card to open the **talk panel**, which zooms in and shows:
  - The agent's comment
  - A **reference artifact** (real cultural/creative work sourced from the web via Gemini Search grounding) with title, creator, year, caption, and an external link
  - **Your take** — three feedback buttons:
    - ◆ *Interesting — worth exploring*
    - → *I have a different direction*
    - ○ *Not sure at this moment*
- Selecting a feedback option closes the talk panel and clears the agent's notification.
- **×** in the talk panel header closes it without giving feedback.
- **Voice slider** — controls how often agents speak (left = quiet, right = reactive).
- **⤓ button** — export session data (events CSV, states CSV, or full JSON).
- **↺ button** or **⌘⇧S** — manual screen capture.
- **—** minimizes, **×** closes the panel.

## The Four Agents

| Agent | Role | Behaviour |
|-------|------|-----------|
| **Remi** | Recombinability | Notices echoes and connections between earlier and current work |
| **Cass** | Contrarian | Challenges assumptions and names what's being taken for granted |
| **Dex**  | Discoverability | Surfaces relevant cultural references, precedents, and artifacts |
| **Rex**  | Reviewability | Reflects on how the work has evolved over the arc of the session |

Agents are **observers, not directors** — they never give instructions or say "you should."

## Data Export

Three export formats available via the **⤓** button in the footer:

### Interaction Events (CSV)
One row per user/system interaction. Designed for quantitative analysis.

| Column | Description |
|--------|-------------|
| `session_id` | Unique session identifier |
| `ts` | ISO 8601 timestamp |
| `event_type` | `hand_raised`, `comment_shown`, `comment_feedback`, `comment_dismissed`, `artifact_shown` |
| `agent_id` | Which agent (`recombinability`, `contrarian`, `discoverability`, `reviewability`) |
| `state_index` | Links to the state snapshot active at the time (`null` if no capture has run yet) |
| `trigger` | `passive` (auto cycle), `active` (manual capture), `user_click`, `passive_cue` |
| `feedback_key` | `explore`, `different`, `unsure` (only for `comment_feedback` events) |
| `feedback_label` | Full text of the selected feedback button |
| `comment_preview` | First 80 chars of the agent comment |
| `comment_full` | Complete agent comment text |
| `artifact_title` | Title of the referenced cultural artifact (if applicable) |

### State Snapshots (CSV)
One row per screen capture cycle. Joins to events on `(session_id, state_index)`.

| Column | Description |
|--------|-------------|
| `session_id` | Unique session identifier |
| `state_index` | Sequential index (0, 1, 2, ...) |
| `ts` | ISO 8601 timestamp of the capture |
| `state_preview` | First 120 chars |
| `state_full` | Full VLM description of what was on screen |

### Full Audit Trail (JSON)
Nested JSON with complete session data including all states and all audit entries.

## API Routes

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/session/new` | Create a new session |
| POST | `/process` | Screenshot → VLM → agent roll |
| GET | `/stream/{sid}` | SSE event stream |
| POST | `/comment` | Generate agent comment (lazy, on click) |
| POST | `/artifact` | Generate cultural artifact reference via Gemini Search grounding |
| POST | `/comment/feedback` | Record user feedback response |
| POST | `/comment/dismiss` | Dismiss an agent comment |
| POST | `/slider` | Update voice probability multiplier |
| GET | `/export/{sid}` | Full JSON audit trail |
| GET | `/export/{sid}/events` | Interaction events CSV |
| GET | `/export/{sid}/states` | State snapshots CSV |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key (used for VLM, comment generation, and artifact search grounding) |

## License

Research prototype — see CLAUDE.md for project context.
