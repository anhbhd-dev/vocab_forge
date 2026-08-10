import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ErrorBreakdownItem } from '@/lib/types'
import { ERROR_TYPE_LABEL, errorTypeColor } from '@/lib/format'

/**
 * Biểu đồ phân loại lỗi — dùng CHÍNH bảng màu error_type của app (bút đỏ/tím/vàng/chì)
 * chứ không dùng palette mặc định của Recharts, để màu ở biểu đồ khớp với màu ở badge
 * và ở feedback chấm bài (yêu cầu nhất quán của file 05).
 */
export function ErrorBreakdownChart({ items }: { items: ErrorBreakdownItem[] }) {
  if (items.length === 0) {
    return (
      <p className="py-8 text-sm text-muted-foreground">Chưa có dữ liệu phân loại lỗi.</p>
    )
  }

  const data = items.map((item) => ({
    ...item,
    label: ERROR_TYPE_LABEL[item.error_type] ?? item.error_type,
  }))

  return (
    <ResponsiveContainer width="100%" height={Math.max(140, data.length * 44)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={110}
          tickLine={false}
          axisLine={false}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: 'color-mix(in srgb, var(--rule) 30%, transparent)' }}
          contentStyle={{
            background: 'var(--popover)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            fontSize: 12,
            color: 'var(--foreground)',
          }}
          formatter={(value: number, _name, entry) => [
            `${value} lần · ${Math.round((entry.payload.share as number) * 100)}%`,
            'Số lượt',
          ]}
        />
        <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={18}>
          {data.map((item) => (
            <Cell key={item.error_type} fill={errorTypeColor(item.error_type)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
