# Scriberr archive search spike verdict

The spike demonstrates topic and capture-date search over the existing rekt archive, with verbatim excerpts, source references, copy controls and audio offsets. Extend Scriberr's recordings workflow using the validated archive adapter and retrieval behavior.

## Source update

The original upstream was 43 commits ahead of Jared and Paul's shared fork tip. [Sync PR #1](https://github.com/jaredirish/Scriberr/pull/1) merged into Jared's main at 9bcd1c3e4c05e1e5b7d2e7bcf05a1c8fe2ff3c30, preserving the fork history. The updated upstream frontend passed npm ci, npm run build and npm run lint. Go, GPU and full-app runtime compatibility have not been validated; the running transcription service was not redeployed.

## Measured result

- 1,212 usable recordings, 71,291 indexed passages, April 22 through October 13.
- 21,834 empty source files/placeholders, 38 skipped inputs, zero index errors. Canonical alternatives are deduplicated.
- Five matching passages for both Wealthbox spellings. Returned excerpts were checked against their source files.
- October 13 has usable text from one overnight recording. Wealthbox has no match on that date; the requested discussion remains unavailable in this archive snapshot.
- Independent checks passed for keyword boundaries, marked all-raw merged chunks, legacy plain merged chunks, HHMMSS offsets against real metadata, date isolation, missing coverage, malformed queries, indexed audio byte ranges and invalid-path rejection.
- Fresh review identified word-splitting and raw merged-offset defects. Both were repaired; the final check additionally protects the observed legacy plain chunk format.
- Desktop and 390-pixel layouts were inspected in Chrome. No horizontal overflow was observed. A real recording loaded with readyState 4 and seeking reached currentTime 900 seconds. Audible word alignment remains unverified.

## Review and operation

Prototype source stays on [spike/rekt-search-20261014](https://github.com/jaredirish/Scriberr/tree/spike/rekt-search-20261014), under spikes/rekt-search/. It is a throwaway stdlib Python and SQLite FTS5 adapter with its own scratch index. No private transcript excerpts, recordings, database, screenshots or logs belong in Git.

The owner opened the live preview on Jared's desktop and saved a desktop shortcut. Homie runs the preview as the transient user unit scriberr-search-spike-20261014.service, bound to its Tailscale interface on port 9502. The source worktree must remain at /home/jared/Projects/scriberr-search-spike-20261014 while this preview is in use. Stop it with systemctl --user stop scriberr-search-spike-20261014.service. It is not enabled for reboot startup.

Independent acceptance code and raw run evidence live under /home/jared/.ringer/jobs/scriberr-search-spike-20261014/; measured verification.json is under /home/jared/.cache/scriberr-search-spike-20261014/. Ringside records the build, fresh review and bounded repairs as versions of one job.

## Integration limits

The preview uses a snapshot index, literal passage-local search, numbered source speakers and approximate raw chunk starts. Overlapping passages can duplicate a match. Integration still needs Scriberr's authentication and player, a durable capture-date field, a refresh policy and full-app runtime validation. Keep this prototype off main.
