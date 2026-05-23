import React from 'react';
import { BookOpen, ArrowRight, ShieldCheck, Lock, Sparkles, ClipboardCheck } from 'lucide-react';
import { ButtonLink } from '../components/ui';

const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-white dark:bg-[#050507]">
      <div className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 bg-gradient-to-b from-primary/25 via-transparent to-transparent dark:from-primary-500/20" />
        <div className="pointer-events-none absolute right-0 top-20 -z-10 h-72 w-72 rounded-full bg-sky-300/20 blur-3xl dark:bg-cyan-500/20" />
        <div className="pointer-events-none absolute left-0 bottom-0 -z-10 h-72 w-72 rounded-full bg-emerald-300/20 blur-3xl dark:bg-violet-500/20" />

        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
          <div className="grid gap-14 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
            <div className="max-w-xl">
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-4 py-2 text-sm font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">
                <ShieldCheck className="h-4 w-4" />
                Privacy-first security, zero-knowledge by design
              </div>

              <h1 className="mt-8 text-4xl font-extrabold tracking-tight text-zinc-900 dark:text-white sm:text-5xl">
                Keep your passwords, notes, and secrets in a vault only you can open.
              </h1>

              <p className="mt-6 text-lg leading-8 text-zinc-600 dark:text-zinc-300">
                AccountSafe combines authenticated encryption, secure key derivation, and automatic lock behavior so your sensitive data stays private and protected.
              </p>

              <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
                <ButtonLink
                  to="/register"
                  variant="default"
                  className="rounded-full px-6 py-3 text-sm font-semibold shadow-lg shadow-primary/20 hover:bg-primary-600"
                >
                  Start free vault
                </ButtonLink>
                <ButtonLink
                  to="/docs/security"
                  variant="outline"
                  className="rounded-full px-6 py-3 text-sm font-semibold"
                  leftIcon={<BookOpen className="h-4 w-4" />}
                  rightIcon={<ArrowRight className="h-4 w-4 opacity-70" />}
                >
                  View security docs
                </ButtonLink>
              </div>

              <div className="mt-12 grid gap-4 sm:grid-cols-2">
                {[
                  {
                    icon: Lock,
                    label: 'AES-256-GCM',
                    description: 'Authenticated encryption protecting your stored secrets.',
                  },
                  {
                    icon: Sparkles,
                    label: 'Auto-lock',
                    description: 'Inactivity and tab-security keep access locked when you step away.',
                  },
                  {
                    icon: ClipboardCheck,
                    label: 'Secure recovery',
                    description: 'Store recovery material safely during account setup.',
                  },
                  {
                    icon: ShieldCheck,
                    label: 'Zero-knowledge',
                    description: 'Your master key stays in memory only; never on disk.',
                  },
                ].map((feature) => (
                  <div key={feature.label} className="rounded-3xl border border-zinc-200 bg-zinc-50 p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
                    <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary-100">
                      <feature.icon className="h-5 w-5" />
                    </div>
                    <h2 className="mt-4 text-base font-semibold text-zinc-900 dark:text-white">{feature.label}</h2>
                    <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{feature.description}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] border border-zinc-200/70 bg-white/95 p-8 shadow-2xl shadow-zinc-200/30 backdrop-blur-xl dark:border-zinc-800/70 dark:bg-zinc-950/85 dark:shadow-black/20">
              <div className="space-y-6">
                <div className="rounded-3xl bg-zinc-100 p-5 dark:bg-zinc-900">
                  <p className="text-sm font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400">AccountSafe Vault</p>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    {['Passwords', 'Secure Notes', 'Recovery Keys', 'Device Audit'].map((item) => (
                      <div key={item} className="rounded-3xl border border-zinc-200 bg-white px-4 py-4 text-sm font-medium text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-3xl border border-primary/15 bg-primary/5 p-5 dark:border-primary/25 dark:bg-primary/10">
                    <p className="text-sm font-semibold text-primary dark:text-primary-100">100% client-side key derivation</p>
                    <p className="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-300">Your vault is decrypted only in the browser after you enter your password.</p>
                  </div>
                  <div className="rounded-3xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
                    <p className="text-sm font-semibold text-zinc-900 dark:text-white">Designed for modern threat models</p>
                    <p className="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-400">If the tab is hidden too long, AccountSafe requires re-authentication before unlocking again.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;
