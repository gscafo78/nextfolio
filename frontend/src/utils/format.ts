import type { Locale } from "date-fns";
import { it, enUS, fr, de } from "date-fns/locale";

const INTL_LOCALE_MAP: Record<string, string> = {
  it: "it-IT",
  en: "en-US",
  fr: "fr-FR",
  de: "de-DE",
};

const DATE_FNS_LOCALE_MAP: Record<string, Locale> = {
  it,
  en: enUS,
  fr,
  de,
};

/** Returns the Intl locale string (e.g. "it-IT") for the given i18n language code. */
export function getIntlLocale(lang: string): string {
  return INTL_LOCALE_MAP[lang] ?? "it-IT";
}

/** Returns the date-fns Locale object for the given i18n language code. */
export function getDateFnsLocale(lang: string): Locale {
  return DATE_FNS_LOCALE_MAP[lang] ?? it;
}

/** Formats a number using the given Intl locale. */
export function fmtNum(
  v: number,
  options: Intl.NumberFormatOptions = {},
  intlLocale = "it-IT"
): string {
  return v.toLocaleString(intlLocale, options);
}
