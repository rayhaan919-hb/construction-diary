import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const inter = localFont({
  src: [
    { path: "../../assets/fonts/Inter-Regular.ttf", weight: "400", style: "normal" },
    { path: "../../assets/fonts/Inter-Medium.ttf", weight: "500", style: "normal" },
    { path: "../../assets/fonts/Inter-SemiBold.ttf", weight: "600", style: "normal" },
    { path: "../../assets/fonts/Inter-Bold.ttf", weight: "700", style: "normal" },
  ],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = localFont({
  src: [
    { path: "../../assets/fonts/JetBrainsMono-Regular.ttf", weight: "400", style: "normal" },
    { path: "../../assets/fonts/JetBrainsMono-Medium.ttf", weight: "500", style: "normal" },
    { path: "../../assets/fonts/JetBrainsMono-Bold.ttf", weight: "700", style: "normal" },
  ],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

const notoArabic = localFont({
  src: [
    { path: "../../assets/fonts/NotoNaskhArabic-Regular.ttf", weight: "400", style: "normal" },
    { path: "../../assets/fonts/NotoNaskhArabic-Bold.ttf", weight: "700", style: "normal" },
  ],
  variable: "--font-noto-arabic",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Site Diary — Owner Portal",
  description: "Construction permit tracking and daily field log portal.",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} ${notoArabic.variable}`}
    >
      <body className="min-h-screen bg-[#F8FAFC] text-[#0F172A] font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
