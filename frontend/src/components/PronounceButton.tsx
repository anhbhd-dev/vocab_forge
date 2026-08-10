import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, Volume2 } from 'lucide-react'
import { mediaUrl } from '@/lib/api'
import { useVoice } from '@/lib/voice'

interface Props {
  /** Đường dẫn audio Kokoro giọng nữ đã sinh sẵn; null nếu chưa có. */
  audioUrl: string | null
  /** Cùng nội dung đó, giọng nam. Dùng khi người học chọn giọng nam ở Cài đặt. */
  audioUrlMale?: string | null
  /** Chữ gốc — dùng cho giọng đọc của trình duyệt khi chưa có file audio. */
  text: string
  size?: 'sm' | 'md'
  className?: string
}

/** Tốc độ khi nghe chậm — đủ chậm để tách được từng âm, chưa chậm tới mức méo tiếng. */
const SLOW_RATE = 0.6

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
 * Bấm lần hai đọc CHẬM lại — nghe lần đầu không rõ là phản xạ tự nhiên bấm lại ngay,
 * nên lần bấm đó nên cho thêm thông tin thay vì lặp y nguyên. Làm bằng `playbackRate`
 * chứ không tổng hợp thêm file: trình duyệt giữ nguyên cao độ khi đổi tốc độ
 * (`preservesPitch`), nên không bị rè giọng, và không tốn thêm giây TTS nào.
 *
 * Không tự động phát: người học đang tự nhớ nghĩa, tiếng bật ra bất ngờ vừa giật mình
 * vừa lộ đáp án.
 */
export function PronounceButton({
  audioUrl,
  audioUrlMale,
  text,
  size = 'md',
  className = '',
}: Props) {
  const [voice] = useVoice()
  const [playing, setPlaying] = useState(false)
  // Chế độ cho lần bấm SẮP TỚI. Mặc định false: bấm lần đầu luôn nghe tốc độ thường,
  // lần bấm thứ hai mới chậm — người học nghe bình thường trước rồi mới cần nghe kỹ.
  const [nextSlow, setNextSlow] = useState(false)
  // Tiếng đang phát có phải bản chậm không — chỉ để hiện badge ½×.
  const [playingSlow, setPlayingSlow] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  // Chọn giọng nam nhưng file chưa sinh xong (audio đổ về sau khi thẻ đã tạo) thì lùi
  // về giọng nữ — có tiếng vẫn hơn im lặng, và lát nữa tự có giọng đúng.
  const src = mediaUrl(voice === 'male' ? (audioUrlMale ?? audioUrl) : audioUrl)

  // Đổi thẻ khi tiếng còn đang phát: cắt tiếng của thẻ cũ, nếu không người học nghe
  // từ trước trong lúc đang nhìn từ sau.
  useEffect(() => {
    // Đổi thẻ thì quay lại từ đầu: "chậm" là ý định cho riêng từ vừa nghe.
    setNextSlow(false)
    return () => {
      audioRef.current?.pause()
      audioRef.current = null
      window.speechSynthesis?.cancel()
    }
  }, [src, text])

  const speakWithBrowser = useCallback(
    (isSlow: boolean) => {
      if (!window.speechSynthesis) return
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'en-US'
      // Cố gắng tôn trọng lựa chọn giọng cả ở đường dự phòng. Chỉ đoán theo tên giọng
      // của hệ điều hành vì Web Speech API không hề khai báo giới tính — đoán trượt thì
      // rơi về giọng mặc định, không đáng để làm gì phức tạp hơn.
      // `\bmale\b` chứ không phải `male`: "female" có chứa "male" nên mẫu lỏng sẽ chọn
      // đúng giọng nữ khi người học đang xin giọng nam.
      const wanted =
        voice === 'male'
          ? /\bmale\b|david|george|mark|guy|alex|ryan|james/i
          : /female|zira|samantha|aria|jenny|susan|karen/i
      const match = window.speechSynthesis
        .getVoices()
        .find((v) => v.lang.startsWith('en') && wanted.test(v.name))
      if (match) utterance.voice = match
      utterance.rate = isSlow ? SLOW_RATE : 0.9
      utterance.onend = () => setPlaying(false)
      utterance.onerror = () => setPlaying(false)
      setPlaying(true)
      window.speechSynthesis.speak(utterance)
    },
    [text, voice],
  )

  const play = useCallback(
    (event: React.MouseEvent) => {
      // Câu ví dụ nằm trong vùng bấm để lật thẻ — chặn nổi bọt kẻo bấm loa lại lật thẻ.
      event.stopPropagation()
      event.preventDefault()

      // Lần đầu nghe tốc độ thường, bấm lại thì chậm, bấm nữa về thường.
      // Phát theo chế độ ĐANG chờ, rồi mới lật cờ cho lần bấm sau.
      const isSlow = nextSlow
      setNextSlow(!isSlow)
      setPlayingSlow(isSlow)

      if (!src) {
        speakWithBrowser(isSlow)
        return
      }

      const audio = audioRef.current ?? new Audio(src)
      audioRef.current = audio
      // preservesPitch: giữ cao độ khi chạy chậm, nếu không giọng sẽ trầm và méo đi.
      audio.preservesPitch = true
      audio.playbackRate = isSlow ? SLOW_RATE : 1
      audio.currentTime = 0
      audio.onended = () => setPlaying(false)
      audio.onerror = () => {
        // File 404 (audio chưa sinh xong, volume mới) — vẫn đọc bằng giọng trình duyệt.
        setPlaying(false)
        speakWithBrowser(isSlow)
      }
      setPlaying(true)
      void audio.play().catch(() => {
        setPlaying(false)
        speakWithBrowser(isSlow)
      })
    },
    [src, nextSlow, speakWithBrowser],
  )

  const iconSize = size === 'sm' ? 'size-3.5' : 'size-4'

  return (
    <button
      type="button"
      onClick={play}
      // Nhãn nói về HÀNH ĐỘNG SẮP TỚI, không phải lần vừa rồi.
      aria-label={`${nextSlow ? 'Nghe chậm' : 'Nghe'} phát âm: ${text}`}
      title={
        nextSlow ? 'Bấm để nghe chậm lại' : `Nghe phát âm${src ? '' : ' (giọng trình duyệt)'}`
      }
      className={`inline-flex shrink-0 items-center justify-center gap-0.5 rounded-full px-1.5 py-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
        playing ? 'text-mint' : ''
      } ${className}`}
    >
      {playing ? (
        <Loader2 className={`${iconSize} animate-spin`} aria-hidden />
      ) : (
        <Volume2 className={iconSize} aria-hidden />
      )}
      {/* Chỉ hiện khi tiếng ĐANG chạy chậm — badge là trạng thái, không phải lời mời bấm. */}
      {playing && playingSlow && (
        <span className="tnum text-[10px] leading-none font-medium" aria-hidden>
          ½×
        </span>
      )}
    </button>
  )
}
