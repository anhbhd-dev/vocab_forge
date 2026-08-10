import { useState } from 'react'
import { Loader2, Save, Volume2 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useVoice } from '@/lib/voice'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'

// Vài múi giờ hay dùng; ai cần múi khác thì gõ tay vào ô.
const TIMEZONES = ['Asia/Ho_Chi_Minh', 'Asia/Singapore', 'Asia/Tokyo', 'Europe/London', 'UTC']

/**
 * Cài đặt nhịp học.
 *
 * Điểm cần hiểu để dùng đúng: người học đặt một KHOẢNG (vd 20–30 từ/ngày) chứ không
 * đặt một con số cứng. Trong khoảng đó, ramp-up (file 02 mục 7) tự nâng mục tiêu khi
 * retention ≥ 85% và tải review còn nhẹ, tự hạ khi retention < 75% ba ngày liên tiếp.
 * Khoảng chính là cam kết của người học; con số cụ thể mỗi ngày do hệ thống chọn.
 */
export function SettingsPage() {
  const { user, refresh } = useAuth()
  const [voice, setVoice] = useVoice()
  const [min, setMin] = useState(user?.daily_new_min ?? 5)
  const [max, setMax] = useState(user?.daily_new_max ?? 30)
  const [timezone, setTimezone] = useState(user?.timezone ?? 'Asia/Ho_Chi_Minh')
  const [saving, setSaving] = useState(false)

  const invalid = min > max

  async function save() {
    if (invalid) return
    setSaving(true)
    try {
      const updated = await api.updateSettings({
        daily_new_min: min,
        daily_new_max: max,
        timezone,
      })
      await refresh()
      toast.success('Đã lưu cài đặt', {
        description: `Mục tiêu hôm nay: ${updated.daily_new_word_goal} từ mới.`,
      })
    } catch (err) {
      toast.error('Không lưu được', { description: (err as Error).message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Cài đặt</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Nhịp học và múi giờ. Thay đổi có hiệu lực ngay ở hàng đợi ôn tập.
        </p>
      </header>

      <Card className="gap-5 px-5 py-5">
        <div>
          <h2 className="font-heading text-lg font-medium">Từ mới mỗi ngày</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Đặt khoảng bạn muốn học. Hệ thống tự tăng khi bạn nhớ tốt (retention ≥ 85% và
            chưa dồn nợ review) và tự giảm khi retention dưới 75% ba ngày liên tiếp — nhưng
            không bao giờ ra ngoài khoảng này.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex items-center gap-2">
            <Label htmlFor="min" className="text-muted-foreground">
              Từ
            </Label>
            <Input
              id="min"
              type="number"
              min={1}
              max={100}
              value={min}
              onChange={(event) => {
                const value = Number(event.target.value)
                setMin(value)
                if (value > max) setMax(value)
              }}
              className="tnum w-20"
              aria-label="Số từ mới tối thiểu mỗi ngày"
            />
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="max" className="text-muted-foreground">
              đến
            </Label>
            <Input
              id="max"
              type="number"
              min={1}
              max={100}
              value={max}
              onChange={(event) => {
                const value = Number(event.target.value)
                setMax(value)
                if (value < min) setMin(value)
              }}
              className="tnum w-20"
              aria-label="Số từ mới tối đa mỗi ngày"
            />
          </div>
          <span className="pb-2 text-sm text-muted-foreground">từ/ngày</span>
        </div>

        {user && (
          <p className="text-sm text-muted-foreground">
            Mục tiêu đang áp dụng:{' '}
            <span className="tnum font-medium text-foreground">
              {user.daily_new_word_goal} từ/ngày
            </span>
            {user.daily_new_word_goal < min && ' — sẽ được nâng lên khi bạn lưu.'}
            {user.daily_new_word_goal > max && ' — sẽ được hạ xuống khi bạn lưu.'}
          </p>
        )}

        <Separator />

        <div>
          <h2 className="font-heading text-lg font-medium">Giọng đọc</h2>
          <p className="mt-1 mb-3 text-sm text-muted-foreground">
            Cả hai giọng đều được sinh sẵn nên đổi giọng là nghe được ngay. Thỉnh thoảng
            đổi giọng là một bài kiểm tra thật: nhận ra từ khi người khác đọc mới là nghe
            được từ, chứ không phải quen tai một người.
          </p>
          <div className="flex gap-2">
            {(
              [
                { value: 'female', label: 'Nữ (af_heart)' },
                { value: 'male', label: 'Nam (am_michael)' },
              ] as const
            ).map((option) => (
              <Button
                key={option.value}
                variant={voice === option.value ? 'default' : 'outline'}
                onClick={() => setVoice(option.value)}
                aria-pressed={voice === option.value}
              >
                <Volume2 className="size-4" aria-hidden />
                {option.label}
              </Button>
            ))}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Lưu ngay trên máy này, không cần bấm "Lưu cài đặt".
          </p>
        </div>

        <Separator />

        <div>
          <h2 className="font-heading text-lg font-medium">Múi giờ</h2>
          <p className="mt-1 mb-3 text-sm text-muted-foreground">
            Quyết định mốc bắt đầu "ngày mới" — ảnh hưởng tới streak và hạn ôn.
          </p>
          <Input
            list="tz-options"
            value={timezone}
            onChange={(event) => setTimezone(event.target.value)}
            className="max-w-xs"
            aria-label="Múi giờ"
          />
          <datalist id="tz-options">
            {TIMEZONES.map((tz) => (
              <option key={tz} value={tz} />
            ))}
          </datalist>
        </div>

        <div className="flex items-center gap-3">
          <Button onClick={save} disabled={saving || invalid}>
            {saving ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Save className="size-4" aria-hidden />
            )}
            Lưu cài đặt
          </Button>
          {invalid && (
            <span className="text-sm text-redpen">Số tối thiểu phải nhỏ hơn số tối đa.</span>
          )}
        </div>
      </Card>
    </div>
  )
}
