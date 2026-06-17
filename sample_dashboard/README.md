# Sample Check-in / Check-out Dashboard

This is a small standalone sample dashboard demonstrating a check-in / check-out flow. It is intentionally not connected to the main app.

How to use

- Open `index.html` directly in your browser, or run a simple static server from the folder:

```bash
cd sample_dashboard
python -m http.server 8000
# then open http://localhost:8000 in your browser
```

Sessions are stored in the browser's `localStorage` under `sample_sessions_v1`.
