import { useState } from 'react'
import { Layers3 } from 'lucide-react'
import { UploadZone } from '@/components/controls/UploadZone'
import { api, APIError } from '@/utils/api'

export default function LarsNetSeparationTab() {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function upload() {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const created = await api.separate.upload(file)
      if (created.job_id) {
        setStatus(await api.separate.status(created.job_id))
      } else {
        setStatus(created)
      }
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Separation failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full grid grid-cols-[420px_1fr] gap-6">
      <section className="crystal-glass rounded-2xl p-6 space-y-5">
        <div className="flex items-center gap-3">
          <Layers3 size={18} className="text-rain-teal" />
          <h2 className="text-[12px] font-black uppercase tracking-[0.18em] text-white/70">LarsNet Separation</h2>
        </div>
        <UploadZone onFileSelected={setFile} />
        <button disabled={!file || busy} onClick={upload} className="w-full crystal-bubble rounded-xl py-3 text-xs font-bold uppercase tracking-widest disabled:opacity-40">
          {busy ? 'Submitting...' : 'Separate'}
        </button>
        {error && <p className="text-xs text-rain-red">{error}</p>}
      </section>
      <section className="crystal-glass rounded-2xl p-6 overflow-auto">
        <pre className="text-xs text-white/60 whitespace-pre-wrap">{status ? JSON.stringify(status, null, 2) : 'No separation job'}</pre>
      </section>
    </div>
  )
}
