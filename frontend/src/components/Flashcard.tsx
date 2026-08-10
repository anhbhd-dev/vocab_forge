import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { BookOpen, Lightbulb, Sparkles } from 'lucide-react'
import type { ReviewCard, ReviewErrorType } from '@/lib/types'
import {
  CARD_DIRECTION_LABEL,
  CARD_STATE_LABEL,
  ERROR_TYPE_EFFECT,
  ESSAY_TYPE_LABEL,
  formatInterval,
} from '@/lib/format'
import { HighlighterSweep, SweepBar } from '@/components/HighlighterSweep'
import { ErrorTypeBadge } from '@/components/ErrorTypeBadge'
import { PronounceButton } from '@/components/PronounceButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

const RATINGS = [
  { value: 1 as const, label: 'Again', key: 'again' as const, token: 'var(--rate-again)' },
  { value: 2 as const, label: 'Hard', key: 'hard' as const, token: 'var(--rate-hard)' },
  { value: 3 as const, label: 'Good', key: 'good' as const, token: 'var(--rate-good)' },
  { value: 4 as const, label: 'Easy', key: 'easy' as const, token: 'var(--rate-easy)' },
]

/** Loại lỗi chọn được khi ôn — đúng tập của review_logs (KHÔNG có 'grammar'). */
const ERROR_CHOICES: ReviewErrorType[] = ['meaning', 'collocation', 'spelling', 'register']

interface Props {
  card: ReviewCard
  index: number
  total: number
  onAnswer: (rating: 1 | 2 | 3 | 4, errorType?: ReviewErrorType) => void
  busy?: boolean
}

/**
 * COMPONENT 1 (file 05): flashcard review — mặt trước/sau + 4 nút rating.
 *
 * Bố cục "một trang sổ tay": trang giấy đơn căn giữa, đường lề đỏ dọc bên trái,
 * số thẻ ở góc như số trang. Không sidebar, không thanh điều hướng — màn hình này
 * người học nhìn hàng trăm lần mỗi ngày nên mọi thứ không phục vụ việc nhớ đều bị bỏ.
 *
 * Khi lật thẻ, từ vựng được tô bằng vệt bút dạ (signature element) có độ đầy tương
 * ứng stability — xem components/HighlighterSweep.tsx.
 */
