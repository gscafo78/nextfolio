import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import itCommon from "./locales/it/common.json";
import enCommon from "./locales/en/common.json";
import frCommon from "./locales/fr/common.json";
import deCommon from "./locales/de/common.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "it",
    supportedLngs: ["it", "en", "fr", "de"],
    defaultNS: "common",
    detection: {
      order: ["localStorage"],
      lookupLocalStorage: "nf-lang",
      caches: ["localStorage"],
    },
    resources: {
      it: { common: itCommon },
      en: { common: enCommon },
      fr: { common: frCommon },
      de: { common: deCommon },
    },
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
