import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Footer from "./components/Footer";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import ToastContainer from "./components/Toast";
import Dashboard from "./pages/Dashboard";
import Analyzer from "./pages/Analyzer";
import ImprovementTracking from "./pages/ImprovementTracking";
import MyStudents from "./pages/MyStudents";
import ProposalImprovement from "./pages/ProposalImprovement";
import SupervisorAnalytics from "./pages/SupervisorAnalytics";
import History from "./pages/History";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import SupervisorWorkspace from "./pages/SupervisorWorkspace";
import {
  checkBackendStatus,
  devLoginSupervisor,
  getCurrentSupervisor,
  getAnalysisHistory,
  getGradingAnalytics,
  getGradingHistory,
  getKnowledgeGraphHistory,
  getSupervisorAnalytics,
  loginSupervisor,
  logoutSupervisor,
  registerSupervisor,
} from "./api";

const TEMP_DEV_LOGIN_BYPASS = true;
const REQUIRE_AUTH = import.meta.env.VITE_REQUIRE_AUTH === "true";

export default function App() {
  const location = useLocation();
  const [backendOnline, setBackendOnline] = useState(false);
  const [backendChecked, setBackendChecked] = useState(false);
  const [backendChecking, setBackendChecking] = useState(true);
  const [analytics, setAnalytics] = useState(null);
  const [history, setHistory] = useState([]);
  const [graphHistory, setGraphHistory] = useState([]);
  const [gradingAnalytics, setGradingAnalytics] = useState(null);
  const [gradingHistory, setGradingHistory] = useState([]);
  const [currentSupervisor, setCurrentSupervisor] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);
  const [loadingData, setLoadingData] = useState(true);
  const [toasts, setToasts] = useState([]);

  const dismissToast = useCallback((id) => {
    setToasts((items) => items.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback((message, type = "info") => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [...items, { id, message, type }].slice(-4));
    window.setTimeout(() => dismissToast(id), 4200);
  }, [dismissToast]);

  const refreshData = useCallback(async () => {
    setLoadingData(true);
    setBackendChecking(true);
    const online = await checkBackendStatus();
    setBackendOnline(online);
    setBackendChecked(true);
    setBackendChecking(false);

    if (!online) {
      setCurrentSupervisor(null);
      setAuthChecked(true);
      setAuthLoading(false);
      setLoadingData(false);
      notify("Backend Offline. Please start the FastAPI server.", "error");
      return;
    }

    try {
      if (REQUIRE_AUTH) {
        try {
          const supervisor = await getCurrentSupervisor();
          setCurrentSupervisor(supervisor);
        } catch {
          setCurrentSupervisor(null);
        } finally {
          setAuthChecked(true);
          setAuthLoading(false);
        }
      } else {
        setCurrentSupervisor(null);
        setAuthChecked(true);
        setAuthLoading(false);
      }
      const [analyticsPayload, historyPayload, graphPayload, gradingAnalyticsPayload, gradingHistoryPayload] = await Promise.all([
        getSupervisorAnalytics(),
        getAnalysisHistory(),
        getKnowledgeGraphHistory(),
        getGradingAnalytics(),
        getGradingHistory(),
      ]);
      setAnalytics(analyticsPayload);
      setHistory(historyPayload.items || []);
      setGraphHistory(graphPayload.items || []);
      setGradingAnalytics(gradingAnalyticsPayload);
      setGradingHistory(gradingHistoryPayload.items || []);
    } catch (error) {
      console.error("Dashboard data refresh failed", error);
      notify("Could not refresh dashboard data. Please retry the connection.", "error");
    } finally {
      setLoadingData(false);
    }
  }, [notify]);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  const handleLogin = useCallback(async (credentials) => {
    const supervisor = await loginSupervisor(credentials);
    setCurrentSupervisor(supervisor);
    setAuthChecked(true);
    setAuthLoading(false);
    await refreshData();
  }, [refreshData]);

  const handleDevLogin = useCallback(async () => {
    await devLoginSupervisor();
    const supervisor = await getCurrentSupervisor();
    setCurrentSupervisor(supervisor);
    setAuthChecked(true);
    setAuthLoading(false);
    await refreshData();
    return supervisor;
  }, [refreshData]);

  const handleRegister = useCallback(async (credentials) => {
    await registerSupervisor(credentials);
    const supervisor = await getCurrentSupervisor();
    setAuthChecked(true);
    setAuthLoading(false);
    setCurrentSupervisor(supervisor);
    refreshData();
    return supervisor;
  }, [refreshData]);

  const handleLogout = useCallback(async () => {
    try {
      await logoutSupervisor();
    } finally {
      setCurrentSupervisor(null);
      setAuthChecked(true);
      setAuthLoading(false);
    }
  }, []);

  const shellContext = useMemo(
    () => ({
      analytics,
      history,
      graphHistory,
      gradingAnalytics,
      gradingHistory,
      backendOnline,
      backendChecked,
      backendChecking,
      currentSupervisor,
      requireAuth: REQUIRE_AUTH,
      loadingData,
      refreshData,
      notify,
    }),
    [analytics, history, graphHistory, gradingAnalytics, gradingHistory, backendOnline, backendChecked, backendChecking, currentSupervisor, loadingData, refreshData, notify],
  );

  if (REQUIRE_AUTH && (authLoading || !authChecked)) {
    return (
      <main className="login-page">
        <section className="loader-card">Loading supervisor session...</section>
      </main>
    );
  }

  const publicAuthRoute = location.pathname === "/login" || location.pathname === "/signup";

  if (REQUIRE_AUTH && !currentSupervisor && !publicAuthRoute) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-shell">
      <Sidebar currentSupervisor={currentSupervisor} onLogout={currentSupervisor ? handleLogout : null} />
      <main className="workspace">
        <Topbar
          currentSupervisor={currentSupervisor}
          onLogout={currentSupervisor ? handleLogout : null}
          onRetry={refreshData}
        />
        <div className="page-container">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard {...shellContext} />} />
            <Route path="/students" element={<MyStudents {...shellContext} />} />
            <Route path="/students/:studentId/analyze" element={<Analyzer {...shellContext} />} />
            <Route path="/students/:studentId/proposals/:proposalId/improvement" element={<ProposalImprovement {...shellContext} />} />
            <Route path="/students/:studentId/proposal" element={<SupervisorWorkspace {...shellContext} />} />
            <Route
              path="/login"
              element={(
                <Login
                  authenticated={Boolean(currentSupervisor)}
                  backendOnline={backendOnline}
                  backendChecked={backendChecked}
                  tempDevLoginBypass={TEMP_DEV_LOGIN_BYPASS}
                  onDevLogin={handleDevLogin}
                  onLogin={handleLogin}
                />
              )}
            />
            <Route
              path="/signup"
              element={(
                <Signup
                  authenticated={Boolean(currentSupervisor)}
                  backendOnline={backendOnline}
                  backendChecked={backendChecked}
                  onRegister={handleRegister}
                />
              )}
            />
            <Route path="/analyzer" element={<Analyzer {...shellContext} />} />
            <Route path="/workspace" element={<SupervisorWorkspace {...shellContext} />} />
            <Route path="/tracking" element={<ImprovementTracking {...shellContext} />} />
            <Route path="/analytics" element={<SupervisorAnalytics {...shellContext} />} />
            <Route path="/history" element={<History {...shellContext} />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </div>
        <Footer />
      </main>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
