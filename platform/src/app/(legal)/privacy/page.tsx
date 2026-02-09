import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy - JunkOS",
  description:
    "Privacy Policy for JunkOS junk removal platform. Learn how we collect, use, and protect your personal information.",
};

const LAST_UPDATED = "February 9, 2026";

const TABLE_OF_CONTENTS = [
  { id: "information-collected", label: "1. Information We Collect" },
  { id: "how-we-use", label: "2. How We Use Your Information" },
  { id: "information-sharing", label: "3. Information Sharing" },
  { id: "data-security", label: "4. Data Security" },
  { id: "cookies", label: "5. Cookies & Tracking" },
  { id: "third-party", label: "6. Third-Party Services" },
  { id: "your-rights", label: "7. Your Rights (CCPA)" },
  { id: "data-retention", label: "8. Data Retention" },
  { id: "children", label: "9. Children's Privacy" },
  { id: "changes", label: "10. Changes to This Policy" },
  { id: "contact", label: "11. Contact Us" },
];

export default function PrivacyPolicyPage() {
  return (
    <article className="space-y-10">
      {/* Page Header */}
      <header className="space-y-4 border-b border-border pb-8">
        <h1 className="font-display text-4xl font-bold tracking-tight text-foreground">
          Privacy Policy
        </h1>
        <p className="text-sm text-muted-foreground">
          Last updated: {LAST_UPDATED}
        </p>
        <p className="text-base text-muted-foreground leading-relaxed">
          JunkOS (&quot;we,&quot; &quot;us,&quot; or &quot;our&quot;) is
          committed to protecting your privacy. This Privacy Policy explains
          how we collect, use, disclose, and safeguard your information when
          you use our platform and junk removal services. Please read this
          policy carefully.
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
        {/* 1. Information We Collect */}
        <section id="information-collected" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            1. Information We Collect
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <h3 className="font-display text-lg font-medium text-foreground">
              Information You Provide
            </h3>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong className="text-foreground">Account information:</strong>{" "}
                Name, email address, phone number, and password when you create
                an account
              </li>
              <li>
                <strong className="text-foreground">Booking details:</strong>{" "}
                Service address, item descriptions, photos of items to be
                removed, scheduling preferences, and special instructions
              </li>
              <li>
                <strong className="text-foreground">Payment information:</strong>{" "}
                Credit card or payment method details (processed and stored
                securely by Stripe; we do not store your full card number)
              </li>
              <li>
                <strong className="text-foreground">Communications:</strong>{" "}
                Messages, feedback, support requests, and any other
                communications you send to us
              </li>
            </ul>

            <h3 className="font-display text-lg font-medium text-foreground pt-2">
              Information Collected Automatically
            </h3>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong className="text-foreground">Device information:</strong>{" "}
                Browser type, operating system, device identifiers, and screen
                resolution
              </li>
              <li>
                <strong className="text-foreground">Usage data:</strong>{" "}
                Pages visited, features used, booking flow interactions,
                timestamps, and referring URLs
              </li>
              <li>
                <strong className="text-foreground">Location data:</strong>{" "}
                Approximate location derived from your IP address, and precise
                location when you provide a service address or enable location
                services
              </li>
              <li>
                <strong className="text-foreground">Log data:</strong>{" "}
                IP address, access times, and error logs for security and
                debugging purposes
              </li>
            </ul>
          </div>
        </section>

        {/* 2. How We Use Your Information */}
        <section id="how-we-use" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            2. How We Use Your Information
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>We use the information we collect to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Process and fulfill your junk removal bookings
              </li>
              <li>
                Match you with available Haulers in your area
              </li>
              <li>
                Process payments and send transaction confirmations
              </li>
              <li>
                Provide real-time tracking of your pickup
              </li>
              <li>
                Send booking confirmations, reminders, and status updates via
                email and SMS
              </li>
              <li>
                Respond to your support requests and communications
              </li>
              <li>
                Generate pricing estimates based on item photos and descriptions
              </li>
              <li>
                Improve and optimize our platform, services, and user experience
              </li>
              <li>
                Detect, prevent, and address fraud, security issues, and
                technical problems
              </li>
              <li>
                Comply with legal obligations and enforce our Terms of Service
              </li>
            </ul>
          </div>
        </section>

        {/* 3. Information Sharing */}
        <section id="information-sharing" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            3. Information Sharing
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              We do not sell your personal information. We may share your
              information in the following circumstances:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong className="text-foreground">With Haulers:</strong>{" "}
                When you make a booking, we share your name, service address,
                phone number, and job details with the assigned Hauler so they
                can perform the service
              </li>
              <li>
                <strong className="text-foreground">Service providers:</strong>{" "}
                We share data with third-party service providers who assist us
                in operating the platform (see Section 6 for details)
              </li>
              <li>
                <strong className="text-foreground">Legal requirements:</strong>{" "}
                We may disclose information when required by law, subpoena,
                court order, or government request
              </li>
              <li>
                <strong className="text-foreground">Safety:</strong>{" "}
                When we believe disclosure is necessary to protect the safety,
                rights, or property of JunkOS, our users, or the public
              </li>
              <li>
                <strong className="text-foreground">Business transfers:</strong>{" "}
                In connection with a merger, acquisition, or sale of assets,
                your information may be transferred as part of the transaction
              </li>
            </ul>
          </div>
        </section>

        {/* 4. Data Security */}
        <section id="data-security" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            4. Data Security
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              We implement industry-standard security measures to protect your
              personal information, including:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Encryption of data in transit using TLS/SSL protocols
              </li>
              <li>
                Encryption of sensitive data at rest
              </li>
              <li>
                PCI DSS-compliant payment processing through Stripe
              </li>
              <li>
                Regular security audits and vulnerability assessments
              </li>
              <li>
                Access controls limiting employee access to personal data on a
                need-to-know basis
              </li>
              <li>
                Secure authentication mechanisms for user accounts
              </li>
            </ul>
            <p>
              While we strive to protect your information, no method of
              electronic transmission or storage is 100% secure. We cannot
              guarantee absolute security, but we are committed to following
              best practices and promptly addressing any security incidents.
            </p>
          </div>
        </section>

        {/* 5. Cookies & Tracking */}
        <section id="cookies" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            5. Cookies & Tracking
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              We use cookies and similar tracking technologies to enhance your
              experience on our platform:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong className="text-foreground">Essential cookies:</strong>{" "}
                Required for the platform to function properly, including
                session management and authentication
              </li>
              <li>
                <strong className="text-foreground">Analytics cookies:</strong>{" "}
                Help us understand how visitors interact with our platform so
                we can improve the user experience
              </li>
              <li>
                <strong className="text-foreground">Functional cookies:</strong>{" "}
                Remember your preferences and settings across sessions
              </li>
            </ul>
            <p>
              You can control cookies through your browser settings. Disabling
              certain cookies may limit your ability to use some features of the
              platform. We do not use cookies for targeted advertising purposes.
            </p>
          </div>
        </section>

        {/* 6. Third-Party Services */}
        <section id="third-party" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            6. Third-Party Services
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              We rely on trusted third-party services to operate our platform.
              Each provider has their own privacy policy governing their
              handling of your data:
            </p>

            <div className="space-y-4 mt-4">
              <div className="rounded-lg border border-border p-4 space-y-1">
                <h4 className="font-display font-semibold text-foreground">
                  Stripe
                </h4>
                <p className="text-sm">
                  Payment processing. Stripe handles all credit card and payment
                  data in compliance with PCI DSS Level 1 standards. We never
                  see or store your full card number.
                </p>
                <a
                  href="https://stripe.com/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  Stripe Privacy Policy
                </a>
              </div>

              <div className="rounded-lg border border-border p-4 space-y-1">
                <h4 className="font-display font-semibold text-foreground">
                  Mapbox
                </h4>
                <p className="text-sm">
                  Mapping and geocoding. Used for address validation, route
                  optimization, and real-time Hauler tracking. Mapbox may
                  collect anonymized location data.
                </p>
                <a
                  href="https://www.mapbox.com/legal/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  Mapbox Privacy Policy
                </a>
              </div>

              <div className="rounded-lg border border-border p-4 space-y-1">
                <h4 className="font-display font-semibold text-foreground">
                  Twilio
                </h4>
                <p className="text-sm">
                  SMS notifications. Used to send booking confirmations, status
                  updates, and Hauler arrival notifications. Your phone number
                  is shared with Twilio for message delivery.
                </p>
                <a
                  href="https://www.twilio.com/legal/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  Twilio Privacy Policy
                </a>
              </div>

              <div className="rounded-lg border border-border p-4 space-y-1">
                <h4 className="font-display font-semibold text-foreground">
                  Resend
                </h4>
                <p className="text-sm">
                  Email delivery. Used for transactional emails such as booking
                  confirmations, receipts, and account notifications. Your email
                  address is shared with Resend for delivery.
                </p>
                <a
                  href="https://resend.com/legal/privacy-policy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  Resend Privacy Policy
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* 7. Your Rights (CCPA) */}
        <section id="your-rights" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            7. Your Rights (CCPA)
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              If you are a California resident, the California Consumer Privacy
              Act (CCPA) provides you with specific rights regarding your
              personal information:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong className="text-foreground">Right to Know:</strong>{" "}
                You have the right to request that we disclose the categories
                and specific pieces of personal information we have collected
                about you, the sources of that information, and the purposes
                for which it is used
              </li>
              <li>
                <strong className="text-foreground">Right to Delete:</strong>{" "}
                You have the right to request the deletion of your personal
                information, subject to certain exceptions (such as completing a
                transaction or complying with legal obligations)
              </li>
              <li>
                <strong className="text-foreground">Right to Opt-Out:</strong>{" "}
                You have the right to opt out of the sale of your personal
                information. JunkOS does not sell personal information
              </li>
              <li>
                <strong className="text-foreground">
                  Right to Non-Discrimination:
                </strong>{" "}
                We will not discriminate against you for exercising any of your
                CCPA rights
              </li>
              <li>
                <strong className="text-foreground">
                  Right to Correct:
                </strong>{" "}
                You have the right to request correction of inaccurate personal
                information we maintain about you
              </li>
            </ul>
            <p>
              To exercise any of these rights, please contact us at{" "}
              <a
                href="mailto:privacy@junkos.com"
                className="text-primary hover:underline"
              >
                privacy@junkos.com
              </a>
              . We will respond to verified requests within 45 days. You may
              also designate an authorized agent to submit a request on your
              behalf.
            </p>
            <p>
              In the preceding 12 months, we have collected the following
              categories of personal information: identifiers (name, email,
              phone), commercial information (booking history), internet
              activity (usage data), and geolocation data (service addresses).
            </p>
          </div>
        </section>

        {/* 8. Data Retention */}
        <section id="data-retention" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            8. Data Retention
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              We retain your personal information for as long as necessary to
              fulfill the purposes outlined in this Privacy Policy, unless a
              longer retention period is required by law:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong className="text-foreground">Account data:</strong>{" "}
                Retained for as long as your account is active. You may request
                account deletion at any time
              </li>
              <li>
                <strong className="text-foreground">Booking records:</strong>{" "}
                Retained for 7 years for tax, legal, and dispute resolution
                purposes
              </li>
              <li>
                <strong className="text-foreground">Payment records:</strong>{" "}
                Retained in accordance with financial regulatory requirements
                (typically 7 years)
              </li>
              <li>
                <strong className="text-foreground">Communication logs:</strong>{" "}
                Support conversations are retained for 2 years after resolution
              </li>
              <li>
                <strong className="text-foreground">Analytics data:</strong>{" "}
                Aggregated and anonymized analytics data may be retained
                indefinitely
              </li>
            </ul>
            <p>
              When your data is no longer needed, we will securely delete or
              anonymize it in accordance with our data retention procedures.
            </p>
          </div>
        </section>

        {/* 9. Children's Privacy */}
        <section id="children" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            9. Children&apos;s Privacy
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              JunkOS is not intended for use by individuals under the age of 18.
              We do not knowingly collect personal information from children
              under 18. If we become aware that we have collected personal
              information from a child under 18, we will take steps to promptly
              delete that information.
            </p>
            <p>
              If you are a parent or guardian and believe that your child has
              provided us with personal information, please contact us at{" "}
              <a
                href="mailto:privacy@junkos.com"
                className="text-primary hover:underline"
              >
                privacy@junkos.com
              </a>{" "}
              so we can take appropriate action.
            </p>
          </div>
        </section>

        {/* 10. Changes to This Policy */}
        <section id="changes" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            10. Changes to This Policy
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              We may update this Privacy Policy from time to time to reflect
              changes in our practices, technologies, legal requirements, or
              other factors. When we make material changes:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                We will update the &quot;Last updated&quot; date at the top of
                this page
              </li>
              <li>
                We will notify registered users via email or a prominent notice
                on our platform
              </li>
              <li>
                Material changes will take effect 30 days after notification
              </li>
            </ul>
            <p>
              We encourage you to review this Privacy Policy periodically to
              stay informed about how we protect your information.
            </p>
          </div>
        </section>

        {/* 11. Contact Us */}
        <section id="contact" className="scroll-mt-24 space-y-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">
            11. Contact Us
          </h2>
          <div className="space-y-3 text-muted-foreground leading-relaxed">
            <p>
              If you have any questions, concerns, or requests regarding this
              Privacy Policy or our data practices, please contact us:
            </p>
            <div className="rounded-lg border border-border bg-muted/30 p-6 space-y-2">
              <p className="font-display font-semibold text-foreground">
                JunkOS - Privacy Team
              </p>
              <p>
                Email:{" "}
                <a
                  href="mailto:privacy@junkos.com"
                  className="text-primary hover:underline"
                >
                  privacy@junkos.com
                </a>
              </p>
              <p>
                General Support:{" "}
                <a
                  href="mailto:support@junkos.com"
                  className="text-primary hover:underline"
                >
                  support@junkos.com
                </a>
              </p>
              <p>South Florida, United States</p>
            </div>
            <p>
              For CCPA-related requests, please include &quot;CCPA Request&quot;
              in the subject line of your email. We will respond to all
              privacy-related inquiries within 30 days.
            </p>
          </div>
        </section>
      </div>

      {/* Bottom Navigation */}
      <div className="border-t border-border pt-8 mt-12">
        <p className="text-sm text-muted-foreground">
          See also our{" "}
          <Link href="/terms" className="text-primary hover:underline">
            Terms of Service
          </Link>{" "}
          for the terms governing your use of our platform.
        </p>
      </div>
    </article>
  );
}
