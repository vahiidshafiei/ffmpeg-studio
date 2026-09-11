from app.i18n import translator


def test_english_locale_loads_and_resolves_real_text():
    translator.set_language("en")
    assert translator.has_loaded_strings()
    assert translator.t("nav.home") == "Home"
    assert translator.t("nav.home") != "nav.home"  # would equal the raw key if loading failed


def test_turkish_locale_loads_and_resolves_real_text():
    translator.set_language("tr")
    assert translator.has_loaded_strings()
    assert translator.t("nav.home") == "Ana Sayfa"
    translator.set_language("en")  # reset for any tests that run after this one


def test_missing_key_falls_back_to_key_itself():
    translator.set_language("en")
    assert translator.t("this.key.does.not.exist") == "this.key.does.not.exist"


def test_unknown_language_code_falls_back_to_english_strings():
    translator.set_language("xx-not-a-real-language")
    # No xx.json exists, but English fallback still loads for any non-English
    # code, so the app keeps working (just in English) rather than breaking.
    assert translator.has_loaded_strings()
    assert translator.t("nav.home") == "Home"
    translator.set_language("en")  # reset


def test_has_loaded_strings_detects_the_actual_packaging_bug(monkeypatch, tmp_path):
    # Simulates exactly what happened when app/i18n/locales/ wasn't bundled
    # into a packaged .exe: the locales directory exists but has no files in
    # it, so both the requested language and the English fallback come back
    # empty. This is the scenario has_loaded_strings() exists to catch.
    monkeypatch.setattr(translator, "_LOCALES_DIR", tmp_path)
    translator.set_language("en")
    assert translator.has_loaded_strings() is False
    assert translator.t("nav.home") == "nav.home"  # falls back to the raw key
    monkeypatch.undo()
    translator.set_language("en")  # reset with the real locales dir restored
