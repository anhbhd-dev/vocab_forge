/** Client gọi REST API — mỗi hàm ứng với một endpoint trong file 01 mục 2. */

import type {
  AnalyticsOverview,
  AnswerResponse,
  Candidate,
  Cluster,
  ClusterExercise,
  Deck,
  ErrorBreakdown,
  IngestionJob,
  Leech,
  ProductionAttempt,
  ReviewErrorType,
  ReviewQueue,
  ReviewStats,
  User,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'vf-token'

/**
 * Đường dẫn tương đối từ API (vd `/audio/ab12.mp3`) → URL tuyệt đối tải được.
 *
 * Backend trả về đường dẫn tương đối chứ không phải URL đầy đủ để đổi domain không
 * phải migrate dữ liệu trong DB — phần ghép host nằm ở đây.
 */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null
  return `${BASE_URL}${path}`
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  })

  if (response.status === 401) {
    setToken(null)
    throw new ApiError(401, 'Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.')
  }

  if (!response.ok) {
    let detail = `Lỗi ${response.status}`
    try {
      const body = await response.json()
      // FastAPI trả 422 với detail là mảng lỗi validate.
      detail =
        typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail ?? body)
    } catch {
      /* body không phải JSON — giữ message mặc định */
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })

export const api = {
  // ---- Auth & User ----
  register: (email: string, password: string) =>
    post<{ access_token: string }>('/api/auth/register', { email, password }),
  login: (email: string, password: string) =>
    post<{ access_token: string }>('/api/auth/login', { email, password }),
  me: () => request<User>('/api/users/me'),
  updateSettings: (patch: {
    daily_new_word_goal?: number
    daily_new_min?: number
    daily_new_max?: number
    timezone?: string
  }) =>
    request<User>('/api/users/me/settings', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  // ---- Decks & lexical items ----
  decks: () => request<Deck[]>('/api/decks'),
  createDeck: (name: string, description?: string) =>
    post<Deck>('/api/decks', { name, description }),
  addLexicalItem: (payload: {
    surface_form: string
    item_type?: string
    deck_id?: string | null
    sentence_context?: string | null
  }) => post<{ lexical_item_id: string; status: string }>('/api/lexical-items', payload),

  // ---- Ingestion ----
  createJob: (payload: {
    source_type: 'pasted_text' | 'url' | 'pdf'
    raw_text?: string
    url?: string
    deck_id?: string | null
    band_min?: number
    band_max?: number
  }) => post<{ job_id: string; status: string }>('/api/ingestion/jobs', payload),
  job: (id: string) => request<IngestionJob>(`/api/ingestion/jobs/${id}`),
  candidates: (id: string) =>
    request<Candidate[]>(`/api/ingestion/jobs/${id}/candidates`),
  approve: (id: string, ids: string[]) =>
    post<{ approved_count: number }>(`/api/ingestion/jobs/${id}/approve`, {
      selected_lexical_item_ids: ids,
    }),

  // ---- Review (fast path) ----
  queue: (limit = 30) => request<ReviewQueue>(`/api/review/queue?limit=${limit}`),
  answer: (cardId: string, rating: 1 | 2 | 3 | 4, errorType?: ReviewErrorType) =>
    post<AnswerResponse>(`/api/review/cards/${cardId}/answer`, {
      rating,
      error_type: errorType ?? null,
    }),
  stats: () => request<ReviewStats>('/api/review/stats'),

  // ---- Production grading ----
  submitAttempt: (cardId: string, sentence: string, essayContext?: string) =>
    post<{ attempt_id: string; status: string }>('/api/production/attempts', {
      card_id: cardId,
      user_sentence: sentence,
      essay_context: essayContext ?? null,
    }),
  attempt: (id: string) => request<ProductionAttempt>(`/api/production/attempts/${id}`),

  // ---- Clusters ----
  clusters: () => request<Cluster[]>('/api/clusters'),
  cluster: (id: string) => request<Cluster>(`/api/clusters/${id}`),
  clusterPractice: (id: string) =>
    request<ClusterExercise>(`/api/clusters/${id}/practice`),

  // ---- Analytics ----
  overview: () => request<AnalyticsOverview>('/api/analytics/overview'),
  errorBreakdown: (days = 30) =>
    request<ErrorBreakdown>(`/api/analytics/error-breakdown?days=${days}`),
  leeches: () => request<Leech[]>('/api/analytics/leeches'),
}

/**
 * Poll cho tới khi điều kiện thoả — dùng cho 2 luồng bất đồng bộ trong spec:
 * ingestion job (file 01 mục 2) và production grading (file 00 mục 4.2).
 */
export async function pollUntil<T>(
  fetcher: () => Promise<T>,
  done: (value: T) => boolean,
  { intervalMs = 1200, timeoutMs = 180_000 } = {},
): Promise<T> {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const value = await fetcher()
    if (done(value)) return value
    if (Date.now() > deadline) {
      throw new ApiError(408, 'Quá thời gian chờ — thử tải lại trang.')
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}
