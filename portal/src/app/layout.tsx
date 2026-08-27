import './globals.css';
import React from 'react';

export const metadata = {
  title: 'NEXUS — Control Plane',
  description: 'AI Developer Infrastructure Control Plane',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark notranslate" translate="no" suppressHydrationWarning>
      <head>
        <meta name="google" content="notranslate" />
      </head>
      <body className="bg-[#09090b] text-slate-100 min-h-screen font-sans antialiased selection:bg-white selection:text-black notranslate" translate="no" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
