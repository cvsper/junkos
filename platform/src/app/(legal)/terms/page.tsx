import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service - Umuve",
  description:
    "Terms of Service for Umuve junk removal platform. Read our terms governing the use of our on-demand junk removal services in South Florida.",
};

const LAST_UPDATED = "February 9, 2026";

const TABLE_OF_CONTENTS = [
  { id: "acceptance", label: "1. Acceptance of Terms" },
  { id: "description", label: "2. Description of Service" },
  { id: "accounts", label: "3. User Accounts" },
  { id: "booking", label: "4. Booking & Cancellation Policy" },
  { id: "payment", label: "5. Payment Terms" },
  { id: "contractor", label: "6. Contractor Relationship" },
  { id: "liability", label: "7. Limitation of Liability" },
  { id: "disputes", label: "8. Dispute Resolution" },
  { id: "changes", label: "9. Changes to Terms" },
  { id: "contact", label: "10. Contact Information" },
];

export default function TermsOfServicePage() {
  return (
    <article className="space-y-10">
      {/* Page Header */}
      <header className="space-y-4 border-b border-border pb-8">
        <h1 className="font-display text-4xl font-bold tracking-tight text-foreground">
          Terms of Service
        </h1>
        <p className="text-sm text-muted-foreground">
          Last updated: {LAST_UPDATED}
        </p>
        <p className="text-base text-muted-foreground leading-relaxed">
          Welcome to Umuve. These Terms of Service (&quot;Terms&quot;) govern
          your access to and use of the Umuve platform, website, and
          on-demand junk removal services (collectively, the
          &quot;Service&quot;). By using our Service, you agree to be bound by
          these Terms.
        </p>
      </header>

      {/* Table of Contents */}
      <nav className="rounded-lg border border-border bg-muted/30 p-6">
        <h2 className="font-display text-lg font-semibold text-foreground mb-4">
          Table of Contents
        </h2>
        <ol className="space-y-2">
          {TABLE_OF_CONTENTS.map((item) => (
            <li key={item.id}>
              <a
                href={`#${item.id}`}
                className="text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                {item.label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      {/* Sections */}
      <div className="space-y-12">
        {/* 1. Acceptance of Terms */}
        <section id="acceptance" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            1. Acceptance of Terms
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              By accessing or using Umuve, you confirm that you are at least 18
              years of age, have the legal capacity to enter into a binding
              agreement, and agree to comply with these Terms.
            </p>
            <p>
              If you are using the Service on behalf of a business or other
              legal entity, you represent that you have the authority to bind
              that entity to these Terms. If you do not agree to these Terms,
              you may not access or use the Service.
            </p>
            <p>
              Your continued use of the Service after any modifications to these
              Terms constitutes acceptance of those changes.
            </p>
          </div>
        </section>

        {/* 2. Description of Service */}
        <section id="description" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            2. Description of Service
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              Umuve is an on-demand junk removal marketplace that connects
              customers in South Florida with independent junk removal
              contractors (&quot;Haulers&quot;). Through our platform, you can:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Request junk removal pickups at your location
              </li>
              <li>
                Upload photos and descriptions of items to be removed
              </li>
              <li>
                Receive upfront pricing estimates based on the items and volume
              </li>
              <li>
                Schedule pickups at your preferred date and time
              </li>
              <li>
                Track your assigned Hauler in real-time
              </li>
              <li>
                Pay securely through the platform
              </li>
            </ul>
            <p>
              Umuve acts as an intermediary platform and does not itself
              perform junk removal services. The actual removal is carried out
              by independent Haulers who use our platform to connect with
              customers.
            </p>
          </div>
        </section>

        {/* 3. User Accounts */}
        <section id="accounts" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            3. User Accounts
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              To use certain features of the Service, you may be required to
              create an account. When creating an account, you agree to:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Provide accurate, current, and complete information during
                registration
              </li>
              <li>
                Maintain and promptly update your account information to keep it
                accurate and current
              </li>
              <li>
                Maintain the security and confidentiality of your login
                credentials
              </li>
              <li>
                Accept responsibility for all activities that occur under your
                account
              </li>
              <li>
                Notify us immediately of any unauthorized use of your account
              </li>
            </ul>
            <p>
              We reserve the right to suspend or terminate accounts that violate
              these Terms, provide false information, or engage in fraudulent
              activity.
            </p>
          </div>
        </section>

        {/* 4. Booking & Cancellation Policy */}
        <section id="booking" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            4. Booking & Cancellation Policy
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <h3 className="font-display text-lg font-medium text-foreground">
              Booking
            </h3>
            <p>
              When you submit a booking through Umuve, you are making a request
              for junk removal services. Your booking is confirmed once payment
              is processed and you receive a booking confirmation with a unique
              Booking ID.
            </p>
            <p>
              Pricing estimates are based on the information you provide
              (photos, item descriptions, volume). The final price may be
              adjusted if the actual scope of work differs materially from what
              was described during booking. Any price adjustments will be
              communicated before the Hauler begins work, and you will have the
              option to approve or cancel at that time.
            </p>

            <h3 className="font-display text-lg font-medium text-foreground pt-2">
              Cancellation
            </h3>
            <p>
              You may cancel a booking subject to the following policy:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong className="text-foreground">
                  More than 24 hours before scheduled pickup:
                </strong>{" "}
                Full refund. No cancellation fee applies.
              </li>
              <li>
                <strong className="text-foreground">
                  Less than 24 hours before scheduled pickup:
                </strong>{" "}
                A cancellation fee of up to 25% of the booking total may
                apply. The remaining balance will be refunded.
              </li>
              <li>
                <strong className="text-foreground">
                  No-show or same-day cancellation:
                </strong>{" "}
                Up to 50% of the booking total may be retained as a
                cancellation fee to compensate the Hauler for lost time and
                opportunity.
              </li>
            </ul>
            <p>
              Umuve reserves the right to cancel bookings due to safety
              concerns, extreme weather, or other circumstances beyond our
              control. In such cases, you will receive a full refund.
            </p>
          </div>
        </section>

        {/* 5. Payment Terms */}
        <section id="payment" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            5. Payment Terms
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              All payments are processed securely through Stripe, our
              third-party payment processor. By providing your payment
              information, you authorize Umuve and Stripe to charge the
              applicable amount to your chosen payment method.
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                All prices are listed in US Dollars (USD) and include applicable
                platform fees
              </li>
              <li>
                Payment is required at the time of booking to confirm your
                reservation
              </li>
              <li>
                Umuve does not store your credit card information; all payment
                data is handled by Stripe in accordance with PCI DSS standards
              </li>
              <li>
                Refunds, when applicable, will be returned to the original
                payment method and may take 5-10 business days to appear on your
                statement
              </li>
              <li>
                You are responsible for any taxes applicable to your purchase
              </li>
            </ul>
            <p>
              If additional charges arise due to a material difference between
              the items described and the actual scope of work, you will be
              notified before any additional charges are applied.
            </p>
          </div>
        </section>

        {/* 6. Contractor Relationship */}
        <section id="contractor" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            6. Contractor Relationship
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              Haulers who perform junk removal services through Umuve are
              independent contractors, not employees of Umuve. This means:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Umuve does not control the manner or method by which Haulers
                perform their services
              </li>
              <li>
                Haulers are responsible for their own insurance, equipment, and
                compliance with applicable laws and regulations
              </li>
              <li>
                Umuve screens and vets Haulers but does not guarantee their
                performance
              </li>
              <li>
                Haulers set their own availability and may accept or decline
                bookings
              </li>
            </ul>
            <p>
              Umuve facilitates the connection between customers and Haulers
              and provides a platform for scheduling, payment, and
              communication. Any disputes regarding the quality of service
              should be reported through our platform for resolution.
            </p>
          </div>
        </section>

        {/* 7. Limitation of Liability */}
        <section id="liability" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            7. Limitation of Liability
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              To the maximum extent permitted by applicable law:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Umuve provides the Service on an &quot;as is&quot; and
                &quot;as available&quot; basis without warranties of any kind,
                whether express or implied
              </li>
              <li>
                Umuve shall not be liable for any indirect, incidental,
                special, consequential, or punitive damages arising from your
                use of or inability to use the Service
              </li>
              <li>
                Umuve&apos;s total aggregate liability for any claims arising
                from or related to the Service shall not exceed the amount you
                paid for the specific booking giving rise to the claim
              </li>
              <li>
                Umuve is not responsible for any damage to property that may
                occur during junk removal, except as required by law. Claims
                for property damage should be directed to the Hauler&apos;s
                insurance
              </li>
            </ul>
            <p>
              Some jurisdictions do not allow the exclusion or limitation of
              certain warranties or damages. In such jurisdictions, our
              liability shall be limited to the greatest extent permitted by
              law.
            </p>
          </div>
        </section>

        {/* 8. Dispute Resolution */}
        <section id="disputes" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            8. Dispute Resolution
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              We aim to resolve any disputes quickly and fairly. If you have a
              concern about our Service:
            </p>
            <ol className="list-decimal pl-6 space-y-2">
              <li>
                <strong className="text-foreground">Contact Us First:</strong>{" "}
                Reach out to our support team at{" "}
                <a
                  href="mailto:support@goumuve.com"
                  className="text-primary hover:underline"
                >
                  support@goumuve.com
                </a>
                . We will make a good-faith effort to resolve the issue within
                30 days.
              </li>
              <li>
                <strong className="text-foreground">Mediation:</strong> If we
                cannot resolve the dispute informally, either party may request
                mediation through a mutually agreed-upon mediator in Miami-Dade
                County, Florida.
              </li>
              <li>
                <strong className="text-foreground">Arbitration:</strong> Any
                dispute not resolved through mediation shall be settled by
                binding arbitration in accordance with the rules of the American
                Arbitration Association, conducted in Miami-Dade County, Florida.
              </li>
            </ol>
            <p>
              These Terms shall be governed by and construed in accordance with
              the laws of the State of Florida, without regard to its conflict
              of laws provisions. You agree to submit to the personal
              jurisdiction of the courts located in Miami-Dade County, Florida.
            </p>
            <p>
              You agree that any claims will be brought on an individual basis
              and not as part of a class action, class arbitration, or
              representative proceeding.
            </p>
          </div>
        </section>

        {/* 9. Changes to Terms */}
        <section id="changes" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            9. Changes to Terms
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              Umuve reserves the right to modify or replace these Terms at any
              time. When we make material changes, we will:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Update the &quot;Last updated&quot; date at the top of this page
              </li>
              <li>
                Notify registered users via email or through the platform
              </li>
              <li>
                Provide at least 30 days&apos; notice before material changes
                take effect
              </li>
            </ul>
            <p>
              Your continued use of the Service after the effective date of any
              changes constitutes your acceptance of the revised Terms. If you
              do not agree with the updated Terms, you should discontinue use of
              the Service.
            </p>
          </div>
        </section>

        {/* 10. Contact Information */}
        <section id="contact" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            10. Contact Information
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              If you have any questions, concerns, or feedback about these Terms
              of Service, please contact us:
            </p>
            <div className="rounded-lg border border-border bg-muted/30 p-6 space-y-2">
              <p className="font-display font-semibold text-foreground">
                Umuve
              </p>
              <p>
                Email:{" "}
                <a
                  href="mailto:legal@goumuve.com"
                  className="text-primary hover:underline"
                >
                  legal@goumuve.com
                </a>
              </p>
              <p>
                Support:{" "}
                <a
                  href="mailto:support@goumuve.com"
                  className="text-primary hover:underline"
                >
                  support@goumuve.com
                </a>
              </p>
              <p>South Florida, United States</p>
            </div>
          </div>
        </section>
      </div>

      {/* Bottom Navigation */}
      <div className="border-t border-border pt-8 mt-12">
        <p className="text-sm text-muted-foreground">
          See also our{" "}
          <Link href="/privacy" className="text-primary hover:underline">
            Privacy Policy
          </Link>{" "}
          for information about how we collect, use, and protect your data.
        </p>
      </div>
    </article>
  );
}
