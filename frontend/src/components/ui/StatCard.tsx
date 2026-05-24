import type { LucideIcon } from 'lucide-react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import clsx from 'clsx'

interface StatCardProps {
  title: string
  value: string | number
  icon: LucideIcon
  gradient: string
  iconBg: string
  trend?: number
  suffix?: string
  loading?: boolean
}

export default function StatCard({
  title,
  value,
  icon: Icon,
  gradient,
  iconBg,
  trend,
  suffix,
  loading = false,
}: StatCardProps) {
  return (
    <div className={clsx('rounded-2xl p-5 text-white relative overflow-hidden', gradient)}>
      {/* Background decoration */}
      <div className="absolute -right-6 -top-6 w-24 h-24 rounded-full bg-white/10" />
      <div className="absolute -right-2 -bottom-4 w-16 h-16 rounded-full bg-white/5" />

      <div className="relative">
        <div className="flex items-center justify-between mb-4">
          <div className={clsx('w-11 h-11 rounded-xl flex items-center justify-center', iconBg)}>
            <Icon className="w-6 h-6 text-white" />
          </div>
          {trend !== undefined && (
            <TrendBadge trend={trend} />
          )}
        </div>

        {loading ? (
          <div className="space-y-2">
            <div className="h-8 w-24 bg-white/20 rounded-lg animate-pulse" />
            <div className="h-4 w-32 bg-white/10 rounded animate-pulse" />
          </div>
        ) : (
          <>
            <p className="text-3xl font-bold tracking-tight mb-0.5">
              {value}
              {suffix && <span className="text-lg font-medium ml-1 opacity-80">{suffix}</span>}
            </p>
            <p className="text-sm opacity-80 font-medium">{title}</p>
          </>
        )}
      </div>
    </div>
  )
}

function TrendBadge({ trend }: { trend: number }) {
  if (trend === 0) return (
    <div className="flex items-center gap-1 bg-white/20 rounded-full px-2 py-0.5 text-xs font-medium">
      <Minus className="w-3 h-3" /> 0%
    </div>
  )
  const positive = trend > 0
  return (
    <div className={clsx(
      'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
      positive ? 'bg-white/20' : 'bg-black/20',
    )}>
      {positive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {Math.abs(trend)}%
    </div>
  )
}
