import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  BookMarked,
  CalendarCheck,
  Flame,
  Target,
  TrendingUp,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { AnalyticsOverview, Leech, ReviewStats } from '@/lib/types'
import { formatPercent } from '@/lib/format'
import { StatTile } from '@/components/StatTile'
import { SweepBar } from '@/components/HighlighterSweep'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'

const STATE_LABEL: Record<string, string> = {
  new: 'Mới',
  learning: 'Đang học',
  review: 'Ôn tập',
  relearning: 'Học lại',
}

/**
 * COMPONENT 2 (file 05): dashboard — due cards + streak + retention rate.
 *
 * Bố cục "trang mở đầu của cuốn sổ": lời chào + việc hôm nay ở trên, các ô ghi chú
 * số liệu, rồi tới phần theo dõi tiến trình. KHÔNG dùng ngôn ngữ trò chơi (không huy
 * hiệu, không "level up") — cảm giác tiến bộ đến từ số liệu thật và từ độ đầy của
 * các vệt bút dạ.
 */
export function DashboardPage() {
  const [stats, setStats] = useState<ReviewStats | null>(null)
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [leeches, setLeeches] = useState<Leech[]>([])

  useEffect(() => {
    let active = true
    void Promise.all([api.stats(), api.overview(), api.leeches()]).then(([s, o, l]) => {
      if (!active) return
      setStats(s)
      setOverview(o)
      setLeeches(l)
    })
    return () => {
      active = false
    }
  }, [])

  if (!stats || !overview) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    )
  }

  const waiting = stats.due_today + stats.new_available
  const states = overview.cards_by_state
  const goalPercent = Math.min(100, (overview.daily_new_word_goal / 30) * 100)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-8"
    >
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Hôm nay</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {waiting > 0
              ? `${waiting} thẻ đang chờ bạn.`
              : 'Không còn thẻ đến hạn — hôm nay bạn đã xong.'}
          </p>
        </div>
        {waiting > 0 && (
          <Button asChild size="lg">
            <Link to="/review">
              Bắt đầu ôn <ArrowRight className="size-4" aria-hidden />
            </Link>
          </Button>
        )}
      </header>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Đến hạn"
          value={stats.due_today}
          hint={`+${stats.new_available} thẻ mới còn lại hôm nay`}
          icon={CalendarCheck}
          tone="var(--highlight)"
        />
        <StatTile
          label="Chuỗi ngày"
          value={stats.streak_days}
          suffix="ngày"
          hint={`${stats.reviewed_today} lượt ôn hôm nay`}
          icon={Flame}
        />
        <StatTile
          label="Retention 7 ngày"
          value={formatPercent(stats.retention_rate_7d)}
          hint={`30 ngày: ${formatPercent(stats.retention_rate_30d)}`}
          icon={TrendingUp}
          tone="var(--mint)"
        />
        <StatTile
          label="Kho từ"
          value={overview.total_lexical_items}
          suffix="mục từ"
          hint={`${stats.total_cards} thẻ · ${stats.leech_count} từ khó`}
          icon={BookMarked}
        />
      </section>

      {/* Ramp-up — logic ở app/srs/rampup.py (file 02 mục 7) */}
      <Card className="gap-0 px-5 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="flex items-center gap-1.5 text-[11px] tracking-wide text-muted-foreground uppercase">
              <Target className="size-3.5" aria-hidden /> Từ mới mỗi ngày
            </p>
            <p className="tnum mt-1.5 text-3xl font-semibold">
              {overview.daily_new_word_goal}
              {overview.ramp_up.action !== 'hold' && (
                <span
                  className="ml-2 text-lg font-medium"
                  style={{
                    color:
                      overview.ramp_up.action === 'raise' ? 'var(--mint)' : 'var(--highlight)',
                  }}
                >
                  → {overview.ramp_up.recommended_goal}
                </span>
              )}
            </p>
          </div>
          <p className="max-w-sm text-sm text-muted-foreground">{overview.ramp_up.reason}</p>
        </div>
        <Progress value={goalPercent} className="mt-4 h-2" />
        <p className="mt-1.5 text-right text-xs text-muted-foreground">mục tiêu 30 từ/ngày</p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="gap-0 px-5 py-5">
          <p className="text-[11px] tracking-wide text-muted-foreground uppercase">
            Thẻ theo trạng thái
          </p>
          <ul className="mt-4 space-y-3">
            {(['new', 'learning', 'review', 'relearning'] as const).map((state) => {
              const count = states[state] ?? 0
              const total = overview.total_cards || 1
              return (
                <li key={state} className="flex items-center gap-3">
                  <span className="w-20 text-sm text-muted-foreground">{STATE_LABEL[state]}</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                    <span
                      className="block h-full rounded-full"
                      style={{
                        width: `${(count / total) * 100}%`,
                        backgroundColor:
                          state === 'review'
                            ? 'var(--mint)'
                            : state === 'relearning'
                              ? 'var(--redpen)'
                              : 'var(--highlight)',
                      }}
                    />
                  </span>
                  <span className="tnum w-10 text-right text-sm">{count}</span>
                </li>
              )
            })}
          </ul>
          <p className="mt-4 text-xs text-muted-foreground">
            Thẻ ở trạng thái “Ôn tập” là những từ đã vào trí nhớ dài hạn — tỉ lệ này tăng
            dần là dấu hiệu tiến bộ đáng tin nhất.
          </p>
        </Card>

        <Card className="gap-0 px-5 py-5">
          <div className="flex items-center justify-between">
            <p className="text-[11px] tracking-wide text-muted-foreground uppercase">
              Từ khó cần để mắt
            </p>
            <Link to="/analytics" className="text-xs text-mint hover:underline">
              Xem tất cả
            </Link>
          </div>
          {leeches.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              Chưa có từ nào thành “từ khó”. Khi có, hệ thống sẽ tự viết lại mẹo nhớ bằng
              cách tiếp cận khác thay vì ẩn thẻ đi như Anki.
            </p>
          ) : (
            <ul className="mt-4 space-y-3">
              {leeches.slice(0, 5).map((leech) => (
                <li key={leech.card_id}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-heading font-medium">{leech.surface_form}</span>
                    <span className="tnum text-xs text-muted-foreground">
                      {leech.lapses} lần quên
                    </span>
                  </div>
                  <SweepBar stability={0.5} className="mt-1.5" />
                  {leech.mnemonic_regenerated && (
                    <span className="text-xs text-mint">đã có mẹo nhớ mới</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </motion.div>
  )
}
