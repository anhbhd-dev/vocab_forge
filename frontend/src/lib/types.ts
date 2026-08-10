/** Kiểu dữ liệu khớp 1-1 với Pydantic schema ở `backend/app/schemas/api.py`. */

export type CardDirection =
  | 'en_to_vi'
  | 'vi_to_en'
  | 'production'
  | 'cluster_discrimination'

export type CardState = 'new' | 'learning' | 'review' | 'relearning'

/** error_type của review_logs (file 01) — KHÔNG có 'grammar'. */
export type ReviewErrorType =
  | 'meaning'
  | 'collocation'
  | 'spelling'
  | 'register'
  | 'none'

/** error_type của production_attempts — có 'grammar', không có 'spelling'. */
export type ProductionErrorType =
  | 'meaning'
  | 'collocation'
  | 'grammar'
  | 'register'
  | 'none'

export type EssayType =
  | 'opinion'
  | 'discussion'
  | 'problem_solution'
  | 'advantage_disadvantage'
  | 'general'

export interface User {
  id: string
  email: string
  daily_new_word_goal: number
  timezone: string
  created_at: string
}

export interface Deck {
  id: string
  name: string
  description: string | null
  created_at: string
}

export interface Example {
  id: string
  sentence: string
  essay_type: EssayType | null
  source: 'user_reading' | 'agent_generated' | null
}

export interface Mnemonic {
  id: string
  mnemonic_text: string
  mnemonic_type: string | null
}

export interface ReviewCard {
  id: string
  sense_id: string
  card_direction: CardDirection
  state: CardState
  due_at: string | null
  last_reviewed_at: string | null
  is_leech: boolean
  reps: number
  lapses: number
  /** D/S/R của FSRS — nguồn dữ liệu cho đường cong quên (signature element). */
  stability: number
  difficulty: number
  retrievability: number

  surface_form: string
  item_type: string
  ipa: string | null
  cefr_level: string | null
  definition_en: string
  definition_vi: string | null
  part_of_speech: string | null
  register: string | null

  examples: Example[]
  mnemonics: Mnemonic[]
  cluster_id: string | null
  interval_preview_days: Record<'again' | 'hard' | 'good' | 'easy', number>
}

export interface ReviewQueue {
  cards: ReviewCard[]
  due_count: number
  new_count: number
  daily_new_word_goal: number
}

export interface AnswerResponse {
  card_id: string
  state: CardState
  due_at: string
  interval_days: number
  stability: number
  difficulty: number
  reps: number
  lapses: number
  is_leech: boolean
  became_leech: boolean
  adjustments: string[]
  followups: string[]
}

export interface ReviewStats {
  due_today: number
  new_available: number
  reviewed_today: number
  streak_days: number
  retention_rate_7d: number | null
  retention_rate_30d: number | null
  total_cards: number
  leech_count: number
}

export interface IngestionJob {
  id: string
  deck_id: string | null
  source_type: string | null
  status: 'pending' | 'extracting' | 'enriching' | 'done' | 'failed'
  error_message: string | null
  created_at: string
  completed_at: string | null
  candidate_count: number
  approved_count: number
  awaiting_approval: boolean
}

export interface Candidate {
  id: string
  lexical_item_id: string
  surface_form: string
  item_type: string
  cefr_level: string | null
  reason: string | null
  sentence_context: string | null
  is_approved: boolean
}

export interface ProductionAttempt {
  id: string
  card_id: string
  user_sentence: string
  submitted_at: string
  status: 'pending' | 'graded'
  is_correct: boolean | null
  error_type: ProductionErrorType | null
  feedback_text: string | null
  corrected_sentence: string | null
  graded_by_model: string | null
  graded_at: string | null
}

export interface ClusterMember {
  sense_id: string
  surface_form: string
  definition_en: string
  distinguishing_note: string | null
}

export interface Cluster {
  id: string
  cluster_label: string | null
  created_at: string
  members: ClusterMember[]
}

export interface ClusterExercise {
  cluster_id: string
  cluster_label: string | null
  question_sentence: string
  correct_sense_id: string
  options: { sense_id: string; surface_form: string }[]
  explanation: string | null
}

export interface AnalyticsOverview {
  total_lexical_items: number
  total_cards: number
  cards_by_state: Partial<Record<CardState, number>>
  reviews_last_7d: number
  retention_rate_7d: number | null
  retention_rate_30d: number | null
  streak_days: number
  daily_new_word_goal: number
  ramp_up: { action: 'raise' | 'hold' | 'lower'; recommended_goal: number; reason: string }
  agent_cache: { agent_name: string; entries: number; hits: number }[]
}

export interface ErrorBreakdownItem {
  error_type: string
  count: number
  share: number
}

export interface ErrorBreakdown {
  review_errors: ErrorBreakdownItem[]
  production_errors: ErrorBreakdownItem[]
  total_reviews_with_error_type: number
  total_production_attempts: number
}

export interface Leech {
  card_id: string
  sense_id: string
  surface_form: string
  definition_en: string
  card_direction: CardDirection
  lapses: number
  reps: number
  latest_mnemonic: string | null
  mnemonic_regenerated: boolean
}
