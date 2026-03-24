import Link from "next/link";
import { blogPosts } from "@/lib/blog-posts";

export default function BlogIndexPage() {
  const sortedPosts = [...blogPosts].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  return (
    <>
      {/* Hero */}
      <section className="bg-gradient-to-br from-red-600 to-red-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20 text-center">
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
            Junk Removal Tips &amp; Guides
          </h1>
          <p className="mt-4 text-lg text-red-100 max-w-2xl mx-auto">
            Practical advice on decluttering, pricing, recycling, and getting
            the most out of your junk removal service in South Florida.
          </p>
        </div>
      </section>

      {/* Articles Grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {sortedPosts.map((post) => (
            <article
              key={post.slug}
              className="group rounded-2xl border border-gray-200 bg-white overflow-hidden hover:shadow-lg hover:border-red-200 transition-all"
            >
              <div className="p-6 flex flex-col h-full">
                <time
                  dateTime={post.date}
                  className="text-sm text-gray-500 font-medium"
                >
                  {new Date(post.date).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </time>
                <h2 className="mt-3 text-xl font-bold text-gray-900 group-hover:text-red-600 transition-colors">
                  <Link href={`/blog/${post.slug}`}>{post.title}</Link>
                </h2>
                <p className="mt-3 text-gray-600 text-sm leading-relaxed flex-1">
                  {post.excerpt}
                </p>
                <Link
                  href={`/blog/${post.slug}`}
                  className="mt-4 inline-flex items-center text-sm font-semibold text-red-600 hover:text-red-700 transition-colors"
                >
                  Read more
                  <svg
                    className="ml-1 w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                    />
                  </svg>
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
          <h2 className="text-3xl font-bold text-gray-900 tracking-tight">
            Ready to Clear the Clutter?
          </h2>
          <p className="mt-4 text-lg text-gray-600 max-w-xl mx-auto">
            Book your junk removal pickup in under 2 minutes. Same-day service
            available across South Florida.
          </p>
          <Link
            href="/book"
            className="mt-8 inline-flex items-center justify-center rounded-xl bg-red-600 text-white font-bold text-lg px-8 py-4 shadow-lg hover:bg-red-700 transition-colors"
          >
            Book a Pickup Now
          </Link>
        </div>
      </section>
    </>
  );
}
