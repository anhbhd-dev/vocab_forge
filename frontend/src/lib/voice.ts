import { useCallback, useEffect, useState } from 'react'

export type VoiceChoice = 'female' | 'male'

const KEY = 'vf-voice'
const EVENT = 'vf-voice-change'

export function getVoice(): VoiceChoice {
  return localStorage.getItem(KEY) === 'male' ? 'male' : 'female'
}

/**
 * Giọng đọc là lựa chọn của THIẾT BỊ, không phải của tài khoản — cùng cơ chế với
 * theme sáng/tối: nó phụ thuộc tai nghe và không gian đang ngồi học chứ không phải
 * hồ sơ người học, và đổi giọng không nên tốn một vòng gọi API.
 *
 * Audio cả hai giọng đều đã sinh sẵn ở vòng agent, nên chuyển giọng chỉ là đổi URL —
 * không hề gọi TTS lúc ôn (nguyên tắc fast path, file 00 mục 4).
 */
export function useVoice(): [VoiceChoice, (next: VoiceChoice) => void] {
  const [voice, setVoiceState] = useState<VoiceChoice>(getVoice)

  useEffect(() => {
    // Đổi ở trang Cài đặt phải ăn ngay vào các nút loa đang hiển thị ở tab khác và ở
    // component khác — `storage` chỉ bắn sang tab khác nên cần thêm event tự phát.
    const sync = () => setVoiceState(getVoice())
    window.addEventListener(EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  const setVoice = useCallback((next: VoiceChoice) => {
    localStorage.setItem(KEY, next)
    window.dispatchEvent(new Event(EVENT))
  }, [])

  return [voice, setVoice]
}
