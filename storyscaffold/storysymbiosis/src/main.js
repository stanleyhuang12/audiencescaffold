const { app, BrowserWindow, ipcMain, screen, globalShortcut } = require('electron')
const path = require('path')
const screenshot = require('screenshot-desktop')
const http = require('http')

const BACKEND = 'http://localhost:8000'
const INTERVAL_MS = 60_000
const W = 320
const H = 480

let win = null
let sessionId = null
let captureInterval = null

// ── Window ────────────────────────────────────────────────────────────────────
function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize

  win = new BrowserWindow({
    width: W, height: H,
    x: width - W - 20,
    y: height - H - 20,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.setAlwaysOnTop(true, 'screen-saver')
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  win.loadFile(path.join(__dirname, 'renderer/index.html'))
  win.on('closed', () => { win = null })
}

// ── Session ───────────────────────────────────────────────────────────────────
async function initSession() {
  try {
    const data = await post('/session/new', {})
    sessionId = data.session_id
    console.log('[SS] session:', sessionId)
  } catch (e) {
    console.error('[SS] session init failed:', e.message)
    // Retry after 3s if backend not ready
    setTimeout(initSession, 3000)
  }
}

// ── Capture ───────────────────────────────────────────────────────────────────
async function captureAndProcess(manual = false) {
  if (!sessionId || !win) return
  win.webContents.send('capture-start', { manual })
  try {
    const buf = await screenshot({ format: 'png' })
    const result = await post('/process', {
      session_id: sessionId,
      image_b64: buf.toString('base64'),
    })
    win.webContents.send('cycle-complete', {
      hand_raisers: result.hand_raisers || [],
      manual,
    })
    console.log(`[SS] cycle${manual ? ' manual' : ''} — raisers: ${result.hand_raisers?.join(', ') || 'none'}`)
  } catch (e) {
    console.error('[SS] capture error:', e.message)
    win.webContents.send('capture-done')
  }
}

function startLoop() {
  captureAndProcess()
  captureInterval = setInterval(captureAndProcess, INTERVAL_MS)
}

// ── IPC ───────────────────────────────────────────────────────────────────────
ipcMain.handle('fetch-comment',   (_, id) => post('/comment',         { session_id: sessionId, agent_id: id }))
ipcMain.handle('fetch-artifact',  (_, id) => post('/artifact',        { session_id: sessionId, agent_id: id }))
ipcMain.handle('dismiss-comment', (_, id) => post('/comment/dismiss', { session_id: sessionId, agent_id: id }))
ipcMain.handle('update-slider',   (_, v)  => post('/slider',          { session_id: sessionId, value: v }))
ipcMain.handle('export-session',  ()      => get(`/export/${sessionId}`))
ipcMain.on('manual-capture', () => captureAndProcess(true))
ipcMain.on('window-drag',    (_, d) => { if (win) { const [x,y] = win.getPosition(); win.setPosition(x+d.dx, y+d.dy) } })
ipcMain.on('window-close',   () => win?.close())
ipcMain.on('window-minimize',() => win?.minimize())

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

function get(path) {
  return new Promise((resolve, reject) => {
    http.get({ hostname: 'localhost', port: 8000, path }, res => {
      let d = ''; res.on('data', c => d += c); res.on('end', () => { try { resolve(JSON.parse(d)) } catch { resolve({}) } })
    }).on('error', reject)
  })
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  createWindow()
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
