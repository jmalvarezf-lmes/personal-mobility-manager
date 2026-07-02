import { Link } from "react-router-dom";
import { logout } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import i18n from "../i18n";
import { useTranslation } from "react-i18next";

export default function Nav() {
  const { user, setUser } = useAuth();
  const { t } = useTranslation();

  async function handleLogout() {
    try {
      await logout();
      setUser(null);
    } catch {
      setUser(null);
    }
  }

  function handleLanguageChange(e: React.ChangeEvent<HTMLSelectElement>) {
    void i18n.changeLanguage(e.target.value);
  }

  return (
    <nav className="flex items-center justify-between bg-white px-6 py-3 shadow">
      <span className="text-lg font-semibold text-gray-800">
        {t("nav.title")}
      </span>
      <div className="flex items-center gap-4">
        <Link to="/map" className="text-blue-600 hover:underline">
          {t("nav.map")}
        </Link>
        {user && (
          <Link to="/my-vehicles" className="text-blue-600 hover:underline">
            {t("nav.myVehicles")}
          </Link>
        )}
        {user ? (
          <>
            <span className="text-sm text-gray-600">{user.email}</span>
            <button
              onClick={() => void handleLogout()}
              className="rounded bg-gray-100 px-3 py-1 text-sm hover:bg-gray-200"
            >
              {t("nav.logout")}
            </button>
          </>
        ) : (
          <a
            href="/api/auth/google/login"
            className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
          >
            {t("nav.loginGoogle")}
          </a>
        )}
        <select
          aria-label={t("nav.language")}
          value={i18n.language.split("-")[0]}
          onChange={handleLanguageChange}
          className="rounded border border-gray-300 px-2 py-1 text-sm text-gray-700"
        >
          <option value="en">EN</option>
          <option value="es">ES</option>
        </select>
      </div>
    </nav>
  );
}
