import React, { useState, useEffect } from 'react'
import Head from 'next/head'
// NOTE: 環境変数でAPIベースURLを制御（既定: localhost:8000）
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type FileExtraction = {
  src_filename: string
  detected_type: 'rent' | 'sale' | 'unknown'
  property_name?: string
  room_label?: string
  area_sqm?: number
  rent_values_yen?: number[]
  sale_price_yen?: number
  tax_mode?: string
  confidence: number
  suggested_filename?: string
}

type JobStatus = {
  job_id: string
  status: string
  message?: string
  files: FileExtraction[]
}

export default function Home() {
  const [files, setFiles] = useState<FileList | null>(null)
  const [job, setJob] = useState<JobStatus | null>(null)
  const [loading, setLoading] = useState(false)

  const onUpload = async () => {
    if (!files || files.length === 0) return
    setLoading(true)
    const form = new FormData()
    Array.from(files).forEach(f => form.append('files', f))
    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        let msg = `アップロード失敗 (HTTP ${res.status})`
        try {
          const err = await res.json()
          if (err?.detail) msg = Array.isArray(err.detail) ? err.detail.map((d:any)=>d.msg||d).join(', ') : err.detail
          else if (err?.message) msg = err.message
        } catch {}
        alert(msg)
        setLoading(false)
        return
      }
      const data = await res.json()
      setJob(data)
    } catch (e: any) {
      alert(`アップロード時に通信エラーが発生しました: ${e?.message || e}`)
    } finally {
      setLoading(false)
    }
  }

  const overrideItem = (index: number, patch: Partial<FileExtraction>) => {
    if (!job) return
    const next = { ...job, files: job.files.map((f, i) => i === index ? { ...f, ...patch } : f) }
    setJob(next)
  }

  const applyOverrides = async () => {
    if (!job) return
    const body = {
      overrides: job.files.map((f, i) => ({
        index: i,
        property_name: f.property_name,
        room_label: f.room_label,
        area_sqm: f.area_sqm,
        detected_type: f.detected_type,
        tax_mode: f.tax_mode,
        sale_price_yen: f.sale_price_yen,
        rent_values_yen: f.rent_values_yen,
      }))
    }
    const res = await fetch(`${API_BASE}/api/job/${job.job_id}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    const data = await res.json()
    setJob(data)
  }

  const finalize = async () => {
    if (!job) return
    const res = await fetch(`${API_BASE}/api/job/${job.job_id}/finalize`, { method: 'POST' })
    const data = await res.json()
    // trigger download
    window.location.href = `${API_BASE}${data.download_url}`
  }

  return (
    <main style={{ maxWidth: 980, margin: '40px auto', padding: 16 }}>
      <Head><title>マイソクPDF自動リネーム（MVP）</title></Head>
      <h1>マイソクPDF自動リネーム（MVP）</h1>
      <p>PDFをドラッグ＆ドロップしてアップロードし、命名候補を確認のうえZIPで一括ダウンロードします。</p>

      <div style={{ border: '1px dashed #ccc', padding: 24, borderRadius: 8, margin: '16px 0' }}>
        <input
          type="file"
          accept="application/pdf,image/*"
          multiple
          onChange={(e) => setFiles(e.target.files)}
        />
        <button onClick={onUpload} disabled={loading} style={{ marginLeft: 12 }}>
          {loading ? 'アップロード中…' : 'アップロード'}
        </button>
      </div>

      {job && (
        <div>
          <h2>命名候補（編集可能）</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ borderBottom: '1px solid #ddd', padding: 8 }}>元ファイル</th>
                <th style={{ borderBottom: '1px solid #ddd', padding: 8 }}>種別</th>
                <th style={{ borderBottom: '1px solid #ddd', padding: 8 }}>物件名</th>
                <th style={{ borderBottom: '1px solid #ddd', padding: 8 }}>号室/階</th>
                <th style={{ borderBottom: '1px solid #ddd', padding: 8 }}>面積(売買)</th>
                <th style={{ borderBottom: '1px solid #ddd', padding: 8 }}>賃料群/価格</th>
                <th style={{ borderBottom: '1px solid #ddd', padding: 8 }}>税込判定</th>
                <th style={{ borderBottom: '1px solid #ddd', padding: 8 }}>命名後</th>
              </tr>
            </thead>
            <tbody>
              {job.files.map((f, idx) => (
                <tr key={idx}>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{f.src_filename}</td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                    <select
                      value={f.detected_type}
                      onChange={(e) => overrideItem(idx, { detected_type: e.target.value as any })}>
                      <option value="rent">賃貸</option>
                      <option value="sale">売買</option>
                      <option value="unknown">不明</option>
                    </select>
                  </td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                    <input
                      value={f.property_name || ''}
                      onChange={(e) => overrideItem(idx, { property_name: e.target.value })}
                      style={{ width: 180 }}
                    />
                  </td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                    <input
                      value={f.room_label || ''}
                      onChange={(e) => overrideItem(idx, { room_label: e.target.value })}
                      style={{ width: 100 }}
                    />
                  </td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                    <input
                      type="number"
                      step="0.01"
                      value={f.area_sqm ?? ''}
                      onChange={(e) => overrideItem(idx, { area_sqm: e.target.value ? parseFloat(e.target.value) : undefined })}
                      style={{ width: 100 }}
                    />
                  </td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                    {f.detected_type === 'rent' ? (
                      <input
                        value={(f.rent_values_yen || []).join(',')}
                        onChange={(e) => {
                          const arr = e.target.value.split(',').map(v => v.trim()).filter(Boolean).map(v => parseInt(v, 10)).filter(v => !isNaN(v))
                          overrideItem(idx, { rent_values_yen: arr })
                        }}
                        placeholder="例: 450000,880000"
                        style={{ width: 160 }}
                      />
                    ) : (
                      <input
                        type="number"
                        value={f.sale_price_yen ?? ''}
                        onChange={(e) => overrideItem(idx, { sale_price_yen: e.target.value ? parseInt(e.target.value, 10) : undefined })}
                        placeholder="円単位"
                        style={{ width: 140 }}
                      />
                    )}
                  </td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                    <select
                      value={f.tax_mode || '不明'}
                      onChange={(e) => overrideItem(idx, { tax_mode: e.target.value })}>
                      <option value="税込">税込</option>
                      <option value="税別">税別</option>
                      <option value="不明">不明</option>
                    </select>
                  </td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{f.suggested_filename}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: 16 }}>
            <button onClick={applyOverrides} style={{ marginRight: 8 }}>命名候補を更新</button>
            <button onClick={finalize}>ZIPで一括ダウンロード</button>
          </div>
        </div>
      )}
    </main>
  )
}
