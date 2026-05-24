import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Sparkles, Save } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import clsx from 'clsx'

import { promptsApi } from '../lib/api'
import type { Prompt, PromptType } from '../types'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Textarea from '../components/ui/Textarea'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../contexts/ToastContext'

const PROMPT_META: Record<PromptType, { label: string; color: string; description: string }> = {
  system: { label: 'System', color: 'bg-violet-100 text-violet-700', description: 'Core bot personality and rules' },
  greeting: { label: 'Greeting', color: 'bg-blue-100 text-blue-700', description: 'First message to new users' },
  qualification: { label: 'Qualification', color: 'bg-cyan-100 text-cyan-700', description: 'Understanding customer needs' },
  presentation: { label: 'Presentation', color: 'bg-indigo-100 text-indigo-700', description: 'Product presentation stage' },
  objections: { label: 'Objections', color: 'bg-amber-100 text-amber-700', description: 'Handling customer objections' },
  closing: { label: 'Closing', color: 'bg-orange-100 text-orange-700', description: 'Converting to purchase' },
  upsell: { label: 'Upsell', color: 'bg-emerald-100 text-emerald-700', description: 'Post-purchase upselling' },
}

export default function Prompts() {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [editing, setEditing] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)

  const { data: prompts, isLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: promptsApi.list,
  })

  const mutation = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) =>
      promptsApi.update(id, { content }),
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: ['prompts'] })
      toast.success('Prompt saved')
      setSaving(null)
      setEditing((e) => { const next = { ...e }; delete next[variables.id]; return next })
    },
    onError: (e: Error) => { toast.error(e.message); setSaving(null) },
  })

  if (isLoading) return <PageLoader />

  const handleSave = (prompt: Prompt) => {
    const content = editing[prompt.id]
    if (!content?.trim()) return
    setSaving(prompt.id)
    mutation.mutate({ id: prompt.id, content })
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Edit the AI prompts that guide the bot's behavior at each stage of the sales funnel.
      </p>

      {prompts?.map((prompt) => {
        const meta = PROMPT_META[prompt.type] ?? { label: prompt.type, color: 'bg-slate-100 text-slate-600', description: '' }
        const isEditing = prompt.id in editing
        const content = isEditing ? editing[prompt.id] : prompt.content

        return (
          <Card key={prompt.id} className="p-5">
            <div className="flex items-start justify-between gap-4 mb-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-violet-50 flex items-center justify-center">
                  <Sparkles className="w-4.5 h-4.5 w-[18px] h-[18px] text-violet-500" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-slate-900">{meta.label}</h3>
                    <span className={clsx('text-xs font-medium px-2 py-0.5 rounded-full', meta.color)}>
                      {prompt.type}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">{meta.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs text-slate-400">
                  Updated {format(parseISO(prompt.updated_at), 'MMM d')}
                </span>
                {!isEditing ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setEditing((e) => ({ ...e, [prompt.id]: prompt.content }))}
                  >
                    Edit
                  </Button>
                ) : (
                  <div className="flex gap-1.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditing((e) => { const next = { ...e }; delete next[prompt.id]; return next })}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleSave(prompt)}
                      loading={saving === prompt.id}
                    >
                      <Save className="w-3.5 h-3.5 mr-1" /> Save
                    </Button>
                  </div>
                )}
              </div>
            </div>

            {isEditing ? (
              <Textarea
                value={editing[prompt.id]}
                onChange={(e) => setEditing((prev) => ({ ...prev, [prompt.id]: e.target.value }))}
                rows={8}
                className="font-mono text-xs"
              />
            ) : (
              <div
                className="bg-slate-50 rounded-xl p-4 text-sm text-slate-700 font-mono leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto cursor-pointer hover:bg-slate-100 transition-colors"
                onClick={() => setEditing((e) => ({ ...e, [prompt.id]: prompt.content }))}
              >
                {prompt.content}
              </div>
            )}
          </Card>
        )
      })}
    </div>
  )
}
