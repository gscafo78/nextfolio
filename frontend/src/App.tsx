import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/context/ThemeContext";
import { PeriodProvider } from "@/context/PeriodContext";
import { MainLayout } from "@/components/layout/MainLayout";
import { PrivateRoute } from "@/components/PrivateRoute";
import { Login } from "@/pages/Login";
import { ForgotPassword } from "@/pages/ForgotPassword";
import { ResetPassword } from "@/pages/ResetPassword";
import { Register } from "@/pages/Register";
import { About } from "@/pages/About";
import { Dashboard } from "@/pages/Dashboard";

// Lazy-loaded pages — split in separate chunks to reduce initial bundle
const Transazioni  = lazy(() => import("@/pages/Transazioni").then((m) => ({ default: m.Transazioni })));
const Performance  = lazy(() => import("@/pages/Performance").then((m) => ({ default: m.Performance })));
const Allocation   = lazy(() => import("@/pages/Allocation").then((m) => ({ default: m.Allocation })));
const Fiscale      = lazy(() => import("@/pages/Fiscale").then((m) => ({ default: m.Fiscale })));
const Alert        = lazy(() => import("@/pages/Alert").then((m) => ({ default: m.Alert })));
const Import       = lazy(() => import("@/pages/Import").then((m) => ({ default: m.Import })));
const Strumenti    = lazy(() => import("@/pages/Strumenti").then((m) => ({ default: m.Strumenti })));
const Dividendi    = lazy(() => import("@/pages/Dividendi").then((m) => ({ default: m.Dividendi })));
const Impostazioni = lazy(() => import("@/pages/Impostazioni").then((m) => ({ default: m.Impostazioni })));
const Admin        = lazy(() => import("@/pages/Admin").then((m) => ({ default: m.Admin })));
const XRay         = lazy(() => import("@/pages/XRay").then((m) => ({ default: m.XRay })));
const WatchlistPage = lazy(() => import("@/pages/Watchlist").then((m) => ({ default: m.Watchlist })));

function PageSkeleton() {
  return (
    <div className="flex-1 p-6 space-y-4 animate-pulse">
      <div className="h-8 bg-gray-100 rounded-lg w-48" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 bg-gray-100 rounded-xl" />
        ))}
      </div>
      <div className="h-64 bg-gray-100 rounded-xl" />
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 1000 * 60, retry: 1 },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route element={<PrivateRoute />}>
            <Route element={<PeriodProvider><MainLayout /></PeriodProvider>}>
              <Route index element={<Dashboard />} />
              <Route path="transazioni"  element={<Suspense fallback={<PageSkeleton />}><Transazioni /></Suspense>} />
              <Route path="performance"  element={<Suspense fallback={<PageSkeleton />}><Performance /></Suspense>} />
              <Route path="allocazione"  element={<Suspense fallback={<PageSkeleton />}><Allocation /></Suspense>} />
              <Route path="fiscale"      element={<Suspense fallback={<PageSkeleton />}><Fiscale /></Suspense>} />
              <Route path="alert"        element={<Suspense fallback={<PageSkeleton />}><Alert /></Suspense>} />
              <Route path="import"       element={<Suspense fallback={<PageSkeleton />}><Import /></Suspense>} />
              <Route path="strumenti"    element={<Suspense fallback={<PageSkeleton />}><Strumenti /></Suspense>} />
              <Route path="dividendi"    element={<Suspense fallback={<PageSkeleton />}><Dividendi /></Suspense>} />
              <Route path="impostazioni" element={<Suspense fallback={<PageSkeleton />}><Impostazioni /></Suspense>} />
              <Route path="admin"        element={<Suspense fallback={<PageSkeleton />}><Admin /></Suspense>} />
              <Route path="xray"         element={<Suspense fallback={<PageSkeleton />}><XRay /></Suspense>} />
              <Route path="watchlist"    element={<Suspense fallback={<PageSkeleton />}><WatchlistPage /></Suspense>} />
              <Route path="about"        element={<About />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
