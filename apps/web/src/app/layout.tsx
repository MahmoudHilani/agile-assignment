import type { Metadata } from "next";
import "./globals.css";
import CompanyLogo from "@/components/CompanyLogo";
import AdminHeader from "@/components/AdminHeader";
import { AdminAuthProvider } from "@/context/AdminAuthContext";

export const metadata: Metadata = {
  title: "AgileMind",
  description: "Company AI Assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AdminAuthProvider>
          <header className="app-header">
            <CompanyLogo />
            <AdminHeader />
          </header>
          <div className="app-content">
            {children}
          </div>
        </AdminAuthProvider>
      </body>
    </html>
  );
}
