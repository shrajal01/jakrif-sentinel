import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sentinel Dashboard",
  description: "Futuristic dashboard for JakRif Sentinel.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen relative overflow-x-hidden text-slate-200">
        <div className="fixed inset-0 z-[-2] bg-[#050505]"></div>
        <div className="bg-blob bg-blue-600/30 w-[500px] h-[500px] rounded-full top-[-10%] left-[-10%] fixed"></div>
        <div className="bg-blob bg-purple-600/30 w-[500px] h-[500px] rounded-full bottom-[-10%] right-[-10%] fixed" style={{ animationDelay: "2s" }}></div>
        <div className="bg-blob bg-emerald-600/20 w-[400px] h-[400px] rounded-full top-[30%] left-[40%] fixed" style={{ animationDelay: "4s" }}></div>
        
        {children}
      </body>
    </html>
  );
}
