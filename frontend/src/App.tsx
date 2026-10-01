import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router";
import { makeQueryClient } from "./api/queryClient";
import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { LoginPage } from "./pages/LoginPage";

// Pages load on first visit, so the login screen doesn't wait for the chart library.
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ScorePage = lazy(() => import("./pages/ScorePage"));
const TransactionsPage = lazy(() => import("./pages/TransactionsPage"));
const TransactionDetailPage = lazy(() => import("./pages/TransactionDetailPage"));
const ReviewsPage = lazy(() => import("./pages/ReviewsPage"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const ModelsPage = lazy(() => import("./pages/ModelsPage"));
const IngestionPage = lazy(() => import("./pages/IngestionPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

export function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route
            path="score"
            element={
              <RequireAuth roles={["analyst", "admin"]}>
                <ScorePage />
              </RequireAuth>
            }
          />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="transactions/:transactionId" element={<TransactionDetailPage />} />
          <Route path="reviews" element={<ReviewsPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="ingestion" element={<IngestionPage />} />
          <Route
            path="admin"
            element={
              <RequireAuth roles={["approver", "admin"]}>
                <AdminPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export function App() {
  const [queryClient] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
