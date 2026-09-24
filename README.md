# Hn38videoAItool

Desktop automation workspace for Google Flow and Meta AI.

- App: Hn38videoAItool
- Version: 1.0.0
- Creator: Hoainguyenstudio
- Zalo: 0965.043.000

## UI

- Dark neon UI inspired by the Hn38 design.
- Animation can be turned ON/OFF.
- Animation level: Nhẹ / Vừa / Mạnh.
- Themes: Neon Dark, Midnight Purple, Cyber Blue, Black & Red, Light.
- Settings are saved locally in `data/settings.json`.

## Login profiles

Meta AI and Google Flow use separate persistent browser profiles:

- `browser_profiles/meta`
- `browser_profiles/flow`

The application never needs your main Chrome profile. Login is performed manually in a visible browser window. Browser state is kept locally by the persistent profile.

Do not commit browser profiles or auth state to GitHub.

## Windows build

GitHub Actions installs Python, PySide6, Playwright and bundled Chromium, then packages the application with PyInstaller.

The application is only considered successful for a generation task when a real downloadable result is detected and saved.
