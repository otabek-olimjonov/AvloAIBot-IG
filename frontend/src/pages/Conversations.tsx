import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, ChevronRight, Search } from 'lucide-react'
import { formatDistanceToNow, parseISO } from 'date-fns'

import { conversationsApi } from '../lib/api'
import type { ConversationStatus, FunnelStage } from '../types'
import Card from '../components/ui/Card'
import Badge, { conversationStatusBadge, funnelStageBadge } from '../components/ui/Badge'
import Pagination from '../components/ui/Pagination'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonRow } from '../components/ui/Spinner'
import Select from '../components/ui/Select'
import Input from '../components/ui/Input'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'ended', label: 'Ended' },
  { value: 'converted', label: 'Converted' },
]

const STAGE_OPTIONS = [
  { value: '', label: 'All stages' },
  { value: 'greeting', label: 'Greeting' },
  { value: 'qualification', label: 'Qualification' },
  { value: 'presentation', label: 'Presentation' },
  { value: 'objection', label: 'Objection' },
  { value: 'closing', label: 'Closing' },
  { value: 'payment', label: 'Payment' },
  { value: 'completed', label: 'Completed' },
]

export default function Conversations() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<ConversationStatus | ''>('')
  const [stage, setStage] = useState<FunnelStage | ''>('')
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['conversations', { page, status: status || undefined, stage: stage || undefined }],
    queryFn: () => conversationsApi.list({
      page,
      per_page: 20,
      status: (status as ConversationStatus) || undefined,
      funnel_stage: (stage as FunnelStage) || undefined,
    }),
  })

  const filtered = search
    ? data?.items.filter((c) =>
        c.instagram_username?.toLowerCase().includes(search.toLowerCase()) ||
        c.instagram_user_id.includes(search),
      )
    : data?.items

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <Input
              placeholder="Search by username or user ID…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>
          <Select
            value={status}
            onChange={(e) => { setStatus(e.target.value as ConversationStatus | ''); setPage(1) }}
            options={STATUS_OPTIONS}
            className="sm:w-44"
          />
          <Select
            value={stage}
            onChange={(e) => { setStage(e.target.value as FunnelStage | ''); setPage(1) }}
            options={STAGE_OPTIONS}
            className="sm:w-48"
          />
        </div>
      </Card>

      {/* Table */}
      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60">
                <th className="table-head">User</th>
                <th className="table-head">Source</th>
                <th className="table-head">Stage</th>
                <th className="table-head text-center">Messages</th>
                <th className="table-head">Status</th>
                <th className="table-head">Started</th>
                <th className="table-head"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-b border-slate-50">
                  <td colSpan={7} className="px-4 py-2.5"><SkeletonRow /></td>
                </tr>
              ))}

              {!isLoading && filtered?.map((conv) => {
                const statusBadge = conversationStatusBadge(conv.status)
                const stageBadge = funnelStageBadge(conv.funnel_stage)
                return (
                  <tr
                    key={conv.id}
                    className="table-row cursor-pointer"
                    onClick={() => navigate(`/conversations/${conv.id}`)}
                  >
                    <td className="table-cell">
                      <div>
                        <p className="font-medium text-slate-900">
                          {conv.instagram_username
                            ? (conv.instagram_username.includes(' ')
                                ? conv.instagram_username
                                : `@${conv.instagram_username}`)
                            : conv.instagram_user_id}
                        </p>
                        {conv.instagram_username && (
                          <p className="text-xs text-slate-400">{conv.instagram_user_id}</p>
                        )}
                      </div>
                    </td>
                    <td className="table-cell">
                      <Badge variant={conv.source === 'dm' ? 'default' : 'info'} size="sm">
                        {conv.source === 'dm' ? 'DM' : 'Comment'}
                      </Badge>
                    </td>
                    <td className="table-cell">
                      <Badge variant={stageBadge.variant} size="sm">{stageBadge.label}</Badge>
                    </td>
                    <td className="table-cell text-center tabular-nums font-medium">
                      {conv.message_count}
                    </td>
                    <td className="table-cell">
                      <Badge variant={statusBadge.variant} dot size="sm">{statusBadge.label}</Badge>
                    </td>
                    <td className="table-cell text-slate-500 text-xs whitespace-nowrap">
                      {formatDistanceToNow(parseISO(conv.started_at), { addSuffix: true })}
                    </td>
                    <td className="table-cell text-right">
                      <ChevronRight className="w-4 h-4 text-slate-300 ml-auto" />
                    </td>
                  </tr>
                )
              })}

              {!isLoading && filtered?.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      icon={MessageSquare}
                      title="No conversations found"
                      description="Try adjusting your filters or wait for new users to start chatting."
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {data && (
          <Pagination
            page={page}
            total={data.total}
            perPage={20}
            onChange={setPage}
          />
        )}
      </Card>
    </div>
  )
}
