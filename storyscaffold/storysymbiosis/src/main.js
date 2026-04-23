const { app, BrowserWindow, ipcMain, screen, globalShortcut, dialog, systemPreferences, shell } = require('electron')
const path = require('path')

// When the launching terminal closes, stdout/stderr writes throw EIO.
// Suppress those silently; re-exit on any other uncaught exception.
process.stdout.on('error', () => {})
process.stderr.on('error', () => {})
process.on('uncaughtException', err => {
  if (err.code === 'EIO') return
  process.stderr.write(`[SS] Uncaught exception: ${err.stack}\n`)
  process.exit(1)
})
const fs = require('fs')
const screenshot = require('screenshot-desktop')
const http = require('http')

const BACKEND = 'http://localhost:8000'
const INTERVAL_MS = 30_000   // screenshot every 30s
const SPEAK_EVERY  = 2        // agents only speak every Nth capture (= 60s)
const W = 320
const H = 480

let win = null
let sessionId = null
let captureInterval = null
let captureCount = 0

// ── Window ────────────────────────────────────────────────────────────────────
function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize

  win = new BrowserWindow({
    width: W, height: H,
    x: width - W - 20,
    y: height - H - 20,
    frame: true,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    skipTaskbar: false,
    maxWidth: 800,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.setAlwaysOnTop(true, 'screen-saver')
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  const query = process.env.SS_DEBUG === '1' ? { debug: '1' } : {}
  win.loadFile(path.join(__dirname, 'renderer/index.html'), { query })
  win.on('closed', () => { win = null })
}

// ── Session ───────────────────────────────────────────────────────────────────
async function initSession() {
  try {
    await new Promise(resolve => setTimeout(resolve, 30_000))                                                             
    const data = await post('/session/new', {})
    sessionId = data.session_id
    console.log('[SS] session:', sessionId)
  } catch (e) {
    console.error('[SS] session init failed:', e.message)
    setTimeout(initSession, 3000)
  }
}

// ── Capture ───────────────────────────────────────────────────────────────────
async function captureAndProcess(manual = false) {
  if (!sessionId || !win) return
  captureCount++
  const roll = manual || (captureCount % SPEAK_EVERY === 0)
  win.webContents.send('capture-start', { manual })
  try {
    const buf = await screenshot({ format: 'png' })
    console.log(`[SS] screenshot captured — ${Math.round(buf.length / 1024)} KB`)
    const result = await post('/process', {
      session_id: sessionId,
      image_b64: buf.toString('base64'),
      manual,
      roll,
    })
    win.webContents.send('cycle-complete', {
      hand_raisers: result.hand_raisers || [],
      manual,
    })
    console.log(`[SS] cycle${manual ? ' manual' : ''} — raisers: ${result.hand_raisers?.join(', ') || 'none'}`)
  } catch (e) {
    try { console.error('[SS] capture error:', e?.message ?? e) } catch (_) {}
    win.webContents.send('capture-done')
  }
}

function startLoop() {
  const safe = () => captureAndProcess().catch(e => { if (e?.code !== 'EIO') try { console.error('[SS] loop error:', e?.message ?? e) } catch (_) {} })
  safe()
  captureInterval = setInterval(safe, INTERVAL_MS)
}

// ── Export helper ─────────────────────────────────────────────────────────────
async function handleExport(format = 'json') {
  // format: 'json' | 'events' | 'states'
  const isJson = format === 'json'
  const ext = isJson ? 'json' : 'csv'
  const label = { json: 'Full audit (JSON)', events: 'Interaction events (CSV)', states: 'State snapshots (CSV)' }[format] || format
  const shortId = sessionId ? sessionId.slice(0, 8) : 'session'

  const { filePath, canceled } = await dialog.showSaveDialog({
    title: `Export ${label}`,
    defaultPath: `storysymbiosis_${format}_${shortId}.${ext}`,
    filters: isJson
      ? [{ name: 'JSON', extensions: ['json'] }]
      : [{ name: 'CSV', extensions: ['csv'] }],
  })

  if (canceled || !filePath) return { status: 'canceled' }

  try {
    const endpoint = isJson
      ? `/export/${sessionId}`
      : `/export/${sessionId}/${format}`

    // Fetch raw text from backend
    const raw = await getRaw(endpoint)
    fs.writeFileSync(filePath, raw, 'utf8')
    console.log(`[SS] exported ${format} → ${filePath}`)
    return { status: 'ok', filePath }
  } catch (e) {
    console.error('[SS] export error:', e.message)
    return { status: 'error', message: e.message }
  }
}

// ── IPC ───────────────────────────────────────────────────────────────────────
ipcMain.handle('fetch-comment',   (_, id)               => post('/comment',          { session_id: sessionId, agent_id: id, trigger: 'user_click' }))
ipcMain.handle('fetch-artifact',  (_, id)               => post('/artifact',         { session_id: sessionId, agent_id: id }))
ipcMain.handle('dismiss-comment', (_, id)               => post('/comment/dismiss',  { session_id: sessionId, agent_id: id }))
ipcMain.handle('submit-feedback', (_, id, key, preview) => post('/comment/feedback', { session_id: sessionId, agent_id: id, feedback_key: key, comment_preview: preview || '' }))
ipcMain.handle('update-slider',   (_, v)                => post('/slider',           { session_id: sessionId, value: v }))
ipcMain.handle('export-session',  (_, format)           => handleExport(format || 'json'))
ipcMain.on('manual-capture',  () => captureAndProcess(true))
ipcMain.on('window-drag',     (_, d) => { if (win) { const [x,y] = win.getPosition(); win.setPosition(x+d.dx, y+d.dy) } })
ipcMain.on('window-close',    () => win?.close())
ipcMain.on('window-minimize', () => win?.minimize())
ipcMain.on('window-resize',   (_, h) => { if (win) { const [w] = win.getSize(); win.setSize(w, Math.ceil(h)) } })

// ── HTTP helpers ──────────────────────────────────────────────────────────────
function post(path, body) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body)
    const req = http.request(
      { hostname: 'localhost', port: 8000, path, method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) } },
      res => { let d = ''; res.on('data', c => d += c); res.on('end', () => { try { resolve(JSON.parse(d)) } catch { resolve({}) } }) }
    )
    req.on('error', reject)
    req.write(payload)
    req.end()
  })
}

