import { useState, useEffect, useCallback, useRef } from "react"

export interface AsyncResult<T> {
  data: T | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

export function useLiveData<T>(
  fetcher: (signal: AbortSignal) => Promise<{ data: T | null; error: string | null }>,
  deps: unknown[] = [],
  intervalMs = 0,
): AsyncResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchRef = useRef(0)

  const load = useCallback(() => {
    const id = ++fetchRef.current
    setIsLoading(true)

    fetcher(new AbortController().signal).then((result) => {
      if (id !== fetchRef.current) return
      setData(result.data)
      setError(result.error)
      setIsLoading(false)
    }).catch(() => {
      if (id !== fetchRef.current) return
      setIsLoading(false)
    })
  }, deps)

  useEffect(() => {
    load()
    if (intervalMs > 0) {
      const interval = setInterval(load, intervalMs)
      return () => clearInterval(interval)
    }
  }, [load, intervalMs])

  return { data, isLoading, error, refetch: load }
}

export function Skeleton({ className = "", lines = 3 }: { className?: string; lines?: number }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3 bg-white/5 rounded animate-pulse" style={{ width: `${80 - i * 15}%` }} />
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-6 text-center">
      <div className="w-8 h-8 rounded-full bg-red-500/10 flex items-center justify-center mb-2">
        <span className="text-red-400 text-sm">!</span>
      </div>
      <p className="text-xs text-red-400/80 mb-2">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="text-[10px] px-2 py-1 rounded border border-white/10 text-white/40 hover:text-white/60">
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-6">
      <p className="text-xs text-white/20">{message}</p>
    </div>
  )
}

export function DataWidget<T>({ result, children, skeletonLines = 3, emptyMessage = "No data" }: {
  result: AsyncResult<T>
  children: (data: T) => React.ReactNode
  skeletonLines?: number
  emptyMessage?: string
}) {
  if (result.isLoading) return <Skeleton lines={skeletonLines} />
  if (result.error) return <ErrorState message={result.error} onRetry={result.refetch} />
  if (result.data === null || result.data === undefined) return <EmptyState message={emptyMessage} />
  return <>{children(result.data)}</>
}