export function Flashcard({ card, index, total, onAnswer, busy }: Props) {
  const [revealed, setRevealed] = useState(false)
  const [errorType, setErrorType] = useState<ReviewErrorType | undefined>()
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    setRevealed(false)
    setErrorType(undefined)
  }, [card.id])

  // Phím tắt: Space lật thẻ, 1-4 chấm điểm — người học nghiêm túc dùng bàn phím.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (busy) return
      const target = event.target as HTMLElement | null
      if (target && ['INPUT', 'TEXTAREA'].includes(target.tagName)) return

      if (event.code === 'Space' || event.code === 'Enter') {
        event.preventDefault()
        if (!revealed) setRevealed(true)
        return
      }
      if (revealed && ['1', '2', '3', '4'].includes(event.key)) {
        event.preventDefault()
        const rating = Number(event.key) as 1 | 2 | 3 | 4
        onAnswer(rating, rating <= 2 ? errorType : undefined)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [revealed, errorType, onAnswer, busy])

  const askForVietnamese = card.card_direction === 'en_to_vi'
  const front = askForVietnamese ? card.surface_form : (card.definition_vi ?? card.definition_en)
  const back = askForVietnamese ? (card.definition_vi ?? card.definition_en) : card.surface_form

  return (
    <motion.article
      key={card.id}
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className="paper-margin relative rounded-2xl border bg-card px-7 py-6 shadow-sm sm:px-12 sm:py-10"
    >
      {/* Đầu trang sổ: nhãn loại thẻ bên trái, "số trang" bên phải */}
      <header className="mb-7 flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-2">
          <span>{CARD_DIRECTION_LABEL[card.card_direction]}</span>
          <span aria-hidden>·</span>
          <span>{CARD_STATE_LABEL[card.state]}</span>
          {card.is_leech && (
            <Badge
              variant="outline"
              className="border-redpen/40 text-redpen"
              title="Từ bị quên nhiều lần — hệ thống đang sinh mẹo nhớ mới"
            >
              từ khó
            </Badge>
          )}
        </span>
        <span className="tnum">
          {index + 1}/{total}
        </span>
      </header>

      {/* --- Mặt trước --- */}
      <h2 className="font-heading text-4xl leading-tight font-semibold tracking-tight sm:text-5xl">
        {revealed && askForVietnamese ? (
          <HighlighterSweep stability={card.stability}>{front}</HighlighterSweep>
        ) : (
          front
        )}
      </h2>

      {/* Dòng tra cứu kiểu từ điển: /phiên âm/ + loa, rồi mới tới nhãn phân loại.
          Chiều vi→en KHÔNG hiện phiên âm lẫn nút phát âm ở mặt trước — nghe được chính
          là đọc trước đáp án. */}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
        {askForVietnamese && card.ipa && <span className="tnum">/{card.ipa}/</span>}
        {askForVietnamese && (
          <PronounceButton audioUrl={card.audio_url} text={card.surface_form} size="sm" />
        )}
        {card.cefr_level && <span>{card.cefr_level}</span>}
        {card.part_of_speech && <span>{card.part_of_speech}</span>}
        {card.register && <span>{card.register}</span>}
      </div>

      {/* Vệt bút dạ thu nhỏ: độ bền trí nhớ của chính từ này */}
      <div className="mt-5 flex items-center gap-3">
        <SweepBar stability={card.stability} className="max-w-40 flex-1" />
        <span className="tnum text-xs text-muted-foreground">
          {card.reps === 0
            ? // Thẻ chưa từng ôn: chưa có trí nhớ nào để đo, hiển thị 0% sẽ gây hiểu
              // nhầm là "đã quên sạch".
              'từ mới'
            : `nhớ ${Math.round(card.retrievability * 100)}% · bền ${card.stability.toFixed(1)}d`}
        </span>
      </div>

      <AnimatePresence mode="wait">
        {!revealed ? (
          <motion.div key="prompt" exit={{ opacity: 0 }}>
            <Button
              variant="outline"
              onClick={() => setRevealed(true)}
              className="mt-8 h-14 w-full border-dashed text-muted-foreground"
            >
              Hiện đáp án
              <kbd className="ml-2 rounded border px-1.5 py-0.5 text-[11px]">Space</kbd>
            </Button>
          </motion.div>
        ) : (
          <motion.div
            key="answer"
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="mt-8 space-y-7"
          >
            <Separator />

            {/* --- Mặt sau --- */}
            <div>
              <p className="font-heading flex items-center gap-2 text-2xl font-medium">
                {!askForVietnamese ? (
                  <HighlighterSweep stability={card.stability}>{back}</HighlighterSweep>
                ) : (
                  back
                )}
                {/* Chiều vi→en: giờ đáp án đã hiện, nghe phát âm mới không bị lộ trước. */}
                {!askForVietnamese && (
                  <PronounceButton audioUrl={card.audio_url} text={card.surface_form} />
                )}
              </p>
              {!askForVietnamese && card.ipa && (
                <p className="tnum mt-1 text-sm text-muted-foreground">/{card.ipa}/</p>
              )}
              {askForVietnamese && card.definition_vi && (
                <p className="mt-2 text-muted-foreground">{card.definition_en}</p>
              )}
            </div>

            {card.examples.length > 0 && (
              <section>
                <p className="mb-3 flex items-center gap-1.5 text-[11px] tracking-wide text-muted-foreground uppercase">
                  <BookOpen className="size-3.5" aria-hidden /> Ví dụ
                </p>
                <ul className="space-y-3">
                  {card.examples.slice(0, 4).map((example) => (
                    <li key={example.id} className="text-[15px] leading-relaxed">
                      <Badge
                        variant="outline"
                        className={`mr-2 align-middle text-[10px] ${
                          example.source === 'user_reading'
                            ? 'border-mint/40 text-mint'
                            : 'text-muted-foreground'
                        }`}
                      >
                        {example.source === 'user_reading'
                          ? 'bài đọc của bạn'
                          : (ESSAY_TYPE_LABEL[example.essay_type ?? 'general'] ?? 'chung')}
                      </Badge>
                      {example.sentence}
                      {/* Nghe cả câu: trọng âm và nối âm của collocation chỉ lộ ra khi
                          nó nằm trong câu, nghe từ rời không thấy được. */}
                      <PronounceButton
                        audioUrl={example.audio_url}
                        text={example.sentence}
                        size="sm"
                        className="ml-1 align-middle"
                      />
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {card.mnemonics.length > 0 && (
              <section className="rounded-xl border-l-2 border-highlight bg-highlight/10 px-4 py-3 text-sm">
                <p className="mb-1 flex items-center gap-1.5 text-[11px] tracking-wide text-muted-foreground uppercase">
                  <Lightbulb className="size-3.5" aria-hidden /> Mẹo nhớ
                  {card.mnemonics.length > 1 && (
                    <span className="text-mint">(đã đổi cách tiếp cận)</span>
                  )}
                </p>
                {card.mnemonics[card.mnemonics.length - 1].mnemonic_text}
              </section>
            )}

            {/* --- Phân loại lỗi: đầu vào cho việc điều chỉnh lịch ôn theo loại lỗi
                   (file 02 mục 5) — thứ Anki không có --- */}
            <section>
              <p className="mb-2 flex items-center gap-1.5 text-[11px] tracking-wide text-muted-foreground uppercase">
                <Sparkles className="size-3.5" aria-hidden /> Nếu sai, sai ở đâu? (không bắt
                buộc)
              </p>
              <div className="flex flex-wrap gap-2">
                {ERROR_CHOICES.map((choice) => (
                  <button
                    key={choice}
                    onClick={() => setErrorType(errorType === choice ? undefined : choice)}
                    className={`rounded-full transition ${
                      errorType === choice ? 'opacity-100' : 'opacity-45 hover:opacity-80'
                    }`}
                    aria-pressed={errorType === choice}
                  >
                    <ErrorTypeBadge type={choice} size="sm" />
                  </button>
                ))}
              </div>
              {errorType && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {ERROR_TYPE_EFFECT[errorType]}
                </p>
              )}
            </section>

            {/* --- 4 nút rating --- */}
            <div className="grid grid-cols-4 gap-2">
              {RATINGS.map((rating) => (
                <button
                  key={rating.value}
                  disabled={busy}
                  onClick={() => onAnswer(rating.value, rating.value <= 2 ? errorType : undefined)}
                  className="flex flex-col items-center gap-1 rounded-xl border px-2 py-3 transition hover:-translate-y-0.5 disabled:opacity-40"
                  style={{
                    borderColor: `color-mix(in srgb, ${rating.token} 45%, transparent)`,
                    backgroundColor: `color-mix(in srgb, ${rating.token} 8%, transparent)`,
                  }}
                >
                  <span className="text-sm font-semibold" style={{ color: rating.token }}>
                    {rating.label}
                  </span>
                  <span className="tnum text-xs text-muted-foreground">
                    {formatInterval(card.interval_preview_days[rating.key] ?? 0)}
                  </span>
                  <kbd className="text-[10px] text-muted-foreground">{rating.value}</kbd>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  )
}
