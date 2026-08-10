import { useMemo } from 'react'
import type { HighlightRole, SentenceHighlight } from '@/lib/types'

/**
 * Màu theo VAI TRÒ, dùng lại đúng bộ bút của design system thay vì bịa màu mới:
 * bút dạ vàng đã có nghĩa "đang học, cần chú ý", bút tím đã có nghĩa "kết hợp từ" ở
 * bảng error_type. Người học gặp lại cùng một màu với cùng một ý nghĩa ở mọi màn hình
 * thì không phải học thêm bảng chú giải nào.
 *
 * Linker cố tình nhạt nhất: nó là bộ khung lập luận, đáng nhận ra nhưng không đáng
 * tranh chỗ với từ đang học.
 */
const ROLE_CLASS: Record<HighlightRole, string> = {
  // Không ép màu chữ: nền vàng mờ nằm trên giấy sáng lẫn giấy tối đều ăn được màu chữ
  // đang thừa kế, ép cứng `text-ink` sẽ vỡ tương phản ở đúng một trong hai chế độ.
  target: 'rounded-sm bg-highlight/50 px-0.5 font-medium',
  collocation:
    'text-violet-pen underline decoration-violet-pen/45 decoration-2 underline-offset-2',
  academic: 'text-mint underline decoration-dotted decoration-mint/60 underline-offset-2',
  linker: 'text-graphite italic',
}

const ROLE_LABEL: Record<HighlightRole, string> = {
  target: 'từ đang học',
  collocation: 'từ đi kèm cố định',
  academic: 'từ học thuật',
  linker: 'từ nối',
}

interface Segment {
  text: string
  role: HighlightRole | null
}

function escapeRegExp(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Dò vị trí các mảnh cần tô, trả về chuỗi đoạn liền mạch phủ kín câu.
 *
 * Vì sao dò lại bằng so khớp chuỗi thay vì tin offset của agent: LLM đếm ký tự sai
 * thường xuyên, nhưng chép lại đúng một đoạn chữ thì gần như luôn đúng. Mảnh nào không
 * tìm thấy trong câu thì BỎ QUA IM LẶNG — thà mất một vệt màu còn hơn tô lệch chỗ hoặc
 * làm vỡ câu.
 */
function segment(sentence: string, highlights: SentenceHighlight[]): Segment[] {
  const lower = sentence.toLowerCase()
  const claimed: Array<{ start: number; end: number; role: HighlightRole }> = []

  // target trước: nếu nó chồng lấn với mảnh khác thì nó phải là mảnh thắng.
  const ordered = [...highlights].sort(
    (a, b) => (a.role === 'target' ? 0 : 1) - (b.role === 'target' ? 0 : 1),
  )

  for (const highlight of ordered) {
    const needle = (highlight.text || '').trim().toLowerCase()
    if (!needle) continue
    let from = 0
    // Tìm lần xuất hiện đầu tiên chưa bị mảnh khác chiếm.
    for (;;) {
      const at = lower.indexOf(needle, from)
      if (at < 0) break
      const end = at + needle.length
      const overlaps = claimed.some((c) => at < c.end && end > c.start)
      if (!overlaps) {
        claimed.push({ start: at, end, role: highlight.role })
        break
      }
      from = at + 1
    }
  }

  claimed.sort((a, b) => a.start - b.start)

  const segments: Segment[] = []
  let cursor = 0
  for (const span of claimed) {
    if (span.start > cursor) {
      segments.push({ text: sentence.slice(cursor, span.start), role: null })
    }
    segments.push({ text: sentence.slice(span.start, span.end), role: span.role })
    cursor = span.end
  }
  if (cursor < sentence.length) {
    segments.push({ text: sentence.slice(cursor), role: null })
  }
  return segments
}

/**
 * Khi agent không trả highlights (dữ liệu cũ, hoặc câu lấy thẳng từ bài đọc của user),
 * vẫn tô được ít nhất từ đang học. `\w*` ở đuôi để bắt cả dạng chia: "exacerbate" khớp
 * "exacerbates", "exacerbated".
 */
function fallbackTarget(sentence: string, surfaceForm: string): SentenceHighlight[] {
  const form = (surfaceForm || '').trim()
  if (!form) return []
  const pattern = new RegExp(`\\b${escapeRegExp(form)}\\w*`, 'i')
  const found = sentence.match(pattern)
  return found ? [{ text: found[0], role: 'target' }] : []
}

interface Props {
  sentence: string
  highlights?: SentenceHighlight[] | null
  /** Từ đang học — dùng để tô dự phòng khi không có `highlights`. */
  surfaceForm?: string
  className?: string
}

export function HighlightedSentence({
  sentence,
  highlights,
  surfaceForm = '',
  className = '',
}: Props) {
  const segments = useMemo(() => {
    const marks =
      highlights && highlights.length > 0
        ? highlights
        : fallbackTarget(sentence, surfaceForm)
    return segment(sentence, marks)
  }, [sentence, highlights, surfaceForm])

  return (
    <span className={className}>
      {segments.map((part, index) =>
        part.role ? (
          <mark
            key={index}
            // <mark> có nền vàng mặc định của trình duyệt — phải tắt, màu do token lo.
            className={`bg-transparent ${ROLE_CLASS[part.role]}`}
            title={ROLE_LABEL[part.role]}
          >
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </span>
  )
}
