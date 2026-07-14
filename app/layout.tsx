import type { Metadata } from "next";
import "./globals.css";

const basePath = process.env.SITE_BASE_PATH ?? "";

export const metadata: Metadata = {
  title: "地质招聘雷达｜2027届央国企招聘监控",
  description:
    "面向2027届地质学硕士的央国企招聘监控页，只展示核实后的新增、临近截止和地质相关岗位。",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: `${basePath}/favicon.svg`,
    shortcut: `${basePath}/favicon.svg`,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className="antialiased"
      >
        {children}
      </body>
    </html>
  );
}
