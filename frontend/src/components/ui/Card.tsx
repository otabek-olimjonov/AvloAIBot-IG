import clsx from 'clsx'
import type { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  padding?: boolean
  hover?: boolean
}

export default function Card({ children, className, padding = true, hover = false, ...rest }: CardProps) {
  return (
    <div
      className={clsx(
        'bg-white border border-slate-200 rounded-xl shadow-sm',
        padding && 'p-5',
        hover && 'hover:shadow-md transition-shadow duration-200 cursor-pointer',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}
