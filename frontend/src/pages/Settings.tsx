import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CreditCard, Instagram, Send, Clock, MessageSquare, Save,
  ChevronDown, ChevronUp, TestTube2,
} from 'lucide-react'

import { settingsApi } from '../lib/api'
import type { Setting } from '../types'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Textarea from '../components/ui/Textarea'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../contexts/ToastContext'

type SettingsMap = Record<string, string>

interface Section {
  key: string
  title: string
  icon: React.ElementType
  fields: { key: string; label: string; type?: string; placeholder?: string; isTextarea?: boolean; sensitive?: boolean }[]
}

const SECTIONS: Section[] = [
  {
    key: 'payment',
    title: 'Payment Details',
    icon: CreditCard,
    fields: [
      { key: 'payment_card_number', label: 'Card Number', placeholder: '8600 1234 5678 9012' },
      { key: 'payment_card_owner', label: 'Card Owner', placeholder: 'John Smith' },
      { key: 'payment_bank', label: 'Bank Name', placeholder: 'Kapital Bank' },
    ],
  },
  {
    key: 'instagram',
    title: 'Instagram Integration',
    icon: Instagram,
    fields: [
      { key: 'instagram_page_id', label: 'Page ID', placeholder: '12345678' },
      { key: 'instagram_access_token', label: 'Access Token', placeholder: 'EAAxxxxx…', sensitive: true },
      { key: 'instagram_verify_token', label: 'Webhook Verify Token', placeholder: 'my_secret_token', sensitive: true },
    ],
  },
  {
    key: 'telegram',
    title: 'Telegram Bot',
    icon: Send,
    fields: [
      { key: 'telegram_bot_token', label: 'Bot Token', placeholder: '123456:ABCxxx…', sensitive: true },
      { key: 'telegram_group_id', label: 'Group / Channel ID', placeholder: '-1001234567890' },
    ],
  },
  {
    key: 'hours',
    title: 'Working Hours',
    icon: Clock,
    fields: [
      { key: 'working_hours_start', label: 'Start Time (HH:MM)', placeholder: '09:00' },
      { key: 'working_hours_end', label: 'End Time (HH:MM)', placeholder: '18:00' },
      { key: 'is_24_7', label: '24/7 Mode (true/false)', placeholder: 'false' },
    ],
  },
  {
    key: 'bot',
    title: 'Bot Behaviour',
    icon: MessageSquare,
    fields: [
      { key: 'offline_message', label: 'Offline Message', isTextarea: true, placeholder: 'We are offline right now, will reply soon…' },
      { key: 'fallback_message_uz', label: 'Fallback Message (UZ)', isTextarea: true },
      { key: 'fallback_message_ru', label: 'Fallback Message (RU)', isTextarea: true },
      {
        key: 'dm_greeting_message',
        label: 'First DM Greeting (sent to new users before AI takes over)',
        isTextarea: true,
        placeholder: 'Assalomu alaykum! 👋 Qanday yordam bera olaman?',
      },
      {
        key: 'comment_auto_dm_enabled',
        label: 'Comment Auto-DM Enabled (true / false)',
        placeholder: 'true',
      },
      {
        key: 'comment_reply_message',
        label: "Public Comment Reply (posted under the comment, use {name} for commenter's name)",
        isTextarea: true,
        placeholder: "Salom, {name}! 😊 DM ga yozib qoldingiz — tez orada javob beramiz! 🌿",
      },
      {
        key: 'comment_auto_dm_message',
        label: "Comment Auto-DM Message (use {name} for commenter’s name)",
        isTextarea: true,
        placeholder: "Salom, {name}! 👋 Izohingiz uchun rahmat. Savolingiz bo'lsa yozing! 😊",
      },
    ],
  },
]

export default function Settings() {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [values, setValues] = useState<SettingsMap>({})
  const [dirty, setDirty] = useState<Set<string>>(new Set())
  const [open, setOpen] = useState<Set<string>>(new Set(SECTIONS.map((s) => s.key)))
  const [testingTelegram, setTestingTelegram] = useState(false)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: settingsApi.list,
  })

  useEffect(() => {
    if (settings) {
      const map: SettingsMap = {}
      settings.forEach((s) => { map[s.key] = s.value })
      setValues(map)
    }
  }, [settings])

  const saveMutation = useMutation({
    mutationFn: (updates: { key: string; value: string }[]) =>
      Promise.all(updates.map((u) => settingsApi.update(u.key, u.value))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      toast.success('Settings saved successfully')
      setDirty(new Set())
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const testTelegramMutation = useMutation({
    mutationFn: settingsApi.testTelegram,
    onSuccess: () => { toast.success('Test message sent to Telegram!'); setTestingTelegram(false) },
    onError: (e: Error) => { toast.error(e.message); setTestingTelegram(false) },
  })

  const handleChange = (key: string, value: string) => {
    setValues((v) => ({ ...v, [key]: value }))
    setDirty((d) => new Set(d).add(key))
  }

  const handleSave = () => {
    const updates = Array.from(dirty).map((key) => ({ key, value: values[key] ?? '' }))
    if (!updates.length) return
    saveMutation.mutate(updates)
  }

  const toggleSection = (key: string) =>
    setOpen((s) => { const n = new Set(s); n.has(key) ? n.delete(key) : n.add(key); return n })

  if (isLoading) return <PageLoader />

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {SECTIONS.map(({ key, title, icon: Icon, fields }) => (
        <Card key={key} padding={false} className="overflow-hidden">
          <button
            className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-slate-50 transition-colors"
            onClick={() => toggleSection(key)}
          >
            <div className="w-8 h-8 rounded-lg bg-violet-100 flex items-center justify-center">
              <Icon className="w-4 h-4 text-violet-600" />
            </div>
            <span className="font-semibold text-slate-900 flex-1">{title}</span>
            {open.has(key) ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>

          {open.has(key) && (
            <div className="px-5 pb-5 space-y-4 border-t border-slate-100 pt-4">
              {fields.map((field) =>
                field.isTextarea ? (
                  <Textarea
                    key={field.key}
                    label={field.label}
                    value={values[field.key] ?? ''}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    placeholder={field.placeholder}
                    rows={3}
                  />
                ) : (
                  <Input
                    key={field.key}
                    label={field.label}
                    type={field.sensitive ? 'password' : field.type ?? 'text'}
                    value={values[field.key] ?? ''}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    placeholder={field.placeholder}
                  />
                ),
              )}

              {key === 'telegram' && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => { setTestingTelegram(true); testTelegramMutation.mutate() }}
                  loading={testingTelegram}
                >
                  <TestTube2 className="w-4 h-4 mr-1.5" /> Send Test Message
                </Button>
              )}
            </div>
          )}
        </Card>
      ))}

      {/* Save bar */}
      <div className="flex items-center justify-between bg-white border border-slate-200 rounded-2xl px-5 py-4 sticky bottom-4 shadow-lg shadow-slate-200/60">
        <p className="text-sm text-slate-600">
          {dirty.size > 0
            ? <span className="text-amber-600 font-medium">{dirty.size} unsaved change{dirty.size > 1 ? 's' : ''}</span>
            : <span className="text-slate-400">All changes saved</span>
          }
        </p>
        <Button
          onClick={handleSave}
          disabled={dirty.size === 0}
          loading={saveMutation.isPending}
        >
          <Save className="w-4 h-4 mr-1.5" /> Save Settings
        </Button>
      </div>
    </div>
  )
}
