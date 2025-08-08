import { useEffect, useMemo, useState } from 'react'

function detectPlatform(){
  const ua = navigator.userAgent || ''
  const isIOS = /iPhone|iPad|iPod/i.test(ua)
  const isAndroid = /Android/i.test(ua)
  const isChromium = !!window.chrome || /Edg\//.test(ua) || /Chromium/i.test(ua)
  const isSafari = /^((?!chrome|android).)*safari/i.test(ua)
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || (window.navigator.standalone === true)
  return { isIOS, isAndroid, isChromium, isSafari, isStandalone }
}

export default function InstallPrompt(){
  const [deferred, setDeferred] = useState(null)
  const [installed, setInstalled] = useState(false)
  const [supported, setSupported] = useState(false)
  const [showHelp, setShowHelp] = useState(false)

  const { isIOS, isAndroid, isChromium, isSafari, isStandalone } = useMemo(detectPlatform, [])

  useEffect(()=>{
    const onPrompt = (e)=>{
      e.preventDefault()
      setDeferred(e)
      setSupported(true)
    }
    const onInstalled = ()=> setInstalled(true)
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('appinstalled', onInstalled)
    // Si ya está instalada, no mostramos botón
    if(isStandalone) setInstalled(true)
    return ()=>{
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [isStandalone])

  if (installed) return null

  // Caso 1: navegadores Chromium/Edge con beforeinstallprompt disponible
  if (supported && (isChromium || isAndroid)) {
    return (
      <button
        className="px-4 py-2 rounded-xl bg-cyan-400 text-black hover:bg-cyan-300 transition"
        onClick={async()=>{
          if(!deferred) return
          deferred.prompt()
          const { outcome } = await deferred.userChoice
          if(outcome === 'accepted') setDeferred(null)
        }}>
        Instalar app
      </button>
    )
  }

  // Caso 2: iOS/Safari u otros que no disparan beforeinstallprompt
  // Mostramos un mini-popover con instrucciones
  return (
    <div className="relative">
      <button
        className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20"
        onClick={()=>setShowHelp(v=>!v)}>
        ¿Instalar?
      </button>
      {showHelp && (
        <div className="absolute right-0 mt-2 w-72 p-3 text-sm rounded-xl bg-black/80 border border-white/10 backdrop-blur">
          {isIOS ? (
            <div>
              En iPhone/iPad: abre en Safari → toca <b>Compartir</b> → <b>Añadir a pantalla de inicio</b>.
            </div>
          ) : isSafari ? (
            <div>
              En Safari macOS: menú <b>Archivo</b> → <b>Añadir a Dock</b>.
            </div>
          ) : (
            <div>
              En tu navegador: abre el menú (⋮) → busca <b>Instalar app</b> o <b>Instalar sitio</b>.
              En Chrome/Edge en escritorio suele aparecer un icono de <b>instalar</b> en la barra de direcciones.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
