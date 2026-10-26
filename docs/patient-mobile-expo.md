# XAI-CVD patient mobile app (Expo Go)

The dedicated `mobile/` app is a React Native/TypeScript Expo Router client of the same FastAPI and encrypted patient store. It is patient-only: the backend rejects staff accounts at mobile login and applies the existing linked-patient authorization to every portal API call. It stores the short-lived bearer token in Expo SecureStore and does not persist passwords, medical data, or reports as app state. PDF files are downloaded to the app's private cache only on user request and passed to the native share/open sheet.

## Install and run

Requirements: Node.js 20.19+ (Expo SDK 54 minimum), npm, Python environment already set up for this project, and Expo Go installed on the phone. This repo has `mobile/package-lock.json`; use `npm ci` for a clean install.

1. On Windows, find the computer's Wi-Fi IPv4 address with:

   ```powershell
   ipconfig
   ```

   Use the IPv4 address for the active Wi-Fi adapter, for example `192.168.1.24`. Do not use `localhost` or `127.0.0.1` in the phone app setting.

2. Copy `mobile/.env.example` to `mobile/.env.local`, then set the address and the FastAPI port:

   ```dotenv
   EXPO_PUBLIC_API_URL=http://192.168.1.24:8000
   ```

   `EXPO_PUBLIC_` values are bundled into client code and are not secrets. Never put passwords, the database encryption key, or access tokens in this file.

3. In an API PowerShell terminal, set the existing local-demo encryption key and start FastAPI on the LAN interface:

   ```powershell
   $env:XAI_CVD_ENCRYPTION_KEY = "<same private key used for the patient demo database>"
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

   The app defaults to port `8000`. Do not expose this development server to the public internet. The mobile app uses the API directly; Expo's tunnel only tunnels Metro and does not tunnel/reach the backend.

4. In a second terminal:

   ```powershell
   cd mobile
   npm ci
   npx expo start --lan
   ```

   Scan the QR code with Expo Go. Keep the computer and phone on the same trusted Wi-Fi. On Android, install an Expo Go build compatible with SDK 54 if the Play Store build reports an SDK mismatch; Expo's compatible-build selector is [expo.dev/go](https://expo.dev/go). If LAN discovery/Metro is blocked, `npm run start:tunnel` can tunnel Metro, but the phone must still be able to reach the API LAN URL above. Guest Wi-Fi client isolation, a VPN, or an incorrect private IP can prevent API access.

## Windows Firewall (only if required)

First try Windows' private-network prompt for Python. If inbound API traffic is still blocked, use an elevated PowerShell and restrict the inbound rule to the phone's current Wi-Fi IP and the computer's LAN IP (replace both placeholders):

```powershell
New-NetFirewallRule -DisplayName "XAI-CVD demo API from phone" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -LocalAddress <COMPUTER_LAN_IP> -RemoteAddress <PHONE_LAN_IP> -Profile Private
```

Remove the temporary rule after the demo:

```powershell
Remove-NetFirewallRule -DisplayName "XAI-CVD demo API from phone"
```

Do not create a public-profile or any-source rule. Native Expo requests use bearer authorization. The FastAPI CORS allowlist remains restricted to configured development origins and is not an authorization mechanism.

## Screens and behavior

- Login and single-use code activation use `/api/mobile/auth/login` and `/api/mobile/auth/activate`; activation code delivery remains manual, with identity checked by staff. No email or SMS is sent.
- Home, My Assessments, Reports, and Progress retrieve real released-only data from the authenticated patient's existing `/api/portal/*` routes. Assessment detail shows the stored model prediction and SHAP contribution bars. Each contribution describes model behavior, not causation.
- Measurement charts use only dated values from released assessment records. The source type (patient, device, or clinician) is not captured by the existing assessment schema, so the UI says so. No values are imputed/interpolated.
- Profile displays the linked profile and saves contact/notification preferences to the same encrypted patient profile. Email/SMS/push delivery is not implemented; these are saved preferences only.
- Reports download through the authenticated portal PDF route and use the device share/open sheet. The server checks the logged-in patient's association and released status on every request.

## Security and production

The mobile token expires with the backend's 8-hour session and is stored in the OS-backed SecureStore. Logout revokes the server session. Reports are fetched over the existing bearer-protected, patient-bound route; no report URLs are public. The current environment is a local synthetic-data demo: LAN HTTP is for development only. Use HTTPS, production identity/session controls, key lifecycle and encrypted backups, rate limiting, and a security review before any real-data deployment. No regulatory compliance claim is made.

Expo Go SDK compatibility varies by platform/version. This project targets SDK 54, the newest Expo Go SDK currently available from the iOS App Store according to Expo's compatibility guidance; Android users should use an Expo Go build that supports SDK 54. A physical-device connection and in-app PDF opening should be checked on the target phone before demonstration.
