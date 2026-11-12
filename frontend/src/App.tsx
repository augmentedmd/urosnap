import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConnectionGate } from '@/components/ConnectionGate'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { NewSession } from '@/pages/NewSession'
import { Recording } from '@/pages/Recording'
import { Gallery } from '@/pages/Gallery'
import { ReportPage } from '@/pages/Report'
import { Sessions } from '@/pages/Sessions'
import { SettingsPage } from '@/pages/Settings'
import { Remote } from '@/pages/Remote'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/remote/:token" element={<Remote />} />
          <Route
            element={
              <ConnectionGate>
                <Layout />
              </ConnectionGate>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/sessions/new" element={<NewSession />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/sessions/:sessionId/record" element={<Recording />} />
            <Route path="/sessions/:sessionId/gallery" element={<Gallery />} />
            <Route path="/sessions/:sessionId/report" element={<ReportPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
