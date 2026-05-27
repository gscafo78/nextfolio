import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/context/ThemeContext";
import { MainLayout } from "@/components/layout/MainLayout";
import { PrivateRoute } from "@/components/PrivateRoute";
import { Login } from "@/pages/Login";
import { ForgotPassword } from "@/pages/ForgotPassword";
import { ResetPassword } from "@/pages/ResetPassword";
import { Dashboard } from "@/pages/Dashboard";
import { Transazioni } from "@/pages/Transazioni";
import { Impostazioni } from "@/pages/Impostazioni";
import { Performance } from "@/pages/Performance";
import { Admin } from "@/pages/Admin";
import { Fiscale } from "@/pages/Fiscale";
import { Alert } from "@/pages/Alert";
import { Import } from "@/pages/Import";
import { Allocation } from "@/pages/Allocation";
import { Strumenti } from "@/pages/Strumenti";
import { Dividendi } from "@/pages/Dividendi";

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
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route element={<PrivateRoute />}>
            <Route element={<MainLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="transazioni" element={<Transazioni />} />
              <Route path="performance" element={<Performance />} />
              <Route path="allocazione" element={<Allocation />} />
              <Route path="fiscale" element={<Fiscale />} />
              <Route path="alert" element={<Alert />} />
              <Route path="import" element={<Import />} />
              <Route path="strumenti" element={<Strumenti />} />
              <Route path="dividendi" element={<Dividendi />} />
              <Route path="impostazioni" element={<Impostazioni />} />
              <Route path="admin" element={<Admin />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
