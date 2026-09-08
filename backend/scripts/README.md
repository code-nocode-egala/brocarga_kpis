# scripts/

Throwaway tools for poking at the Bubble integration by hand. Nothing here is
imported by the app.

## play_bubble.py

Runs `BubbleClient` -> `mappers.map_invoices` end to end and prints what came
back. Open the file, edit the `EDIT ME` block, run it from `backend/`:

    python scripts/play_bubble.py
    python scripts/play_bubble.py --repl

`MODE = "file"` (default) replaces the client's `requests.Session` with a stub
that serves `bubble_data.json` in Bubble's real page envelope, so cursor
pagination and the mapper run exactly as in production while the data is yours
to edit. `MODE = "live"` points the same code at your Bubble app using
`BUBBLE_BASE_URL` / `BUBBLE_API_TOKEN`.

`bubble_data.json` is a plain list of raw Bubble rows -- paste an actual
`/api/1.1/obj/<type>` response body in (either the whole `{"response": {...}}`
envelope or just the `results` list; both are accepted).
