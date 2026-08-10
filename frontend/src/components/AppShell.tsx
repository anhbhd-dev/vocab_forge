import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  AudioLines,
  BarChart3,
  BookOpen,
  FilePlus2,
  LogOut,
  Moon,
  NotebookPen,
  Settings,
  Sun,
} from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { useVoice } from '@/lib/voice'
import { Button } from '@/components/ui/button'

const NAV = [
  { to: '/', label: 'Hôm nay', icon: NotebookPen, end: true },
  { to: '/review', label: 'Ôn tập', icon: BookOpen, end: false },
  { to: '/import', label: 'Nhập bài', icon: FilePlus2, end: false },
  { to: '/analytics', label: 'Phân tích', icon: BarChart3, end: false },
  { to: '/settings', label: 'Cài đặt', icon: Settings, end: false },
]

/**
 * Đổi giọng đọc ngay trên thanh điều hướng.
 *
 * Để nút này ở trang Cài đặt là sai chỗ: người học nghe phát âm ở màn hình ôn tập, và
 * quyết định "muốn nghe giọng khác" nảy ra ĐÚNG lúc vừa nghe xong một từ. Bắt họ rời
 * màn hình ôn để đi tìm một công tắc thì thực tế là không ai đổi giọng bao giờ.
 *
 * Cả hai giọng đều sinh sẵn nên bấm là đổi ngay, không chờ, không gọi TTS.
 */
function VoiceToggle() {
  const [voice, setVoice] = useVoice()
  const male = voice === 'male'

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setVoice(male ? 'female' : 'male')}
      aria-label={`Giọng đọc: ${male ? 'nam' : 'nữ'}. Bấm để đổi sang giọng ${male ? 'nữ' : 'nam'}.`}
      title={`Giọng ${male ? 'nam' : 'nữ'} — bấm để đổi`}
      className="gap-1.5 px-2 text-muted-foreground"
    >
      <AudioLines className="size-4" aria-hidden />
      <span className="text-xs">{male ? 'Nam' : 'Nữ'}</span>
    </Button>
  )
}

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('vf-theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setDark((value) => !value)}
      aria-label={dark ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối'}
    >
      {dark ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
    </Button>
  )
}

/**
 * Khung app: thanh điều hướng mảnh ở trên, nội dung trên nền giấy kẻ ô.
 * Trang Ôn tập cố ý KHÔNG có sidebar — mọi thứ không phục vụ việc nhớ đều bị loại.
 */
export function AppShell() {
  const { user, logout } = useAuth()

  return (
    <div className="paper-grid min-h-screen">
      <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-5">
          <span className="font-heading mr-3 font-semibold tracking-tight">VocabForge</span>

          <nav className="flex items-center gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm transition ${
                    isActive
                      ? 'bg-secondary text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`
                }
              >
                <item.icon className="size-4" aria-hidden />
                <span className="hidden sm:inline">{item.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <span className="hidden text-xs text-muted-foreground md:inline">{user?.email}</span>
            <VoiceToggle />
            <ThemeToggle />
            <Button variant="ghost" size="icon" onClick={logout} aria-label="Đăng xuất">
              <LogOut className="size-4" aria-hidden />
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 py-8">
        <Outlet />
      </main>
    </div>
  )
}
