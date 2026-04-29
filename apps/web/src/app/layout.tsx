import type { Metadata } from "next";
import "./globals.css";
import CompanyLogo from "@/components/CompanyLogo";

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
    <html lang="en">
      <body>
        <header className="app-header">
          <CompanyLogo />
        </header>
        <div className="app-content">
          {children}
        </div>
      </body>
    </html>
  );
}
