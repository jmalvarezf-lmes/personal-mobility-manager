import { Link } from "react-router-dom";
import { logout } from "../api/auth";
import { useAuth } from "../context/AuthContext";

export default function Nav() {
  const { user, setUser } = useAuth();

  async function handleLogout() {
    try {
      await logout();
      setUser(null);
    } catch {
      // Ignore logout errors — clear state anyway
      setUser(null);
    }
  }

  return (
    <nav className="flex items-center justify-between bg-white px-6 py-3 shadow">
      <span className="text-lg font-semibold text-gray-800">
        Personal Mobility Manager
      </span>
      <div className="flex items-center gap-4">
        <Link to="/map" className="text-blue-600 hover:underline">
          Map
        </Link>
        {user && (
          <Link to="/my-vehicles" className="text-blue-600 hover:underline">
            My Vehicles
          </Link>
        )}
        {user ? (
          <>
            <span className="text-sm text-gray-600">{user.email}</span>
            <button
              onClick={() => void handleLogout()}
              className="rounded bg-gray-100 px-3 py-1 text-sm hover:bg-gray-200"
            >
              Logout
            </button>
          </>
        ) : (
          <a
            href="/api/auth/google/login"
            className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
          >
            Login with Google
          </a>
        )}
      </div>
    </nav>
  );
}
