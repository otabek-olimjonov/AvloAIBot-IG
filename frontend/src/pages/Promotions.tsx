import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, Tag } from 'lucide-react'
import { format, parseISO } from 'date-fns'

import { promotionsApi } from '../lib/api'
import type { Promotion } from '../types'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Textarea from '../components/ui/Textarea'
import Select from '../components/ui/Select'
import EmptyState from '../components/ui/EmptyState'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../contexts/ToastContext'

const TYPE_OPTIONS = [
  { value: 'percentage', label: 'Percentage Discount (%)' },
  { value: 'fixed', label: 'Fixed Discount (UZS)' },
  { value: 'bundle', label: 'Bundle Deal' },
]

export default function Promotions() {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [editTarget, setEditTarget] = useState<Promotion | null | 'new'>(null)
  const [deleteTarget, setDeleteTarget] = useState<Promotion | null>(null)

  const { data: promotions, isLoading } = useQuery({
    queryKey: ['promotions'],
    queryFn: promotionsApi.list,
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, val }: { id: string; val: boolean }) =>
      promotionsApi.update(id, { is_active: val }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['promotions'] }),
    onError: (e: Error) => toast.error(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => promotionsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['promotions'] })
      toast.success('Promotion deleted')
      setDeleteTarget(null)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (isLoading) return <PageLoader />

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setEditTarget('new')}>
          <Plus className="w-4 h-4 mr-1.5" /> Add Promotion
        </Button>
      </div>

      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60">
                <th className="table-head">Name</th>
                <th className="table-head">Type</th>
                <th className="table-head">Value</th>
                <th className="table-head">Code</th>
                <th className="table-head">Period</th>
                <th className="table-head">Status</th>
                <th className="table-head"></th>
              </tr>
            </thead>
            <tbody>
              {promotions?.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      icon={Tag}
                      title="No promotions yet"
                      description="Create promotions to give your customers discounts and special deals."
                      action={<Button onClick={() => setEditTarget('new')}><Plus className="w-4 h-4 mr-1.5" />Add Promotion</Button>}
                    />
                  </td>
                </tr>
              )}
              {promotions?.map((promo) => (
                <tr key={promo.id} className="table-row">
                  <td className="table-cell font-medium">{promo.name}</td>
                  <td className="table-cell">
                    <Badge variant="info" size="sm">
                      {promo.type === 'percentage' ? '%' : promo.type === 'fixed' ? 'Fixed' : 'Bundle'}
                    </Badge>
                  </td>
                  <td className="table-cell tabular-nums font-semibold">
                    {promo.type === 'percentage' ? `${promo.value}%` : promo.type === 'fixed' ? `${promo.value} UZS` : promo.value}
                  </td>
                  <td className="table-cell font-mono text-xs text-slate-600">
                    {promo.promo_code ?? '—'}
                  </td>
                  <td className="table-cell text-xs text-slate-500 whitespace-nowrap">
                    {format(parseISO(promo.start_date), 'MMM d')} – {format(parseISO(promo.end_date), 'MMM d, yyyy')}
                  </td>
                  <td className="table-cell">
                    <button onClick={() => toggleMutation.mutate({ id: promo.id, val: !promo.is_active })}>
                      <Badge variant={promo.is_active ? 'success' : 'default'} dot size="sm">
                        {promo.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </button>
                  </td>
                  <td className="table-cell">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => setEditTarget(promo)}
                        className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-violet-600 transition-colors"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setDeleteTarget(promo)}
                        className="p-1.5 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-500 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {editTarget !== null && (
        <PromotionFormModal
          promotion={editTarget === 'new' ? null : editTarget}
          onClose={() => setEditTarget(null)}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Promotion"
        message={`Delete "${deleteTarget?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
        loading={deleteMutation.isPending}
      />
    </div>
  )
}

function PromotionFormModal({ promotion, onClose }: { promotion: Promotion | null; onClose: () => void }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const isEdit = !!promotion

  const today = format(new Date(), 'yyyy-MM-dd')
  const [form, setForm] = useState({
    name: promotion?.name ?? '',
    type: promotion?.type ?? 'percentage',
    value: promotion?.value ?? '',
    description_for_bot: promotion?.description_for_bot ?? '',
    promo_code: promotion?.promo_code ?? '',
    start_date: promotion?.start_date?.slice(0, 10) ?? today,
    end_date: promotion?.end_date?.slice(0, 10) ?? today,
    is_active: promotion?.is_active ?? true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      isEdit
        ? promotionsApi.update(promotion!.id, { ...form, start_date: form.start_date + 'T00:00:00', end_date: form.end_date + 'T23:59:59' })
        : promotionsApi.create({ ...form, start_date: form.start_date + 'T00:00:00', end_date: form.end_date + 'T23:59:59' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['promotions'] })
      toast.success(isEdit ? 'Promotion updated' : 'Promotion created')
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const set = (f: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [f]: e.target.value }))

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? 'Edit Promotion' : 'Add Promotion'}
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
        <Input label="Promotion Name" required value={form.name} onChange={set('name')} placeholder="Summer Sale" />
        <div className="grid grid-cols-2 gap-4">
          <Select label="Type" options={TYPE_OPTIONS} value={form.type} onChange={set('type')} />
          <Input
            label={form.type === 'percentage' ? 'Discount (%)' : form.type === 'fixed' ? 'Amount (UZS)' : 'Value'}
            required
            value={form.value}
            onChange={set('value')}
            placeholder={form.type === 'percentage' ? '15' : '50000'}
          />
        </div>
        <Textarea label="Description for Bot" value={form.description_for_bot} onChange={set('description_for_bot')} placeholder="How the bot should describe this promotion…" rows={2} />
        <Input label="Promo Code (optional)" value={form.promo_code} onChange={set('promo_code')} placeholder="SUMMER15" />
        <div className="grid grid-cols-2 gap-4">
          <Input label="Start Date" type="date" value={form.start_date} onChange={set('start_date')} />
          <Input label="End Date" type="date" value={form.end_date} onChange={set('end_date')} />
        </div>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="promo-active"
            checked={form.is_active}
            onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
            className="w-4 h-4 text-violet-600 rounded"
          />
          <label htmlFor="promo-active" className="text-sm font-medium text-slate-700">Active</label>
        </div>
      </div>
    </Modal>
  )
}
