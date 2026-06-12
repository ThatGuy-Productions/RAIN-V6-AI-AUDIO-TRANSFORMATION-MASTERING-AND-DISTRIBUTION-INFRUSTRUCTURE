import { useState } from 'react'
import { BrainCircuit } from 'lucide-react'
import { api, APIError } from '@/utils/api'

export default function RainNetTrainingTab() {
  const [manifestPath, setManifestPath] = useState('')
  const [epochs, setEpochs] = useState(10)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function start() {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.rainnet.train({ manifest_path: manifestPath, epochs, batch_size: 8, device: 'cuda' }))
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'RainNet training failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full grid grid-cols-[420px_1fr] gap-6">
      <section className="crystal-glass rounded-2xl p-6 space-y-5">
        <div className="flex items-center gap-3">
          <BrainCircuit size={18} className="text-rain-teal" />
          <h2 className="text-[12px] font-black uppercase tracking-[0.18em] text-white/70">RainNet Training</h2>
        </div>
        <input value={manifestPath} onChange={(event) => setManifestPath(event.target.value)} className="w-full rounded-xl bg-black/30 border border-white/10 p-3 text-sm text-white outline-none" placeholder="/datasets/rainnet/manifest.jsonl" />
        <label className="block text-[10px] uppercase tracking-widest text-white/40">
          Epochs {epochs}
          <input className="mt-3 w-full accent-rain-teal" type="range" min="1" max="100" value={epochs} onChange={(event) => setEpochs(Number(event.target.value))} />
        </label>
        <button disabled={!manifestPath || busy} onClick={start} className="w-full crystal-bubble rounded-xl py-3 text-xs font-bold uppercase tracking-widest disabled:opacity-40">
          {busy ? 'Submitting...' : 'Train'}
        </button>
        {error && <p className="text-xs text-rain-red">{error}</p>}
      </section>
      <section className="crystal-glass rounded-2xl p-6 overflow-auto">
        <pre className="text-xs text-white/60 whitespace-pre-wrap">{result ? JSON.stringify(result, null, 2) : 'No training job'}</pre>
      </section>
    </div>
  )
}
