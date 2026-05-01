export type JobStatus =
  | 'pending'
  | 'running'
  | 'summarizing'
  | 'completed'
  | 'failed'

export interface JobMeta {
  id: string
  status: JobStatus
  created_at: string
  updated_at: string
  audio_filename: string
  model: string
  language: string | null
  detected_language: string | null
  duration_seconds: number | null
  error: string | null
  summary_error: string | null
  template_id: string | null
}

export interface Template {
  id: string
  name: string
  description: string | null
  prompt: string
}

export interface Segment {
  start: number
  end: number
  text: string
}

export interface JobDetail extends JobMeta {
  text: string | null
  segments: Segment[] | null
  summary: string | null
}

export interface Health {
  status: string
  model_size: string
  device: string
  compute_type: string
  summary_enabled: boolean
  ollama_model: string | null
}

const BASE = '/api'

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error(`health failed: ${res.status}`)
  return res.json()
}

export async function listJobs(): Promise<JobMeta[]> {
  const res = await fetch(`${BASE}/jobs`)
  if (!res.ok) throw new Error(`listJobs failed: ${res.status}`)
  return res.json()
}

export async function getJob(id: string): Promise<JobDetail> {
  const res = await fetch(`${BASE}/jobs/${id}`)
  if (!res.ok) throw new Error(`getJob failed: ${res.status}`)
  return res.json()
}

export async function getTemplates(): Promise<Template[]> {
  const res = await fetch(`${BASE}/templates`)
  if (!res.ok) throw new Error(`getTemplates failed: ${res.status}`)
  return res.json()
}

export async function createJob(
  audio: Blob,
  filename: string,
  options: { language?: string; templateId?: string } = {},
): Promise<JobMeta> {
  const fd = new FormData()
  fd.append('audio', audio, filename)
  if (options.language) fd.append('language', options.language)
  if (options.templateId) fd.append('template_id', options.templateId)
  const res = await fetch(`${BASE}/jobs`, { method: 'POST', body: fd })
  if (!res.ok) throw new Error(`createJob failed: ${res.status}`)
  return res.json()
}
