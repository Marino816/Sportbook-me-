import type { Metadata } from "next";
export const metadata: Metadata = { title: "Careers — SB ME DFS.AI", description: "Career opportunities at SB ME DFS.AI." };

import Link from "next/link";
import { LegalPage, P } from "@/components/legal/legal-page";

export default function CareersPage() {
  return (
    <LegalPage title="Careers" lastUpdated="August 14, 2026">
      <P>
        We&rsquo;re building the future of sports intelligence and daily fantasy sports analytics. We don&rsquo;t
        have open roles posted right now, but we&rsquo;re always interested in hearing from talented people.
      </P>
      <P>
        To express interest in future opportunities, reach out through the{" "}
        <Link href="/contact" style={{ color: "#c9a84c" }}>Contact page</Link>.
      </P>
    </LegalPage>
  );
}
