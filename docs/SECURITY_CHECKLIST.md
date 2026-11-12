# Security & Deployment Checklist

**Prototype status:** OpenSnap implements technical safeguards suitable for local evaluation. It does **not** claim HIPAA compliance or production readiness. Clinical use requires institutional IT, security, compliance, and clinical engineering review.

## Data residency

- [ ] All patient data, media, and reports remain on the Windows recording computer
- [ ] No cloud storage, external databases, telemetry, or third-party APIs in the runtime path
- [ ] If Cloudflare hosts the UI shell, confirm it serves assets only (no API proxy, no Tunnel for PHI/media)
- [ ] Storage directory encrypted with institution-approved mechanism (e.g., BitLocker)
- [ ] NTFS ACLs restrict session directories and SQLite DB to authorized accounts

## Application security

- [ ] Desktop API protected according to institutional workstation policy
- [ ] Input validation enabled on all create/update endpoints
- [ ] Application logs exclude patient names, MRNs, and DOBs
- [ ] Audit log reviewed for administrative and recording actions
- [ ] Retention / deletion policy approved before enabling purge tooling

## Mobile remote

- [ ] HTTPS only on approved clinic network
- [ ] Pairing tokens short-lived and cryptographically random
- [ ] One active remote controller per session; revocation tested
- [ ] Replay protection verified (duplicate command IDs ignored)
- [ ] Confirmed mobile UI never receives PHI, photos, video, notes, or PDFs
- [ ] Recording continues when the phone disconnects

## Network

- [ ] Service not reachable from public internet
- [ ] Firewall scoped to clinic LAN/VLAN
- [ ] Certificate trust chain validated on physician iPhones
- [ ] Localhost desktop path documented separately from LAN remote path

## Hardware validation

- [ ] HDMI capture path validated end-to-end with clinical tower
- [ ] Frame-rate warnings verified against capture hardware
- [ ] Disconnection / reconnection behavior observed during procedure simulation
- [ ] Disk-space warning threshold appropriate for procedure volume

## Clinical report content

- [ ] PDF contains only letterhead, demographics, procedure details, Notes, selected photos
- [ ] No structured Findings / Impression / Plan fields present
- [ ] Practice letterhead verified against official contact information
- [ ] Manual Epic Media upload workflow documented (no direct Epic integration)
