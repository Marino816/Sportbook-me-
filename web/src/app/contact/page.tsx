import type { Metadata } from "next";
export const metadata: Metadata = { title: "Customer Support — SB ME DFS.AI", description: "Contact SB ME DFS.AI customer support for account, billing, subscription, refund, and privacy requests." };

import { LegalPage, H2, P, SUPPORT_EMAIL } from "@/components/legal/legal-page";
import { Mail, User, CreditCard, RotateCcw, ShieldCheck } from "lucide-react";

const gold = "#c9a84c";
const cardBg = "#0a0f24";
const cardElevated = "#10162f";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";
const textMuted = "#64748b";

export default function ContactPage() {
  const categories = [
    { icon: Mail, title: "General Support", desc: "General questions about the platform, features, or your account." },
    { icon: User, title: "Account Support", desc: "Help with sign-in, account settings, or profile issues." },
    { icon: CreditCard, title: "Billing & Subscription Support", desc: "Questions about plans, charges, upgrades, downgrades, or cancellation." },
    { icon: RotateCcw, title: "Refund Requests", desc: "Requests related to refunds or erroneous charges. See our Refund & Cancellation Policy." },
    { icon: ShieldCheck, title: "Privacy Requests", desc: "Requests to access, correct, or delete your personal information." },
  ];

  return (
    <LegalPage title="Customer Support" lastUpdated="August 14, 2026">
      <P>
        We&rsquo;re here to help. For any support, billing, account, or privacy inquiry, please email our
        support team and include your account email and a clear description of your request so we can assist
        you quickly.
      </P>

      <div className="rounded-2xl border p-6 mb-8 flex items-center gap-4" style={{ background: cardElevated, borderColor: border }}>
        <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: `${gold}10` }}>
          <Mail size={22} style={{ color: gold }} />
        </div>
        <div>
          <div className="text-xs font-bold tracking-widest uppercase mb-1" style={{ color: textMuted }}>Support Email</div>
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-lg font-extrabold" style={{ color: gold }}>{SUPPORT_EMAIL}</a>
        </div>
      </div>

      <H2>Support Categories</H2>
      <div className="grid sm:grid-cols-2 gap-4 mb-6">
        {categories.map((c, i) => {
          const Icon = c.icon;
          return (
            <div key={i} className="rounded-2xl border p-5" style={{ background: cardElevated, borderColor: border }}>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${gold}10` }}>
                  <Icon size={18} style={{ color: gold }} />
                </div>
                <h3 className="text-sm font-extrabold" style={{ color: textPrimary }}>{c.title}</h3>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: textSecondary }}>{c.desc}</p>
            </div>
          );
        })}
      </div>

      <H2>Billing & Subscription Help</H2>
      <P>
        To cancel or manage your subscription, sign in to your account and use the Stripe Customer Portal
        available on the Billing page. For billing questions or refund requests, email us at{" "}
        <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: gold }}>{SUPPORT_EMAIL}</a>.
      </P>

      <H2>Response Time</H2>
      <P>
        We aim to respond to support inquiries within 1–2 business days. Please note that we do not provide
        gambling, wagering, or investment advice, and we cannot guarantee any particular outcome from use of the
        Service.
      </P>
    </LegalPage>
  );
}
