"""Which language this build speaks. The Chinese tree says 'zh'; packaging/localize.py rewrites this file to 'en' when it
produces the English tree. Code that must behave differently per language (time parsing, length budgets, cue words)
reads LANG from here — nothing is decided at runtime by environment or settings, one package is one language."""
LANG = 'zh'
