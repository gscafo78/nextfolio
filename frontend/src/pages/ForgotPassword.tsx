import { useState } from "react";
import { Link } from "react-router-dom";
import { authService } from "@/services/auth";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await authService.forgotPassword(email);
      setSent(true);
    } catch {
      setError("Errore nell'invio. Riprova tra qualche istante.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">
            Next<span className="text-brand-600">Folio</span>
          </h1>
          <p className="text-sm text-gray-500 mt-1">Reimposta la password</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          {sent ? (
            <div className="text-center space-y-3">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="text-sm font-medium text-gray-900">Email inviata!</p>
              <p className="text-sm text-gray-500">
                Se <strong>{email}</strong> è registrata, riceverai un link per reimpostare la password. Controlla anche la cartella spam.
              </p>
              <Link to="/login" className="block mt-4 text-sm text-brand-600 hover:underline">
                Torna al login
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <p className="text-sm text-gray-500 mb-4">
                Inserisci la tua email e ti invieremo un link per scegliere una nuova password.
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@esempio.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
              >
                {loading ? "Invio in corso..." : "Invia link di reset"}
              </button>
              <Link to="/login" className="block text-center text-sm text-gray-500 hover:text-gray-700">
                Torna al login
              </Link>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
