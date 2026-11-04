# Orangepedia (static copy)

موقع ثابت (HTML/CSS/JS) — يشتغل على GitHub Pages بدون أي سيرفر.

- `index.html` — الـ Home (نقطة البداية) + بحث فوري عربي/إنجليزي.
- باقي الصفحات: `freemax-new.html`, `services.html` … إلخ.
- `search.html` — صفحة نتايج البحث.

## النشر على GitHub Pages
1. ارفع كل محتوى الفولدر على ريبو.
2. Settings → Pages → Branch: `main` / root → Save.

## إضافة صفحات جديدة
1. احفظ الصفحة HTML (SingleFile) وحطّها في `source/`.
2. `pip install beautifulsoup4 lxml` ثم `python tools/build.py`
3. الصفحة هتظهر في الـ Home والبحث، وكروت الـ Home الرمادي هتتفعّل لو اسمها مطابق.

كلمات بحث عربي لكل صفحة في `aliases.json` (اختياري): `{"slug": "كلمات عربي"}`.
