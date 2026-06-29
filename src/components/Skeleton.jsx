import { cn } from '../lib/utils'

export function Skeleton({ className }) {
  return <div className={cn('rs-skeleton rounded-lg', className)} />
}

// Matches the RouteCard footprint so the grid doesn't jump when data arrives.
export function RouteCardSkeleton() {
  return (
    <div className="rounded-2xl border border-brand-900/10 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <Skeleton className="h-6 w-24 rounded-full" />
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <Skeleton className="mt-3 h-4 w-20" />
      <div className="mt-3 flex items-baseline gap-4">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-4 w-16" />
      </div>
      <Skeleton className="mt-3 h-16 w-full rounded-xl" />
      <Skeleton className="mt-4 h-11 w-full rounded-xl" />
    </div>
  )
}

export function ResultsSkeleton() {
  return (
    <div>
      <Skeleton className="h-4 w-28" />
      <Skeleton className="mt-3 h-7 w-64" />
      <Skeleton className="mt-2 h-4 w-80 max-w-full" />
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <RouteCardSkeleton key={i} />
        ))}
      </div>
    </div>
  )
}

export function RouteDetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl">
      <Skeleton className="h-4 w-32" />
      <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-5">
          <Skeleton className="h-20 w-full rounded-2xl" />
          <Skeleton className="h-44 w-full rounded-2xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
        </div>
        <Skeleton className="hidden h-64 w-full rounded-2xl lg:block" />
      </div>
    </div>
  )
}

export function CompareSkeleton() {
  return (
    <div className="mx-auto max-w-2xl">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="mt-3 h-4 w-20" />
      <Skeleton className="mt-3 h-7 w-72" />
      <Skeleton className="mt-2 h-4 w-80 max-w-full" />
      <div className="mt-5 grid grid-cols-2 gap-3">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="rounded-2xl border border-brand-900/10 bg-white p-4">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="mt-3 h-6 w-20 rounded-full" />
            <Skeleton className="mt-3 h-6 w-24" />
            <Skeleton className="mt-2 h-4 w-16" />
            <Skeleton className="mt-2 h-6 w-20 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function LiveJourneySkeleton() {
  return (
    <div className="mx-auto max-w-2xl">
      <Skeleton className="h-4 w-28" />
      <Skeleton className="mt-3 h-4 w-20" />
      <Skeleton className="mt-3 h-7 w-52" />
      <Skeleton className="mt-2 h-4 w-60" />
      <div className="mt-5 space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-xl" />
        ))}
      </div>
      <Skeleton className="mt-6 h-28 w-full rounded-2xl" />
    </div>
  )
}

export function HubPickerSkeleton() {
  return (
    <div className="mx-auto max-w-2xl">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="mt-3 h-4 w-28" />
      <Skeleton className="mt-3 h-7 w-56" />
      <Skeleton className="mt-2 h-4 w-96 max-w-full" />
      <div className="mt-5 space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-28 w-full rounded-2xl" />
        ))}
      </div>
    </div>
  )
}
