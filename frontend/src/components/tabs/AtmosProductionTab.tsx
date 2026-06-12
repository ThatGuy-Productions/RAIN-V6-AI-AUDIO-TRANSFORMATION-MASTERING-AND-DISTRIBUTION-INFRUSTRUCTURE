import { useState } from 'react'
import { Box, Download } from 'lucide-react'
import { useSessionStore } from '@/stores/session'
import { useAuthStore } from '@/stores/auth'

const baseUrl = (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:8000/api/v1'

export default function AtmosProductionTab() {
  const sessionId = useSessionStore((state) => state.sessionId)
  const token = useAuthStore((state) => state.accessToken)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function renderAtmos() {
    if (!sessionId) return
    setBusy(true)
    setError(null)
    try {
      const response = await fetch(`${baseUrl}/master/${sessionId}/spatial`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ format: 'atmos_71', binaural_preview: true }),
      })
      if (!response.ok) throw new Error(response.statusText)
      setResult(await response.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Atmos render failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full grid grid-cols-[380px_1fr] gap-6">
      <section className="crystal-glass rounded-2xl p-6 space-y-5">
        <div className="flex items-center gap-3">
          <Box size={18} className="text-rain-purple" />
          <h2 className="text-[12px] font-black uppercase tracking-[0.18em] text-white/70">Atmos Production</h2>
        </div>
        <div className="crystal-bubble rounded-xl p-4">
          <div className="text-[10px] uppercase tracking-widest text-white/30">Session</div>
          <div className="mt-2 text-sm text-white/80 break-all">{sessionId ?? 'No mastered session loaded'}</div>
        </div>
        <button disabled={!sessionId || busy} onClick={renderAtmos} className="w-full crystal-bubble rounded-xl py-3 text-xs font-bold uppercase tracking-widest disabled:opacity-40">
          {busy ? 'Rendering...' : 'Render Atmos'}
        </button>
        {error && <p className="text-xs text-rain-red">{error}</p>}
      </section>
      <section className="crystal-glass rounded-2xl p-6 overflow-auto">
        {result ? (
          <div className="space-y-4">
            <div className="flex gap-3 flex-wrap">
              {typeof result.adm_bwf_url === 'string' && <a href={result.adm_bwf_url} className="crystal-bubble rounded-xl px-4 py-3 text-xs font-bold uppercase tracking-widest inline-flex gap-2"><Download size={14} /> ADM BWF</a>}
              {typeof result.atmos_wav_url === 'string' && <a href={result.atmos_wav_url} className="crystal-bubble rounded-xl px-4 py-3 text-xs font-bold uppercase tracking-widest inline-flex gap-2"><Download size={14} /> Atmos WAV</a>}
              {typeof result.binaural_preview_url === 'string' && <a href={result.binaural_preview_url} className="crystal-bubble rounded-xl px-4 py-3 text-xs font-bold uppercase tracking-widest inline-flex gap-2"><Download size={14} /> Binaural</a>}
            </div>
            <pre className="text-xs text-white/60 whitespace-pre-wrap">{JSON.stringify(result.project_report ?? result, null, 2)}</pre>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-white/30 text-xs uppercase tracking-widest">No Atmos project</div>
        )}
      </section>
    </div>
  )
}
