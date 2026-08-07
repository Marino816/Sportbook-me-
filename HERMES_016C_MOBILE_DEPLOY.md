# HERMES-016C — Mobile Deployment Verification

**Status**: DEPLOYMENT-READY — Awaiting manual execution
**Date**: August 6, 2026

---

## Deployment Readiness

| Item | Status |
|------|--------|
| Source code | ✅ Complete |
| Build configuration | ✅ eas.json, app.json |
| Bundle ID (iOS) | ✅ com.sportbookme.app |
| Package name (Android) | ✅ com.sportbookme.app |
| Splash screen config | ✅ Black bg, contain mode |
| App icon config | ✅ assets/icon.png placeholder |
| Build commands documented | ✅ MOBILE_DEPLOYMENT_VERIFICATION.md |
| Founder acceptance checklist | ✅ FOUNDER_ACCEPTANCE.md (37 items) |

---

## Channel Status

| Channel | Code Ready | Build Required | Publish Required | Verified |
|---------|-----------|----------------|------------------|----------|
| iOS TestFlight | ✅ | ⬜ eas build iOS | ⬜ App Store Connect | ⬜ |
| Android APK | ✅ | ⬜ eas build Android | ⬜ Upload to server | ⬜ |
| Google Play | ✅ | ⬜ eas build Android | ⬜ Play Console | ⬜ |
| Expo Preview | ✅ | ⬜ npx expo publish | ⬜ Expo dashboard | ⬜ |
| Demo Website | ✅ | ⬜ npm run build | ⬜ Vercel deploy | ⬜ |
| Documentation | ✅ | ⬜ Deploy docs/ | ⬜ docs.sbmedfsai.com | ⬜ |

---

## Required Credentials

| Credential | Needed For |
|------------|-----------|
| Apple Developer account | TestFlight submission |
| Apple Distribution Certificate | iOS signing |
| Google Play Console account | Play Store submission |
| Android keystore | APK/AAB signing |
| Expo EAS account | Build + publish |
| Vercel account (or similar) | Web demo + docs deploy |
| Server access | APK upload to downloads.sportbookme.ai |

---

## Installation Instructions

### iOS (TestFlight)
1. Accept TestFlight invitation email
2. Install TestFlight from App Store
3. Open invitation → Install SPORTBOOK ME
4. Launch and log in

### Android (APK)
1. Open downloads.sportbookme.ai/android/latest.apk
2. Allow install from unknown sources
3. Install and launch

### Android (Play Store)
1. Accept internal testing invitation
2. Open play.google.com/apps/testing/com.sportbookme.app
3. Install via Play Store

### Expo Preview
1. Install Expo Go from App Store / Play Store
2. Open expo.dev/preview/XXXXXXXX
3. Scan QR code with Expo Go

---

## Live URLs (to be populated after deployment)

| Channel | URL |
|---------|-----|
| TestFlight | testflight.apple.com/join/[REAL_CODE] |
| Android APK | downloads.sportbookme.ai/android/latest.apk |
| Google Play | play.google.com/apps/testing/com.sportbookme.app |
| Expo Preview | expo.dev/@[account]/sportbook-me-mobile |
| Demo | sbmedfsai.com/demo |
| Docs | docs.sbmedfsai.com/mobile |

---

## Recommendation

**HERMES-016C is DEPLOYMENT-READY** but cannot be certified as COMPLETE until:

1. Apple Developer + Google Play Console credentials are provisioned
2. EAS builds are executed (requires Apple signing certs + Android keystore)
3. Each channel is published and URL is populated
4. Founder completes 37-item acceptance checklist

This environment cannot execute mobile builds or publish to app stores. Once the above credentials are available, follow MOBILE_DEPLOYMENT_VERIFICATION.md to complete deployment in under 2 hours.

---

## Current Status

```
☐ iOS TestFlight      — ready for eas build
☐ Android APK         — ready for eas build
☐ Google Play         — ready for eas build
☐ Expo Preview        — ready for npx expo publish
☐ Demo Website        — ready for vercel deploy
☐ Documentation       — ready for deploy
```

---

**HERMES-016C**: Deployment-ready, awaiting credentials + execution