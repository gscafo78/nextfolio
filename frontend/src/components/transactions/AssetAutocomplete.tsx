import { useEffect, useRef, useState } from "react";
import { assetService, type Asset } from "@/services/transactions";

interface AssetAutocompleteProps {
  onSelect: (asset: Asset) => void;
  placeholder?: string;
}

export function AssetAutocomplete({ onSelect, placeholder = "Cerca per nome, ticker o ISIN..." }: AssetAutocompleteProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Asset[]>([]);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Asset | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      return;
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        setResults(await assetService.search(query));
        setOpen(true);
      } catch {
        setResults([]);
      }
    }, 300);
  }, [query]);

  const choose = (asset: Asset) => {
    setSelected(asset);
    setQuery(asset.symbol);
    setOpen(false);
    onSelect(asset);
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={selected ? `${selected.symbol} — ${selected.name}` : query}
        onChange={(e) => {
          setSelected(null);
          setQuery(e.target.value);
        }}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
      />
      {open && results.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
          {results.map((a) => (
            <li
              key={a.id}
              onClick={() => choose(a)}
              className="px-3 py-2 hover:bg-gray-50 cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-sm text-gray-900">{a.symbol}</span>
                <span className="text-xs text-gray-400">{a.isin ?? a.exchange}</span>
              </div>
              <div className="text-xs text-gray-500 truncate">{a.name}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
