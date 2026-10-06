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
        <LI>AI conversation history and assistant preferences;</LI>
        <LI>Optimizer/builder runs, coach sessions, scout alerts, and mission-control preferences tied to the account;</LI>
        <LI>OAuth and Apple account-binding rows, and billing entitlement rows, when those tables exist.</LI>
      </UL>

      <H2>What is retained, why, and for how long</H2>
      <P>
        Payment and accounting records may be kept after the login is removed: Stripe subscription and revenue
        rows, AI usage/audit logs, and billing checkout rows when present. Those rows have the user identifier
        set to null so they are no longer attached to the deleted login. Shared sports data (players, slates,
        projections) is not user-owned and is not deleted. Stripe webhook event ids used for payment
        idempotency are not user-linked and stay.
      </P>
      <P>
        This workflow does not run a timed purge job. Retained accounting records are kept for as long as needed
        to comply with legal, tax, fraud-prevention, and accounting obligations, matching the retention
        described in our{" "}
        <Link href="/privacy" style={{ color: gold }}>Privacy Policy</Link>
        : personal information is kept as long as necessary for those purposes, then deleted or de-identified.
        There is no separate numbered retention clock implemented in the deletion code.
      </P>

      <H2>Subscriptions</H2>
      <P>
        Deleting a Sportbook Me account removes Sportbook Me access for that login. It does not cancel billing
        with Apple, Google Play, or Stripe. If you subscribed through the App Store, manage or cancel it in
        Apple ID subscription settings. If you subscribed through Google Play, manage or cancel it in Google Play
        subscriptions. If you subscribed through Stripe on the website, cancel in Billing before or after
        deleting the account; leftover Stripe subscription and revenue rows may remain with the user identifier
        removed.
      </P>
      <P>
        Apple subscriptions:{" "}
        <a href="https://apps.apple.com/account/subscriptions" style={{ color: gold }}>
          apps.apple.com/account/subscriptions
        </a>
        . Google Play subscriptions:{" "}
        <a href="https://play.google.com/store/account/subscriptions" style={{ color: gold }}>
          play.google.com/store/account/subscriptions
        </a>
        .
      </P>

      <H2>Questions</H2>
      <P>
        For questions that are not this deletion request, use our{" "}
        <Link href="/contact" style={{ color: gold }}>Contact page</Link>.
      </P>
    </LegalPage>
  );
}
