import path from "node:path";
import fs from "node:fs";
import { Font } from "@react-pdf/renderer";

let fontsRegistered = false;

function fontPath(filename: string): string {
  return path.join(process.cwd(), "assets", "fonts", filename);
}

/**
 * Registers local bundled TTF fonts once for offline @react-pdf/renderer generation.
 */
export function ensurePdfFontsRegistered(): void {
  if (fontsRegistered) return;

  const requiredFiles = [
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
    "Inter-Bold.ttf",
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono-Medium.ttf",
    "JetBrainsMono-Bold.ttf",
    "NotoNaskhArabic-Regular.ttf",
    "NotoNaskhArabic-Bold.ttf",
  ];

  for (const file of requiredFiles) {
    const full = fontPath(file);
    if (!fs.existsSync(full)) {
      throw new Error(`Bundled PDF font missing at ${full}`);
    }
  }

  Font.register({
    family: "Inter",
    fonts: [
      { src: fontPath("Inter-Regular.ttf"), fontWeight: 400 },
      { src: fontPath("Inter-Medium.ttf"), fontWeight: 500 },
      { src: fontPath("Inter-SemiBold.ttf"), fontWeight: 600 },
      { src: fontPath("Inter-Bold.ttf"), fontWeight: 700 },
    ],
  });

  Font.register({
    family: "JetBrainsMono",
    fonts: [
      { src: fontPath("JetBrainsMono-Regular.ttf"), fontWeight: 400 },
      { src: fontPath("JetBrainsMono-Medium.ttf"), fontWeight: 500 },
      { src: fontPath("JetBrainsMono-Bold.ttf"), fontWeight: 700 },
    ],
  });

  Font.register({
    family: "NotoNaskhArabic",
    fonts: [
      { src: fontPath("NotoNaskhArabic-Regular.ttf"), fontWeight: 400 },
      { src: fontPath("NotoNaskhArabic-Bold.ttf"), fontWeight: 700 },
    ],
  });

  // Prevent mid-word hyphenation issues on UUIDs, dates, and RTL scripts
  Font.registerHyphenationCallback((word) => [word]);

  fontsRegistered = true;
}
