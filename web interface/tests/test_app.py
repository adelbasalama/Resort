from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_example_feedback_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ui.sqlite3"))
    monkeypatch.setenv("SERVICE_MODE", "demo")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20).run()
    assert not app.exception
    assert app.button[0].disabled
    app.radio[0].set_value("Try an example").run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["result"].recognition.item_name == "Drink can"
    app.button[0].click().run()
    assert not app.exception
    assert len(app.success) == 1
    next(button for button in app.button if "Sort another" in button.label).click().run()
    assert not app.exception
    assert app.radio[0].value == "Upload a photo"
