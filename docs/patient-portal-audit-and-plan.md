# Patient Management and Portal: Repository Audit and Implementation

## Current architecture

- Staff-facing application: Next.js 15 App Router, React 19, TypeScript, shared shell in `frontend/components/layout/app-shell.tsx`, and in-memory assessment state in `frontend/components/providers.tsx`.
- Backend: FastAPI in `backend/main.py`. Prediction uses the existing saved hybrid ML/MLP artifacts through `src/predict.py` and `src/hybrid.py`; explanation values are generated against the hybrid probability output.
- Reports: `src/report.py` builds ReportLab PDFs with the same assessment's Matplotlib patient graph from `src/patient_graph.py`.
- Dataset-level explanations: `/risk-factor-network` uses cached Spearman associations from `src/risk_network.py`; it is independent of patient assessment records.
- Before this enhancement, storage and identity were session-only/in-process. The optional local demo now adds SQLite records, user roles, cookie sessions, keyed duplicate search, encrypted patient/assessment/report payloads, and audit events. The regular assessment history remains session-only; assessments started from a patient record are stored durably.
- Current access boundary: prediction, extraction, risk-network, and report endpoints have no authentication. CORS is restricted to local origins but is not an authorization control. No notification, verified contact channel, portal identity proof, or deployment-specific key management is configured.
- Tests and dependencies: Python `unittest` tests and a Next.js typecheck/build are present. The local record store uses standard-library SQLite and `cryptography`; frontend login, patient management, report review, and portal routes are available.

## Implemented integration

1. Deployment target is the user's selected local synthetic-data demo. Staff accounts are created offline; the encryption key is operator supplied and never generated at runtime.
2. `/patients` provides searchable, paginated staff record listing and registration; `/patients/[id]` provides overview, stored assessment history, recorded-measurement tables, report/PDF access, and manual portal-invite/revoke controls.
3. `/assessment?patientId=...` runs the existing prediction and stores immutable input/output/explanation/model-version data under that patient record. The existing assessment logic is reused.
4. Persisted reports reuse the existing PDF/graph builder, receive report IDs/versions, and default to `pending_review`. `/reports/review` is limited on the backend to clinician/admin roles; review and release are separate operations.
5. `/portal/login`, `/portal/activate`, and `/portal` use the same source of truth. A portal account only gets its linked patient's explicitly released report PDFs and the associated assessment entries. Activation codes are one-use/24h and manually delivered after in-person identity checking.
6. Existing Risk Factor Network and session Reports routes remain in place. Added tests cover encrypted-at-rest fields, duplicate detection, invitation reuse/revocation, release filtering, and a cross-patient HTTP authorization scenario.

## Demo boundary and remaining work

This is not a clinical/production deployment. Local SQLite plus field/file encryption does not provide TLS, MFA, whole-database/WAL or backup encryption, key rotation, clinic isolation, production rate limiting, or tested recovery. No regulations compliance claim is made. The portal currently shows actual released history and source-entered measurements as a table; charted progress views, measurement provenance distinctions, patient-side SHAP detail pages, account recovery, data export/deletion, and PWA service worker remain future work. The HTTP integration test stalls in this local Python 3.14/ASGI environment; only the storage unit tests have completed successfully so far. No end-to-end browser or two-report graph-isolation result is claimed.
