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
    <nav className="flex items-center justify-between bg-white px-6 py-3 shadow">
      <span className="text-lg font-semibold text-gray-800">
        {t("nav.title")}
      </span>
      <div className="flex items-center gap-4">
        <Link to="/map" className="text-blue-600 hover:underline">
          {t("nav.map")}
        </Link>
        {user ? (
          <div ref={menuRef} className="relative">
            <button
              type="button"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
              className="rounded bg-gray-100 px-3 py-1 text-sm text-gray-700 hover:bg-gray-200"
            >
              {user.email}
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
