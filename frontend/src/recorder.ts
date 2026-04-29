export interface RecordingResult {
  blob: Blob
  mimeType: string
  duration: number
}

const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4',
]

function pickMimeType(): string {
  for (const c of MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(c)) return c
  }
  return ''
}

export class Recorder {
  private mediaRecorder: MediaRecorder | null = null
  private chunks: Blob[] = []
  private stream: MediaStream | null = null
  private startTime = 0
  private mimeType = ''

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })
    this.mimeType = pickMimeType()
    this.mediaRecorder = new MediaRecorder(this.stream, {
      mimeType: this.mimeType,
      audioBitsPerSecond: 64_000,
    })
    this.chunks = []
    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data)
    }
    this.mediaRecorder.start(1000)
    this.startTime = performance.now()
  }

  isRecording(): boolean {
    return this.mediaRecorder?.state === 'recording'
  }

  stop(): Promise<RecordingResult> {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder) return reject(new Error('not started'))
      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.chunks, { type: this.mimeType })
        const duration = (performance.now() - this.startTime) / 1000
        this.cleanup()
        resolve({ blob, mimeType: this.mimeType, duration })
      }
      this.mediaRecorder.stop()
    })
  }

  private cleanup(): void {
    this.stream?.getTracks().forEach((t) => t.stop())
    this.stream = null
    this.mediaRecorder = null
  }
}

export function extensionForMime(mime: string): string {
  if (mime.includes('webm')) return '.webm'
  if (mime.includes('ogg')) return '.ogg'
  if (mime.includes('mp4')) return '.m4a'
  return '.bin'
}
