import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authService } from "@/services/auth";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

const schema = z.object({
  name: z.string().min(2, "Inserisci il tuo nome"),
  email: z.string().email("Email non valida"),
  password: z.string().min(8, "Minimo 8 caratteri"),
  confirmPassword: z.string(),
}).refine((d) => d.password === d.confirmPassword, {
  message: "Le password non coincidono",
  path: ["confirmPassword"],
});

type FormData = z.infer<typeof schema>;

export function Register() {
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const { mutate, isPending, error } = useMutation({
    mutationFn: ({ email, password, name }: FormData) =>
      authService.register(email, password, name),
    onSuccess: (tokens) => {
      authService.saveTokens(tokens);
      navigate("/");
    },
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand-600">Nextfolio</h1>
          <p className="mt-2 text-sm text-gray-500">Gestisci il tuo patrimonio in modo intelligente</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Crea account</h2>

          <form onSubmit={handleSubmit((d) => mutate(d))} className="space-y-4">
            <Input label="Nome" error={errors.name?.message} {...register("name")} />
            <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
            <Input label="Password" type="password" error={errors.password?.message} {...register("password")} />
            <Input
              label="Conferma password"
              type="password"
              error={errors.confirmPassword?.message}
              {...register("confirmPassword")}
            />

            {error && (
              <p className="text-sm text-red-600 text-center">
                Registrazione fallita. L'email potrebbe essere già in uso.
              </p>
            )}

            <Button type="submit" loading={isPending} className="w-full">
              Registrati
            </Button>
          </form>

          <p className="mt-4 text-sm text-center text-gray-500">
            Hai già un account?{" "}
            <Link to="/login" className="text-brand-600 hover:underline font-medium">
              Accedi
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
