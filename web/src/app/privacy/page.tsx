import type { Metadata } from "next";
export const metadata: Metadata = { title: "Privacy Policy — SB ME DFS.AI", description: "Privacy Policy for SB ME DFS.AI. How we collect, use, and protect your personal information." };

import Link from "next/link";
import { LegalPage, H2, H3, P, UL, LI, SUPPORT_EMAIL, gold } from "@/components/legal/legal-page";

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" lastUpdated="August 14, 2026">
      <P>
        SPORTBOOK ME DFS AI LLC (&ldquo;SB ME DFS.AI,&rdquo; &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;)
        operates the SB ME DFS.AI website, applications, and services (the &ldquo;Service&rdquo;). This Privacy Policy
        explains how we collect, use, disclose, and protect your personal information when you use the Service.
      </P>

      <H2>1. Information You Provide</H2>
      <H3>Account & Profile Information</H3>
      <P>
        When you create an account, we collect information such as your name, email address, and account
        credentials. You may also provide additional profile information in the course of using the Service.
      </P>
      <H3>Subscription & Transaction Information</H3>
      <P>
        When you purchase a paid subscription, we collect information about your plan selection and
        subscription status. Payment information (such as credit card details) is processed and stored by our
        third-party payment processor and is not stored directly by SB ME DFS.AI.
      </P>
      <H3>Customer Support Communications</H3>
      <P>
        When you contact us for support, we collect the information you provide in your communication, including
        your email address and any details you share about your inquiry.
      </P>

      <H2>2. Information Collected Automatically</H2>
      <H3>Device, Browser & Log Information</H3>
      <P>
        We automatically collect certain information when you access the Service, including your IP address,
        browser type, operating system, device information, referring URLs, pages visited, and the dates and
        times of your visits.
      </P>
      <H3>Cookies & Similar Technologies</H3>
      <P>
        We and our service providers may use cookies, web beacons, and similar technologies to operate the
        Service, maintain sessions, remember preferences, analyze usage, and improve the Service. You can manage
        cookie preferences through your browser settings, but disabling certain cookies may affect the
        functionality of the Service.
      </P>
      <H3>Product Usage Information</H3>
      <P>
        We collect information about how you interact with the Service, including features used, queries
        submitted, pages accessed, and time spent on various sections, to improve and develop the Service.
      </P>

      <H2>3. Purposes for Processing Information</H2>
      <P>We use the information we collect for the following purposes:</P>
      <UL>
        <LI>To provide, operate, and maintain the Service;</LI>
        <LI>To process subscriptions and manage accounts;</LI>
        <LI>To communicate with you about your account, subscriptions, and Service updates;</LI>
        <LI>To respond to customer support inquiries;</LI>
        <LI>To analyze and improve the Service and develop new features;</LI>
        <LI>To detect, prevent, and address fraud, abuse, and security incidents;</LI>
        <LI>To comply with legal obligations and enforce our Terms of Service;</LI>
        <LI>To send administrative and informational communications (you may opt out of marketing communications).</LI>
      </UL>

      <H2>4. Third-Party Service Providers</H2>
      <H3>Payment Processors</H3>
      <P>
        We use Stripe as our payment processor. When you purchase a subscription, your payment information is
        transmitted to and processed by Stripe. Stripe&rsquo;s use of your personal information is governed by
        their privacy policy. SB ME DFS.AI does not store full credit card numbers or complete payment
        credentials on our servers.
      </P>
      <H3>Analytics & Infrastructure Providers</H3>
      <P>
        We may engage third-party service providers for analytics, hosting, infrastructure, monitoring, and
        other operational purposes. These providers process information on our behalf under contractual terms
        that require appropriate data protection.
      </P>
      <H3>Sports Data Providers</H3>
      <P>
        We work with third-party sports data and odds providers to deliver the analytical content within the
        Service. These providers receive query-level data in order to fulfill data requests but do not receive
        personal account information.
      </P>

      <H2>5. Data Retention</H2>
      <P>
        We retain personal information for as long as necessary to provide the Service, comply with legal
        obligations, resolve disputes, and enforce our agreements. When information is no longer needed, we
        take reasonable steps to delete or de-identify it.
      </P>

      <H2>6. Security</H2>
      <P>
        We implement reasonable administrative, technical, and physical safeguards designed to protect your
        personal information. However, no method of electronic storage or transmission is completely secure, and
        we cannot guarantee absolute security.
      </P>

      <H2>7. Disclosures Required by Law</H2>
      <P>
        We may disclose personal information if required by law, regulation, legal process, or governmental
        request, or to protect the rights, property, or safety of SB ME DFS.AI, our users, or the public, in
        accordance with applicable law.
      </P>

      <H2>8. Business Transfers</H2>
      <P>
        In the event of a merger, acquisition, reorganization, sale of assets, or similar transaction, user
        information may be transferred as part of that transaction. We will provide notice if your information
        becomes subject to a different privacy policy.
      </P>

      <H2>9. Children&rsquo;s Privacy</H2>
      <P>
        The Service is not directed to individuals under the age of 18. We do not knowingly collect personal
        information from children. If we learn that we have collected personal information from a child, we
        will take steps to delete it promptly.
      </P>

      <H2>10. Your Privacy Rights</H2>
      <P>
        Depending on your jurisdiction, you may have rights regarding your personal information, including the
        right to access, correct, delete, or port your data, and the right to opt out of certain processing.
        To exercise these rights, please contact us at <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: gold }}>{SUPPORT_EMAIL}</a>.
        We will respond to verified requests in accordance with applicable law.
      </P>

      <H2>11. Changes to This Privacy Policy</H2>
      <P>
        We may update this Privacy Policy from time to time. We will post the updated version with a new
        &ldquo;Last Updated&rdquo; date. Your continued use of the Service after the effective date constitutes
        your acceptance of the updated Privacy Policy.
      </P>

      <H2>12. Contact</H2>
      <P>
        Questions or requests about this Privacy Policy may be directed to us at <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: gold }}>{SUPPORT_EMAIL}</a> or
        through the <Link href="/contact" style={{ color: gold }}>Contact page</Link>.
      </P>
    </LegalPage>
  );
}
