import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, Check, Layers, X } from 'lucide-react'
import { api } from '@/lib/api'
import type { ClusterExercise, ReviewCard } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

interface Props {
  card: ReviewCard
  index: number
  total: number
  onAnswer: (correct: boolean) => void
  onSkip: () => void
}

/**
 * COMPONENT 4 (file 05): bài tập phân biệt cận nghĩa — chọn từ đúng trong nhóm.
 *
 * Câu hỏi do backend dựng từ ví dụ CÓ SẴN trong DB (khoét chỗ trống), không gọi LLM —
 * endpoint này nằm trong vòng review nên phải tuân thủ fast path.
 *
 * Sau khi chọn, hiện `distinguishing_note` của Cluster Agent cho TỪNG từ để người học
 * hiểu vì sao đúng/sai, thay vì chỉ báo đúng-sai suông.
 */
export function ClusterExerciseCard({ card, index, total, onAnswer, onSkip }: Props) {
  const [exercise, setExercise] = useState<ClusterExercise | null>(null)
  const [notes, setNotes] = useState<Record<string, string | null>>({})
  const [picked, setPicked] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [unavailable, setUnavailable] = useState(false)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    let active = true
    setPicked(null)
    setExercise(null)
    setUnavailable(false)
    setLoading(true)

    async function load() {
      if (!card.cluster_id) {
        if (active) {
          setUnavailable(true)
          setLoading(false)
        }
        return
      }
      try {
        const [ex, cluster] = await Promise.all([
          api.clusterPractice(card.cluster_id),
          api.cluster(card.cluster_id),
        ])
        if (!active) return
        setExercise(ex)
        setNotes(Object.fromEntries(cluster.members.map((m) => [m.sense_id, m.distinguishing_note])))
      } catch {
        if (active) setUnavailable(true)
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [card.id, card.cluster_id])

  if (loading) {
    return (
      <div className="paper-margin space-y-4 rounded-2xl border bg-card px-7 py-8 sm:px-12">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  if (unavailable || !exercise) {
    return (
      <div className="paper-margin rounded-2xl border bg-card px-7 py-10 text-center sm:px-12">
        <p className="font-heading text-lg font-medium">Chưa dựng được bài tập cho nhóm này</p>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          Cần ít nhất 2 từ trong nhóm và một câu ví dụ có chứa từ mục tiêu.
        </p>
        <Button className="mt-5" onClick={onSkip}>
          Thẻ tiếp theo <ArrowRight className="size-4" aria-hidden />
        </Button>
      </div>
    )
  }

  const correct = picked === exercise.correct_sense_id

  return (
    <motion.article
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className="paper-margin rounded-2xl border bg-card px-7 py-6 shadow-sm sm:px-12 sm:py-10"
    >
      <header className="mb-6 flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <Layers className="size-3.5" aria-hidden /> Phân biệt cận nghĩa
        </span>
        <span className="tnum">
          {index + 1}/{total}
        </span>
      </header>

      {exercise.cluster_label && (
        <h2 className="font-heading text-xl font-semibold tracking-tight">
          {exercise.cluster_label}
        </h2>
      )}

      <p className="mt-6 text-2xl leading-relaxed">{exercise.question_sentence}</p>

      <div className="mt-7 grid gap-2 sm:grid-cols-2">
        {exercise.options.map((option) => {
          const isCorrectOption = option.sense_id === exercise.correct_sense_id
          const isPicked = picked === option.sense_id
          let tone = 'var(--rule)'
          if (picked) {
            if (isCorrectOption) tone = 'var(--mint)'
            else if (isPicked) tone = 'var(--redpen)'
          }
          return (
            <button
              key={option.sense_id}
              disabled={!!picked}
              onClick={() => setPicked(option.sense_id)}
              className="rounded-xl border px-4 py-3 text-left transition hover:-translate-y-0.5 disabled:translate-y-0"
              style={{
                borderColor: tone,
                backgroundColor:
                  picked && (isCorrectOption || isPicked)
                    ? `color-mix(in srgb, ${tone} 10%, transparent)`
                    : 'transparent',
              }}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="font-heading font-medium">{option.surface_form}</span>
                {picked && isCorrectOption && (
                  <Check className="size-4 text-mint" aria-label="đáp án đúng" />
                )}
                {picked && isPicked && !isCorrectOption && (
                  <X className="size-4 text-redpen" aria-label="bạn chọn sai" />
                )}
              </span>
              {picked && notes[option.sense_id] && (
                <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">
                  {notes[option.sense_id]}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <AnimatePresence>
        {picked && (
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6"
          >
            <p
              className="text-sm font-medium"
              style={{ color: correct ? 'var(--mint)' : 'var(--redpen)' }}
            >
              {correct ? 'Chính xác.' : 'Chưa đúng — đọc phần khác biệt ở trên.'}
            </p>
            {exercise.explanation && (
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {exercise.explanation}
              </p>
            )}
            <Button className="mt-4" onClick={() => onAnswer(correct)}>
              Thẻ tiếp theo <ArrowRight className="size-4" aria-hidden />
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  )
}
