"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AdminSidebar } from "@/components/admin/Sidebar";
import { useAuth } from "@/lib/auth";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isAuthenticated, isLoading, isAdmin } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!isAdmin) {
      router.replace("/dashboard");
      return;
    }
  }, [isLoading, isAuthenticated, isAdmin, router]);

  // Show nothing while redirecting
  if (isLoading || !isAuthenticated || !isAdmin) {
    return (
      <div className="flex min-h-screen bg-[#0F1115] items-center justify-center">
        <div className="text-[#A1A1A1] text-sm font-bold">Verifying access...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#0F1115]">
      <AdminSidebar />
      <main className="flex-1 ml-64 min-h-screen">{children}</main>
    </div>
  );
}
