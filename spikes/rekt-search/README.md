# Scriberr archive search spike

Python 3.11+ standard library only. Uses SQLite FTS5 and read-only archive inputs. No model environments, dependencies, live app state, or source writes. Identity inherits Scriberr's charcoal surfaces and #fe9a00 orange.

From this directory, one command builds the scratch index and serves a foreground localhost preview:

```sh
python3 server.py index --transcripts /home/jared/rekt/transcripts --audio-root /mnt/tank-rekt/2-scriberred --db /home/jared/.cache/scriberr-search-spike-20261014/index.sqlite && python3 server.py serve --db /home/jared/.cache/scriberr-search-spike-20261014/index.sqlite --host 127.0.0.1 --port 19502
```

Stop with Ctrl+C. After review, the owner can run `serve` with `--host 100.107.203.51 --port 9502` for a Tailscale demo. Public and wildcard binds are rejected. This is a foreground spike, not a persistent service. No authentication: only bind to a trusted local/Tailscale interface.

`/api/status` reports usable recordings, passages, empty inputs, skipped/failed inputs, source deduplication, index time, capture date span and per-date coverage. `/api/search?q=&from=&to=&offset=0&limit=40` browses or searches passages; total counts all matches, limit is capped at 100. Dates are inclusive capture dates from filenames, interpreted in America/New_York with 12 AM/PM conversion. Bad dates return JSON 400. Punctuation-only input returns no matches. Query words are literal AND terms: punctuation separates words, never invokes FTS syntax. Case folds and both `Wealthbox` and `wealth box` normalize to the same single token. No semantic matching or speaker identity inference.

For each recording, prefer `.global.merged.md`, then legacy `MERGED-*` with a recording stem in metadata, otherwise raw `.txt` chunks. Alternatives are deduplicated. Empty source counts include empty alternatives and canonical “No words transcribed” placeholders, which are not usable speech. Raw chunk suffixes are HHMMSS: `__00500` is 00:05:00 (300 seconds). Other archive formats are intentionally outside this adapter. Canonical merged raw fallback blocks are parsed even without diarized utterances; chunk headings and no-diarization markers are excluded from speech. Quotes remain exact contiguous source substrings; long blocks target at most 1,200 characters, ending at whitespace to keep words intact, with one whitespace-delimited word of overlap so the Wealthbox alias survives boundaries. An indivisible word longer than 1,200 characters is kept whole. All speech text, including tails and boundary whitespace, is retained; overlap can produce duplicate matches. Diarized utterance timestamps are exact source timestamps (not a guarantee of transcription or alignment accuracy). Raw chunk starts and subdivisions are approximate. Source paths remain next to quotes. Empty or missing date coverage never produces invented results.

`/api/recording/<id>` returns indexed transcript passages and provenance. `/api/audio/<id>` serves only the audio path resolved at index time under the archive root; no user-supplied paths. Full `YYYY-MM/<stem>.aac` is preferred. If only a chunk exists, the response labels it `chunk only`, separately reports `audio_offset_seconds`, and enables playback only for passages within that chunk's nominal five-minute window. Single byte ranges (including suffix ranges) return 206; invalid/unsatisfiable ranges return 416. Source symlinks escaping the archive root are refused.

The UI supports live search, date filtering, Yesterday in New York, Clear, pagination, themes, source quotes, clipboard/manual copy, full transcript expansion and native audio with requested offsets. AAC decoding and seeking vary by browser; a seek request is not proof of audible alignment. Raw chunks may contain transcript gaps. This scratch schema does not integrate with Scriberr's live repository/player, and needs no production migration.

Independent acceptance command (owned by the orchestrator):

```sh
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=status.showUntrackedFiles GIT_CONFIG_VALUE_0=all python3 /home/jared/.ringer/jobs/scriberr-search-spike-20261014/verify.py
```

See task `notes.md` and the scratch `verification.json` for measured evidence and inspection limits. Do not put transcript content, audio, databases or logs in tracked source.

The verifier needs permission to open its temporary localhost socket. The process-only Git option expands untracked filenames for its scope assertion; it writes no Git configuration. A headless host without an ALSA output device cannot establish audible playback or word alignment. Inspect and listen on Jared’s desktop for that remaining check.
