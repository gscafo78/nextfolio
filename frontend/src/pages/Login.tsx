import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate, Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ShieldCheck, TrendingUp, BarChart2, Shield, ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
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

const FEATURES = [
  { Icon: BarChart2, label: "P&L e performance in tempo reale" },
  { Icon: TrendingUp, label: "Analisi del rischio e benchmark" },
  { Icon: Shield, label: "Dati cifrati end-to-end" },
];

const TICKERS = [
  { name: "MSCI World", change: "+22.4%", pos: true },
  { name: "S&P 500",    change: "+28.1%", pos: true },
  { name: "BTP 10Y",    change: "-1.8%",  pos: false },
  { name: "Oro",        change: "+8.3%",  pos: true },
];

function PortfolioChart() {
  return (
    <svg viewBox="0 0 560 200" preserveAspectRatio="none" className="w-full h-full">
      <defs>
        <linearGradient id="lgArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#3b82f6" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="lgLine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"   stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#10b981" />
        </linearGradient>
      </defs>

      {/* Grid lines */}
      {[40, 80, 120, 160].map((y) => (
        <line key={y} x1="0" y1={y} x2="560" y2={y} stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
      ))}

      {/* Area fill */}
      <path
        d="M0,182 C50,175 80,170 110,162 C140,154 165,158 195,148
           C225,138 245,143 275,128 C305,113 325,118 355,102
           C385,86 408,94 435,76 C462,58 482,64 510,48
           C528,37 544,40 560,30
           L560,200 L0,200 Z"
        fill="url(#lgArea)"
      />

      {/* Invested baseline (dashed) */}
      <path
        d="M0,194 C120,187 240,178 360,168 C440,161 510,155 560,150"
        stroke="rgba(255,255,255,0.18)"
        strokeWidth="1.5"
        strokeDasharray="5 4"
        fill="none"
      />

      {/* Main portfolio line */}
      <path
        d="M0,182 C50,175 80,170 110,162 C140,154 165,158 195,148
           C225,138 245,143 275,128 C305,113 325,118 355,102
           C385,86 408,94 435,76 C462,58 482,64 510,48
           C528,37 544,40 560,30"
        stroke="url(#lgLine)"
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
      />

      {/* Data dots */}
      {[[110,162],[195,148],[275,128],[355,102],[435,76],[510,48],[560,30]].map(([cx, cy], i) => (
        <circle key={i} cx={cx} cy={cy} r="3" fill="#10b981" opacity={i === 6 ? "1" : "0.55"} />
      ))}

      {/* Glowing end dot */}
      <circle cx="560" cy="30" r="6" fill="#10b981" opacity="0.2" />
      <circle cx="560" cy="30" r="3" fill="#10b981" />
    </svg>
  );
}

