import type { Metadata } from "next";
import localFont from "next/font/local";
import { siteConfig, UI_REVISION } from "@/config/site";
import { AuthProvider } from "@/context/AuthContext";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import "@/styles/globals.css";

const headingFont = localFont({
  src: "./fonts/Newsreader.ttf",
  variable: "--font-heading",
  display: "swap",
});

const bodyFont = localFont({
  src: "./fonts/SourceSans3.ttf",
  variable: "--font-body",
  display: "swap",
});

const monoFont = localFont({
  src: "./fonts/JetBrainsMono.ttf",
  variable: "--font-code",
  display: "swap",
});

export const metadata: Metadata = {
  title: `${siteConfig.name} | ${siteConfig.tagline}`,
  description: siteConfig.tagline,
  icons: {
    icon: siteConfig.logo.favicon,
  },
  other: {
    "ui-revision": String(UI_REVISION),
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${headingFont.variable} ${bodyFont.variable} ${monoFont.variable}`}
    >
      <body>
        <AuthProvider>
          <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
            <Navbar />
            <main style={{ flex: 1 }}>{children}</main>
            <Footer />
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
