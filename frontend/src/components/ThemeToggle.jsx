import { Moon, Sun } from 'lucide-react'
import { useThemeStore } from '../store/useThemeStore'

export default function ThemeToggle({ tone = 'light' }) {
  const theme = useThemeStore((s) => s.theme)
  const toggle = useThemeStore((s) => s.toggle)
  const isDark = theme === 'dark'

  const toneClass =
    tone === 'dark'
      ? 'text-white/80 hover:text-white hover:bg-white/10'
      : 'text-muted hover:text-content hover:bg-sunken'

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={`flex h-9 w-9 items-center justify-center rounded-full transition ${toneClass}`}
    >
      {isDark ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
    </button>
  )
}
