import { useEffect, useState } from 'react'
import { Layers, Lightbulb } from 'lucide-react'
import { api } from '@/lib/api'
import type { Cluster, ErrorBreakdown, Leech } from '@/lib/types'
import { ERROR_TYPE_EFFECT } from '@/lib/format'
import { ErrorBreakdownChart } from '@/components/ErrorBreakdownChart'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

/**
 * Phân tích theo LOẠI LỖI — dữ liệu Anki không có (file 02 mục 5), nên nó là nội dung
 * chính của trang chứ không bị giấu trong một tab phụ hời hợt.
 */
export function AnalyticsPage() {
  const [breakdown, setBreakdown] = useState<ErrorBreakdown | null>(null)
  const [leeches, setLeeches] = useState<Leech[]>([])
  const [clusters, setClusters] = useState<Cluster[]>([])

  useEffect(() => {
    let active = true
    void Promise.all([api.errorBreakdown(30), api.leeches(), api.clusters()]).then(
      ([b, l, c]) => {
        if (!active) return
        setBreakdown(b)
        setLeeches(l)
        setClusters(c)
      },
    )
    return () => {
      active = false
    }
  }, [])

  if (!breakdown) return <Skeleton className="h-72 rounded-2xl" />

  const topError = breakdown.review_errors[0] ?? breakdown.production_errors[0]

  return (
    <div className="space-y-8">
      <header>
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Phân tích 30 ngày</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Không chỉ đúng/sai — hệ thống phân loại lỗi để biết bạn yếu ở đâu và điều chỉnh
          lịch ôn cho đúng chỗ.
        </p>
      </header>

      <Card className="gap-0 px-5 py-5">
        <Tabs defaultValue="review">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <TabsList>
              <TabsTrigger value="review">Khi ôn thẻ</TabsTrigger>
              <TabsTrigger value="production">Khi tự viết câu</TabsTrigger>
            </TabsList>
            {topError && (
              <p className="text-xs text-muted-foreground">
                Lỗi hay gặp nhất: {ERROR_TYPE_EFFECT[topError.error_type] ?? ''}
              </p>
            )}
          </div>
          <TabsContent value="review" className="mt-5">
            <ErrorBreakdownChart items={breakdown.review_errors} />
          </TabsContent>
          <TabsContent value="production" className="mt-5">
            <ErrorBreakdownChart items={breakdown.production_errors} />
          </TabsContent>
        </Tabs>
      </Card>

      <Card className="gap-0 px-5 py-5">
        <p className="flex items-center gap-1.5 text-[11px] tracking-wide text-muted-foreground uppercase">
          <Lightbulb className="size-3.5" aria-hidden /> Từ khó — {leeches.length}
        </p>
        {leeches.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Chưa có từ nào. Khi một thẻ bị quên quá nhiều lần, hệ thống KHÔNG ẩn nó đi như
            Anki mà viết lại mẹo nhớ bằng cách tiếp cận khác hẳn.
          </p>
        ) : (
          <ul className="mt-4 divide-y">
            {leeches.map((leech) => (
              <li key={leech.card_id} className="py-4 first:pt-0">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-heading font-medium">{leech.surface_form}</span>
                  <span className="tnum text-xs text-muted-foreground">
                    {leech.lapses} lần quên / {leech.reps} lượt ôn
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{leech.definition_en}</p>
                {leech.latest_mnemonic && (
                  <p className="mt-2 rounded-lg border-l-2 border-highlight bg-highlight/10 px-3 py-2 text-sm">
                    <span className="mr-2 text-[11px] tracking-wide text-muted-foreground uppercase">
                      {leech.mnemonic_regenerated ? 'Mẹo nhớ mới' : 'Mẹo nhớ'}
                    </span>
                    {leech.latest_mnemonic}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="gap-0 px-5 py-5">
        <p className="flex items-center gap-1.5 text-[11px] tracking-wide text-muted-foreground uppercase">
          <Layers className="size-3.5" aria-hidden /> Nhóm từ dễ nhầm — {clusters.length}
        </p>
        {clusters.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Chưa có nhóm nào. Khi kho từ của bạn có đủ từ cận nghĩa, agent sẽ gom cụm và
            chỉ ra sắc thái khác biệt để bạn chọn đúng từ khi viết.
          </p>
        ) : (
          <ul className="mt-4 space-y-5">
            {clusters.map((cluster) => (
              <li key={cluster.id}>
                <p className="font-heading font-medium">{cluster.cluster_label}</p>
                <ul className="mt-2 space-y-2">
                  {cluster.members.map((member) => (
                    <li key={member.sense_id} className="text-sm">
                      <span className="font-medium">{member.surface_form}</span>
                      {member.distinguishing_note && (
                        <span className="text-muted-foreground"> — {member.distinguishing_note}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
