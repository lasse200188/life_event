import type { ReactNode } from "react";

export const metadata = {
  title: "Life Event",
  description: "Life Event Workflow Plattform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
