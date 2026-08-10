import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth'
import { HighlighterSweep } from '@/components/HighlighterSweep'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function LoginPage() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      if (mode === 'login') await login(email, password)
      else await register(email, password)
      navigate('/')
    } catch (err) {
      toast.error(mode === 'login' ? 'Đăng nhập thất bại' : 'Đăng ký thất bại', {
        description: (err as Error).message,
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="paper-grid flex min-h-screen items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-md"
      >
        <div className="mb-6">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            <HighlighterSweep stability={28}>VocabForge</HighlighterSweep> Pro
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            Sổ tay từ vựng học thuật cho IELTS — mỗi từ được lên lịch ôn theo đúng thời
            điểm bạn sắp quên nó.
          </p>
        </div>

        <Card className="px-6 py-6">
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">
                Mật khẩu {mode === 'register' && <span className="text-muted-foreground">(tối thiểu 6 ký tự)</span>}
              </Label>
              <Input
                id="password"
                type="password"
                required
                minLength={6}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>

            <Button type="submit" disabled={busy} className="w-full">
              {mode === 'login' ? 'Mở sổ' : 'Tạo sổ mới'}
            </Button>

            <button
              type="button"
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              className="w-full text-center text-sm text-muted-foreground hover:text-foreground"
            >
              {mode === 'login' ? 'Chưa có tài khoản? Đăng ký' : 'Đã có tài khoản? Đăng nhập'}
            </button>
          </form>
        </Card>
      </motion.div>
    </div>
  )
}
