# gphotos-fixer docs site 📚

The landing page and documentation website for [**gphotos-fixer**](https://github.com/nazimcanislam/gphotos-fixer), a Python tool that rescues and organizes your Google Photos Takeout exports 📸

🌐 **Live site:** https://nazimcanislam.github.io/gphotos-fixer/

> 💡 Looking for the tool itself (installation, usage, CLI flags)? See the [main README](../README.md) ([Türkçe](../README.tr.md)). This folder only contains the website.

---

## 🎯 What is this?

A small static site built with [Astro](https://astro.build) that:

- 🧭 explains the problem with Google Takeout exports (broken JSON names, Windows path limits, wrong timestamps)
- ✨ showcases the features and the output folder structure
- 🚀 gives a quick usage guide for new users
- 🔎 helps people find the project via search engines (SEO and `schema.json` structured data)

---

## 🧱 Tech stack

| Tool | Purpose |
|------|---------|
| [Astro](https://astro.build) | Static site generator |
| [Bun](https://bun.sh) | Package manager and script runner |
| [GitHub Pages](https://pages.github.com) | Hosting |
| [GitHub Actions](../.github/workflows/deploy-docs.yml) | Automatic build and deploy |

Requires **Node.js 22.23.4+** (see `engines` in `package.json`).

---

## 📁 Project structure

```text
docs/
├── public/                  # Static files served as-is
│   ├── assets/favicon_io/   # Favicons and app icons
│   ├── gphotos-fixer-og-image.jpg   # Social preview image
│   └── robots.txt
├── src/
│   ├── assets/              # Images processed by Astro (logo)
│   ├── components/          # Page sections
│   │   ├── Header.astro
│   │   ├── Hero.astro
│   │   ├── Problem.astro
│   │   ├── Features.astro
│   │   ├── Usage.astro
│   │   ├── Output.astro
│   │   ├── AlsoByAuthor.astro
│   │   └── Footer.astro
│   ├── data/schema.json     # Structured data (JSON-LD) for SEO
│   ├── layouts/Layout.astro # Base HTML layout and meta tags
│   ├── pages/index.astro    # The single page that assembles all sections
│   └── styles/base.css      # Global styles
├── astro.config.mjs         # Site URL and base path
└── package.json
```

---

## 🧞 Commands

All commands are run from the `docs/` folder:

| Command | Action |
|---------|--------|
| `bun install` | 📦 Install dependencies |
| `bun run dev` | 🔥 Start the dev server at `localhost:4321/gphotos-fixer/` |
| `bun run build` | 🏗️ Build the production site to `./dist/` |
| `bun run preview` | 👀 Preview the production build locally |

> 📌 The site is served under the `/gphotos-fixer` base path (set in `astro.config.mjs`), so local URLs include it too.

---

## 🚢 Deployment

The site deploys automatically to GitHub Pages with the
[`deploy-docs.yml`](../.github/workflows/deploy-docs.yml) workflow.

- ✅ It runs on pushes to `main` that change files in `docs/` (or the workflow file itself).
- 🖐️ It can also be started manually from the **Actions** tab (*workflow_dispatch*).
- 🙅 Changes to the Python code or the root READMEs do **not** trigger a deploy.

---

## 🔄 Keeping things in sync

When the tool changes, remember the site:

- 🏷️ **New version?** Update `softwareVersion` in `src/data/schema.json` (and `__version__` in `gphotos_fixer/__init__.py`).
- 🆕 **New feature or CLI flag?** Update `Features.astro` and `Usage.astro` so the site matches the main README.
- 📂 **Output structure changed?** Update `Output.astro`.

---

## 🤝 Contributing

Found a typo, a broken link, or a confusing explanation on the site? Issues and PRs are welcome! 💙

📄 Licensed under the [MIT License](../LICENSE).
