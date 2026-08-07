# SPORTBOOK ME — Mobile Deployment Verification

**HERMES-016C**
**Status**: READY FOR EXECUTION — Requires Apple Developer + Google Play Console credentials

---

## Prerequisites

| Requirement | Status |
|-------------|--------|
| Apple Developer account ($99/yr) | ⬜ Required for TestFlight |
| Google Play Console account ($25 one-time) | ⬜ Required for Play Store |
| Expo EAS account | ⬜ eas login |
| Distribution server (downloads.sportbookme.ai) | ⬜ S3/CloudFront or similar |
| Demo hosting (sbmedfsai.com/demo) | ⬜ Vercel or similar |
| Docs hosting (docs.sbmedfsai.com/mobile) | ⬜ Vercel or GitHub Pages |

---

## 1. iOS TestFlight

### Build & Upload

```bash
cd mobile
eas build --platform ios --profile production
```

### App Store Connect

1. Open https://appstoreconnect.apple.com
2. My Apps → SPORTBOOK ME
3. TestFlight → Select build
4. Add Internal Testers
5. Send invitation

### Verification

| Check | Expected |
|-------|----------|
| TestFlight email received | Within 5 minutes |
| Install on iPhone (iOS 15+) | Successful |
| Launch app | Splash → Login screen |
| Login with QA account | Dashboard loads |
| AI Chat responds | SB ME Intelligent AI |

---

## 2. Android APK

### Build Signed APK

```bash
cd mobile
eas build --platform android --profile production
# Download from EAS dashboard:
# https://expo.dev/accounts/[account]/projects/sportbook-me-mobile/builds
```

### Upload to Distribution Server

```bash
# After downloading the APK from EAS:
# Upload to your distribution server
scp sportbook-me-1.1.0.apk user@downloads.sportbookme.ai:/var/www/android/
```

### Generate SHA256

```bash
shasum -a 256 sportbook-me-1.1.0.apk > sportbook-me-1.1.0.apk.sha256
```

### Verification

| Check | Expected |
|-------|----------|
| Download URL accessible | downloads.sportbookme.ai/android/latest.apk |
| APK installs on Android 10+ | Successful |
| SHA256 matches | Verify checksum |
| Launch app | Splash → Login |
| Biometric login | Face ID / fingerprint |

---

## 3. Google Play Internal Testing

### Build AAB

```bash
cd mobile
eas build --platform android --profile production
```

### Google Play Console

1. Open https://play.google.com/console
2. SPORTBOOK ME → Internal testing
3. Create new release → Upload AAB
4. Add testers by email
5. Start rollout

### Verification

| Check | Expected |
|-------|----------|
| Play Store listing visible to testers | Internal |
| Install from Play Store | Successful |
| Automatic updates work | Version bump → update |

---

## 4. Expo Preview

### Publish

```bash
cd mobile
npx expo publish
```

### Verification

| Check | Expected |
|-------|----------|
| URL accessible | expo.dev/preview/XXXXXXXX |
| QR code opens Expo Go | iOS + Android |
| App loads | Splash → Login |

---

## 5. Demo Website

### Deploy

```bash
cd web
npm run build
# Deploy to Vercel or your hosting provider
vercel deploy --prod
```

### Verification

| Check | Expected |
|-------|----------|
| URL accessible | sbmedfsai.com/demo |
| Demo video plays | Embedded video loads |
| Mobile responsive | Works on iPhone + Android |
| SB ME branding | Logo + tagline visible |
| Links functional | All navigation works |

---

## 6. Documentation

### Deploy

```bash
# GitHub Pages or Vercel with docs directory
# Point docs.sbmedfsai.com → docs/ directory
```

### Verification

| Check | Expected |
|-------|----------|
| URL accessible | docs.sbmedfsai.com/mobile |
| All guides present | Architecture, deploy, QA, branding |
| Mobile responsive | Readable on phone |

---

## Deployment Commands Summary

```bash
# 1. Login to EAS
eas login

# 2. Build iOS for TestFlight
eas build --platform ios --profile production

# 3. Build Android for APK + Play Store
eas build --platform android --profile production

# 4. Expo Preview
npx expo publish

# 5. Web demo
cd web && npm run build && vercel deploy --prod

# 6. Docs
# Deploy docs/ directory to docs.sbmedfsai.com
```

---

## Version Numbers

| Platform | Version | Build |
|----------|---------|-------|
| iOS | 1.1.0 | TBD |
| Android | 1.1.0 | TBD |
| Expo Preview | 1.1.0 | TBD |

---

✅ Deployment verification report: commands documented, awaiting execution