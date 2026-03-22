import type { Metadata } from "next";
import Link from "next/link";

const CITIES = [
  { slug: "miami", name: "Miami" },
  { slug: "fort-lauderdale", name: "Fort Lauderdale" },
  { slug: "west-palm-beach", name: "West Palm Beach" },
  { slug: "boca-raton", name: "Boca Raton" },
  { slug: "pompano-beach", name: "Pompano Beach" },
  { slug: "delray-beach", name: "Delray Beach" },
  { slug: "boynton-beach", name: "Boynton Beach" },
  { slug: "jupiter", name: "Jupiter" },
  { slug: "palm-beach-gardens", name: "Palm Beach Gardens" },
  { slug: "hollywood-fl", name: "Hollywood" },
  { slug: "pembroke-pines", name: "Pembroke Pines" },
  { slug: "coral-springs", name: "Coral Springs" },
  { slug: "deerfield-beach", name: "Deerfield Beach" },
  { slug: "lake-worth", name: "Lake Worth" },
  { slug: "riviera-beach", name: "Riviera Beach" },
  { slug: "royal-palm-beach", name: "Royal Palm Beach" },
  { slug: "wellington", name: "Wellington" },
  { slug: "plantation", name: "Plantation" },
  { slug: "sunrise", name: "Sunrise" },
  { slug: "davie", name: "Davie" },
  { slug: "miramar", name: "Miramar" },
  { slug: "hialeah", name: "Hialeah" },
  { slug: "homestead", name: "Homestead" },
  { slug: "coconut-creek", name: "Coconut Creek" },
] as const;

type CitySlug = (typeof CITIES)[number]["slug"];

function getCityBySlug(slug: string) {
  return CITIES.find((c) => c.slug === slug);
}

export function generateStaticParams() {
  return CITIES.map((city) => ({ city: city.slug }));
}

export function generateMetadata({
  params,
}: {
  params: { city: string };
}): Metadata {
  const city = getCityBySlug(params.city);
  const name = city?.name ?? "Your City";

  return {
    title: `Junk Removal in ${name}, FL | Umuve - Hauling Made Simple`,
    description: `Affordable junk removal in ${name}, Florida. We donate first, dispose last. Furniture, appliances, yard waste & more. Starting at $79. Book online in minutes.`,
    openGraph: {
      title: `Junk Removal in ${name}, FL | Umuve`,
      description: `Affordable junk removal in ${name}, Florida. We donate first, dispose last. Starting at $79.`,
      type: "website",
      url: `https://app.goumuve.com/${params.city}`,
    },
    alternates: {
      canonical: `https://app.goumuve.com/${params.city}`,
    },
  };
}

const SERVICES = [
  {
    title: "Furniture Removal",
    description: "Sofas, tables, mattresses, dressers and more",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
      </svg>
    ),
  },
  {
    title: "Appliance Removal",
    description: "Fridges, washers, dryers, ovens, dishwashers",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-2.25-1.313M21 7.5v2.25m0-2.25l-2.25 1.313M3 7.5l2.25-1.313M3 7.5l2.25 1.313M3 7.5v2.25m9 3l2.25-1.313M12 12.75l-2.25-1.313M12 12.75V15m0 6.75l2.25-1.313M12 21.75V19.5m0 2.25l-2.25-1.313m0-16.875L12 2.25l2.25 1.313M21 14.25v2.25l-2.25 1.313m-13.5 0L3 16.5v-2.25" />
      </svg>
    ),
  },
  {
    title: "Yard Waste",
    description: "Branches, leaves, soil, landscaping debris",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
      </svg>
    ),
  },
  {
    title: "Construction Debris",
    description: "Drywall, lumber, concrete, renovation waste",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.25 5.25a2.121 2.121 0 01-3-3l5.25-5.25m3-3l5.25-5.25a2.121 2.121 0 013 3l-5.25 5.25" />
      </svg>
    ),
  },
  {
    title: "Estate Cleanout",
    description: "Full property cleanouts with care and respect",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h5.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5V3.545M12.75 21h7.5V10.75M2.25 21h1.5m18 0h-18M2.25 9l4.5-1.636M18.75 3l-1.5.545m0 6.205l3 1m1.5.5l-1.5-.5M6.75 7.364V3h-3v18m3-13.636l10.5-3.819" />
      </svg>
    ),
  },
  {
    title: "Garage Cleanout",
    description: "Clear out years of accumulated items fast",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
      </svg>
    ),
  },
  {
    title: "Hot Tub Removal",
    description: "Safe disconnect, disassembly and hauling",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18a3.75 3.75 0 00.495-7.467 5.99 5.99 0 00-1.925 3.546 5.974 5.974 0 01-2.133-1A3.75 3.75 0 0012 18z" />
      </svg>
    ),
  },
  {
    title: "E-Waste Recycling",
    description: "TVs, monitors, computers, printers, electronics",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25A2.25 2.25 0 015.25 3h13.5A2.25 2.25 0 0121 5.25z" />
      </svg>
    ),
  },
];

