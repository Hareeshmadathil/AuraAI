# Installation and rollback

No packages were installed automatically. After founder review, use the existing virtual environment:

```powershell
python -m pip install "crawl4ai==0.9.1" "browser-use==0.13.4"
python -m playwright install chromium
```

Do not install optional ML, GPU, Docker, video, or `all` extras. Before installation, capture `python -m pip freeze`. Roll back with `python -m pip uninstall crawl4ai browser-use playwright` and restore the captured requirements; remove only the dedicated Playwright Chromium cache after confirming it is not shared.
