import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/lib/auth'
import { AppShell } from '@/components/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { ReviewPage } from '@/pages/ReviewPage'
import { ImportPage } from '@/pages/ImportPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { Toaster } from '@/components/ui/sonner'
import { Skeleton } from '@/components/ui/skeleton'

// Trang phân tích kéo theo Recharts (~250kB) nhưng người học vào đây ít hơn hẳn so
// với vòng ôn tập — tách ra chunk riêng để màn hình ôn tập tải nhanh nhất có thể.
const AnalyticsPage = lazy(() =>
  import('@/pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })),
)

function Gate() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-5 py-10">
        <Skeleton className="h-10 w-48" />
      </div>
    )
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/import" element={<ImportPage />} />
        {/* Vào thẳng màn hình duyệt của một job cụ thể — đích của thông báo
            "đã trích xuất xong N từ". */}
        <Route path="/import/:jobId" element={<ImportPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route
          path="/analytics"
          element={
            <Suspense fallback={<Skeleton className="h-72 rounded-2xl" />}>
              <AnalyticsPage />
            </Suspense>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Gate />
        <Toaster position="bottom-right" />
      </AuthProvider>
    </BrowserRouter>
  )
}
