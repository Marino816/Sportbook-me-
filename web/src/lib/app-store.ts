import { track } from "@vercel/analytics";

export const APP_STORE_ID = "6808706342";
export const APP_STORE_URL = "https://apps.apple.com/app/sportbook-me-dfs-ai/id6808706342";
export const APP_STORE_CTA = "Download Sportbook Me DFS AI for iPhone";
export const APP_STORE_BADGE_ALT = "Download Sportbook Me DFS AI on the App Store";

export function trackAppStoreClick(placement: string) {
  track("app_store_click", { placement });
}
