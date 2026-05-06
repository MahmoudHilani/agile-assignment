"use client";

import Image from "next/image";

export default function CompanyLogo() {
  return (
    <div className="company-header">
      <Image
        src="/logo.jpeg"
        alt="Company Logo"
        width={36}
        height={36}
        className="company-logo-img"
      />
      <span className="company-name">AgileMind</span>
    </div>
  );
}