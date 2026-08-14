import type { Metadata } from "next";
export const metadata: Metadata = { title: "Refund & Cancellation Policy — SB ME DFS.AI", description: "Refund and cancellation policy for SB ME DFS.AI subscriptions, including Starter, Pro Arena, and Elite Stack plans." };

import Link from "next/link";
import { LegalPage, H2, H3, P, UL, LI, SUPPORT_EMAIL, gold } from "@/components/legal/legal-page";

export default function RefundPolicyPage() {
  return (
    <LegalPage title="Refund & Cancellation Policy" lastUpdated="August 14, 2026">
      <P>
        This Refund &amp; Cancellation Policy describes the terms under which you may cancel your SB ME DFS.AI
        subscription and the circumstances under which refunds may be available.
      </P>

      <H2>Subscription Plans</H2>
      <P>The Service offers the following subscription plans:</P>
      <UL>
        <LI><strong style={{ color: "#f0f6fc" }}>Starter</strong> — Free ($0/month). No billing information required.</LI>
        <LI><strong style={{ color: "#f0f6fc" }}>Pro Arena</strong> — $29/month. Includes expanded analytical features.</LI>
        <LI><strong style={{ color: "#f0f6fc" }}>Elite Stack</strong> — $79/month. Includes all available features.</LI>
      </UL>
      <P>Annual billing options may also be available for paid plans at a discounted rate.</P>

      <H2>Automatic Renewal</H2>
      <P>
        Paid subscriptions (Pro Arena and Elite Stack) renew automatically each billing period (monthly or annually,
        as applicable) until cancelled. The renewal charge will be processed through our payment processor at the
        start of each renewal period, using the payment method on file. You may cancel future renewal at any time
        as described below.
      </P>

      <H2>Cancellation</H2>
      <P>
        You may cancel your paid subscription at any time through the billing portal accessible from your account.
        When you cancel:
      </P>
      <UL>
        <LI>Future recurring charges are stopped;</LI>
        <LI>Your access to paid features ordinarily continues through the end of the already-paid billing period;</LI>
        <LI>At the end of that period, your account will revert to the free Starter plan and paid features will no longer be available.</LI>
      </UL>

      <H2>How to Cancel</H2>
      <P>
        To cancel your subscription:
      </P>
      <UL>
        <LI>Sign in to your SB ME DFS.AI account;</LI>
        <LI>Navigate to the Billing page;</LI>
        <LI>Use the Stripe Customer Portal to manage or cancel your subscription;</LI>
        <LI>Follow the cancellation prompts.</LI>
      </UL>
      <P>
        Your cancellation is effective once completed through the Customer Portal. We recommend completing
        cancellation at least one business day before your next renewal date to avoid the next charge.
      </P>

      <H2>Refund Policy</H2>
      <P>
        Paid subscriptions are generally non-refundable. By purchasing a subscription, you acknowledge that
        you will have immediate access to the paid features after payment, and you agree that charges are
        generally not refundable once incurred.
      </P>
      <P>
        However, we will review refund requests on a case-by-case basis in the following circumstances:
      </P>
      <UL>
        <LI>Duplicate charges or billing errors;</LI>
        <LI>Unauthorized charges (charges you did not authorize);</LI>
        <LI>Technical issues that prevented you from accessing paid features for a significant portion of the billing period;</LI>
        <LI>Other exceptional circumstances at our discretion.</LI>
      </UL>
      <P>
        This refund policy is subject to applicable law. If your jurisdiction provides a statutory right of
        withdrawal or cancellation that applies to our Service, we will honor that right in accordance with
        applicable law. Nothing in this policy limits your rights under applicable consumer protection laws.
      </P>

      <H2>Upgrades and Downgrades</H2>
      <P>
        Upgrades from a lower-tier to a higher-tier paid plan (for example, from Pro Arena to Elite Stack) take
        effect immediately and the price difference for the remaining portion of the current billing period may
        be charged on a prorated basis or applied at the next renewal, depending on the plan change. Please
        contact us at <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: gold }}>{SUPPORT_EMAIL}</a> for details about plan changes.
      </P>
      <P>
        Downgrades from a higher-tier to a lower-tier paid plan (for example, from Elite Stack to Pro Arena)
        take effect at the end of the current billing period. Your access to higher-tier features continues
        through the end of the already-paid period.
      </P>

      <H2>Duplicate or Erroneous Charges</H2>
      <P>
        If you believe you have been charged in error, or if you see duplicate charges on your payment method,
        please contact us immediately at <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: gold }}>{SUPPORT_EMAIL}</a>.
        We will investigate and, where appropriate, issue a refund for any erroneous charges.
      </P>

      <H2>Contact Regarding Billing</H2>
      <P>
        For billing questions, refund requests, or subscription support, contact us at <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: gold }}>{SUPPORT_EMAIL}</a> or
        through the <Link href="/contact" style={{ color: gold }}>Contact page</Link>.
        Please include your account email and relevant details about your inquiry.
      </P>
    </LegalPage>
  );
}
