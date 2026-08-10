import type { ProductionErrorType, ReviewErrorType } from './types'

/**
 * Interval (ngày, dạng phân số) → nhãn ngắn trên nút rating.
 * Backend trả số ngày phân số (vd 0.00694 = 10 phút) vì `due_at` giữ độ chính xác
 * tới micro-giây cho same-day review (file 01 mục 3).
 */
export function formatInterval(days: number): string {
  const minutes = days * 24 * 60
  if (minutes < 1) return '<1m'
  if (minutes < 60) return `${Math.round(minutes)}m`
  if (days < 1) return `${Math.round(minutes / 60)}h`
  if (days < 30) return `${days < 10 ? days.toFixed(days % 1 ? 1 : 0) : Math.round(days)}d`
  if (days < 365) return `${(days / 30).toFixed(1)}mo`
  return `${(days / 365).toFixed(1)}y`
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}

export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })
}

/** Nhãn tiếng Việt cho từng loại lỗi — dùng chung toàn app. */
export const ERROR_TYPE_LABEL: Record<string, string> = {
  meaning: 'Sai nghĩa',
  collocation: 'Sai kết hợp từ',
  register: 'Sai văn phong',
  grammar: 'Sai ngữ pháp',
  spelling: 'Sai chính tả',
  none: 'Không lỗi',
}

/**
 * Giải thích NGẮN hệ quả tới lịch ôn (file 02 mục 5) — điểm khác biệt cốt lõi so với
 * Anki, nên phải nói rõ cho người học biết vì sao thẻ được/không được giãn lịch.
 */
export const ERROR_TYPE_EFFECT: Record<string, string> = {
  meaning: 'Giảm mạnh lịch ôn, ưu tiên ôn lại nghĩa cơ bản trước.',
  collocation: 'Giảm vừa phải, sẽ hiện thêm câu ví dụ thay vì lặp định nghĩa.',
  register: 'Giữ nguyên lịch ôn — đây là lỗi văn phong, không phải quên nghĩa.',
  grammar: 'Không ảnh hưởng lịch ôn của từ này.',
  spelling: 'Gần như giữ nguyên lịch ôn — bạn vẫn nhớ đúng nghĩa.',
  none: 'Lịch ôn giãn ra bình thường.',
}

export type AnyErrorType = ReviewErrorType | ProductionErrorType

/** Biến CSS màu tương ứng — khai báo một lần trong index.css (@theme). */
export function errorTypeColor(type: string | null | undefined): string {
  switch (type) {
    case 'meaning':
      return 'var(--err-meaning)'
    case 'collocation':
      return 'var(--err-collocation)'
    case 'register':
      return 'var(--err-register)'
    case 'grammar':
    case 'spelling':
      return 'var(--err-grammar)'
    default:
      return 'var(--err-none)'
  }
}

export const CARD_DIRECTION_LABEL: Record<string, string> = {
  en_to_vi: 'Anh → Việt',
  vi_to_en: 'Việt → Anh',
  production: 'Tự viết câu',
  cluster_discrimination: 'Phân biệt cận nghĩa',
}

export const CARD_STATE_LABEL: Record<string, string> = {
  new: 'Mới',
  learning: 'Đang học',
  review: 'Ôn tập',
  relearning: 'Học lại',
}

export const ESSAY_TYPE_LABEL: Record<string, string> = {
  opinion: 'Opinion',
  discussion: 'Discussion',
  problem_solution: 'Problem–Solution',
  advantage_disadvantage: 'Adv–Disadv',
  general: 'Chung',
}
