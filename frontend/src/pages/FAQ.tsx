import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, HelpCircle, ChevronDown, ChevronUp, GripVertical } from 'lucide-react'

import { faqApi } from '../lib/api'
import type { FAQ } from '../types'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Textarea from '../components/ui/Textarea'
import EmptyState from '../components/ui/EmptyState'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../contexts/ToastContext'

export default function FAQPage() {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [editTarget, setEditTarget] = useState<FAQ | null | 'new'>(null)
  const [deleteTarget, setDeleteTarget] = useState<FAQ | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const { data: faqs, isLoading } = useQuery({
    queryKey: ['faq'],
    queryFn: faqApi.list,
    select: (data) => [...data].sort((a, b) => a.sort_order - b.sort_order),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => faqApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['faq'] })
      toast.success('FAQ deleted')
      setDeleteTarget(null)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const toggle = (id: string) =>
    setExpanded((s) => {
      const next = new Set(s)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  if (isLoading) return <PageLoader />

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setEditTarget('new')}>
          <Plus className="w-4 h-4 mr-1.5" /> Add FAQ
        </Button>
      </div>

      {!faqs?.length ? (
        <Card>
          <EmptyState
            icon={HelpCircle}
            title="No FAQ entries yet"
            description="Add commonly asked questions and answers to help the AI respond better."
            action={
              <Button onClick={() => setEditTarget('new')}>
                <Plus className="w-4 h-4 mr-1.5" /> Add FAQ
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="space-y-2">
          {faqs.map((faq, index) => (
            <Card
              key={faq.id}
              padding={false}
              className="overflow-hidden"
              hover
            >
              <button
                className="w-full flex items-center gap-3 px-5 py-4 text-left"
                onClick={() => toggle(faq.id)}
              >
                <GripVertical className="w-4 h-4 text-slate-300 flex-shrink-0" />
                <span className="w-5 h-5 rounded-full bg-violet-100 text-violet-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
                  {index + 1}
                </span>
                <span className="flex-1 font-medium text-slate-900 text-sm text-left">{faq.question}</span>
                <div className="flex items-center gap-2 ml-auto flex-shrink-0">
                  <button
                    onClick={(e) => { e.stopPropagation(); setEditTarget(faq) }}
                    className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-violet-600 transition-colors"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteTarget(faq) }}
                    className="p-1.5 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-500 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                  {expanded.has(faq.id)
                    ? <ChevronUp className="w-4 h-4 text-slate-400" />
                    : <ChevronDown className="w-4 h-4 text-slate-400" />
                  }
                </div>
              </button>

              {expanded.has(faq.id) && (
                <div className="px-5 pb-4 pt-0 border-t border-slate-100">
                  <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">{faq.answer}</p>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {editTarget !== null && (
        <FAQFormModal
          faq={editTarget === 'new' ? null : editTarget}
          nextOrder={(faqs?.length ?? 0) + 1}
          onClose={() => setEditTarget(null)}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete FAQ"
        message={`Delete "${deleteTarget?.question}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
        loading={deleteMutation.isPending}
      />
    </div>
  )
}

function FAQFormModal({
  faq,
  nextOrder,
  onClose,
}: {
  faq: FAQ | null
  nextOrder: number
  onClose: () => void
}) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const isEdit = !!faq

  const [form, setForm] = useState({
    question: faq?.question ?? '',
    answer: faq?.answer ?? '',
    sort_order: String(faq?.sort_order ?? nextOrder),
  })

  const mutation = useMutation({
    mutationFn: () =>
      isEdit
        ? faqApi.update(faq!.id, { ...form, sort_order: Number(form.sort_order) })
        : faqApi.create({ ...form, sort_order: Number(form.sort_order) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['faq'] })
      toast.success(isEdit ? 'FAQ updated' : 'FAQ created')
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const set = (f: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((prev) => ({ ...prev, [f]: e.target.value }))

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? 'Edit FAQ' : 'Add FAQ'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>
            {isEdit ? 'Save Changes' : 'Create'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input label="Question" required value={form.question} onChange={set('question')} placeholder="What is the delivery time?" />
        <Textarea label="Answer" required value={form.answer} onChange={set('answer')} placeholder="Delivery takes 1–3 business days…" rows={4} />
        <Input label="Sort Order" type="number" value={form.sort_order} onChange={set('sort_order')} />
      </div>
    </Modal>
  )
}
