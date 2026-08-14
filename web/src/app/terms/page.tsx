import type { Metadata } from "next";
export const metadata: Metadata = { title: "Terms of Service — SB ME DFS.AI", description: "Terms of Service for SB ME DFS.AI, the sports analytics and daily fantasy sports intelligence software platform." };

import Link from "next/link";
import { LegalPage, H2, H3, P, UL, LI, SUPPORT_EMAIL, gold } from "@/components/legal/legal-page";

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" lastUpdated="August 14, 2026">
      <P>
        These Terms of Service (&ldquo;Terms&rdquo;) govern your access to and use of the SB ME DFS.AI
        website, applications, and services (collectively, the &ldquo;Service&rdquo;), operated by
        SPORTBOOK ME DFS AI LLC (&ldquo;SB ME DFS.AI,&rdquo; &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;).
        By creating an account or otherwise accessing or using the Service, you agree to be bound by these Terms.
      </P>

      <H2>1. Acceptance of Terms</H2>
      <P>
        By accessing or using the Service, you agree to these Terms and to our Privacy Policy. If you do not agree
        to these Terms, you may not access or use the Service. We may update these Terms from time to time as
        described in Section 20 below.
      </P>

      <H2>2. Description of Service</H2>
      <P>
        SB ME DFS.AI is a subscription-based sports analytics and daily fantasy sports intelligence software
        platform. The Service provides analytical tools including sports data, statistical analysis, player
        projections, lineup optimization, player-prop analysis, odds information, market information, and
        AI-assisted sports intelligence. Customers purchase access to software and analytical features.
      </P>
      <P>
        SB ME DFS.AI provides sports analytics, informational tools, projections and daily fantasy sports
        intelligence software. SB ME DFS.AI is not a sportsbook, bookmaker, casino, gambling operator or
        paid-entry fantasy contest operator. We do not accept or place wagers, collect contest entry fees,
        maintain gambling balances, or award monetary or material prizes based on sporting-event outcomes.
      </P>

      <H2>3. Eligibility and Accounts</H2>
      <P>
        You must be at least 18 years old (or the age of majority in your jurisdiction) to use the Service.
        You are responsible for maintaining the confidentiality of your account credentials and for all
        activity that occurs under your account. You agree to provide accurate and complete information when
        creating your account and to keep that information up to date.
      </P>

      <H2>4. Subscription Plans</H2>
      <P>
        The Service offers subscription plans, including a free Starter plan and paid plans such as Pro Arena
        ($29/month) and Elite Stack ($79/month). Plan features and pricing are described on our website and are
        subject to change. Paid subscriptions provide access to additional analytical features for the duration
        of the subscription period.
      </P>

      <H2>5. Billing and Automatic Renewal</H2>
      <P>
        Paid subscriptions renew automatically each billing period (monthly or annually, as applicable) until
        cancelled. By purchasing a paid subscription, you authorize us (through our payment processor) to charge
        your payment method for the subscription amount on a recurring basis. Payment information is processed
        through our third-party payment processor and is not stored directly by SB ME DFS.AI.
      </P>

      <H2>6. Cancellation</H2>
      <P>
        You may cancel your subscription at any time through the billing portal available in your account.
        Cancellation stops future recurring charges. Your access to paid features ordinarily continues through
        the end of the already-paid billing period, after which your account will revert to the free Starter
        plan. See our Refund &amp; Cancellation Policy for further details.
      </P>

      <H2>7. Refund Policy</H2>
      <P>
        Our refund and cancellation terms are set out in our Refund &amp; Cancellation Policy, which is
        incorporated into these Terms by reference. Please review that policy before purchasing a subscription.
      </P>

      <H2>8. Sports Analytics / DFS Intelligence Services</H2>
      <P>
        The Service provides analytical and informational tools for daily fantasy sports and sports analysis.
        Projections, optimization results, odds information, player-prop information, AI responses, and other
        analytics produced by the Service are estimates and informational outputs based on statistical models,
        third-party data, and available information. Such outputs are provided for entertainment and informational
        purposes only.
      </P>

      <H2>9. No Gambling or Wagering Services</H2>
      <P>
        SB ME DFS.AI does not operate a sportsbook or casino; does not accept or place wagers; does not accept
        gambling deposits; does not hold customer gambling balances; does not operate paid-entry fantasy contests;
        does not collect contest entry fees; does not award monetary or material prizes based on sporting outcomes;
        does not process wagers for sportsbooks; and does not act as a bookmaker. Sportsbook odds, lines, player
        props, and similar information displayed by the Service are provided as sports-data and analytical
        information only.
      </P>

      <H2>10. No Guaranteed Results</H2>
      <P>
        SB ME DFS.AI does not guarantee winnings, profits, or successful DFS lineups.
        All analytics and projections are estimates, and actual outcomes may differ materially. Sports outcomes
        are inherently uncertain, and you acknowledge that you are solely responsible for your decisions and
        for any outcomes resulting from them.
      </P>

      <H2>11. Third-Party Sportsbooks and DFS Platforms</H2>
      <P>
        The Service may display odds, lines, and other information relating to third-party sportsbooks and
        daily fantasy sports platforms. SB ME DFS.AI is not affiliated with, endorsed by, or responsible for any
        such third-party platform. Users independently decide whether and how to use information produced by the
        Service and are responsible for complying with applicable laws and the rules of any third-party platform
        they use.
      </P>

      <H2>12. Third-Party Data</H2>
      <P>
        The Service incorporates sports data, odds, lines, and other information from third-party data providers.
        While we endeavor to provide accurate and timely information, we do not guarantee the accuracy,
        completeness, or availability of third-party data. Odds and lines may be delayed, inaccurate, or
        subject to change without notice.
      </P>

      <H2>13. User Responsibilities</H2>
      <P>
        You are solely responsible for your use of the Service, including any decisions made based on Service
        output, and for compliance with all applicable laws, regulations, and third-party platform rules. You
        are responsible for determining whether your use of the Service is lawful in your jurisdiction.
      </P>

      <H2>14. Acceptable Use</H2>
      <P>You agree not to:</P>
      <UL>
        <LI>Use the Service for any unlawful purpose or in violation of these Terms;</LI>
        <LI>Attempt to gain unauthorized access to the Service, other users&rsquo; accounts, or our systems;</LI>
        <LI>Interfere with or disrupt the Service, its servers, or networks;</LI>
        <LI>Reverse engineer, decompile, or disassemble any part of the Service;</LI>
        <LI>Scrape, harvest, or systematically collect data from the Service without authorization;</LI>
        <LI>Resell, sublicense, or redistribute Service output or data except as expressly permitted;</LI>
        <LI>Misrepresent your identity or affiliation; or</LI>
        <LI>Use automated means to abuse or overload the Service.</LI>
      </UL>

      <H2>15. Intellectual Property</H2>
      <P>
        The Service, including its software, design, branding, logos, trademarks, and content, is owned by
        SB ME DFS.AI or its licensors and is protected by intellectual property laws. Subject to your compliance
        with these Terms, we grant you a limited, non-exclusive, non-transferable, revocable license to access
        and use the Service for your personal use. &ldquo;SB ME DFS.AI&rdquo; and &ldquo;SB ME Intelligent AI&rdquo;
        are trademarks of SPORTBOOK ME DFS AI LLC.
      </P>

      <H2>16. Account Suspension / Termination</H2>
      <P>
        We may suspend or terminate your access to the Service, in whole or in part, at any time, with or without
        notice, if we reasonably believe you have violated these Terms, if required by law, or for operational or
        security reasons. Upon termination, your right to use the Service ceases immediately.
      </P>

      <H2>17. Service Availability</H2>
      <P>
        We strive to keep the Service available but do not guarantee uninterrupted or error-free operation. The
        Service may be unavailable from time to time for maintenance, upgrades, or reasons beyond our control.
        Features may change or be discontinued over time.
      </P>

      <H2>18. Disclaimers</H2>
      <P>
        THE SERVICE IS PROVIDED ON AN &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE&rdquo; BASIS WITHOUT WARRANTIES
        OF ANY KIND, WHETHER EXPRESS OR IMPLIED, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
        PURPOSE, NON-INFRINGEMENT, OR ACCURACY. TO THE MAXIMUM EXTENT PERMITTED BY LAW, WE DISCLAIM ALL SUCH
        WARRANTIES.
      </P>

      <H2>19. Limitation of Liability</H2>
      <P>
        TO THE MAXIMUM EXTENT PERMITTED BY LAW, SB ME DFS.AI AND ITS AFFILIATES, OFFICERS, EMPLOYEES, AND AGENTS
        SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR FOR ANY
        LOSS OF PROFITS, DATA, OR GOODWILL, ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF THE SERVICE, EVEN IF
        ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. IN NO EVENT SHALL OUR AGGREGATE LIABILITY EXCEED THE AMOUNTS
        YOU PAID TO US FOR THE SERVICE IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.
      </P>

      <H2>20. Indemnification</H2>
      <P>
        You agree to indemnify and hold harmless SB ME DFS.AI and its affiliates, officers, employees, and agents
        from any claims, liabilities, damages, and expenses (including reasonable attorneys&rsquo; fees) arising
        out of your use of the Service, your violation of these Terms, or your violation of any law or third-party
        rights.
      </P>

      <H2>21. Governing Law</H2>
      <P>
        These Terms are governed by and construed in accordance with the laws of the United States and the state
        in which SPORTBOOK ME DFS AI LLC is organized, without regard to conflict-of-law principles. Any dispute
        arising out of these Terms shall be subject to the exclusive jurisdiction of the applicable courts in
        that state.
      </P>

      <H2>22. Changes to Terms</H2>
      <P>
        We may update these Terms from time to time. Material changes will be communicated by posting an updated
        &ldquo;Last Updated&rdquo; date and, where appropriate, by other notice. Your continued use of the Service
        after the updated Terms become effective constitutes your acceptance of the revised Terms.
      </P>

      <H2>23. Contact Information</H2>
      <P>
        Questions about these Terms may be directed to us at <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: gold }}>{SUPPORT_EMAIL}</a> or
        through the <Link href="/contact" style={{ color: gold }}>Contact page</Link>.
      </P>
    </LegalPage>
  );
}
