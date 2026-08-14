import type { Metadata } from "next";
export const metadata: Metadata = { title: "Blog — SB ME DFS.AI", description: "Sports analytics and daily fantasy sports articles from SB ME DFS.AI." };

import Link from "next/link";
import { LegalPage, P } from "@/components/legal/legal-page";

export default function BlogPage() {
  return (
    <LegalPage title="Blog" lastUpdated="August 14, 2026">
      <P>
        The SB ME DFS.AI blog is coming soon. We&rsquo;ll be publishing articles on sports analytics, daily
        fantasy sports strategy, lineup building, and product updates.
      </P>
      <P>
        In the meantime, explore the <Link href="/" style={{ color: "#c9a84c" }}>platform</Link> or reach out
        to our team through the <Link href="/contact" style={{ color: "#c9a84c" }}>Contact page</Link>.
      </P>
    </LegalPage>
  );
}
