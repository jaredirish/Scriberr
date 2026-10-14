# Scriberr archive search spike

Question: can Jared find a remembered conversation, read the exact phrasing, and play the relevant audio using a topic and recording date?

## Verified upstream

- Jared's fork: https://github.com/jaredirish/Scriberr, fork of paulirish/Scriberr, original source rishikanthc/Scriberr.
- Jared and Paul both point at 5e5dc17a133a05dbf3f1b7d200aa78f80280cdd2.
- Original upstream main is a353078, 43 commits ahead with no divergent commits. The isolated spike branch starts at this upstream commit.
- Homie worktree: /home/jared/Projects/scriberr-search-spike-20261014.
- Branch: spike/rekt-search-20261014. Production homie-scriberr on 9500 is unchanged.
- Current upstream list search matches title and audio_path only. CreatedAt is the application job creation time, not capture time.
- Rekt archive on Homie: /home/jared/rekt/transcripts, 37,333 plain-text chunks and 432 global merged transcripts at inspection. Audio archive: /mnt/tank-rekt/2-scriberred.
- October 13 available recordings cover approximately 12:12 to 2:42 a.m. Filename dates are local capture times; do not invent later coverage.

## Reuse decision

GitHub query: transcript search sqlite fts5. Checked source README.md, internal/repository/implementations.go, internal/models/transcription.go, web/frontend/src/features/transcription/components/AudioFilesTable.tsx, and committed screenshots/homepage-dark.png.

| Candidate | Evidence | Missing for this task |
| --- | --- | --- |
| Existing Scriberr browser plus SQLite FTS5 | Existing app, playback, transcript browsing; already uses SQLite | Rekt archive adapter, capture date, passage results |
| FlorianBruniaux/youtube-video-insights | GitHub search result, 21 stars at inspection | YouTube-specific; archive and playback integration unverified |
| TT-Wang/memem | GitHub search result, 32 stars at inspection | Suitability for this archive unverified; would introduce another app |

Verdict: extend the existing product. Articulability HIGH: local transcript inputs, capture-date bounds, literal topic search, exact excerpts, audio offsets. This is a throwaway spike, not a new durable service. Codex owns the spike result and checks; Jared chooses whether to integrate it into Scriberr.

## Spike boundary

Implement under spikes/rekt-search/ in the updated fork. Use a stdlib Python server and scratch SQLite FTS5 index so the archive can be exercised without starting GPU model environments or changing Scriberr's live database. No third-party dependencies, model calls, embeddings, transcription reruns, or writes to source audio/transcripts. Keep the existing Scriberr orange and charcoal visual language.

Index canonical global merged transcripts where available; otherwise index raw five-minute text chunks. Deduplicate alternatives for a recording. Capture dates come from rekt filenames, with correct 12 a.m./p.m. conversion and America/New_York date controls. Preserve source paths and offsets, distinguish exact diarized timestamps from approximate raw chunk starts. Empty transcripts should be counted separately from usable text.

Search full transcript words, with a clear deterministic treatment of punctuation and Wealthbox versus wealth box. Include date bounds and Yesterday/Clear controls. Results show capture date/time, source recording, exact matching excerpts and available speaker labels. Never infer that a numbered speaker is Sam. Show transcript detail, copyable wording and audio playback at the available offset. Audio paths must come from indexed allowlisted archive files, with HTTP range support and no arbitrary file serving. If audio is unavailable, retain the quote and show the limitation.

The UI should show usable archive coverage and distinguish no matches from no indexed text on a selected date. Use real source content only; never fabricate results for yesterday. Keep source provenance next to each excerpt.

Bind the spike to localhost for inspection, or Homie's Tailscale address for Jared. Never expose ambient recordings on 0.0.0.0. Store generated indexes and logs outside tracked source. One documented command should build the scratch index and serve the UI on an unused port, proposed 9502.

## Validation contract

- Build the real archive index and report usable recordings, indexed passages, date span, empty source count and skipped/failed files.
- Search Wealthbox and wealth box, and prove returned excerpts exist verbatim in the identified source.
- Verify October 13 filtering has no results from other dates; dates without indexed text must say so.
- Verify empty query browsing and malformed queries return valid responses without crashes or arbitrary SQL/FTS expressions.
- Verify a real audio result supports byte-range reads and that invalid audio IDs/path traversal cannot read arbitrary files.
- Open the working page on Jared's desktop. Inspect desktop and narrow layouts, keyboard focus, date controls, result selection and audio seeking. One repair pass if needed.
- Keep code on the spike branch, commit/push only task files, and record the verdict and evidence. Production promotion is outside the spike.

## Direction contract

THESIS: remembered conversations become source-backed passages with one step to audio.

OWN-WORLD: inherit Scriberr's charcoal surfaces, off-white text and orange actions; readable system body typography and restrained controls.

STORY: choose topic/date, scan the real excerpt, inspect its source and listen.

FIRST VIEWPORT: compact Scriberr header, prominent search field and adjacent date controls, small factual coverage line, then matching passages with capture times and a readable transcript/player detail area.

FORM: extend the established recordings workflow; no new visual identity or concept tournament.

FINISH: usable archive search demonstrated against real data, desktop/mobile inspected, evidence and spike source pushed, unresolved integration limits stated.
