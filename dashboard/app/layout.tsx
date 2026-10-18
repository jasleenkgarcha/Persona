import type { Metadata } from "next";
import { DM_Sans, Manrope } from "next/font/google";
import Shell from "@/components/Shell";
import { CallsProvider } from "@/lib/use-calls";
import "./globals.css";

const sans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm",
});

const display = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

export const metadata: Metadata = {
  title: "goodcall",
  description: "A little proof before hello.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} h-full antialiased`}>
      <body className="min-h-full">
        <CallsProvider>
          <Shell>{children}</Shell>
        </CallsProvider>
      </body>
    </html>
  );
}
