import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { toast } from 'sonner'
import { CheckCircle2, Inbox } from 'lucide-react'
import { api } from '@/lib/api'
import type { AnswerResponse, ReviewCard, ReviewErrorType } from '@/lib/types'
import { formatInterval } from '@/lib/format'
import { Flashcard } from '@/components/Flashcard'
import { ProductionPanel } from '@/components/ProductionPanel'
import { ClusterExerciseCard } from '@/components/ClusterExerciseCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * Một buổi ôn: nạp hàng đợi MỘT lần rồi chạy hết — không gọi lại giữa chừng để vòng
 * review giữ được cảm giác liền mạch (và đúng tinh thần fast path của file 00 mục 4.1).
 */
export function ReviewPage() {
  const [cards, setCards] = useState<ReviewCard[]>([])
  const [index, setIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState<AnswerResponse | null>(null)
  const [done, setDone] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const queue = await api.queue(30)
      setCards(queue.cards)
      setIndex(0)
    } catch (err) {
      toast.error('Không tải được hàng đợi', { description: (err as Error).message })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const card = cards[index]
  const next = useCallback(() => {
    setLast(null)
    setIndex((i) => i + 1)
  }, [])

  const answer = useCallback(
    async (rating: 1 | 2 | 3 | 4, errorType?: ReviewErrorType) => {
      const current = cards[index]
      if (!current || busy) return
      setBusy(true)
      try {
        const result = await api.answer(current.id, rating, errorType)
        setLast(result)
        setDone((d) => d + 1)
        // Again = thẻ quay lại sau vài phút; đẩy về cuối hàng đợi của buổi này.
        if (rating === 1) setCards((prev) => [...prev, current])
        setIndex((i) => i + 1)
        if (result.became_leech) {
          toast('Thẻ này đã thành từ khó', {
            description: 'Đang viết lại mẹo nhớ bằng cách tiếp cận khác.',
          })
        }
      } catch (err) {
        toast.error('Không ghi được kết quả', { description: (err as Error).message })
      } finally {
        setBusy(false)
      }
    },
    [cards, index, busy],
  )

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton className="h-1 w-full" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    )
  }

  if (!card) {
    return (
      <div className="mx-auto max-w-lg py-16 text-center">
        {done > 0 ? (
          <CheckCircle2 className="mx-auto size-10 text-mint" aria-hidden />
        ) : (
          <Inbox className="mx-auto size-10 text-muted-foreground" aria-hidden />
        )}
        <h1 className="font-heading mt-4 text-2xl font-semibold">
          {done > 0 ? 'Xong buổi ôn' : 'Không có thẻ nào đến hạn'}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {done > 0
            ? `Bạn đã ôn ${done} thẻ. Quay lại khi có thẻ đến hạn tiếp theo.`
            : 'Nhập một bài đọc để agent trích xuất collocation đáng học.'}
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button variant="outline" asChild>
            <Link to="/">Về trang chính</Link>
          </Button>
          <Button asChild>
            <Link to="/import">Nhập bài đọc</Link>
          </Button>
        </div>
      </div>
    )
  }

  const progress = cards.length ? (index / cards.length) * 100 : 0

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      {/* Tiến độ buổi ôn: một vạch mảnh như dấu bút chì gạch lề — không phải
          progress bar kiểu trò chơi. */}
      <div className="h-px w-full bg-border">
        <motion.div
          className="h-px"
          style={{ background: 'var(--mint)' }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>

      <AnimatePresence mode="wait">
        {card.card_direction === 'production' ? (
          <ProductionPanel
            key={card.id}
            card={card}
            index={index}
            total={cards.length}
            onNext={next}
          />
        ) : card.card_direction === 'cluster_discrimination' ? (
          <ClusterExerciseCard
            key={card.id}
            card={card}
            index={index}
            total={cards.length}
            onSkip={next}
            // Chọn sai giữa các từ cận nghĩa chính là nhầm nghĩa → error_type='meaning'
            // (file 02 mục 5), nên lịch ôn bị siết đúng mức.
            onAnswer={(correct) => answer(correct ? 3 : 1, correct ? undefined : 'meaning')}
          />
        ) : (
          <Flashcard
            key={card.id}
            card={card}
            index={index}
            total={cards.length}
            onAnswer={answer}
            busy={busy}
          />
        )}
      </AnimatePresence>

      {last && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="rounded-xl border bg-card px-5 py-3 text-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-muted-foreground">
              Thẻ trước → ôn lại sau{' '}
              <span className="tnum font-medium text-foreground">
                {formatInterval(last.interval_days)}
              </span>
            </span>
            <span className="tnum text-xs text-muted-foreground">
              bền {last.stability.toFixed(1)}d · khó {last.difficulty.toFixed(1)}
            </span>
          </div>
          {/* Minh bạch khi lịch ôn bị can thiệp bởi error_type — người học cần hiểu
              vì sao thẻ không bị siết như một lần Again thông thường. */}
          {last.adjustments.map((text) => (
            <p key={text} className="mt-1 text-xs text-mint">
              {text}
            </p>
          ))}
        </motion.div>
      )}
    </div>
  )
}
