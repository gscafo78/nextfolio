import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate, Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { MailCheck, TrendingUp, BarChart2, Shield, ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { authService } from "@/services/auth";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

const registerSchema = z
  .object({
    name: z.string().min(1, "Campo obbligatorio"),
    email: z.string().email("Email non valida"),
    password: z.string().min(8, "Minimo 8 caratteri"),
    confirmPassword: z.string().min(1, "Campo obbligatorio"),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: "Le due password non coincidono",
    path: ["confirmPassword"],
  });

const otpSchema = z.object({
  code: z.string().length(6, "Il codice è di 6 cifre").regex(/^\d+$/, "Solo cifre"),
});

type RegisterData = z.infer<typeof registerSchema>;
type OtpData = z.infer<typeof otpSchema>;

const FEATURES = [
  { Icon: BarChart2, label: "P&L e performance in tempo reale" },
  { Icon: TrendingUp, label: "Analisi del rischio e benchmark" },
  { Icon: Shield, label: "Dati cifrati end-to-end" },
];

const COUNTDOWN_SECS = 15 * 60;
const RESEND_COOLDOWN = 60;

export function Register() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState<"form" | "otp">("form");
  const [pendingEmail, setPendingEmail] = useState("");
  const [countdown, setCountdown] = useState(COUNTDOWN_SECS);
  const [resendCooldown, setResendCooldown] = useState(0);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const resendRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const registerForm = useForm<RegisterData>({ resolver: zodResolver(registerSchema) });
  const otpForm = useForm<OtpData>({ resolver: zodResolver(otpSchema) });

  function startCountdowns() {
    if (countdownRef.current) clearInterval(countdownRef.current);
    if (resendRef.current) clearInterval(resendRef.current);

    setCountdown(COUNTDOWN_SECS);
    setResendCooldown(RESEND_COOLDOWN);

    countdownRef.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { clearInterval(countdownRef.current!); return 0; }
        return c - 1;
      });
    }, 1000);

    resendRef.current = setInterval(() => {
      setResendCooldown((c) => {
        if (c <= 1) { clearInterval(resendRef.current!); return 0; }
        return c - 1;
      });
    }, 1000);
  }

  useEffect(() => {
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (resendRef.current) clearInterval(resendRef.current);
    };
  }, []);

  const registerMutation = useMutation({
    mutationFn: ({ name, email, password }: RegisterData) =>
      authService.register(email, password, name),
    onSuccess: (res, vars) => {
      if (res.requires_verification) {
        setPendingEmail(vars.email);
        setStep("otp");
        startCountdowns();
      } else if (res.access_token) {
        authService.saveTokens({
          access_token: res.access_token,
          refresh_token: res.refresh_token,
          token_type: res.token_type,
          requires_2fa: false,
          session_token: null,
        });
        navigate("/");
      }
    },
  });

  const verifyMutation = useMutation({
    mutationFn: ({ code }: OtpData) => authService.verifyEmail(pendingEmail, code),
    onSuccess: (res) => {
      authService.saveTokens(res);
      navigate("/");
    },
  });

  const resendMutation = useMutation({
    mutationFn: () => authService.resendVerification(pendingEmail),
    onSuccess: () => {
      startCountdowns();
      otpForm.reset();
    },
  });

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="min-h-screen flex">

      {/* ── Left brand panel ──────────────────────────────────── */}
      <div
        className="hidden lg:flex flex-col w-[500px] xl:w-[560px] relative overflow-hidden flex-shrink-0"
        style={{ background: "linear-gradient(160deg, #05101f 0%, #0b1a30 60%, #061525 100%)" }}
      >
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.055) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />
        <div className="absolute top-1/4 left-1/4 w-80 h-80 rounded-full bg-blue-600/15 blur-[90px] pointer-events-none" />
        <div className="absolute bottom-1/3 right-0 w-72 h-72 rounded-full bg-emerald-500/8 blur-[70px] pointer-events-none" />

        <div className="relative z-10 p-10 flex-shrink-0">
          <Link to="/login" className="flex items-center gap-2.5 w-fit">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-900/60">
              <TrendingUp className="w-[18px] h-[18px] text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">
              Next<span className="text-emerald-400">folio</span>
            </span>
          </Link>
        </div>

        <div className="relative z-10 px-10 flex-1 flex flex-col justify-center pb-20">
          <h1 className="text-[38px] xl:text-5xl font-extrabold text-white leading-[1.08] mb-4">
            Inizia a tracciare<br />
            <span className="bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
              i tuoi investimenti.
            </span>
          </h1>
          <p className="text-slate-400 text-sm leading-relaxed mb-8 max-w-sm">
            Crea il tuo account gratuito e ottieni una visione completa del tuo patrimonio.
          </p>
          <div className="flex flex-col gap-3">
            {FEATURES.map(({ Icon, label }) => (
              <div key={label} className="flex items-center gap-3 text-sm text-slate-300">
                <div className="w-7 h-7 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-3.5 h-3.5 text-blue-400" />
                </div>
                {label}
              </div>
            ))}
          </div>
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

          {step === "form" ? (
            <>
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900">{t("auth.createAccount")}</h2>
                <p className="text-sm text-gray-400 mt-1">{t("auth.createAccountDesc")}</p>
              </div>

              <form
                onSubmit={registerForm.handleSubmit((d) => registerMutation.mutate(d))}
                className="space-y-4"
              >
                <Input
                  label={t("common.name")}
                  type="text"
                  autoComplete="name"
                  error={registerForm.formState.errors.name?.message}
                  {...registerForm.register("name")}
                />
                <Input
                  label={t("auth.email")}
                  type="email"
                  autoComplete="email"
                  error={registerForm.formState.errors.email?.message}
                  {...registerForm.register("email")}
                />
                <Input
                  label={t("auth.password")}
                  type="password"
                  autoComplete="new-password"
                  placeholder={t("auth.minCharsPlaceholder")}
                  error={registerForm.formState.errors.password?.message}
                  {...registerForm.register("password")}
                />
                <Input
                  label={t("auth.confirmPassword")}
                  type="password"
                  autoComplete="new-password"
                  placeholder={t("auth.repeatPlaceholder")}
                  error={registerForm.formState.errors.confirmPassword?.message}
                  {...registerForm.register("confirmPassword")}
                />

                {registerMutation.isError && (
                  <div className="text-sm text-red-600 text-center bg-red-50 border border-red-100 rounded-xl py-2.5 px-4">
                    {t("auth.registerError")}
                  </div>
                )}

                <Button
                  type="submit"
                  loading={registerMutation.isPending}
                  className="w-full !py-3 !text-base gap-2"
                >
                  {t("auth.register")}
                  {!registerMutation.isPending && <ArrowRight className="w-4 h-4" />}
                </Button>

                <div className="text-center pt-1">
                  <span className="text-sm text-gray-400">{t("auth.alreadyAccount")} </span>
                  <Link to="/login" className="text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors">
                    {t("auth.signIn")}
                  </Link>
                </div>
              </form>
            </>
          ) : (
            <>
              <div className="flex flex-col items-center mb-8 text-center">
                <div className="w-14 h-14 rounded-2xl bg-emerald-50 flex items-center justify-center mb-4">
                  <MailCheck className="w-7 h-7 text-emerald-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900">{t("auth.verifyEmail")}</h2>
                <p className="text-sm text-gray-400 mt-2 max-w-[280px]">
                  {t("auth.verifyEmailDesc", { email: pendingEmail })}
                </p>
              </div>

              <form
                onSubmit={otpForm.handleSubmit((d) => verifyMutation.mutate(d))}
                className="space-y-4"
              >
                <Input
                  label={t("auth.verificationCode")}
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="000000"
                  maxLength={6}
                  error={otpForm.formState.errors.code?.message}
                  {...otpForm.register("code")}
                />

                {countdown > 0 ? (
                  <p className="text-xs text-center text-gray-400">
                    {t("auth.codeExpires")}{" "}
                    <span className="font-semibold text-gray-600 tabular-nums">{formatTime(countdown)}</span>
                  </p>
                ) : (
                  <p className="text-xs text-center text-red-500">{t("auth.codeExpired")}</p>
                )}

                {verifyMutation.isError && (
                  <div className="text-sm text-red-600 text-center bg-red-50 border border-red-100 rounded-xl py-2.5 px-4">
                    {t("auth.invalidCode")}
                  </div>
                )}

                <Button
                  type="submit"
                  loading={verifyMutation.isPending}
                  className="w-full !py-3 !text-base"
                  disabled={countdown === 0}
                >
                  {t("auth.verify")}
                </Button>

                <div className="text-center">
                  {resendCooldown > 0 ? (
                    <p className="text-sm text-gray-400">
                      {t("auth.resendIn")}{" "}
                      <span className="tabular-nums">{resendCooldown}s</span>
                    </p>
                  ) : (
                    <button
                      type="button"
                      onClick={() => resendMutation.mutate()}
                      disabled={resendMutation.isPending}
                      className="text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors disabled:opacity-50"
                    >
                      {resendMutation.isPending ? t("auth.sending") : t("auth.resendCode")}
                    </button>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => setStep("form")}
                  className="w-full text-sm text-gray-400 hover:text-gray-600 transition-colors py-2"
                >
                  ← {t("auth.backToRegister")}
                </button>
              </form>
            </>
          )}

          <p className="text-center text-xs text-gray-300 mt-12">
            {t("auth.copyright", { year: new Date().getFullYear() })}
          </p>
        </div>
      </div>
    </div>
  );
}
