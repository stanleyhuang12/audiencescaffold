# StorySymbiosis

Always-on-top Electron panel. Four AI agents watch your screen every 20s and raise a speech bubble when they have something to say.

## Run

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-... uvicorn main:app --reload --port 8000
```

### 2. Electron panel
```bash
npm install
npm start
```

**macOS**: grant Screen Recording permission on first launch (System Settings → Privacy & Security → Screen Recording).

## Usage
- Panel floats bottom-right, always on top. Drag titlebar to move.
- Speech bubble appears on an agent's card when they want to speak
- Click the card to load and expand their comment
- Click **▸ reference** inside the comment for a cultural artifact
- **Voice slider** = how often agents speak (left = quiet, right = reactive)
- **↺ button** or **⌘⇧S** = manual capture
- **—** minimizes, **×** closes
