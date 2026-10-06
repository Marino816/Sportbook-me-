import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Delete Your Sportbook Me DFS AI Account — SB ME DFS.AI",
  description:
    "Request deletion of your Sportbook Me DFS AI account and associated app data. This page loads without signing in. Ownership is verified before anything is deleted.",
};

import Link from "next/link";
import { LegalPage, H2, P, UL, LI, gold } from "@/components/legal/legal-page";
import { DeleteAccountForm } from "./delete-account-form";

export default function DeleteAccountPage() {
  return (
    <LegalPage title="Delete Your Sportbook Me DFS AI Account" lastUpdated="October 6, 2026">
      <P>
        This page is the account-deletion request for <strong style={{ color: "#f0f6fc" }}>Sportbook Me DFS AI</strong>
        {" "}(website <strong style={{ color: "#f0f6fc" }}>sbmedfsai.com</strong>, Android package{" "}
        <strong style={{ color: "#f0f6fc" }}>com.sportbookme.app</strong>).
        You can open it without signing in to the Android or iOS app.
      </P>

      <DeleteAccountForm />

      <H2>How to request deletion</H2>
      <UL>
        <LI>Open this page at https://sbmedfsai.com/delete-account. No app login is required to read these instructions.</LI>
        <LI>Sign in on the website with the Sportbook Me account you want deleted. Signing in is how we verify ownership. We do not delete an account from an email address typed into an unauthenticated form.</LI>
        <LI>Check the confirmation box, type DELETE, and submit <em>Permanently delete account</em>.</LI>
        <LI>When the request succeeds, deletion has already completed in that same request. You are signed out. There is no support-ticket queue and no extra waiting period in this workflow.</LI>
      </UL>

      <H2>What is deleted when the request succeeds</H2>
      <P>We delete the verified account and associated user-owned Sportbook Me app data, including:</P>
      <UL>
        <LI>Login identifiers (email and password hash) and the user record;</LI>
        <LI>Saved lineups and lineup history;</LI>
        <LI>AI conversation transcripts, assistant preferences, and AI chat usage rows (including conversation ids, tool payloads, and error text);</LI>
        <LI>Optimizer/builder runs, coach sessions, scout alerts, and mission-control preferences tied to the account;</LI>
        <LI>OAuth and Apple account-binding rows, and billing entitlement rows, when those tables exist.</LI>
      </UL>
      <P>
        Access tokens issued for that login stop working on the same request: protected API routes load the user
        record from the database, and that record is gone. This product does not issue or store refresh tokens.
      </P>

      <H2>What is retained, why, and for how long</H2>
      <P>
        Payment and accounting records may be kept after the login is removed: Stripe subscription and revenue
        rows, and billing checkout rows when present. Those rows have the user identifier set to null so they
        are no longer attached to the deleted login. They are kept for tax, accounting, and payment-dispute
        obligations.
      </P>
      <P>
        AI audit rows that store only hashed request/response fingerprints, token/cost counters, and the
        endpoint name may be kept for cost accounting and security monitoring. The user identifier and any
        plaintext error text on those rows are removed. Ordinary chat content is not kept there.
      </P>
      <P>
        Shared sports data (players, slates, projections) is not user-owned and is not deleted. Stripe webhook
        event ids used for payment idempotency are not user-linked and stay.
      </P>
      <P>
        This workflow does not run a timed purge job. Retained accounting and hashed audit records are kept for
        as long as needed to comply with legal, tax, fraud-prevention, and accounting obligations, matching the
        retention described in our{" "}
        <Link href="/privacy" style={{ color: gold }}>Privacy Policy</Link>
        . There is no separate numbered retention clock implemented in the deletion code.
      </P>

      <H2>Cancel subscriptions before you delete</H2>
      <P>
        Deleting a Sportbook Me account removes Sportbook Me access for that login. It does not cancel billing
        with Apple, Google Play, Stripe, or PayKings. Cancel with the provider first if you want charges to stop.
        After deletion you can still cancel through the store or by emailing support, but you will not be able
        to open in-app billing for that login.
      </P>
      <UL>
        <LI>
          Apple App Store:{" "}
          <a href="https://apps.apple.com/account/subscriptions" style={{ color: gold }}>
            apps.apple.com/account/subscriptions
          </a>
        </LI>
        <LI>
          Google Play:{" "}
          <a href="https://play.google.com/store/account/subscriptions" style={{ color: gold }}>
            play.google.com/store/account/subscriptions
          </a>
        </LI>
        <LI>
          Stripe (website checkout): sign in, open{" "}
          <Link href="/billing" style={{ color: gold }}>Billing</Link>
          , and use Manage in Stripe before you delete the account.
        </LI>
        <LI>
          PayKings: this release has no PayKings customer portal. Email{" "}
          <a href="mailto:support@sbmedfsai.com" style={{ color: gold }}>support@sbmedfsai.com</a>
          {" "}with your account email and ask to cancel PayKings billing before you delete.
        </LI>
      </UL>

      <H2>Questions</H2>
      <P>
        For billing cancellation help or questions that are not this deletion request, email{" "}
        <a href="mailto:support@sbmedfsai.com" style={{ color: gold }}>support@sbmedfsai.com</a>
        {" "}or use our{" "}
        <Link href="/contact" style={{ color: gold }}>Contact page</Link>.
      </P>
    </LegalPage>
  );
}
