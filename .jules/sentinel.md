## 2024-08-10 - [Defensive Intent Handling]
**Vulnerability:** Broad Activity Export vulnerabilities exist due to exported launcher activities lacking explicit validation of incoming intents.
**Learning:** Exported launcher activities are publicly accessible by any app. Without explicit action validation, malicious apps could send unexpected intents, leading to unintended behavior or state manipulation.
**Prevention:** Always implement defense-in-depth by explicitly validating the incoming intent's action (e.g., verifying it's `Intent.ACTION_MAIN`) in `onCreate` for exported activities.
