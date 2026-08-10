import { motion, useReducedMotion } from 'framer-motion'
import { useId, useMemo } from 'react'
import type { ReactNode } from 'react'

/**
 * SIGNATURE ELEMENT của VocabForge Pro — "vệt highlight bút dạ".
 *
 * Từ vựng được tô bằng một vệt bút dạ quét ngang khi lật thẻ. Vệt KHÔNG phải trang
 * trí: hình dạng của nó là cách app này biểu diễn tiến trình ghi nhớ của một từ.
 *
 *   stability (số ngày để khả năng nhớ tụt còn 90%, do FSRS tính)
 *     0        → vệt mảnh, ngắt quãng, màu vàng   (từ mới, chưa có gì để nhớ)
 *     ~7 ngày  → vệt liền, dày hơn, vàng ngả xanh (đang hình thành trí nhớ)
 *     30+ ngày → vệt đầy, màu bạc hà              (nhớ chắc)
 *
 * Nhìn vệt là biết từ đang ở đâu trong quá trình ghi nhớ mà không cần đọc con số —
 * đây là thứ chỉ app này có, thay cho progress bar kiểu trò chơi.
 */

/** 0 → 1 theo thang log: khác biệt giữa 1 và 7 ngày đáng kể hơn giữa 60 và 90. */
function maturity(stability: number): number {
  if (stability <= 0) return 0
  return Math.min(1, Math.log10(1 + stability) / Math.log10(31))
}

export function sweepColor(stability: number): string {
  const m = maturity(stability)
  // Nội suy trong không gian màu: vàng highlight → bạc hà.
  return `color-mix(in oklab, var(--mint) ${Math.round(m * 100)}%, var(--highlight))`
}

interface Props {
  children: ReactNode
  stability: number
  /** Chỉ vẽ vệt khi thẻ đã lật (đáp án hiện ra). */
  active?: boolean
  className?: string
}

export function HighlighterSweep({
  children,
  stability,
  active = true,
  className = '',
}: Props) {
  const clipId = useId()
  const reduceMotion = useReducedMotion()
  const m = useMemo(() => maturity(stability), [stability])

  // Từ mới: vệt mảnh và ngắt quãng (nét bút chưa đều). Từ chín: vệt dày, liền mạch.
  const thickness = 34 + m * 44 // % chiều cao dòng chữ được phủ
  const opacity = 0.3 + m * 0.38
  const dash = m < 0.35 ? `${6 + m * 40} ${9 - m * 8}` : undefined

  return (
    <span className={`relative inline-block ${className}`}>
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-[-0.35em] bottom-[0.08em]"
        style={{ height: `${thickness}%` }}
      >
        <svg
          viewBox="0 0 100 20"
          preserveAspectRatio="none"
          className="h-full w-full"
          role="presentation"
        >
          <defs>
            {/* Bo hai đầu hơi lệch để giống nét bút dạ thật, không phải hình chữ nhật */}
            <clipPath id={clipId} clipPathUnits="objectBoundingBox">
              <path d="M0.01,0.18 C0.05,0.02 0.95,0.05 0.99,0.14 C1.0,0.55 0.97,0.92 0.93,0.97 C0.5,1.02 0.12,0.99 0.03,0.94 C0.0,0.7 0.0,0.35 0.01,0.18 Z" />
            </clipPath>
          </defs>
          <motion.rect
            x="0"
            y="0"
            width="100"
            height="20"
            clipPath={`url(#${clipId})`}
            fill={sweepColor(stability)}
            strokeDasharray={dash}
            initial={reduceMotion || !active ? false : { scaleX: 0, originX: 0 }}
            animate={{ scaleX: active ? 1 : 0, opacity: active ? opacity : 0 }}
            transition={
              reduceMotion
                ? { duration: 0 }
                : // Nhanh, dứt khoát, hơi trễ ở cuối — cảm giác quét bút thật.
                  { duration: 0.42, ease: [0.22, 1, 0.36, 1] }
            }
            style={{ transformOrigin: 'left center' }}
          />
        </svg>
      </span>
      <span className="relative">{children}</span>
    </span>
  )
}

/**
 * Phiên bản thu nhỏ dùng trong danh sách/thống kê: chỉ vệt, không có chữ.
 * Giữ signature element xuất hiện nhất quán ở mọi cấp độ của app.
 */
export function SweepBar({
  stability,
  className = '',
}: {
  stability: number
  className?: string
}) {
  const m = maturity(stability)
  return (
    <span
      className={`block h-1.5 rounded-full ${className}`}
      style={{ backgroundColor: 'color-mix(in srgb, var(--rule) 60%, transparent)' }}
      role="img"
      aria-label={`Độ bền trí nhớ ${stability.toFixed(1)} ngày`}
    >
      <span
        className="block h-full rounded-full transition-[width] duration-500"
        style={{
          width: `${Math.max(6, m * 100)}%`,
          backgroundColor: sweepColor(stability),
        }}
      />
    </span>
  )
}
