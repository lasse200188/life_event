import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Life Event - Geburt Planer",
  description: "Digitale Checkliste und Fristenplan fuer Geburt in Deutschland",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
