import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, Package, ToggleLeft, ToggleRight } from 'lucide-react'

import { productsApi } from '../lib/api'
import type { Product } from '../types'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Textarea from '../components/ui/Textarea'
import EmptyState from '../components/ui/EmptyState'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import Badge from '../components/ui/Badge'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../contexts/ToastContext'

function fmtPrice(n: number) {
  return new Intl.NumberFormat('uz-UZ').format(n)
}

export default function Products() {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [editTarget, setEditTarget] = useState<Product | null | 'new'>(null)
  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null)

  const { data: products, isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: productsApi.list,
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, val }: { id: string; val: boolean }) =>
      productsApi.update(id, { is_available: val }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
    onError: (e: Error) => toast.error(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => productsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['products'] })
      toast.success('Product deleted')
      setDeleteTarget(null)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (isLoading) return <PageLoader />

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setEditTarget('new')}>
          <Plus className="w-4 h-4 mr-1.5" /> Add Product
        </Button>
      </div>

      {!products?.length ? (
        <Card>
          <EmptyState
            icon={Package}
            title="No products yet"
            description="Add your first product to get started."
            action={
              <Button onClick={() => setEditTarget('new')}>
                <Plus className="w-4 h-4 mr-1.5" /> Add Product
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onEdit={() => setEditTarget(product)}
              onDelete={() => setDeleteTarget(product)}
              onToggle={(val) => toggleMutation.mutate({ id: product.id, val })}
            />
          ))}
        </div>
      )}

      {editTarget !== null && (
        <ProductFormModal
          product={editTarget === 'new' ? null : editTarget}
          onClose={() => setEditTarget(null)}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Product"
        message={`Are you sure you want to delete "${deleteTarget?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
        loading={deleteMutation.isPending}
      />
    </div>
  )
}

function ProductCard({
  product,
  onEdit,
  onDelete,
  onToggle,
}: {
  product: Product
  onEdit: () => void
  onDelete: () => void
  onToggle: (val: boolean) => void
}) {
  return (
    <Card hover className="p-5 flex flex-col gap-3">
      {/* Image placeholder */}
      <div className="w-full h-36 bg-gradient-to-br from-violet-50 to-purple-100 rounded-xl flex items-center justify-center overflow-hidden">
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
        ) : (
          <Package className="w-12 h-12 text-violet-300" />
        )}
      </div>

      <div className="flex-1">
        <div className="flex items-start justify-between gap-2 mb-1">
          <h3 className="font-semibold text-slate-900 text-sm leading-snug">{product.name}</h3>
          <Badge variant={product.is_available ? 'success' : 'default'} size="sm">
            {product.is_available ? 'Available' : 'Hidden'}
          </Badge>
        </div>
        <p className="text-sm text-slate-500 line-clamp-2 leading-relaxed mb-3">
          {product.description ?? 'No description'}
        </p>
        <p className="text-lg font-bold text-violet-700">{fmtPrice(product.price)} UZS</p>
      </div>

      <div className="flex items-center gap-2 pt-2 border-t border-slate-100">
        <button
          onClick={() => onToggle(!product.is_available)}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
        >
          {product.is_available
            ? <ToggleRight className="w-4 h-4 text-emerald-500" />
            : <ToggleLeft className="w-4 h-4 text-slate-400" />
          }
          {product.is_available ? 'Available' : 'Hidden'}
        </button>
        <div className="ml-auto flex gap-1">
          <button
            onClick={onEdit}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-violet-600 transition-colors"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-500 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </Card>
  )
}

function ProductFormModal({
  product,
  onClose,
}: {
  product: Product | null
  onClose: () => void
}) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const isEdit = !!product

  const [form, setForm] = useState({
    name: product?.name ?? '',
    description: product?.description ?? '',
    price: String(product?.price ?? ''),
    image_url: product?.image_url ?? '',
    is_available: product?.is_available ?? true,
  })

  const mutation = useMutation({
    mutationFn: () =>
      isEdit
        ? productsApi.update(product!.id, { ...form, price: Number(form.price) })
        : productsApi.create({ ...form, price: Number(form.price) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['products'] })
      toast.success(isEdit ? 'Product updated' : 'Product created')
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? 'Edit Product' : 'Add Product'}
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
        <Input label="Product Name" required value={form.name} onChange={set('name')} placeholder="Lavender Pillow Premium" />
        <Textarea label="Description" value={form.description} onChange={set('description')} placeholder="Describe the product…" rows={3} />
        <Input label="Price (UZS)" required type="number" value={form.price} onChange={set('price')} placeholder="150000" />
        <Input label="Image URL" value={form.image_url} onChange={set('image_url')} placeholder="https://…" />
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="available"
            checked={form.is_available}
            onChange={(e) => setForm((f) => ({ ...f, is_available: e.target.checked }))}
            className="w-4 h-4 text-violet-600 rounded"
          />
          <label htmlFor="available" className="text-sm font-medium text-slate-700">
            Available for sale
          </label>
        </div>
      </div>
    </Modal>
  )
}
