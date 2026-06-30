import { useEffect } from 'react'
import { X, Share2, Link2 } from 'lucide-react'
import { motion, AnimatePresence } from 'motion/react'
import ShareJourneyCard from './ShareJourneyCard'
import { useToastStore } from '../store/useToastStore'

export default function ShareModal({ route, open, onClose }) {
  const toast = useToastStore((s) => s.toast)

  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!route) return null

  const shareText = `Check out this RouteSarthi journey: ${route.legs[0]?.from} → ${
    route.legs[route.legs.length - 1]?.to
  }, ${route.confirmation === 'confirmed' ? 'confirmed' : 'planned'} for ${route.totalFareInr ? `₹${route.totalFareInr}` : 'the trip'}.`
  const shareUrl = typeof window !== 'undefined' ? window.location.href : ''

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: 'RouteSarthi journey', text: shareText, url: shareUrl })
      } catch {
        /* user cancelled the native share sheet — no-op */
      }
      return
    }
    await handleCopy()
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(`${shareText} ${shareUrl}`)
      toast({ message: 'Link copied — paste it anywhere', tone: 'success' })
    } catch {
      toast({ message: "Couldn't copy — try sharing instead", tone: 'info' })
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-40 flex items-center justify-center bg-content/40 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="w-full max-w-sm"
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 320, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-white">Share this journey</p>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="flex h-8 w-8 items-center justify-center rounded-full text-white/70 transition hover:bg-white/10 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <ShareJourneyCard route={route} />

            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={handleShare}
                className="flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary-hover"
              >
                <Share2 className="h-4 w-4" />
                Share
              </button>
              <button
                type="button"
                onClick={handleCopy}
                className="flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                <Link2 className="h-4 w-4" />
                Copy link
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
