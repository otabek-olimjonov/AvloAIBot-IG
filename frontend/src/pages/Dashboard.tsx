import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts'
import {
  MessageSquare, ShoppingBag, TrendingUp, Banknote,
  ArrowRight, Package,
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { Link } from 'react-router-dom'

import { analyticsApi, ticketsApi } from '../lib/api'
import StatCard from '../components/ui/StatCard'
import Card from '../components/ui/Card'
import Badge, { orderStatusBadge, paymentStatusBadge } from '../components/ui/Badge'
import { PageLoader } from '../components/ui/Spinner'

const CHART_PERIODS = [7, 30, 90] as const
const PIE_COLORS = ['#7c3aed', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

function fmt(n: number) {
  return new Intl.NumberFormat().format(n)
}

function fmtCurrency(n: number) {
  return new Intl.NumberFormat('uz-UZ').format(n)
}

export default function Dashboard() {
  const [chartDays, setChartDays] = useState<7 | 30 | 90>(30)

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['analytics', 'dashboard'],
    queryFn: analyticsApi.dashboard,
    refetchInterval: 30_000,
  })

  const { data: chart, isLoading: chartLoading } = useQuery({
    queryKey: ['analytics', 'chart', chartDays],
    queryFn: () => analyticsApi.chart(chartDays),
  })

  const { data: productStats, isLoading: productLoading } = useQuery({
    queryKey: ['analytics', 'products'],
    queryFn: analyticsApi.products,
  })

  const { data: recentTickets } = useQuery({
    queryKey: ['tickets', { status: undefined, page: 1, per_page: 5 }],
    queryFn: () => ticketsApi.list({ page: 1, per_page: 5 }),
  })

  // Transform chart data for recharts
  const chartData = chart
    ? chart.labels.map((label, i) => ({
        date: format(parseISO(label), 'MMM d'),
        conversations: chart.conversations[i],
        orders: chart.orders[i],
      }))
    : []

  const pieData = (productStats ?? [])
    .filter((p) => p.count > 0)
    .map((p) => ({ name: p.product.replace('Lavender Pillow ', '').replace(' (2 pcs)', ''), value: p.count, revenue: p.revenue }))

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Today's Conversations"
          value={statsLoading ? '—' : fmt(stats?.today_conversations ?? 0)}
          icon={MessageSquare}
          gradient="bg-gradient-to-br from-violet-500 to-violet-700"
          iconBg="bg-white/20"
          loading={statsLoading}
        />
        <StatCard
          title="Today's Orders"
          value={statsLoading ? '—' : fmt(stats?.today_orders ?? 0)}
          icon={ShoppingBag}
          gradient="bg-gradient-to-br from-blue-500 to-blue-700"
          iconBg="bg-white/20"
          loading={statsLoading}
        />
        <StatCard
          title="Conversion Rate"
          value={statsLoading ? '—' : `${stats?.conversion_rate ?? 0}%`}
          icon={TrendingUp}
          gradient="bg-gradient-to-br from-emerald-500 to-emerald-700"
          iconBg="bg-white/20"
          loading={statsLoading}
        />
        <StatCard
          title="Today's Revenue"
          value={statsLoading ? '—' : fmtCurrency(stats?.today_revenue ?? 0)}
          suffix="UZS"
          icon={Banknote}
          gradient="bg-gradient-to-br from-amber-500 to-orange-600"
          iconBg="bg-white/20"
          loading={statsLoading}
        />
      </div>

      {/* Chart row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Trend chart */}
        <Card className="xl:col-span-2 p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-semibold text-slate-900">Activity Trend</h2>
              <p className="text-sm text-slate-500">Conversations vs Orders</p>
            </div>
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
              {CHART_PERIODS.map((d) => (
                <button
                  key={d}
                  onClick={() => setChartDays(d)}
                  className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                    chartDays === d
                      ? 'bg-white text-violet-700 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>

          {chartLoading ? (
            <div className="h-56 flex items-center justify-center">
              <PageLoader />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="colorConv" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorOrders" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,.12)', fontSize: 12 }}
                  labelStyle={{ fontWeight: 600, color: '#1e293b' }}
                />
                <Area type="monotone" dataKey="conversations" name="Conversations" stroke="#7c3aed" strokeWidth={2.5} fill="url(#colorConv)" dot={false} />
                <Area type="monotone" dataKey="orders" name="Orders" stroke="#3b82f6" strokeWidth={2.5} fill="url(#colorOrders)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Pie chart */}
        <Card className="p-5">
          <div className="mb-4">
            <h2 className="font-semibold text-slate-900">Sales by Product</h2>
            <p className="text-sm text-slate-500">All-time breakdown</p>
          </div>

          {productLoading ? (
            <div className="h-56 flex items-center justify-center"><PageLoader /></div>
          ) : pieData.length === 0 ? (
            <div className="h-56 flex flex-col items-center justify-center text-slate-400">
              <Package className="w-10 h-10 mb-2 opacity-40" />
              <p className="text-sm">No sales data yet</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  dataKey="value"
                  paddingAngle={3}
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(val: number, name: string, props) => [
                    `${val} orders · ${fmtCurrency(props.payload?.revenue ?? 0)} UZS`,
                    props.payload?.name,
                  ]}
                  contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,.12)', fontSize: 12 }}
                />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Recent tickets */}
      <Card padding={false}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <h2 className="font-semibold text-slate-900">Recent Tickets</h2>
            <p className="text-sm text-slate-500">Latest 5 orders</p>
          </div>
          <Link
            to="/tickets"
            className="flex items-center gap-1 text-sm text-violet-600 hover:text-violet-700 font-medium"
          >
            View all <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60">
                <th className="table-head">#</th>
                <th className="table-head">Customer</th>
                <th className="table-head">Product</th>
                <th className="table-head">Amount</th>
                <th className="table-head">Payment</th>
                <th className="table-head">Status</th>
              </tr>
            </thead>
            <tbody>
              {recentTickets?.items.map((t) => {
                const orderBadge = orderStatusBadge(t.order_status)
                const payBadge = paymentStatusBadge(t.payment_status)
                return (
                  <tr key={t.id} className="table-row">
                    <td className="table-cell font-mono text-xs text-slate-500">#{t.ticket_number}</td>
                    <td className="table-cell font-medium">@{t.client_instagram}</td>
                    <td className="table-cell text-slate-600">{t.product_name}</td>
                    <td className="table-cell font-semibold">{fmtCurrency(t.total_amount)} UZS</td>
                    <td className="table-cell">
                      <Badge variant={payBadge.variant} dot>{payBadge.label}</Badge>
                    </td>
                    <td className="table-cell">
                      <Badge variant={orderBadge.variant} dot>{orderBadge.label}</Badge>
                    </td>
                  </tr>
                )
              })}
              {!recentTickets?.items.length && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-sm text-slate-400">
                    No tickets yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
