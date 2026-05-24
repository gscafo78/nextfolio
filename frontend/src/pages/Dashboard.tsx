import { TopBar } from "@/components/layout/TopBar";
import { useAuth } from "@/hooks/useAuth";

export function Dashboard() {
  const { user } = useAuth();

  return (
    <>
      <TopBar title="Dashboard" />
      <main className="flex-1 p-6">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            Benvenuto, {user?.name} 👋
          </h2>
          <p className="text-gray-500 mt-1">Ecco il riepilogo del tuo portafoglio</p>
        </div>

        {/* Placeholder cards — saranno popolate nella Fase 4 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {[
            { label: "Valore portafoglio", value: "€ —" },
            { label: "P&L totale", value: "— %" },
            { label: "Variazione oggi", value: "€ —" },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-5">
              <p className="text-sm text-gray-500">{label}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
            </div>
          ))}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
          <p className="text-sm">I grafici saranno disponibili dopo aver aggiunto le prime transazioni.</p>
        </div>
      </main>
    </>
  );
}