const PRICING = [
  { item: "Single Item", price: "$79", note: "Small items like chairs, lamps" },
  { item: "Sofa / Couch", price: "$89", note: "Any size, we carry it out" },
  { item: "Fridge / Appliance", price: "$99", note: "Safe disconnect & haul" },
  { item: "Full Truck Load", price: "$579", note: "Clear out an entire space" },
];

const WHY_UMUVE = [
  {
    title: "Donate First",
    description: "We partner with local charities and shelters. Usable items get donated before anything is disposed of.",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
      </svg>
    ),
  },
  {
    title: "25% Cheaper",
    description: "Our pricing beats the big guys. No hidden fees, no surprises. What we quote is what you pay.",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    title: "Same-Day Service",
    description: "Need it gone today? We offer same-day and next-day pickups throughout South Florida.",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    title: "Photo Estimates",
    description: "Snap a photo of your junk, get an instant price estimate. No need for an in-person visit.",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
      </svg>
    ),
  },
];

export default function CityPage({ params }: { params: { city: string } }) {
  const city = getCityBySlug(params.city);
  const cityName = city?.name ?? "Your City";

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    name: `Umuve Junk Removal - ${cityName}, FL`,
    description: `Professional junk removal services in ${cityName}, Florida. Furniture, appliances, yard waste, construction debris and more.`,
    url: `https://app.goumuve.com/${params.city}`,
    telephone: "+1-561-000-0000",
    address: {
      "@type": "PostalAddress",
      addressLocality: cityName,
      addressRegion: "FL",
      addressCountry: "US",
    },
    areaServed: {
      "@type": "City",
      name: cityName,
    },
    priceRange: "$79 - $579",
    image: "https://app.goumuve.com/logo-nav.png",
    sameAs: ["https://app.goumuve.com"],
    openingHoursSpecification: {
      "@type": "OpeningHoursSpecification",
      dayOfWeek: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      opens: "07:00",
      closes: "19:00",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-red-600 to-red-800 text-white">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28 text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight">
            Junk Removal in {cityName}, Florida
          </h1>
          <p className="mt-6 text-lg sm:text-xl text-red-100 max-w-2xl mx-auto">
            Hauling made simple. We donate &amp; recycle first — landfill is always the last resort.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/book"
              className="inline-flex items-center justify-center rounded-xl bg-white text-red-700 font-bold text-lg px-8 py-4 shadow-lg hover:bg-red-50 transition-colors"
            >
              Book a Pickup
            </Link>
            <span className="text-red-200 text-sm">Starting at just $79</span>
          </div>
        </div>
      </section>

      {/* Services Grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 tracking-tight">
            What We Haul in {cityName}
          </h2>
          <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
            From a single item to a full property cleanout, we handle it all with care.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {SERVICES.map((service) => (
            <div
              key={service.title}
              className="group rounded-2xl border border-gray-200 bg-white p-6 hover:shadow-lg hover:border-red-200 transition-all"
            >
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-red-50 text-red-600 mb-4 group-hover:bg-red-100 transition-colors">
                {service.icon}
              </div>
              <h3 className="text-lg font-semibold text-gray-900">{service.title}</h3>
              <p className="mt-2 text-sm text-gray-600">{service.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 tracking-tight">
              Transparent Pricing
            </h2>
            <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
              No hidden fees. No surprises. What we quote is what you pay.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-4xl mx-auto">
            {PRICING.map((p) => (
              <div
                key={p.item}
                className="rounded-2xl bg-white border border-gray-200 p-6 text-center hover:shadow-lg hover:border-red-200 transition-all"
              >
                <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">{p.item}</p>
                <p className="mt-2 text-4xl font-extrabold text-red-600">{p.price}</p>
                <p className="mt-2 text-sm text-gray-500">{p.note}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Why Umuve */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 tracking-tight">
            Why {cityName} Chooses Umuve
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {WHY_UMUVE.map((item) => (
            <div key={item.title} className="flex gap-4">
              <div className="flex-shrink-0 inline-flex items-center justify-center w-12 h-12 rounded-xl bg-red-50 text-red-600">
                {item.icon}
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{item.title}</h3>
                <p className="mt-1 text-gray-600">{item.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="bg-gradient-to-br from-red-600 to-red-800 text-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
            Ready to Clear the Clutter?
          </h2>
          <p className="mt-4 text-lg text-red-100 max-w-xl mx-auto">
            Book your junk removal pickup in {cityName} in under 2 minutes. Same-day service available.
          </p>
          <Link
            href="/book"
            className="mt-8 inline-flex items-center justify-center rounded-xl bg-white text-red-700 font-bold text-lg px-8 py-4 shadow-lg hover:bg-red-50 transition-colors"
          >
            Book a Pickup Now
          </Link>
        </div>
      </section>

      {/* Nearby Cities */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Also Serving Nearby Cities
        </h2>
        <div className="flex flex-wrap gap-2">
          {CITIES.filter((c) => c.slug !== params.city).map((c) => (
            <Link
              key={c.slug}
              href={`/${c.slug}`}
              className="text-sm text-gray-600 hover:text-red-600 hover:underline underline-offset-4 transition-colors px-2 py-1 rounded-lg hover:bg-red-50"
            >
              {c.name}, FL
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
