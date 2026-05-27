import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate, Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { authService } from "@/services/auth";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

const credSchema = z.object({
  email: z.string().email("Email non valida"),
  password: z.string().min(1, "Campo obbligatorio"),
});
const totpSchema = z.object({
  code: z.string().length(6, "Il codice è di 6 cifre").regex(/^\d+$/, "Solo cifre"),
});

type CredData = z.infer<typeof credSchema>;
type TotpData = z.infer<typeof totpSchema>;

export function Login() {
  const navigate = useNavigate();
  const [step, setStep] = useState<"credentials" | "totp">("credentials");
  const [sessionToken, setSessionToken] = useState("");

  const credForm = useForm<CredData>({ resolver: zodResolver(credSchema) });
  const totpForm = useForm<TotpData>({ resolver: zodResolver(totpSchema) });

  const loginMutation = useMutation({
    mutationFn: ({ email, password }: CredData) => authService.login(email, password),
    onSuccess: (res) => {
      if (res.requires_2fa && res.session_token) {
        setSessionToken(res.session_token);
        setStep("totp");
      } else {
        authService.saveTokens(res);
        navigate("/");
      }
    },
  });

  const totpMutation = useMutation({
    mutationFn: ({ code }: TotpData) => authService.verify2fa(sessionToken, code),
    onSuccess: (res) => {
      authService.saveTokens(res);
      navigate("/");
    },
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand-600">Nextfolio</h1>
          <p className="mt-2 text-sm text-gray-500">Il tuo portafoglio, tutto sotto controllo</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          {step === "credentials" ? (
            <>
              <h2 className="text-lg font-semibold text-gray-900 mb-6">Accedi</h2>
              <form onSubmit={credForm.handleSubmit((d) => loginMutation.mutate(d))} className="space-y-4">
                <Input
                  label="Email"
                  type="email"
                  autoComplete="email"
                  error={credForm.formState.errors.email?.message}
                  {...credForm.register("email")}
                />
                <Input
                  label="Password"
                  type="password"
                  autoComplete="current-password"
                  error={credForm.formState.errors.password?.message}
                  {...credForm.register("password")}
                />
                {loginMutation.isError && (
                  <p className="text-sm text-red-600 text-center">Credenziali non valide. Riprova.</p>
                )}
                <Button type="submit" loading={loginMutation.isPending} className="w-full">
                  Accedi
                </Button>
                <div className="text-center">
                  <Link to="/forgot-password" className="text-sm text-gray-500 hover:text-brand-600">
                    Password dimenticata?
                  </Link>
                </div>
              </form>
            </>
          ) : (
            <>
              <div className="flex flex-col items-center mb-6 text-center">
                <div className="w-12 h-12 bg-brand-50 rounded-full flex items-center justify-center mb-3">
                  <ShieldCheck className="w-6 h-6 text-brand-600" />
                </div>
                <h2 className="text-lg font-semibold text-gray-900">Verifica in due passaggi</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Inserisci il codice dalla tua app di autenticazione
                </p>
              </div>
              <form onSubmit={totpForm.handleSubmit((d) => totpMutation.mutate(d))} className="space-y-4">
                <Input
                  label="Codice 6 cifre"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="000000"
                  maxLength={6}
                  error={totpForm.formState.errors.code?.message}
                  {...totpForm.register("code")}
                />
                {totpMutation.isError && (
                  <p className="text-sm text-red-600 text-center">Codice non valido. Riprova.</p>
                )}
                <Button type="submit" loading={totpMutation.isPending} className="w-full">
                  Verifica
                </Button>
                <button
                  type="button"
                  onClick={() => setStep("credentials")}
                  className="w-full text-sm text-gray-500 hover:text-gray-700"
                >
                  ← Torna al login
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
