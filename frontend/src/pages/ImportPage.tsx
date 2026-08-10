import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Check, FileText, Link2, Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { api, pollUntil } from '@/lib/api'
import type { Candidate } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'

type Phase = 'input' | 'extracting' | 'review' | 'enriching' | 'done'

/**
 * Luồng ingestion theo file 03 mục 6: nhập bài đọc → Extraction Agent → **user duyệt**
 * → enrichment chạy nền. Điểm mấu chốt: KHÔNG tự động thêm hết ứng viên; mỗi ứng viên
 * hiện kèm `reason` của agent để người học quyết định có căn cứ.
 */
export function ImportPage() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>('input')
  const [source, setSource] = useState<'pasted_text' | 'url'>('pasted_text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  // Khoảng band thay vì một mức: một bài đọc chứa từ ở nhiều độ khó, người học thường
  // muốn quét từ mức đang có tới mức đang nhắm tới.
  const [bandMin, setBandMin] = useState(5)
  const [bandMax, setBandMax] = useState(8)
  const [jobId, setJobId] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())

  async function startExtraction() {
    setPhase('extracting')
    try {
      const { job_id } = await api.createJob({
        source_type: source,
        raw_text: source === 'pasted_text' ? text : undefined,
        url: source === 'url' ? url : undefined,
        band_min: bandMin,
        band_max: bandMax,
      })
      setJobId(job_id)

      // Job đi qua 'done' HAI lần (xem docstring ingestion_pipeline.py); lần này là
      // lúc candidates đã sẵn sàng chờ duyệt.
      const job = await pollUntil(
        () => api.job(job_id),
        (value) => value.status === 'done' || value.status === 'failed',
      )
      if (job.status === 'failed') {
        toast.error('Trích xuất thất bại', { description: job.error_message ?? undefined })
        setPhase('input')
        return
      }
      const list = await api.candidates(job_id)
      setCandidates(list)
      setSelected(new Set(list.map((c) => c.lexical_item_id)))
      setPhase('review')
    } catch (err) {
      toast.error('Không trích xuất được', { description: (err as Error).message })
      setPhase('input')
    }
  }

  async function approve() {
    if (!jobId) return
    setPhase('enriching')
    try {
      await api.approve(jobId, [...selected])
      await pollUntil(
        () => api.job(jobId),
        (value) =>
          (value.status === 'done' && value.approved_count > 0) || value.status === 'failed',
      )
      setPhase('done')
    } catch (err) {
      toast.error('Enrichment lỗi', { description: (err as Error).message })
      setPhase('review')
    }
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Nhập bài đọc</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Agent trích các collocation học thuật đáng học — ưu tiên cụm từ, không phải từ
          đơn lẻ. Bạn duyệt trước khi thẻ được tạo. Khoảng band quyết định độ khó của từ
          được lấy: rộng thì trải đều nhiều mức, hẹp thì tập trung đúng một mức.
        </p>
      </header>

      {phase === 'input' && (
        <Card className="gap-4 px-5 py-5">
          <Tabs value={source} onValueChange={(value) => setSource(value as typeof source)}>
            <TabsList>
              <TabsTrigger value="pasted_text">
                <FileText className="size-4" aria-hidden /> Dán văn bản
              </TabsTrigger>
              <TabsTrigger value="url">
                <Link2 className="size-4" aria-hidden /> URL
              </TabsTrigger>
            </TabsList>
            <TabsContent value="pasted_text" className="mt-4">
              <Textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                rows={11}
                aria-label="Nội dung bài đọc"
                placeholder="Dán một bài đọc IELTS, bài báo học thuật…"
                className="resize-none bg-background leading-relaxed"
              />
            </TabsContent>
            <TabsContent value="url" className="mt-4">
              <Input
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://…"
                aria-label="Địa chỉ bài đọc"
              />
            </TabsContent>
          </Tabs>

          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="flex items-center gap-2">
              <Label htmlFor="band-min" className="text-muted-foreground">
                Khoảng band
              </Label>
              <Input
                id="band-min"
                type="number"
                min={4}
                max={9}
                step={0.5}
                value={bandMin}
                // Kéo band_max lên theo để không bao giờ gửi lên khoảng ngược — backend
                // từ chối, mà báo lỗi sau khi bấm thì người dùng mất công quay lại sửa.
                onChange={(event) => {
                  const value = Number(event.target.value)
                  setBandMin(value)
                  if (value > bandMax) setBandMax(value)
                }}
                className="tnum w-20"
                aria-label="Band thấp nhất"
              />
              <span className="text-muted-foreground" aria-hidden>
                →
              </span>
              <Input
                id="band-max"
                type="number"
                min={4}
                max={9}
                step={0.5}
                value={bandMax}
                onChange={(event) => {
                  const value = Number(event.target.value)
                  setBandMax(value)
                  if (value < bandMin) setBandMin(value)
                }}
                className="tnum w-20"
                aria-label="Band cao nhất"
              />
            </div>
            <Button
              onClick={startExtraction}
              disabled={source === 'pasted_text' ? !text.trim() : !url.trim()}
            >
              <Sparkles className="size-4" aria-hidden /> Trích xuất từ vựng
            </Button>
          </div>
        </Card>
      )}

      {(phase === 'extracting' || phase === 'enriching') && (
        <Card className="items-center gap-3 px-5 py-12 text-center">
          <Loader2 className="mx-auto size-6 animate-spin text-muted-foreground" aria-hidden />
          <p className="text-sm text-muted-foreground">
            {phase === 'extracting'
              ? 'Extraction Agent đang đọc bài… chạy nền, có thể mất vài chục giây.'
              : 'Đang sinh nghĩa, câu ví dụ theo dạng bài IELTS và mẹo nhớ…'}
          </p>
        </Card>
      )}

      {phase === 'review' && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              <span className="tnum font-medium text-foreground">{selected.size}</span>/
              {candidates.length} mục được chọn
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setSelected(new Set())}>
                Bỏ chọn hết
              </Button>
              <Button onClick={approve} disabled={selected.size === 0}>
                Tạo thẻ cho {selected.size} mục
              </Button>
            </div>
          </div>

          <ul className="space-y-2">
            {candidates.map((candidate, i) => {
              const active = selected.has(candidate.lexical_item_id)
              return (
                <motion.li
                  key={candidate.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.03, 0.3) }}
                >
                  <button
                    onClick={() => toggle(candidate.lexical_item_id)}
                    aria-pressed={active}
                    className="w-full rounded-xl border bg-card px-5 py-4 text-left transition"
                    style={{
                      borderColor: active ? 'var(--mint)' : 'var(--rule)',
                      backgroundColor: active
                        ? 'color-mix(in srgb, var(--mint) 7%, var(--card))'
                        : 'var(--card)',
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <span className="font-heading text-lg font-medium">
                          {candidate.surface_form}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {candidate.item_type.replace('_', ' ')}
                        </span>
                        {candidate.cefr_level && (
                          <span className="tnum text-xs text-muted-foreground">
                            {candidate.cefr_level}
                          </span>
                        )}
                      </div>
                      {active && <Check className="size-4 shrink-0 text-mint" aria-hidden />}
                    </div>
                    {candidate.reason && (
                      <p className="mt-1 text-sm text-muted-foreground">{candidate.reason}</p>
                    )}
                    {candidate.sentence_context && (
                      <p className="mt-2 border-l-2 border-border pl-3 text-sm italic">
                        {candidate.sentence_context}
                      </p>
                    )}
                  </button>
                </motion.li>
              )
            })}
          </ul>
        </>
      )}

      {phase === 'done' && (
        <Card className="items-center gap-4 px-5 py-12 text-center">
          <Check className="mx-auto size-8 text-mint" aria-hidden />
          <div>
            <p className="font-heading text-lg font-medium">Đã tạo thẻ xong</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {selected.size} mục từ đã có nghĩa, câu ví dụ và mẹo nhớ (với từ trừu tượng).
              Thẻ đã vào hàng đợi ôn tập.
            </p>
          </div>
          <div className="flex justify-center gap-2">
            <Button onClick={() => navigate('/review')}>Ôn ngay</Button>
            <Button
              variant="outline"
              onClick={() => {
                setPhase('input')
                setText('')
                setUrl('')
                setCandidates([])
                setSelected(new Set())
              }}
            >
              Nhập bài khác
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
