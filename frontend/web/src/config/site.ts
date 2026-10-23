export const siteConfig = {
  name: "FinFriend",
  tagline: "Educational Indian market analytics. Not investment advice.",
  footerText: "Educational only. Not investment advice.",
  logo: {
    mark: "/brand/logo-mark.svg",
    horizontal: "/brand/logo-horizontal.svg",
    horizontalLight: "/brand/logo-horizontal-light.svg",
    favicon: "/brand/favicon.svg",
  },
} as const;

export type SiteConfig = typeof siteConfig;

export const UI_REVISION = 1;
