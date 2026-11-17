import type { Metadata } from "next";
import { Inter, Geist, Vazirmatn } from "next/font/google";
import "./globals.css";
import Layout from "@/components/layout";
import { Providers } from "@/components/providers";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

const inter = Inter({ subsets: ["latin"] });

// Farsi (and future RTL languages): the Inter/Geist faces carry no
// Arabic-script glyphs. Vazirmatn is applied under [dir="rtl"] in
// globals.css via this CSS variable.
const vazirmatn = Vazirmatn({
  subsets: ["arabic", "latin"],
  variable: "--font-fa",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Statisticians Workbench",
  description: "A modern data analysis platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // <html> intentionally renders lang="en" with no dir on the server:
  // the TranslationProvider corrects both attributes client-side
  // (post-hydration) once the effective language is known —
  // see translation-context.tsx and lib/rtl.ts.
  return (
    <html lang="en" className={cn("font-sans", geist.variable, vazirmatn.variable)}>
      <body className={inter.className} suppressHydrationWarning>
        <Providers>
          <Layout>{children}</Layout>
        </Providers>
      </body>
    </html>
  );
}