import type { Metadata } from "next";
import Link from "next/link";
import { blogPosts, getPostBySlug, getAllSlugs } from "@/lib/blog-posts";

export function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Metadata {
  const post = getPostBySlug(params.slug);
  if (!post) {
    return { title: "Post Not Found | Umuve Blog" };
  }

  return {
    title: post.metaTitle,
    description: post.metaDescription,
    keywords: post.keywords,
    openGraph: {
      title: post.metaTitle,
      description: post.metaDescription,
      type: "article",
      url: `https://app.goumuve.com/blog/${post.slug}`,
      publishedTime: post.date,
      authors: ["Umuve"],
    },
    alternates: {
      canonical: `https://app.goumuve.com/blog/${post.slug}`,
    },
  };
}

export default function BlogPostPage({
  params,
}: {
  params: { slug: string };
}) {
  const post = getPostBySlug(params.slug);

  if (!post) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <h1 className="text-3xl font-bold text-gray-900">Post Not Found</h1>
        <p className="mt-4 text-gray-600">
          The article you&apos;re looking for doesn&apos;t exist.
        </p>
        <Link
          href="/blog"
          className="mt-6 inline-block text-red-600 font-semibold hover:text-red-700"
        >
          Back to Blog
        </Link>
      </div>
    );
  }

  const relatedPosts = post.relatedSlugs
    .map((slug) => getPostBySlug(slug))
    .filter(Boolean);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.metaDescription,
    datePublished: post.date,
    author: {
      "@type": "Organization",
      name: "Umuve",
      url: "https://app.goumuve.com",
    },
    publisher: {
      "@type": "Organization",
      name: "Umuve",
      url: "https://app.goumuve.com",
      logo: {
        "@type": "ImageObject",
        url: "https://app.goumuve.com/logo-nav.png",
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `https://app.goumuve.com/blog/${post.slug}`,
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Article Header */}
      <header className="bg-gradient-to-br from-red-600 to-red-800 text-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
          <Link
            href="/blog"
            className="inline-flex items-center text-sm text-red-200 hover:text-white transition-colors mb-6"
          >
            <svg
              className="mr-1 w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"
              />
            </svg>
            All Articles
          </Link>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight leading-tight">
            {post.title}
          </h1>
          <time
            dateTime={post.date}
            className="mt-4 block text-sm text-red-200"
          >
            {new Date(post.date).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </time>
        </div>
      </header>

      {/* Article Body */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        <div
          className="blog-content max-w-none text-gray-700 text-lg leading-relaxed
            [&_h2]:text-2xl [&_h2]:font-bold [&_h2]:text-gray-900 [&_h2]:tracking-tight [&_h2]:mt-10 [&_h2]:mb-4
            [&_h3]:text-xl [&_h3]:font-bold [&_h3]:text-gray-900 [&_h3]:mt-8 [&_h3]:mb-3
            [&_p]:mb-4
            [&_a]:text-red-600 [&_a]:font-semibold hover:[&_a]:underline
            [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:mb-4 [&_ul]:space-y-1
            [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:mb-4 [&_ol]:space-y-1
            [&_li]:text-gray-700
            [&_strong]:text-gray-900
            [&_table]:border-collapse [&_table]:w-full [&_table]:mb-4
            [&_th]:bg-gray-100 [&_th]:text-left [&_th]:px-4 [&_th]:py-2 [&_th]:text-sm [&_th]:font-semibold [&_th]:text-gray-900 [&_th]:border [&_th]:border-gray-200
            [&_td]:px-4 [&_td]:py-2 [&_td]:text-sm [&_td]:text-gray-700 [&_td]:border [&_td]:border-gray-200"
          dangerouslySetInnerHTML={{ __html: post.content }}
        />

        {/* CTA */}
        <div className="mt-12 rounded-2xl bg-red-50 border border-red-100 p-8 text-center">
          <h3 className="text-2xl font-bold text-gray-900">
            Need Junk Removal in South Florida?
          </h3>
          <p className="mt-2 text-gray-600">
            Book your pickup in under 2 minutes. Same-day service available.
          </p>
          <Link
            href="/book"
            className="mt-6 inline-flex items-center justify-center rounded-xl bg-red-600 text-white font-bold text-lg px-8 py-4 shadow-lg hover:bg-red-700 transition-colors"
          >
            Book a Pickup — Starting at $79
          </Link>
        </div>
      </article>

      {/* Related Articles */}
      {relatedPosts.length > 0 && (
        <section className="bg-gray-50">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">
              Related Articles
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {relatedPosts.map((related) =>
                related ? (
                  <Link
                    key={related.slug}
                    href={`/blog/${related.slug}`}
                    className="group rounded-2xl border border-gray-200 bg-white p-6 hover:shadow-lg hover:border-red-200 transition-all"
                  >
                    <h3 className="text-lg font-bold text-gray-900 group-hover:text-red-600 transition-colors">
                      {related.title}
                    </h3>
                    <p className="mt-2 text-sm text-gray-600">
                      {related.excerpt}
                    </p>
                  </Link>
                ) : null
              )}
            </div>
          </div>
        </section>
      )}
    </>
  );
}
