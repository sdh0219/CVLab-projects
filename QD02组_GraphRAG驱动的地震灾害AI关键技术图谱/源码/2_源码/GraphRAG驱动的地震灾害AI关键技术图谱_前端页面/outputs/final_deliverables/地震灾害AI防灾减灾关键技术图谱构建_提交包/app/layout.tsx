import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GraphRAG驱动的地震灾害AI关键技术图谱",
  description:
    "用GraphRAG从地震灾害多源文本证据中构建、检索、总结和校验AI关键技术图谱的研究原型。",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
