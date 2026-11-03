export type Params = {
  title: string
  idea: string
  caption: string
  lyrics: string
  duration: number
  seed: number
  instrumental: boolean
  vocal_language: string
}

export type Track = {
  id: string
  created_at: string
  engine: string
  title: string
  idea: string
  caption: string
  lyrics: string
  duration: number
  seed: number
  params: Params
  meta: { bpm?: number | null; keyscale?: string | null; dit_model?: string }
  wav_url: string
  mp3_url: string
}

export type Job = {
  id: string
  status: 'queued' | 'running' | 'done' | 'error'
  error: string | null
  position: number
  params: Params
}

export type Config = {
  engine: string
  engine_ready: boolean
  engine_error: string | null
  lyrics_enabled: boolean
}

export type Song = { title: string; caption: string; lyrics: string }

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const detail = await r.json().then((j) => j.detail, () => r.statusText)
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return r.status === 204 ? (undefined as T) : r.json()
}

export const api = {
  config: () => req<Config>('GET', '/api/config'),
  tracks: () => req<Track[]>('GET', '/api/tracks'),
  jobs: () => req<Job[]>('GET', '/api/jobs'),
  generate: (p: Params) => req<{ id: string }>('POST', '/api/jobs', p),
  dismissJob: (id: string) => req<void>('DELETE', `/api/jobs/${id}`),
  deleteTrack: (id: string) => req<void>('DELETE', `/api/tracks/${id}`),
  writeSong: (b: {
    idea: string
    style: string
    lyrics: string
    language: string
    instrumental: boolean
    duration: number
  }) => req<Song>('POST', '/api/lyrics', b),
}
