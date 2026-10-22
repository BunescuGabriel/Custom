export type VoiceMap = Record<string, Record<string, string>>;

export type Job = {
  id: string;
  status: string;
  stage: string;
  cancel_requested: boolean;
  audio_generation_id: number | null;
  video_generation_id: number | null;
  error_message: string | null;
  result_url: string | null;
  result_name: string | null;
  result_kind: "audio" | "video" | null;
  audio_url: string | null;
  audio_name: string | null;
};

export type HistoryItem = {
  id: number;
  title: string;
  status: string;
  duration_seconds: number | null;
  created_at: string;
  file_url: string | null;
  file_name: string | null;
};

export type AppSettings = {
  video_width: number;
  video_height: number;
  video_fps: 24 | 30 | 60;
  title_duration_seconds: number;
  default_rate_percent: number;
  default_pitch_hz: number;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || "The request could not be processed.");
  }
  return response.json() as Promise<T>;
}

export const api = {
  config: () => request<{ voices: VoiceMap; settings: AppSettings }>("/api/config"),
  updateSettings: (settings: AppSettings) => request<AppSettings>("/api/settings", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings),
  }),
  uploadBackground: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<{ path: string; name: string }>("/api/backgrounds", { method: "POST", body: data });
  },
  createJob: (body: object) => request<Job>("/api/jobs", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  createVocabularyJob: (body: object) => request<Job>("/api/vocabulary/jobs", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  jobs: () => request<Job[]>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  cancelJob: (id: string) => request(`/api/jobs/${id}/cancel`, { method: "POST" }),
  audioHistory: () => request<HistoryItem[]>("/api/history/audio"),
  videoHistory: () => request<HistoryItem[]>("/api/history/video"),
};
