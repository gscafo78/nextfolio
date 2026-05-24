import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MainLayout } from "@/components/layout/MainLayout";
import { PrivateRoute } from "@/components/PrivateRoute";
import { Login } from "@/pages/Login";
import { Dashboard } from "@/pages/Dashboard";
import { Transazioni } from "@/pages/Transazioni";
import { Impostazioni } from "@/pages/Impostazioni";
import { Performance } from "@/pages/Performance";
import { Admin } from "@/pages/Admin";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 1000 * 60, retry: 1 },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<PrivateRoute />}>
            <Route element={<MainLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="transazioni" element={<Transazioni />} />
              <Route path="performance" element={<Performance />} />
              <Route path="fiscale" element={<div>Fiscale — prossimamente</div>} />
              <Route path="alert" element={<div>Alert — prossimamente</div>} />
              <Route path="impostazioni" element={<Impostazioni />} />
              <Route path="admin" element={<Admin />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
