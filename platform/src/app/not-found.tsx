import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <h1 className="font-display text-6xl font-bold text-primary">404</h1>
      <p className="mt-4 text-lg text-muted-foreground">Page not found</p>
      <Link
        href="/book"
        className="mt-8 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-white hover:bg-primary/90"
      >
        Book a Pickup
      </Link>
    </div>
  );
}
