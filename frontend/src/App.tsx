import { BrowserRouter, Route, Routes } from "react-router";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import ApiDocsPage from "./pages/ApiDocsPage";
import LandingPage from "./pages/LandingPage";
import MapPage from "./pages/MapPage";
import MyVehiclesPage from "./pages/MyVehiclesPage";
import NotificationChannelsPage from "./pages/NotificationChannelsPage";
import PreferencesPage from "./pages/PreferencesPage";
import SerProvidersPage from "./pages/SerProvidersPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/api-docs" element={<ApiDocsPage />} />
          <Route
            path="/my-vehicles"
            element={
              <ProtectedRoute>
                <MyVehiclesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/preferences"
            element={
              <ProtectedRoute>
                <PreferencesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ser-providers"
            element={
              <ProtectedRoute>
                <SerProvidersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notification-channels"
            element={
              <ProtectedRoute>
                <NotificationChannelsPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