// Returns raw string (not parsed) — used for file export
function getRaw(path) {
  return new Promise((resolve, reject) => {
    http.get({ hostname: 'localhost', port: 8000, path }, res => {
      let d = ''; res.on('data', c => d += c); res.on('end', () => resolve(d))
    }).on('error', reject)
  })
}

// ── Screen recording permission (macOS) ───────────────────────────────────────
async function ensureScreenPermission() {
  if (process.platform !== 'darwin') return
  const status = systemPreferences.getMediaAccessStatus('screen')
  console.log('[SS] screen recording permission:', status)
  if (status !== 'granted') {
    await dialog.showMessageBox({
      type: 'warning',
      title: 'Screen Recording Permission Required',
      message: 'StorySymbiosis needs Screen Recording access.',
      detail: 'Click OK to open System Settings → Privacy & Security → Screen Recording.\n\nAdd your terminal app (Terminal or iTerm2) to the list and toggle it on, then fully restart the app.',
      buttons: ['Open System Settings', 'Cancel'],
      defaultId: 0,
    }).then(({ response }) => {
      if (response === 0)
        shell.openExternal('x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture')
    })
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  createWindow()
  await ensureScreenPermission()
  await initSession()
  startLoop()
  const key = process.platform === 'darwin' ? 'Command+Shift+S' : 'Ctrl+Shift+S'
  globalShortcut.register(key, () => captureAndProcess(true))
  console.log(`[SS] hotkey: ${key}`)
})

app.on('window-all-closed', () => {
  clearInterval(captureInterval)
  globalShortcut.unregisterAll()
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => { if (!win) createWindow() })
