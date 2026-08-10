import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, Loader2, PenTool } from 'lucide-react'
import { toast } from 'sonner'
import { api, pollUntil } from '@/lib/api'
import type { ProductionAttempt, ReviewCard } from '@/lib/types'
import { ERROR_TYPE_EFFECT, errorTypeColor } from '@/lib/format'
import { ErrorTypeBadge } from '@/components/ErrorTypeBadge'
import { HighlighterSweep } from '@/components/HighlighterSweep'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface Props {
  card: ReviewCard
  index: number
  total: number
  /** Sang thẻ kế — KHÔNG chờ chấm xong (file 00 mục 4.2). */
  onNext: () => void
}

/**
 * COMPONENT 3 (file 05): ô viết câu + feedback AI, tô màu theo error_type.
 *
 * Điểm UX quan trọng theo file 00 mục 4.2: chấm bài BẮT BUỘC gọi LLM nên chậm, nhưng
 * KHÔNG được chặn cả buổi ôn. Vì vậy ngay sau khi gửi câu, nút "Thẻ tiếp theo" mở
 * ngay; kết quả chấm về sau sẽ báo bằng toast nếu người học đã đi tiếp.
 */
export function ProductionPanel({ card, index, total, onNext }: Props) {
  const [sentence, setSentence] = useState('')
  const [attempt, setAttempt] = useState<ProductionAttempt | null>(null)
  const [grading, setGrading] = useState(false)
  const reduceMotion = useReducedMotion()
  const mounted = useRef(true)

  useEffect(() => {
    setSentence('')
    setAttempt(null)
    setGrading(false)
  }, [card.id])

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  async function submit() {
    if (!sentence.trim()) return
    setGrading(true)
    const target = card.surface_form
    try {
      const { attempt_id } = await api.submitAttempt(card.id, sentence.trim())
      const graded = await pollUntil(
        () => api.attempt(attempt_id),
        (value) => value.status === 'graded',
        { intervalMs: 1500, timeoutMs: 90_000 },
      )
      if (mounted.current) setAttempt(graded)
      else {
        // Người học đã sang thẻ khác — báo kết quả bằng toast thay vì mất luôn.
        toast(`Đã chấm: ${target}`, { description: graded.feedback_text ?? undefined })
      }
    } catch (err) {
      toast.error('Không chấm được câu', { description: (err as Error).message })
    } finally {
      if (mounted.current) setGrading(false)
    }
  }

  return (
    <motion.article
      key={card.id}
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className="paper-margin rounded-2xl border bg-card px-7 py-6 shadow-sm sm:px-12 sm:py-10"
    >
      <header className="mb-6 flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <PenTool className="size-3.5" aria-hidden /> Tự viết câu
        </span>
        <span className="tnum">
          {index + 1}/{total}
        </span>
      </header>

      <h2 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
        <HighlighterSweep stability={card.stability}>{card.surface_form}</HighlighterSweep>
      </h2>
      <p className="mt-3 text-muted-foreground">{card.definition_en}</p>

      <Textarea
        value={sentence}
        onChange={(event) => setSentence(event.target.value)}
        disabled={!!attempt}
        rows={4}
        aria-label="Viết một câu dùng cụm từ này"
        placeholder="Viết một câu academic dùng đúng cụm từ này…"
        className="mt-7 resize-none bg-background text-[15px] leading-relaxed"
      />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!attempt && (
          <Button onClick={submit} disabled={!sentence.trim() || grading}>
            {grading && <Loader2 className="size-4 animate-spin" aria-hidden />}
            Gửi chấm
          </Button>
        )}
        <Button variant="ghost" onClick={onNext}>
          {attempt ? 'Thẻ tiếp theo' : 'Sang thẻ tiếp theo'}
          <ArrowRight className="size-4" aria-hidden />
        </Button>
        {grading && (
          <span className="text-xs text-muted-foreground">
            AI đang chấm — bạn cứ đi tiếp, có kết quả sẽ báo.
          </span>
        )}
      </div>

      <AnimatePresence>
        {attempt && (
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 rounded-xl border-l-2 bg-background px-5 py-4"
            style={{ borderLeftColor: errorTypeColor(attempt.error_type) }}
          >
            <div className="flex flex-wrap items-center gap-3">
              <ErrorTypeBadge type={attempt.error_type} />
              <span className="text-sm text-muted-foreground">
                {attempt.is_correct ? 'Câu dùng đúng' : 'Cần sửa'}
              </span>
            </div>

            {attempt.feedback_text && (
              <p className="mt-3 text-[15px] leading-relaxed">{attempt.feedback_text}</p>
            )}

            {attempt.corrected_sentence && (
              <p className="mt-3 rounded-lg bg-muted px-4 py-3 text-[15px] leading-relaxed">
                <span className="mr-2 text-[11px] tracking-wide text-muted-foreground uppercase">
                  Câu sửa
                </span>
                {attempt.corrected_sentence}
              </p>
            )}

            <p className="mt-3 text-xs text-muted-foreground">
              {ERROR_TYPE_EFFECT[attempt.error_type ?? 'none']}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  )
}
