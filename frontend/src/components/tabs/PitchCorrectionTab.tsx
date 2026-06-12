import { useState } from 'react'
import { SlidersHorizontal, Download } from 'lucide-react'
import { UploadZone } from '@/components/controls/UploadZone'
import { api, APIError } from '@/utils/api'

export default function PitchCorrectionTab() {
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState('natural')
  const [strength, setStrength] = useState(0.65)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.pitchCorrection.process>> | null>(null)

  async function run() {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.pitchCorrection.process(file, { mode, strength, humanization: 0.45, retune_speed: 0.14 }))
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Pitch correction failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full grid grid-cols-[minmax(320px,420px)_1fr] gap-6">
      <section className="crystal-glass rounded-2xl p-6 space-y-5">
        <div className="flex items-center gap-3">
          <SlidersHorizontal size={18} className="text-rain-teal" />
          <h2 className="text-[12px] font-black uppercase tracking-[0.18em] text-white/70">Pitch Correction</h2>
        </div>
        <UploadZone onFileSelected={setFile} />
        <div className="grid grid-cols-3 gap-2">
          {['transparent', 'natural', 'aggressive'].map((item) => (
            <button key={item} onClick={() => setMode(item)} className={`rounded-lg border px-3 py-2 text-[10px] uppercase tracking-widest ${mode === item ? 'border-rain-teal text-white bg-rain-teal/10' : 'border-white/10 text-white/50'}`}>
              {item}
            </button>
          ))}
        </div>
        <label className="block text-[10px] uppercase tracking-widest text-white/40">
          Strength
          <input className="mt-3 w-full accent-rain-teal" type="range" min="0" max="1" step="0.01" value={strength} onChange={(event) => setStrength(Number(event.target.value))} />
        </label>
        <button disabled={!file || busy} onClick={run} className="w-full crystal-bubble rounded-xl py-3 text-xs font-bold uppercase tracking-widest disabled:opacity-40">
          {busy ? 'Processing...' : 'Process'}
        </button>
        {error && <p className="text-xs text-rain-red">{error}</p>}
      </section>
      <section className="crystal-glass rounded-2xl p-6 overflow-auto">
        {result ? (
          <div className="space-y-5">
            <div className="grid grid-cols-3 gap-3">
              <Metric label="Key" value={`${result.detected_key} ${result.detected_scale}`} />
              <Metric label="Mean correction" value={`${Number(result.statistics.mean_correction_cents ?? 0).toFixed(1)} cents`} />
              <Metric label="Mode" value={String(result.statistics.mode)} />
            </div>
            <a className="inline-flex items-center gap-2 crystal-bubble rounded-xl px-4 py-3 text-xs font-bold uppercase tracking-widest" href={result.corrected_wav_url}>
              <Download size={14} /> WAV
            </a>
            <pre className="text-xs text-white/60 whitespace-pre-wrap">{JSON.stringify(result.statistics, null, 2)}</pre>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-white/30 text-xs uppercase tracking-widest">No correction report</div>
        )}
      </section>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="crystal-bubble rounded-xl p-4">
      <div className="text-[10px] uppercase tracking-widest text-white/30">{label}</div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
    </div>
  )
}
