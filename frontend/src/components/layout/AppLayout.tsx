import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import { useLocation, useOutlet } from 'react-router-dom'

import { BottomNav } from './BottomNav'
import { Header } from './Header'
import { MainContent } from './MainContent'
import { Sidebar } from './Sidebar'

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/chat': 'AI Chat',
  '/documents': 'Documents',
  '/settings': 'Settings',
  '/admin': 'Admin Panel',
}

function resolveTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname]
  const topLevel = `/${pathname.split('/')[1] ?? ''}`
  return PAGE_TITLES[topLevel] ?? 'RAG Console'
}

const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
}

export function AppLayout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const location = useLocation()
  // useOutlet() (rather than <Outlet/> directly) hands back a stable element
  // reference that AnimatePresence can keep mounted during its exit
  // animation — <Outlet/> alone swaps instantly on route change, before
  // framer-motion ever gets a chance to animate the outgoing page.
  const outlet = useOutlet()

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white dark:bg-gray-950">
      <Sidebar mobileOpen={mobileNavOpen} onCloseMobile={() => setMobileNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header title={resolveTitle(location.pathname)} onOpenMobileNav={() => setMobileNavOpen(true)} />
        <MainContent className="pb-16 lg:pb-0">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.16, ease: 'easeOut' }}
              className="h-full"
            >
              {outlet}
            </motion.div>
          </AnimatePresence>
        </MainContent>
      </div>
      <BottomNav onOpenMore={() => setMobileNavOpen(true)} />
    </div>
  )
}
