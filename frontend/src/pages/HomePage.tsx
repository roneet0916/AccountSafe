import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { CategoryManager } from '../features/vault/components';
import { ShieldCheck, Lock, Sparkles, Key, ArrowRight } from 'lucide-react';

const securityFeatures = [
  {
    title: 'Zero-Knowledge Vault',
    description: 'Only encrypted data is stored on the server. Your master key never leaves memory.',
    icon: ShieldCheck,
  },
  {
    title: 'AES-256-GCM Encryption',
    description: 'Industry-standard authenticated encryption keeps your passwords and secrets confidential.',
    icon: Lock,
  },
  {
    title: 'Automatic Locking',
    description: 'Auto-locks after inactivity and re-requires authentication if the tab returns after a long absence.',
    icon: Sparkles,
  },
  {
    title: 'Secure Recovery',
    description: 'Create and store recovery material securely during registration without exposing your master password.',
    icon: Key,
  },
];

const HomePage: React.FC = () => {
  const { token } = useAuth();

  return (
    <div className="min-h-screen bg-white text-zinc-900 dark:bg-[#050507] dark:text-zinc-100">
      {token ? (
        <CategoryManager />
      ) : (
        <div className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 bg-gradient-to-b from-primary/20 via-transparent to-transparent dark:from-primary-500/20" />
          <div className="pointer-events-none absolute right-[-8rem] top-20 -z-10 h-96 w-96 rounded-full bg-emerald-300/20 blur-3xl dark:bg-cyan-500/20" />
          <div className="pointer-events-none absolute left-0 top-72 -z-10 h-72 w-72 rounded-full bg-sky-300/20 blur-3xl dark:bg-violet-500/20" />

          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
            <div className="grid gap-12 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
              <div className="max-w-xl">
                <span className="inline-flex rounded-full bg-primary/10 px-3 py-1 text-sm font-semibold text-primary ring-1 ring-primary/15 dark:bg-primary/15 dark:text-primary-100">
                  Secure vault with zero-knowledge privacy
                </span>
                <h1 className="mt-8 text-4xl font-extrabold tracking-tight text-zinc-900 dark:text-white sm:text-5xl">
                  A modern, private password vault built for security-first teams.
                </h1>
                <p className="mt-6 text-lg leading-8 text-zinc-600 dark:text-zinc-300">
                  AccountSafe protects your credentials, notes, and secrets with AES-256-GCM encryption and Argon2id key derivation. Your master key stays in memory only, never on disk.
                </p>

                <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
                  <Link
                    to="/login"
                    className="inline-flex items-center justify-center rounded-full bg-primary px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-primary/20 transition-all hover:bg-primary-600"
                  >
                    Log in to your vault
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                  <Link
                    to="/register"
                    className="inline-flex items-center justify-center rounded-full border border-zinc-200 bg-white px-6 py-3 text-sm font-semibold text-zinc-900 shadow-sm transition-all hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
                  >
                    Create free account
                  </Link>
                </div>

                <div className="mt-10 grid gap-4 sm:grid-cols-2">
                  {securityFeatures.map((feature) => {
                    const Icon = feature.icon;
                    return (
                      <div key={feature.title} className="rounded-3xl border border-zinc-200/70 bg-white/90 p-5 shadow-lg shadow-zinc-200/40 backdrop-blur-sm transition hover:-translate-y-0.5 dark:border-zinc-800/60 dark:bg-zinc-950/80 dark:shadow-black/20">
                        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary-100">
                          <Icon className="h-6 w-6" />
                        </div>
                        <h2 className="mt-4 text-base font-semibold text-zinc-900 dark:text-white">{feature.title}</h2>
                        <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{feature.description}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="relative rounded-[2rem] border border-zinc-200/70 bg-zinc-50/90 p-8 shadow-2xl shadow-zinc-200/20 backdrop-blur-xl dark:border-zinc-800/70 dark:bg-zinc-950/80 dark:shadow-black/20">
                <div className="absolute inset-x-0 top-0 h-1 rounded-t-3xl bg-gradient-to-r from-cyan-400 via-primary to-violet-500" />
                <div className="space-y-6 pt-6">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary-100">
                      <ShieldCheck className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-zinc-900 dark:text-white">Encrypted Vault Snapshot</p>
                      <p className="text-sm text-zinc-500 dark:text-zinc-400">Everything is encrypted client-side before leaving your browser.</p>
                    </div>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    {['Login', 'Passwords', 'Notes', 'Recovery'].map((item) => (
                      <div key={item} className="rounded-3xl border border-zinc-200 bg-white p-5 text-sm font-medium text-zinc-800 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100">
                        {item}
                      </div>
                    ))}
                  </div>

                  <div className="rounded-[1.75rem] border border-zinc-200 bg-white p-6 shadow-lg dark:border-zinc-800 dark:bg-zinc-950">
                    <p className="text-sm font-semibold text-zinc-900 dark:text-white">Privacy-first team workflows</p>
                    <p className="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-400">
                      Share and manage secrets securely with a vault built for individuals and small teams who want full control over their data.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-14 rounded-3xl border border-zinc-200/80 bg-white/90 px-6 py-5 shadow-xl shadow-zinc-200/30 backdrop-blur-xl dark:border-zinc-800/80 dark:bg-zinc-950/80 dark:shadow-black/20">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-semibold uppercase tracking-[0.24em] text-zinc-500 dark:text-zinc-400">Built for trust</p>
                  <p className="mt-2 text-base font-semibold text-zinc-900 dark:text-white">Never store the master key. Always keep your vault under your control.</p>
                </div>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  {['AES-256', 'Argon2id', 'Zero-Knowledge', 'Auto-Lock'].map((label) => (
                    <div key={label} className="rounded-2xl bg-zinc-100 px-4 py-3 text-center text-xs font-semibold uppercase tracking-[0.18em] text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
                      {label}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HomePage;
