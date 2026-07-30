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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuOpen && !mobileMenuOpen) {
      return;
    }

    function handleOutsideClick(e: MouseEvent) {
      if (menuOpen && menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
      if (
        mobileMenuOpen &&
        mobileMenuRef.current &&
        !mobileMenuRef.current.contains(e.target as Node) &&
        mobileMenuButtonRef.current &&
        !mobileMenuButtonRef.current.contains(e.target as Node)
      ) {
        setMobileMenuOpen(false);
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setMenuOpen(false);
        setMobileMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen, mobileMenuOpen]);

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
    <nav className="relative z-[1100] bg-white px-4 py-2 shadow sm:px-6 sm:py-3">
      <div className="flex items-center justify-between gap-2">
        <Link
          to="/"
          className="flex shrink-0 items-center gap-2 whitespace-nowrap text-lg font-semibold text-gray-800"
        >
          <img src={logoMark} alt="" className="h-8 w-8" />
          <span className="hidden sm:inline">{t("nav.title")}</span>
        </Link>
        <div className="flex items-center gap-2 sm:gap-4">
          <div className="hidden items-center gap-4 sm:flex">
            <Link to="/map" className="whitespace-nowrap text-blue-600 hover:underline">
              {t("nav.map")}
            </Link>
            <Link to="/api-docs" className="whitespace-nowrap text-blue-600 hover:underline">
              {t("nav.apiDocs")}
            </Link>
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
                <span className="max-w-[110px] truncate sm:max-w-none">{user.email}</span>
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
              <span className="sm:hidden">{t("nav.login")}</span>
              <span className="hidden sm:inline">{t("nav.loginGoogle")}</span>
            </Button>
          )}
          <button
            ref={mobileMenuButtonRef}
            type="button"
            aria-label={t("nav.menu")}
            aria-haspopup="true"
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen((open) => !open)}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-gray-700 hover:bg-gray-100 sm:hidden"
          >
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
              {mobileMenuOpen ? (
                <path
                  fillRule="evenodd"
                  d="M5.28 4.22a.75.75 0 00-1.06 1.06L8.94 10l-4.72 4.72a.75.75 0 101.06 1.06L10 11.06l4.72 4.72a.75.75 0 101.06-1.06L11.06 10l4.72-4.72a.75.75 0 00-1.06-1.06L10 8.94 5.28 4.22z"
                  clipRule="evenodd"
                />
              ) : (
                <path
                  fillRule="evenodd"
                  d="M3 5.75A.75.75 0 013.75 5h12.5a.75.75 0 010 1.5H3.75A.75.75 0 013 5.75zM3 10a.75.75 0 01.75-.75h12.5a.75.75 0 010 1.5H3.75A.75.75 0 013 10zm0 4.25a.75.75 0 01.75-.75h12.5a.75.75 0 010 1.5H3.75a.75.75 0 01-.75-.75z"
                  clipRule="evenodd"
                />
              )}
            </svg>
          </button>
        </div>
      </div>
      {mobileMenuOpen && (
        <div
          ref={mobileMenuRef}
          className="mt-2 flex flex-col gap-3 border-t border-gray-200 pt-3 sm:hidden"
        >
          <Link
            to="/map"
            onClick={() => setMobileMenuOpen(false)}
            className="text-blue-600 hover:underline"
          >
            {t("nav.map")}
          </Link>
          <Link
            to="/api-docs"
            onClick={() => setMobileMenuOpen(false)}
            className="text-blue-600 hover:underline"
          >
            {t("nav.apiDocs")}
          </Link>
          <select
            aria-label={t("nav.language")}
            value={i18n.language.split("-")[0]}
            onChange={handleLanguageChange}
            className="w-fit rounded border border-gray-300 py-1 pl-2 pr-6 text-sm"
          >
            <option value="en">EN</option>
            <option value="es">ES</option>
          </select>
        </div>
      )}
    </nav>
  );
}
