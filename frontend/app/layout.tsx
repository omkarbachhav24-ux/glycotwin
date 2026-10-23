import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "GlycoTwin Clinical Console",
  description:
    "Research prototype showing a patient digital twin that forecasts glucose and flags possible excursions. Built on synthetic data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <div className="disclaimer" role="note">
          <strong>Research prototype.</strong>
          <span>
            Not a medical device, not a diagnostic tool, and not a substitute for clinical
            care. Every patient and reading here is synthetic.
          </span>
        </div>
        {children}
      </body>
    </html>
  );
}
