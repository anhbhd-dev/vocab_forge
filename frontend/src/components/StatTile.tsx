import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'

/**
 * Ô thống kê kiểu "ghi chú lề sổ": nhãn nhỏ viết hoa như tiêu đề mục, số liệu to
 * bằng font mono tabular. Số liệu là nhân vật chính — file 05 yêu cầu tôn vinh dữ
 * liệu thật (retention, stability) chứ không giấu trong tab phụ.
 */
export function StatTile({
  label,
  value,
  suffix,
  hint,
  icon: Icon,
  tone,
}: {
  label: string
  value: ReactNode
  suffix?: string
  hint?: string
  icon?: LucideIcon
  tone?: string
}) {
  return (
    <Card className="gap-0 px-5 py-4">
      <p className="flex items-center gap-1.5 text-[11px] tracking-wide text-muted-foreground uppercase">
        {Icon && <Icon className="size-3.5" aria-hidden />}
        {label}
      </p>
      <p className="mt-1.5 flex items-baseline gap-1.5">
        <span className="tnum text-3xl font-semibold" style={tone ? { color: tone } : undefined}>
          {value}
        </span>
        {suffix && <span className="text-sm text-muted-foreground">{suffix}</span>}
      </p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </Card>
  )
}
