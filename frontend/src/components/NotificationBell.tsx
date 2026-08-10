import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Bell, CheckCheck, Inbox } from 'lucide-react'
import { api } from '@/lib/api'
import type { AppNotification } from '@/lib/types'
import { Button } from '@/components/ui/button'

/**
 * Nhịp hỏi thăm server. 15 giây là khoảng đủ để một job trích xuất (~10-60s) được báo
 * gần như ngay khi xong, mà vẫn chỉ là một request rỗng mỗi 15s — rẻ hơn nhiều so với
 * dựng WebSocket cho đúng một loại sự kiện.
 */
const POLL_MS = 15_000

/** Nơi mỗi loại thông báo dẫn tới. Thông báo mà không hành động được thì vô nghĩa. */
function linkFor(item: AppNotification): string | null {
  switch (item.type) {
    case 'extraction_done':
      // count = 0 nghĩa là không có gì để duyệt — đưa về màn hình nhập bài khác.
      return item.job_id && (item.count ?? 0) > 0 ? `/import/${item.job_id}` : '/import'
    case 'extraction_failed':
      return '/import'
    case 'enrichment_done':
      return '/review'
    default:
      return null
  }
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'vừa xong'
  if (minutes < 60) return `${minutes} phút trước`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} giờ trước`
  return `${Math.floor(hours / 24)} ngày trước`
}

/**
 * Chuông thông báo.
 *
 * Lý do tồn tại: trích xuất và tạo thẻ chạy ở vòng agent, mất từ vài chục giây tới vài
 * phút. Trước đây màn hình nhập bài bắt người học ngồi nhìn spinner suốt quãng đó —
 * vừa phí thời gian đáng lẽ dùng để ôn, vừa hỏng hẳn nếu họ lỡ đóng tab. Giờ việc chạy
 * nền, xong thì để lại một thông báo, bấm vào là tới đúng chỗ cần hành động.
 */
export function NotificationBell() {
  const navigate = useNavigate()
  const [items, setItems] = useState<AppNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  const load = useCallback(async () => {
    try {
      const data = await api.notifications()
      setItems(data.notifications)
      setUnread(data.unread_count)
    } catch {
      // Mất mạng chốc lát không đáng nổi một toast đỏ ở góc màn hình: lần poll sau tự
      // khỏi. Thông báo là tiện nghi, không phải dữ liệu người học đang nhập.
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [load])

  // Bấm ra ngoài thì đóng — panel nổi mà không tự đóng là cái bẫy trên màn hình.
  useEffect(() => {
    if (!open) return
    function onClick(event: MouseEvent) {
      if (!boxRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function openItem(item: AppNotification) {
    setOpen(false)
    const target = linkFor(item)
    if (item.read_at === null) {
      setItems((prev) =>
        prev.map((n) => (n.id === item.id ? { ...n, read_at: new Date().toISOString() } : n)),
      )
      setUnread((n) => Math.max(0, n - 1))
      // Điều hướng trước, đánh dấu đã đọc sau: người học không phải chờ một request chỉ
      // để đi tới trang họ vừa bấm. Đánh dấu hỏng thì cùng lắm là còn chấm đỏ.
      if (target) navigate(target)
      try {
        await api.markNotificationRead(item.id)
      } catch {
        void load()
      }
      return
    }
    if (target) navigate(target)
  }

  async function markAll() {
    setItems((prev) => prev.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })))
    setUnread(0)
    try {
      await api.markAllNotificationsRead()
    } catch {
      void load()
    }
  }

  return (
    <div className="relative" ref={boxRef}>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen((value) => !value)}
        aria-label={unread > 0 ? `Thông báo (${unread} chưa đọc)` : 'Thông báo'}
        aria-expanded={open}
        className="relative"
      >
        <Bell className="size-4" aria-hidden />
        {unread > 0 && (
          <span
            className="tnum absolute -top-0.5 -right-0.5 flex size-4 items-center justify-center rounded-full bg-redpen text-[10px] leading-none font-medium text-white"
            aria-hidden
          >
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </Button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            /* Trên điện thoại: neo theo VIEWPORT, không neo theo nút chuông. Chuông nằm
               giữa cụm nút bên phải nên panel 320px treo right-0 sẽ thò khỏi mép trái màn
               hình 375px và bị cắt. Từ sm trở lên mới quay về kiểu dropdown thường. */
            className="fixed inset-x-3 top-16 z-30 overflow-hidden rounded-xl border bg-card shadow-lg sm:absolute sm:inset-x-auto sm:top-full sm:right-0 sm:mt-2 sm:w-80"
            role="dialog"
            aria-label="Thông báo"
          >
            <div className="flex items-center justify-between border-b px-3 py-2">
              <span className="text-xs tracking-wide text-muted-foreground uppercase">
                Thông báo
              </span>
              {unread > 0 && (
                <button
                  onClick={markAll}
                  className="flex items-center gap-1 text-xs text-muted-foreground transition hover:text-foreground"
                >
                  <CheckCheck className="size-3.5" aria-hidden /> Đánh dấu đã đọc
                </button>
              )}
            </div>

            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                <Inbox className="mx-auto mb-2 size-5 opacity-60" aria-hidden />
                Chưa có thông báo nào.
                <br />
                Nhập một bài đọc, xong sẽ báo ở đây.
              </div>
            ) : (
              <ul className="max-h-96 overflow-y-auto">
                {items.map((item) => {
                  const failed = item.type.endsWith('_failed')
                  return (
                    <li key={item.id}>
                      <button
                        onClick={() => openItem(item)}
                        className={`w-full border-b px-3 py-2.5 text-left transition last:border-b-0 hover:bg-muted/60 ${
                          item.read_at === null ? 'bg-highlight/8' : ''
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          {/* Chấm chưa đọc: dấu hiệu duy nhất cần liếc là thấy. */}
                          <span
                            className={`mt-1.5 size-1.5 shrink-0 rounded-full ${
                              item.read_at === null
                                ? failed
                                  ? 'bg-redpen'
                                  : 'bg-mint'
                                : 'bg-transparent'
                            }`}
                            aria-hidden
                          />
                          <div className="min-w-0 flex-1">
                            <p
                              className={`text-sm ${failed ? 'text-redpen' : ''} ${
                                item.read_at === null ? 'font-medium' : ''
                              }`}
                            >
                              {item.title}
                            </p>
                            {item.body && (
                              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                                {item.body}
                              </p>
                            )}
                            <p className="mt-1 text-[11px] text-muted-foreground">
                              {timeAgo(item.created_at)}
                            </p>
                          </div>
                        </div>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
