import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { logout } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import i18n from "../i18n";
import { useTranslation } from "react-i18next";
import Button from "./ui/Button";
import logoMark from "../assets/logo-mark.png";

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
      <Link
        to="/"
        className="flex shrink-0 items-center gap-2 whitespace-nowrap text-lg font-semibold text-gray-800"
      >
        <img src={logoMark} alt="" className="h-8 w-8" />
        {t("nav.title")}
      </Link>
      <div className="flex items-center gap-4">
        <Link to="/map" className="whitespace-nowrap text-blue-600 hover:underline">
          {t("nav.map")}
        </Link>
        <Link to="/api-docs" className="whitespace-nowrap text-blue-600 hover:underline">
          {t("nav.apiDocs")}
        </Link>
        {user ? (
          <div ref={menuRef} className="relative">
            <Button
              variant="secondary"
              size="sm"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
              className="gap-1"
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
            </Button>
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
          <Button as="a" href="/api/auth/google/login" variant="primary" size="sm">
            {t("nav.loginGoogle")}
          </Button>
        )}
        <select
          aria-label={t("nav.language")}
          value={i18n.language.split("-")[0]}
          onChange={handleLanguageChange}
          className="rounded border border-gray-300 py-1 pl-2 pr-6 text-sm"
        >
          <option value="en">EN</option>
          <option value="es">ES</option>
        </select>
      </div>
    </nav>
  );
}
