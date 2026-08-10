import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, Volume2 } from 'lucide-react'
import { mediaUrl } from '@/lib/api'

interface Props {
  /** Đường dẫn audio Kokoro đã sinh sẵn; null nếu chưa có. */
  audioUrl: string | null
  /** Chữ gốc — dùng cho giọng đọc của trình duyệt khi chưa có file audio. */
  text: string
  size?: 'sm' | 'md'
  className?: string
}

/**
 * Nút phát âm.
 *
 * Hai nguồn tiếng, theo thứ tự ưu tiên:
 *
 * 1. **File Kokoro sinh sẵn** — giọng tự nhiên, giống nhau trên mọi máy, phát tức thì
 *    vì chỉ là file tĩnh.
 * 2. **`speechSynthesis` của trình duyệt** — khi backend chưa kịp sinh audio (enrichment
 *    chạy nền) hoặc TTS bị tắt. Giọng phụ thuộc hệ điều hành nên chất lượng không đồng
 *    đều, nhưng có tiếng vẫn hơn im lặng, và người học không phải chờ.
 *
 * Không tự động phát: người học đang tự nhớ nghĩa, tiếng bật ra bất ngờ vừa giật mình
 * vừa lộ đáp án.
 */
export function PronounceButton({ audioUrl, text, size = 'md', className = '' }: Props) {
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const src = mediaUrl(audioUrl)

  // Đổi thẻ khi tiếng còn đang phát: cắt tiếng của thẻ cũ, nếu không người học nghe
  // từ trước trong lúc đang nhìn từ sau.
  useEffect(() => {
    return () => {
      audioRef.current?.pause()
      audioRef.current = null
      window.speechSynthesis?.cancel()
    }
  }, [src, text])

  const speakWithBrowser = useCallback(() => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'en-US'
    utterance.rate = 0.9
    utterance.onend = () => setPlaying(false)
    utterance.onerror = () => setPlaying(false)
    setPlaying(true)
    window.speechSynthesis.speak(utterance)
  }, [text])

  const play = useCallback(
    (event: React.MouseEvent) => {
      // Câu ví dụ nằm trong vùng bấm để lật thẻ — chặn nổi bọt kẻo bấm loa lại lật thẻ.
      event.stopPropagation()
      event.preventDefault()

      if (!src) {
        speakWithBrowser()
        return
      }

      const audio = audioRef.current ?? new Audio(src)
      audioRef.current = audio
      audio.currentTime = 0
      audio.onended = () => setPlaying(false)
      audio.onerror = () => {
        // File 404 (audio bị xoá, volume mới) — vẫn đọc được bằng giọng trình duyệt.
        setPlaying(false)
        speakWithBrowser()
      }
      setPlaying(true)
      void audio.play().catch(() => {
        setPlaying(false)
        speakWithBrowser()
      })
    },
    [src, speakWithBrowser],
  )

  const iconSize = size === 'sm' ? 'size-3.5' : 'size-4'

  return (
    <button
      type="button"
      onClick={play}
      aria-label={`Phát âm: ${text}`}
      title={src ? 'Nghe phát âm' : 'Nghe phát âm (giọng trình duyệt)'}
      className={`inline-flex shrink-0 items-center justify-center rounded-full p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
        playing ? 'text-mint' : ''
      } ${className}`}
    >
      {playing ? (
        <Loader2 className={`${iconSize} animate-spin`} aria-hidden />
      ) : (
        <Volume2 className={iconSize} aria-hidden />
      )}
    </button>
  )
}
