const { app, BrowserWindow, Tray, Menu } = require('electron')
const { spawn } = require('child_process')
const path = require('path'); let child=null, tray=null

function bridgePath() {
  const bin = process.platform === 'win32' ? 'bridge.exe' : 'bridge'
  return path.join(process.resourcesPath || app.getAppPath(), 'bin', bin)
}
function startBridge() {
  try {
    const bp = bridgePath()
    child = spawn(bp, [], { stdio: 'ignore', detached: process.platform !== 'win32' })
    child.unref?.()
  } catch(e) { console.error('bridge spawn error', e) }
}
function stopBridge() {
  try { if (process.platform==='win32') child?.kill('SIGTERM'); else process.kill(-child.pid, 'SIGTERM') } catch {}
}

function createWindow () {
  const win = new BrowserWindow({
    width: 1100, height: 720, webPreferences: { preload: path.join(__dirname,'preload.js') }
  })
  win.loadFile(path.join(__dirname, 'dist', 'index.html'))
}

app.whenReady().then(()=>{
  startBridge()
  createWindow()
  tray = new Tray(path.join(__dirname,'dist','icons','icon-192.png'))
  tray.setToolTip('547 Desktop')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Abrir', click: ()=> createWindow() },
    { label: 'Reiniciar nodo', click: ()=> { stopBridge(); setTimeout(startBridge, 800) } },
    { type: 'separator' },
    { label: 'Salir', click: ()=> { stopBridge(); app.quit() } }
  ]))
})
app.on('window-all-closed', ()=>{} )
app.on('before-quit', ()=> stopBridge())
