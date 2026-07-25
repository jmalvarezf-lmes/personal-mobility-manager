import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { logout } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import i18n from "../i18n";
import { useTranslation } from "react-i18next";

export default function Nav() {
  const { user, setUser } = useAuth();
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }

    function handleOutsideClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  async function handleLogout() {
    setMenuOpen(false);
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
    <nav className="relative z-[1100] flex items-center justify-between bg-white px-6 py-3 shadow">
      <span className="text-lg font-semibold text-gray-800">
        {t("nav.title")}
      </span>
      <div className="flex items-center gap-4">
        <Link to="/map" className="text-blue-600 hover:underline">
          {t("nav.map")}
        </Link>
        <Link to="/api-docs" className="text-blue-600 hover:underline">
          {t("nav.apiDocs")}
        </Link>
        {user ? (
          <div ref={menuRef} className="relative">
            <button
              type="button"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
              className="flex items-center gap-1 rounded bg-gray-100 px-3 py-1 text-sm text-gray-700 hover:bg-gray-200"
            >
              {user.email}
              <svg
                aria-hidden="true"
                viewBox="0 0 20 20"
                fill="currentColor"
                className={`h-4 w-4 transition-transform ${menuOpen ? "rotate-180" : ""}`}
              >
                <path
                  fillRule="evenodd"
                  d="M5.23 7.21a.75.75 0 011.06.02L10 11.19l3.71-3.96a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
            {menuOpen && (
              <div
                role="menu"
                aria-label={t("nav.account")}
                className="absolute right-0 z-10 mt-2 w-48 rounded border border-gray-200 bg-white py-1 shadow-lg"
              >
                <Link
                  to="/my-vehicles"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                >
                  {t("nav.myVehicles")}
                </Link>
                <Link
                  to="/preferences"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                >
                  {t("nav.preferences")}
                </Link>
                <Link
                  to="/ser-providers"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                >
                  {t("nav.serProviders")}
                </Link>
                <Link
                  to="/notification-channels"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                >
                  {t("nav.notificationChannels")}
                </Link>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => void handleLogout()}
                  className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
                >
                  {t("nav.logout")}
                </button>
              </div>
            )}
          </div>
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
