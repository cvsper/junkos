"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { SupportChat } from "@/components/support-chat";

export default function CustomerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, user, logout } = useAuthStore();
  const router = useRouter();

  const handleSignOut = () => {
    logout();
    router.push("/");
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Navbar */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <img src="/logo-nav.png" alt="Umuve" className="h-9 w-auto object-contain" />
          </Link>

          {/* Navigation Links */}
          <div className="flex items-center gap-6">
            <Link
              href="/book"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Book a Pickup
            </Link>
            <Link
              href="/dashboard"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              My Jobs
            </Link>

            {isAuthenticated ? (
              <>
                <Link
                  href="/referrals"
                  className="text-sm font-medium text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M21 11.25v8.25a1.5 1.5 0 01-1.5 1.5H5.25a1.5 1.5 0 01-1.5-1.5v-8.25M12 4.875A2.625 2.625 0 109.375 7.5H12m0-2.625V7.5m0-2.625A2.625 2.625 0 1114.625 7.5H12m0 0V21m-8.625-9.75h18c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125h-18c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
                    />
                  </svg>
                  Refer a Friend
                </Link>
                <Link
                  href="/profile"
                  className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                  Profile
                </Link>
                <button
                  onClick={handleSignOut}
                  className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  Sign Out
                </button>
              </>
            ) : (
              <Link
                href="/login"
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                Sign In
              </Link>
            )}
          </div>
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1">{children}</main>

      {/* Support Chat Widget */}
      <SupportChat />
    </div>
  );
}
