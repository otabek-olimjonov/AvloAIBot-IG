import clsx from 'clsx'

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'violet' | 'slate'

const variants: Record<BadgeVariant, string> = {
  default: 'bg-slate-100 text-slate-600',
  success: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
  danger: 'bg-rose-100 text-rose-700',
  info: 'bg-blue-100 text-blue-700',
  violet: 'bg-violet-100 text-violet-700',
  slate: 'bg-slate-200 text-slate-600',
}

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
  dot?: boolean
  size?: 'sm' | 'md'
}

export default function Badge({ variant = 'default', children, className, dot, size = 'md' }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full font-semibold whitespace-nowrap',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs',
        variants[variant],
        className,
      )}
    >
      {dot && (
        <span
          className={clsx(
            'w-1.5 h-1.5 rounded-full flex-shrink-0',
            variant === 'success' && 'bg-emerald-500',
            variant === 'warning' && 'bg-amber-500',
            variant === 'danger' && 'bg-rose-500',
            variant === 'info' && 'bg-blue-500',
            variant === 'violet' && 'bg-violet-500',
            variant === 'default' && 'bg-slate-400',
            variant === 'slate' && 'bg-slate-400',
          )}
        />
      )}
      {children}
    </span>
  )
}

// ─── Helper mappers ────────────────────────────────────────────
export function conversationStatusBadge(status: string) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    active: { variant: 'success', label: 'Active' },
    ended: { variant: 'slate', label: 'Ended' },
    converted: { variant: 'violet', label: 'Converted' },
  }
  return map[status] ?? { variant: 'default', label: status }
}

export function funnelStageBadge(stage: string) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    greeting: { variant: 'info', label: 'Greeting' },
    qualification: { variant: 'info', label: 'Qualification' },
    presentation: { variant: 'violet', label: 'Presentation' },
    objection: { variant: 'warning', label: 'Objection' },
    closing: { variant: 'warning', label: 'Closing' },
    payment: { variant: 'violet', label: 'Payment' },
    completed: { variant: 'success', label: 'Completed' },
  }
  return map[stage] ?? { variant: 'default', label: stage }
}

export function orderStatusBadge(status: string) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    new: { variant: 'info', label: 'New' },
    in_progress: { variant: 'warning', label: 'In Progress' },
    completed: { variant: 'success', label: 'Completed' },
    cancelled: { variant: 'danger', label: 'Cancelled' },
  }
  return map[status] ?? { variant: 'default', label: status }
}

export function paymentStatusBadge(status: string) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    confirmed: { variant: 'success', label: 'Confirmed' },
    pending: { variant: 'warning', label: 'Pending' },
    rejected: { variant: 'danger', label: 'Rejected' },
  }
  return map[status] ?? { variant: 'default', label: status }
}
