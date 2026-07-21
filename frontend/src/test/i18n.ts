import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enTranslation from "../../public/locales/en/translation.json";

/**
 * Dedicated i18next instance for unit/component tests.
 *
 * Unlike `src/i18n.ts` (production), this instance never uses
 * `i18next-http-backend` — it loads the real `en/translation.json` resource
 * bundle directly at import time, so component tests render the real
 * English strings with no network request and no dev server dependency.
 */
const testI18n = i18n.createInstance();

void testI18n.use(initReactI18next).init({
  lng: "en",
  fallbackLng: "en",
  supportedLngs: ["en"],
  resources: {
    en: {
      translation: enTranslation,
    },
  },
  interpolation: {
    escapeValue: false,
  },
});

export default testI18n;
