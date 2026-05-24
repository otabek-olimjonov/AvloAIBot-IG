import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Bot, User, Image } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import clsx from 'clsx'

import { conversationsApi } from '../lib/api'
import type { Message } from '../types'
import Card from '../components/ui/Card'
import Badge, { conversationStatusBadge, funnelStageBadge } from '../components/ui/Badge'
import { PageLoader } from '../components/ui/Spinner'
import Button from '../components/ui/Button'

export default function ConversationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: conv, isLoading: convLoading } = useQuery({
    queryKey: ['conversation', id],
    queryFn: () => conversationsApi.get(id!),
    enabled: !!id,
  })

  const { data: messages, isLoading: msgLoading } = useQuery({
    queryKey: ['conversation', id, 'messages'],
    queryFn: () => conversationsApi.messages(id!),
    enabled: !!id,
    refetchInterval: conv?.status === 'active' ? 10_000 : false,
  })

  const isLoading = convLoading || msgLoading

  if (isLoading) return <PageLoader />

  if (!conv) return (
    <div className="text-center py-20 text-slate-500">
      Conversation not found.
    </div>
  )

  const statusBadge = conversationStatusBadge(conv.status)
  const stageBadge = funnelStageBadge(conv.funnel_stage)

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Back + header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Chat area */}
        <Card padding={false} className="lg:col-span-2 flex flex-col" style={{ height: '72vh' }}>
          {/* Chat header */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 bg-slate-50/60 flex-shrink-0">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white text-sm font-bold">
              {(conv.instagram_username ?? conv.instagram_user_id)[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-slate-900 truncate">
                {conv.instagram_username ? `@${conv.instagram_username}` : conv.instagram_user_id}
              </p>
              <p className="text-xs text-slate-500">{conv.message_count} messages</p>
            </div>
            <Badge variant={statusBadge.variant} dot size="sm">{statusBadge.label}</Badge>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {messages?.items.map((msg) => (
              <ChatBubble key={msg.id} message={msg} />
            ))}
            {messages?.items.length === 0 && (
              <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                No messages yet
              </div>
            )}
          </div>
        </Card>

        {/* Metadata sidebar */}
        <div className="space-y-4">
          <Card className="p-4 space-y-3">
            <h3 className="font-semibold text-slate-900 text-sm">Conversation Info</h3>
            <MetaRow label="Instagram User" value={`@${conv.instagram_username ?? conv.instagram_user_id}`} />
            <MetaRow label="Source" value={conv.source === 'dm' ? 'Direct Message' : 'Comment Reply'} />
            <MetaRow
              label="Funnel Stage"
              value={<Badge variant={stageBadge.variant} size="sm">{stageBadge.label}</Badge>}
            />
            <MetaRow
              label="Status"
              value={<Badge variant={statusBadge.variant} dot size="sm">{statusBadge.label}</Badge>}
            />
            <MetaRow label="Started" value={format(parseISO(conv.started_at), 'MMM d, yyyy HH:mm')} />
            {conv.ended_at && (
              <MetaRow label="Ended" value={format(parseISO(conv.ended_at), 'MMM d, yyyy HH:mm')} />
            )}
          </Card>

          {conv.ticket_id && (
            <Card className="p-4">
              <h3 className="font-semibold text-slate-900 text-sm mb-3">Linked Ticket</h3>
              <Button
                variant="secondary"
                size="sm"
                className="w-full"
                onClick={() => navigate(`/tickets?id=${conv.ticket_id}`)}
              >
                View Order Ticket
              </Button>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

function ChatBubble({ message }: { message: Message }) {
  const isBot = message.role === 'bot'
  return (
    <div className={clsx('flex gap-2.5 max-w-[85%]', isBot ? 'ml-auto flex-row-reverse' : '')}>
      {/* Avatar */}
      <div className={clsx(
        'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5',
        isBot ? 'bg-violet-100' : 'bg-slate-200',
      )}>
        {isBot
          ? <Bot className="w-4 h-4 text-violet-600" />
          : <User className="w-4 h-4 text-slate-500" />
        }
      </div>

      {/* Bubble */}
      <div className="space-y-1">
        {message.media_url && (
          <div className={clsx('rounded-2xl overflow-hidden max-w-[240px]', isBot ? 'rounded-tr-md' : 'rounded-tl-md')}>
            <img src={message.media_url} alt="media" className="w-full object-cover" />
          </div>
        )}
        {message.content && (
          <div className={clsx(
            'px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed',
            isBot
              ? 'bg-violet-600 text-white rounded-tr-md'
              : 'bg-white border border-slate-200 text-slate-800 rounded-tl-md shadow-sm',
          )}>
            {message.content}
          </div>
        )}
        <p className={clsx('text-xs text-slate-400', isBot ? 'text-right' : '')}>
          {format(parseISO(message.created_at), 'HH:mm')}
        </p>
      </div>
    </div>
  )
}

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <span className="text-xs text-slate-500 flex-shrink-0 pt-0.5">{label}</span>
      <span className="text-xs font-medium text-slate-900 text-right">{value}</span>
    </div>
  )
}
