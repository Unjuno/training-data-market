# Security and data handling

This version is a static synthetic-data demo. It has no authentication, voting API, or training service. Local storage is a convenience, not a security boundary or a shared vote database. Do not enter passwords, personal data, or secrets into the reason field.

## Before connecting real services

Use authenticated server sessions; enforce authorization and the 10-pick limit server-side in transactions. Enforce deadlines using server time. Keep job credentials, model checkpoints and internal evaluation data outside the public bundle. Escape untrusted output; render reasons as text. Protect cookie-authenticated writes against CSRF and limit abusive requests. Do not accept arbitrary worker URLs or execute user-supplied code.

Static builds use an explicit file allowlist. `.gitignore` is defense in depth, not a secrets scanner. Dataset rights must be verified separately before public redistribution.

Do not post credentials or personal voting records in public GitHub issues. Use a private reporting channel agreed with the repository owner; none is configured by this starter.
