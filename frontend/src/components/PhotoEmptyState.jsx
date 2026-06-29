// A premium empty-state panel: full photographic background with an indigo
// brand overlay and centered white content. Keeps the same tinted-photo
// aesthetic as the Search hero so empty screens still feel intentional.
export default function PhotoEmptyState({ image, icon: Icon, title, text, children }) {
  return (
    <div className="relative mx-auto max-w-md overflow-hidden rounded-3xl">
      <img src={image} alt="" className="absolute inset-0 h-full w-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-t from-brand-900/95 via-brand-900/80 to-brand-900/55" />
      <div className="relative flex flex-col items-center px-6 py-16 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white/15 backdrop-blur-sm ring-1 ring-white/20">
          <Icon className="h-6 w-6 text-white" />
        </span>
        <h1 className="mt-4 font-display text-xl font-bold text-white">{title}</h1>
        <p className="mt-2 max-w-xs text-sm text-white/75">{text}</p>
        {children && <div className="mt-6">{children}</div>}
      </div>
    </div>
  )
}
