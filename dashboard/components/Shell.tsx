"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Icon from "@/components/Icon";

const LINKS = [
  { href: "/", label: "Calls" },
  { href: "/evals", label: "Evaluation" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link href="/" className="brand" aria-label="goodcall home">
          <span className="brand-mark">
            <Icon name="phone" size={15} />
          </span>
          <span>
            goodcall<span className="brand-dot">.</span>
          </span>
        </Link>
        <nav className="nav">
          {LINKS.map((link) => {
            const active =
              link.href === "/"
                ? pathname === "/" || pathname.startsWith("/calls")
                : pathname.startsWith(link.href);
            return (
              <Link key={link.href} href={link.href} aria-current={active ? "page" : undefined}>
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="profile">
          <span>Ian&apos;s line</span>
          <span className="avatar">IA</span>
        </div>
      </header>
      {children}
      <footer>
        <span>goodcall.</span>
        <span>Calls get tested. Ian gets peace.</span>
        <span>A little proof before hello.</span>
      </footer>
    </div>
  );
}