export function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState<"credentials" | "totp">("credentials");
  const [sessionToken, setSessionToken] = useState("");

  const credForm = useForm<CredData>({ resolver: zodResolver(credSchema) });
  const totpForm = useForm<TotpData>({ resolver: zodResolver(totpSchema) });

  const { data: regStatus } = useQuery({
    queryKey: ["registration-status"],
    queryFn: authService.getRegistrationStatus,
    staleTime: 1000 * 60 * 5,
  });

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
    <div className="min-h-screen flex">

      {/* ── Left brand panel ──────────────────────────────────── */}
      <div
        className="hidden lg:flex flex-col w-[500px] xl:w-[560px] relative overflow-hidden flex-shrink-0"
        style={{ background: "linear-gradient(160deg, #05101f 0%, #0b1a30 60%, #061525 100%)" }}
      >
        {/* Dot-grid texture */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.055) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />

        {/* Glow orbs */}
        <div className="absolute top-1/4 left-1/4 w-80 h-80 rounded-full bg-blue-600/15 blur-[90px] pointer-events-none" />
        <div className="absolute bottom-1/3 right-0 w-72 h-72 rounded-full bg-emerald-500/8 blur-[70px] pointer-events-none" />
        <div className="absolute top-10 right-20 w-40 h-40 rounded-full bg-blue-400/8 blur-[50px] pointer-events-none" />

        {/* ── Logo ── */}
        <div className="relative z-10 p-10 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-900/60">
              <TrendingUp className="w-[18px] h-[18px] text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">
              Next<span className="text-emerald-400">folio</span>
            </span>
          </div>
        </div>

        {/* ── Main content ── */}
        <div className="relative z-10 px-10 flex-1 flex flex-col justify-end pb-60">

          {/* Portfolio value card */}
          <div className="mb-8 w-fit bg-white/5 border border-white/10 rounded-2xl px-5 py-4 backdrop-blur-sm shadow-xl">
            <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-0.5">
              Portafoglio totale
            </div>
            <div className="text-2xl font-bold text-white tabular-nums">€ 142.830</div>
            <div className="flex items-center gap-1.5 mt-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-semibold text-emerald-400">+18.4% anno corrente</span>
            </div>
          </div>

          <h1 className="text-[42px] xl:text-5xl font-extrabold text-white leading-[1.08] mb-4">
            Il tuo patrimonio,<br />
            <span className="bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
              sempre sotto controllo.
            </span>
          </h1>

          <p className="text-slate-400 text-sm leading-relaxed mb-8 max-w-sm">
            Dashboard professionale per tracciare, analizzare e ottimizzare
            ogni investimento in tempo reale.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2 mb-8">
            {FEATURES.map(({ Icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-3 py-1.5 text-[11px] text-slate-300"
              >
                <Icon className="w-3 h-3 text-blue-400 flex-shrink-0" />
                {label}
              </div>
            ))}
          </div>

          {/* Ticker strip */}
          <div className="flex gap-6 pt-5 border-t border-white/8">
            {TICKERS.map((tk) => (
              <div key={tk.name}>
                <div className="text-[9px] text-slate-600 uppercase tracking-wider">{tk.name}</div>
                <div className={`text-xs font-bold mt-0.5 ${tk.pos ? "text-emerald-400" : "text-red-400"}`}>
                  {tk.change}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Chart decoration at bottom */}
        <div className="absolute bottom-0 left-0 right-0 h-56 z-0 opacity-55">
          <PortfolioChart />
        </div>
      </div>

      {/* ── Right form panel ──────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center bg-white px-8 py-12 min-h-screen">
        <div className="w-full max-w-[360px]">

          {/* Mobile-only logo */}
          <div className="lg:hidden flex flex-col items-center mb-10">
            <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center mb-3 shadow-lg shadow-blue-200">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">
              Next<span className="text-emerald-500">folio</span>
            </span>
            <p className="text-sm text-gray-400 mt-1">{t("auth.mobileTagline")}</p>
          </div>

          {step === "credentials" ? (
            <>
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900">{t("auth.welcome")}</h2>
                <p className="text-sm text-gray-400 mt-1">{t("auth.signInDesc")}</p>
              </div>

              <form
                onSubmit={credForm.handleSubmit((d) => loginMutation.mutate(d))}
                className="space-y-4"
              >
                <Input
                  label={t("auth.email")}
                  type="email"
                  autoComplete="email"
                  error={credForm.formState.errors.email?.message}
                  {...credForm.register("email")}
                />
                <Input
                  label={t("auth.password")}
                  type="password"
                  autoComplete="current-password"
                  error={credForm.formState.errors.password?.message}
                  {...credForm.register("password")}
                />

                {loginMutation.isError && (
                  <div className="text-sm text-red-600 text-center bg-red-50 border border-red-100 rounded-xl py-2.5 px-4">
                    {t("auth.invalidCredentials")}
                  </div>
                )}

                <Button
                  type="submit"
                  loading={loginMutation.isPending}
                  className="w-full !py-3 !text-base gap-2"
                >
                  {t("auth.signIn")}
                  {!loginMutation.isPending && <ArrowRight className="w-4 h-4" />}
                </Button>

                <div className="text-center pt-1 space-y-2">
                  <div>
                    <Link
                      to="/forgot-password"
                      className="text-sm text-gray-400 hover:text-blue-600 transition-colors"
                    >
                      {t("auth.forgotPassword")}
                    </Link>
                  </div>
                  {regStatus?.allow_public_registration && (
                    <div>
                      <span className="text-sm text-gray-400">{t("auth.noAccount")} </span>
                      <Link
                        to="/register"
                        className="text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors"
                      >
                        {t("auth.createAccount")}
                      </Link>
                    </div>
                  )}
                </div>
              </form>
            </>
          ) : (
            <>
              <div className="flex flex-col items-center mb-8 text-center">
                <div className="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center mb-4">
                  <ShieldCheck className="w-7 h-7 text-blue-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900">{t("auth.twoFactorTitle")}</h2>
                <p className="text-sm text-gray-400 mt-1">
                  {t("auth.twoFactorDesc")}
                </p>
              </div>

              <form
                onSubmit={totpForm.handleSubmit((d) => totpMutation.mutate(d))}
                className="space-y-4"
              >
                <Input
                  label={t("auth.codeLabel")}
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="000000"
                  maxLength={6}
                  error={totpForm.formState.errors.code?.message}
                  {...totpForm.register("code")}
                />

                {totpMutation.isError && (
                  <div className="text-sm text-red-600 text-center bg-red-50 border border-red-100 rounded-xl py-2.5 px-4">
                    {t("auth.invalidCode")}
                  </div>
                )}

                <Button
                  type="submit"
                  loading={totpMutation.isPending}
                  className="w-full !py-3 !text-base"
                >
                  {t("auth.verify")}
                </Button>

                <button
                  type="button"
                  onClick={() => setStep("credentials")}
                  className="w-full text-sm text-gray-400 hover:text-gray-600 transition-colors py-2"
                >
                  ← {t("auth.backToLogin")}
                </button>
              </form>
            </>
          )}

          {/* Footer */}
          <p className="text-center text-xs text-gray-300 mt-12">
            {t("auth.copyright", { year: new Date().getFullYear() })}
          </p>
        </div>
      </div>
    </div>
  );
}
