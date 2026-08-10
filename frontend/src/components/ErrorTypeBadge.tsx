import { AlertCircle, Check, Link2, PenLine, SpellCheck, Type } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { ERROR_TYPE_LABEL, errorTypeColor } from '@/lib/format'

const ICONS: Record<string, LucideIcon> = {
  meaning: AlertCircle,
  collocation: Link2,
  register: PenLine,
  grammar: Type,
  spelling: SpellCheck,
  none: Check,
}

/**
 * Nhãn loại lỗi dùng CHUNG ở mọi nơi hiển thị error_type (chấm bài viết, biểu đồ
 * phân tích, khi ôn thẻ) — yêu cầu file 05: mỗi loại một mã màu nhất quán xuyên suốt.
 *
 * Mỗi loại còn có icon riêng để phân biệt được khi in đen trắng hoặc với người mù màu:
 * màu không bao giờ là kênh thông tin duy nhất.
 */
export function ErrorTypeBadge({
  type,
  size = 'md',
}: {
  type: string | null | undefined
  size?: 'sm' | 'md'
}) {
  const key = type ?? 'none'
  const color = errorTypeColor(type)
  const Icon = ICONS[key] ?? AlertCircle

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${
        size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs'
      }`}
      style={{
        color,
        borderColor: `color-mix(in srgb, ${color} 45%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)`,
      }}
    >
      <Icon className={size === 'sm' ? 'size-3' : 'size-3.5'} aria-hidden />
      {ERROR_TYPE_LABEL[key] ?? key}
    </span>
  )
}
