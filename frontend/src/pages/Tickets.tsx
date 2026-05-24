import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Ticket, ExternalLink } from 'lucide-react'
import { format, parseISO } from 'date-fns'

import { ticketsApi } from '../lib/api'
import type { OrderStatus } from '../types'
import Card from '../components/ui/Card'
import Badge, { orderStatusBadge, paymentStatusBadge } from '../components/ui/Badge'
import Pagination from '../components/ui/Pagination'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonRow } from '../components/ui/Spinner'
import Select from '../components/ui/Select'
import Modal from '../components/ui/Modal'
import type { Ticket as TicketType } from '../types'

const ORDER_STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'new', label: 'New' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
]

function fmtCurrency(n: number) {
  return new Intl.NumberFormat('uz-UZ').format(n)
}

export default function Tickets() {
  const [page, setPage] = useState(1)
  const [orderStatus, setOrderStatus] = useState<OrderStatus | ''>('')
  const [selected, setSelected] = useState<TicketType | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['tickets', { status: orderStatus || undefined, page }],
    queryFn: () => ticketsApi.list({ page, per_page: 20, order_status: (orderStatus as OrderStatus) || undefined }),
    refetchInterval: 30_000,
  })

  return (
    <div className="space-y-4">
      {/* Filter */}
      <Card className="p-4">
        <div className="flex gap-3">
          <Select
            value={orderStatus}
            onChange={(e) => { setOrderStatus(e.target.value as OrderStatus | ''); setPage(1) }}
            options={ORDER_STATUS_OPTIONS}
            className="w-48"
          />
        </div>
      </Card>

      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60">
                <th className="table-head">#</th>
                <th className="table-head">Customer</th>
                <th className="table-head">Product</th>
                <th className="table-head">Qty</th>
                <th className="table-head">Amount</th>
                <th className="table-head">Payment</th>
                <th className="table-head">Status</th>
                <th className="table-head">Date</th>
                <th className="table-head"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-b border-slate-50">
                  <td colSpan={9} className="px-4 py-2.5"><SkeletonRow /></td>
                </tr>
              ))}

              {!isLoading && data?.items.map((t) => {
                const orderBadge = orderStatusBadge(t.order_status)
                const payBadge = paymentStatusBadge(t.payment_status)
                return (
                  <tr key={t.id} className="table-row cursor-pointer" onClick={() => setSelected(t)}>
                    <td className="table-cell font-mono text-xs text-slate-500">#{t.ticket_number}</td>
                    <td className="table-cell">
                      <div>
                        <p className="font-medium">@{t.client_instagram}</p>
                        {t.client_name && <p className="text-xs text-slate-400">{t.client_name}</p>}
                      </div>
                    </td>
                    <td className="table-cell text-slate-700 max-w-[160px] truncate">{t.product_name}</td>
                    <td className="table-cell text-center tabular-nums">{t.product_quantity}</td>
                    <td className="table-cell tabular-nums font-semibold">
                      {fmtCurrency(t.total_amount)} UZS
                    </td>
                    <td className="table-cell">
                      <Badge variant={payBadge.variant} dot size="sm">{payBadge.label}</Badge>
                    </td>
                    <td className="table-cell">
                      <Badge variant={orderBadge.variant} dot size="sm">{orderBadge.label}</Badge>
                    </td>
                    <td className="table-cell text-xs text-slate-500 whitespace-nowrap">
                      {format(parseISO(t.created_at), 'MMM d, HH:mm')}
                    </td>
                    <td className="table-cell">
                      <ExternalLink className="w-3.5 h-3.5 text-slate-300" />
                    </td>
                  </tr>
                )
              })}

              {!isLoading && data?.items.length === 0 && (
                <tr>
                  <td colSpan={9}>
                    <EmptyState
                      icon={Ticket}
                      title="No tickets found"
                      description="Tickets are created automatically when a customer completes the order flow."
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {data && (
          <Pagination page={page} total={data.total} perPage={20} onChange={setPage} />
        )}
      </Card>

      {/* Detail modal */}
      {selected && (
        <TicketDetailModal ticket={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function TicketDetailModal({ ticket: t, onClose }: { ticket: TicketType; onClose: () => void }) {
  const orderBadge = orderStatusBadge(t.order_status)
  const payBadge = paymentStatusBadge(t.payment_status)

  return (
    <Modal open onClose={onClose} title={`Ticket #${t.ticket_number}`} size="lg">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Section title="Customer">
          <Row label="Instagram" value={`@${t.client_instagram}`} />
          {t.client_name && <Row label="Name" value={t.client_name} />}
          {t.client_phone && <Row label="Phone" value={t.client_phone} />}
          {t.client_city && <Row label="City" value={t.client_city} />}
          {t.client_address && <Row label="Address" value={t.client_address} />}
        </Section>
        <Section title="Order">
          <Row label="Product" value={t.product_name} />
          <Row label="Quantity" value={String(t.product_quantity)} />
          <Row label="Total" value={`${new Intl.NumberFormat('uz-UZ').format(t.total_amount)} UZS`} />
          <Row label="Payment Method" value={t.payment_method === 'transfer' ? 'Bank Transfer' : 'Cash on Delivery'} />
        </Section>
        <Section title="Payment">
          <Row label="Status" value={<Badge variant={payBadge.variant} dot size="sm">{payBadge.label}</Badge>} />
          {t.payment_transaction_id && <Row label="Transaction ID" value={t.payment_transaction_id} />}
          {t.payment_amount_verified != null && (
            <Row label="Verified Amount" value={`${new Intl.NumberFormat('uz-UZ').format(t.payment_amount_verified)} UZS`} />
          )}
          {t.payment_screenshot_url && (
            <a
              href={t.payment_screenshot_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-violet-600 hover:underline flex items-center gap-1 mt-1"
            >
              View Screenshot <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </Section>
        <Section title="Status">
          <Row label="Order" value={<Badge variant={orderBadge.variant} dot size="sm">{orderBadge.label}</Badge>} />
          <Row label="Created" value={format(parseISO(t.created_at), 'MMM d, yyyy HH:mm')} />
          <Row label="Updated" value={format(parseISO(t.updated_at), 'MMM d, yyyy HH:mm')} />
          {t.notes && <Row label="Notes" value={t.notes} />}
        </Section>
      </div>
    </Modal>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{title}</p>
      <div className="bg-slate-50 rounded-xl p-3 space-y-2">{children}</div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <span className="text-xs text-slate-500 flex-shrink-0">{label}</span>
      <span className="text-xs font-medium text-slate-900 text-right">{value}</span>
    </div>
  )
}
