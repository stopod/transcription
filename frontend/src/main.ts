import './style.css'
import {
  createJob,
  getHealth,
  getJob,
  listJobs,
  type JobDetail,
  type JobMeta,
} from './api'
import { Recorder, extensionForMime } from './recorder'

const recorder = new Recorder()
let pollHandle: number | null = null

const app = document.querySelector<HTMLDivElement>('#app')!
app.innerHTML = `
  <main>
    <h1>議事録レコーダー</h1>
    <section class="controls">
      <button id="rec-btn" type="button">録音開始</button>
      <label id="file-label" class="file-btn">
        ファイルを取り込み
        <input id="file-input" type="file" accept="audio/*,.aac,.m4a,.mp3,.wav,.flac,.ogg,.opus,.webm" hidden />
      </label>
      <span id="rec-status">未録音</span>
    </section>
    <section class="current">
      <h2>現在のジョブ</h2>
      <div id="current">なし</div>
    </section>
    <section class="history">
      <h2>履歴</h2>
      <ul id="history"><li>読み込み中...</li></ul>
    </section>
    <footer>
      <span id="health">backend: ?</span>
    </footer>
  </main>
`

const recBtn = document.querySelector<HTMLButtonElement>('#rec-btn')!
const recStatus = document.querySelector<HTMLSpanElement>('#rec-status')!
const fileInput = document.querySelector<HTMLInputElement>('#file-input')!
const currentEl = document.querySelector<HTMLDivElement>('#current')!
const historyEl = document.querySelector<HTMLUListElement>('#history')!
const healthEl = document.querySelector<HTMLSpanElement>('#health')!

recBtn.addEventListener('click', onToggleRecord)
fileInput.addEventListener('change', onPickFile)
void refreshHistory()
void checkHealth()

async function checkHealth() {
  try {
    const h = await getHealth()
    healthEl.textContent = `backend: ${h.status} / ${h.model_size} on ${h.device} (${h.compute_type})`
  } catch (e) {
    healthEl.textContent = `backend: unreachable (${(e as Error).message})`
  }
}

async function onToggleRecord() {
  if (recorder.isRecording()) {
    recBtn.disabled = true
    recStatus.textContent = '停止中...'
    try {
      const result = await recorder.stop()
      const ext = extensionForMime(result.mimeType)
      const stamp = new Date().toISOString().replace(/[:.]/g, '-')
      const filename = `recording-${stamp}${ext}`
      await uploadAndTrack(result.blob, filename)
    } catch (e) {
      recStatus.textContent = `エラー: ${(e as Error).message}`
    } finally {
      recBtn.disabled = false
      recBtn.textContent = '録音開始'
    }
  } else {
    try {
      await recorder.start()
      recBtn.textContent = '録音停止'
      recStatus.textContent = '録音中'
    } catch (e) {
      recStatus.textContent = `マイク取得失敗: ${(e as Error).message}`
    }
  }
}

async function onPickFile() {
  const file = fileInput.files?.[0]
  fileInput.value = ''
  if (!file) return
  try {
    await uploadAndTrack(file, file.name)
  } catch (e) {
    recStatus.textContent = `エラー: ${(e as Error).message}`
  }
}

async function uploadAndTrack(blob: Blob, filename: string) {
  recStatus.textContent = `アップロード中 (${(blob.size / 1024 / 1024).toFixed(1)} MB)...`
  const meta = await createJob(blob, filename)
  recStatus.textContent = `ジョブ作成: ${meta.id}`
  startPolling(meta.id)
  await refreshHistory()
}

function startPolling(jobId: string) {
  if (pollHandle !== null) window.clearInterval(pollHandle)
  pollHandle = window.setInterval(async () => {
    try {
      const job = await getJob(jobId)
      renderCurrent(job)
      if (job.status === 'completed' || job.status === 'failed') {
        if (pollHandle !== null) window.clearInterval(pollHandle)
        pollHandle = null
        await refreshHistory()
      }
    } catch {
      // transient errors are tolerated; next tick will retry
    }
  }, 2000)
}

function renderCurrent(job: JobDetail) {
  let body = ''
  if (job.status === 'completed') {
    if (job.text && job.text.trim()) {
      body = `<pre class="transcript">${escapeHtml(job.text)}</pre>
              <button type="button" id="copy-btn">全文コピー</button>`
    } else {
      body = `<p>完了しました（音声検出なし — マイク音量が低かった可能性があります）</p>`
    }
  } else if (job.status === 'failed') {
    body = `<p class="error">失敗: ${escapeHtml(job.error ?? '')}</p>`
  } else {
    body = `<p>処理中...</p>`
  }
  currentEl.innerHTML = `
    <div class="job-card">
      <div><strong>${job.id}</strong></div>
      <div>状態: ${job.status}</div>
      <div>言語: ${job.detected_language ?? job.language ?? 'auto'}</div>
      ${
        job.duration_seconds
          ? `<div>長さ: ${job.duration_seconds.toFixed(1)} 秒</div>`
          : ''
      }
      ${body}
    </div>
  `
  const copyBtn = document.querySelector<HTMLButtonElement>('#copy-btn')
  if (copyBtn && job.text) {
    copyBtn.addEventListener('click', () => {
      void navigator.clipboard.writeText(job.text!)
      copyBtn.textContent = 'コピー済み'
    })
  }
}

async function refreshHistory() {
  try {
    const jobs = await listJobs()
    if (jobs.length === 0) {
      historyEl.innerHTML = `<li>履歴なし</li>`
      return
    }
    historyEl.innerHTML = jobs.map(renderHistoryItem).join('')
    historyEl.querySelectorAll<HTMLAnchorElement>('a[data-job]').forEach((a) => {
      a.addEventListener('click', async (e) => {
        e.preventDefault()
        const id = a.dataset.job!
        const job = await getJob(id)
        renderCurrent(job)
      })
    })
  } catch {
    historyEl.innerHTML = `<li>履歴取得失敗</li>`
  }
}

function renderHistoryItem(j: JobMeta): string {
  const ts = new Date(j.created_at).toLocaleString()
  return `<li><a href="#" data-job="${j.id}">${ts}</a> — ${j.status} (${escapeHtml(j.audio_filename)})</li>`
}

function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"']/g,
    (c) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[c]!,
  )
}
