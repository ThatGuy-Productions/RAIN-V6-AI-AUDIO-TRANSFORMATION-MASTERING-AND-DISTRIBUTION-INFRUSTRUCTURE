import { useState } from 'react'
import { Download, Wand2 } from 'lucide-react'
import { api, APIError } from '@/utils/api'

const instruments = ['piano', 'acoustic guitar', 'electric guitar', 'bass guitar', 'orchestral strings', 'drums', 'pads', 'ambient textures']

export default function InstrumentSynthesisTab() {
  const [prompt, setPrompt] = useState('warm evolving chords with a clean hook')
  const [instrument, setInstrument] = useState('piano')
  const [tempo, setTempo] = useState(120)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.instrumentSynthesis.generate>> | null>(null)

  async function generate() {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.instrumentSynthesis.generate({ prompt, instrument, tempo_bpm: tempo, key: 'C', genre: 'pop', duration_seconds: 12 }))
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Synthesis failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full grid grid-cols-[380px_1fr] gap-6">
      <section className="crystal-glass rounded-2xl p-6 space-y-5">
        <div className="flex items-center gap-3">
          <Wand2 size={18} className="text-rain-purple" />
          <h2 className="text-[12px] font-black uppercase tracking-[0.18em] text-white/70">Instrument Synthesis</h2>
        </div>
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} className="w-full h-28 rounded-xl bg-black/30 border border-white/10 p-3 text-sm text-white outline-none focus:border-rain-teal/50" />
        <select value={instrument} onChange={(event) => setInstrument(event.target.value)} className="w-full rounded-xl bg-black/30 border border-white/10 p-3 text-sm text-white">
          {instruments.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <label className="block text-[10px] uppercase tracking-widest text-white/40">
          Tempo {tempo}
          <input className="mt-3 w-full accent-rain-purple" type="range" min="60" max="180" value={tempo} onChange={(event) => setTempo(Number(event.target.value))} />
        </label>
        <button onClick={generate} disabled={busy} className="w-full crystal-bubble rounded-xl py-3 text-xs font-bold uppercase tracking-widest disabled:opacity-40">
          {busy ? 'Generating...' : 'Generate'}
        </button>
        {error && <p className="text-xs text-rain-red">{error}</p>}
      </section>
      <section className="crystal-glass rounded-2xl p-6 overflow-auto">
        {result ? (
          <div className="space-y-4">
            <div className="text-sm text-white/70">{result.status}</div>
            <div className="flex gap-3">
              {result.wav_url && <a href={result.wav_url} className="crystal-bubble rounded-xl px-4 py-3 text-xs font-bold uppercase tracking-widest inline-flex gap-2"><Download size={14} /> WAV</a>}
              <a href={result.midi_url} className="crystal-bubble rounded-xl px-4 py-3 text-xs font-bold uppercase tracking-widest inline-flex gap-2"><Download size={14} /> MIDI</a>
            </div>
            <pre className="text-xs text-white/60 whitespace-pre-wrap">{JSON.stringify(result.metadata, null, 2)}</pre>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-white/30 text-xs uppercase tracking-widest">No generated instrument</div>
        )}
      </section>
    </div>
  )
}
