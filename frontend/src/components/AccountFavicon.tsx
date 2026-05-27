export function faviconUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const { hostname } = new URL(url.startsWith("http") ? url : `https://${url}`);
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=32`;
  } catch {
    return null;
  }
}

export function AccountFavicon({ url, size = 5 }: { url: string | null | undefined; size?: number }) {
  const src = faviconUrl(url);
  if (!src) return null;
  return (
    <img
      src={src}
      alt=""
      className={`w-${size} h-${size} rounded-sm object-contain flex-shrink-0`}
      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
    />
  );
}
