import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from src.config import BASE_DIR
from src.services.operations import run_process


@pytest.mark.browser
def test_browser_layout_keyboard_and_generation(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {
        **os.environ,
        "APP_MEDIA_DIR": str(tmp_path / "browser-media"),
        "LOG_FORMAT": "json",
    }
    output = tmp_path / "server.log"
    with output.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "tests/browser_app.py",
                f"--server.port={port}",
                "--server.address=127.0.0.1",
                "--server.headless=true",
            ],
            cwd=BASE_DIR,
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            address = f"http://127.0.0.1:{port}"
            for _ in range(100):
                try:
                    urllib.request.urlopen(address + "/_stcore/health", timeout=1).close()
                    break
                except (OSError, urllib.error.URLError):
                    if process.poll() is not None:
                        pytest.fail(output.read_text(encoding="utf-8"))
                    time.sleep(0.1)
            with sync_playwright() as playwright:
                executable = next(
                    (
                        str(path)
                        for path in (
                            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
                        )
                        if path.is_file()
                    ),
                    None,
                )
                browser = playwright.chromium.launch(headless=True, executable_path=executable)
                page = browser.new_page(reduced_motion="reduce")
                page.goto(address)
                expect(
                    page.get_by_role("heading", name="Text în audio și video", exact=True)
                ).to_be_visible(timeout=30000)
                screenshots = tmp_path / "screenshots"
                screenshots.mkdir(parents=True, exist_ok=True)
                for width in (360, 768, 1280):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.get_by_role("radio", name="Generator", exact=True).locator("..").click()
                    expect(page.get_by_role("textbox", name="Text", exact=True)).to_be_visible()
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth + 1"
                    )
                    page.screenshot(
                        path=str(screenshots / f"generator-{width}.png"), full_page=True
                    )
                    page.get_by_role("radio", name="Istoric audio", exact=True).locator(
                        ".."
                    ).click()
                    expect(page.get_by_text("28 rezultate", exact=False)).to_have_count(0)
                    expect(page.get_by_text("Pagina 1 · 25 rezultate", exact=False)).to_be_visible()
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth + 1"
                    )
                    page.screenshot(path=str(screenshots / f"history-{width}.png"), full_page=True)
                page.get_by_role("spinbutton", name="Pagina", exact=True).fill("2")
                page.get_by_role("spinbutton", name="Pagina", exact=True).press("Enter")
                expect(page.get_by_text("Pagina 2 · 3 rezultate", exact=False)).to_be_visible()
                page.get_by_role("radio", name="Generator", exact=True).locator("..").click()
                text_input = page.get_by_role("textbox", name="Text", exact=True)
                text_input.fill("This is a message for the browser test.")
                text_input.press("Tab")
                expect(page.get_by_role("button", name="Generează MP3", exact=True)).to_be_enabled()
                page.keyboard.press("Tab")
                assert page.evaluate("document.activeElement !== document.body")
                if shutil.which("ffmpeg") and shutil.which("ffprobe"):
                    page.get_by_role("button", name="Generează MP3", exact=True).click()
                    expect(page.get_by_role("status").filter(has_text="secunde")).to_be_visible(
                        timeout=30000
                    )
                    status = page.get_by_role("status").filter(has_text="secunde")
                    expect(status).to_have_attribute("aria-live", "polite")
                    expect(status).to_have_attribute("aria-atomic", "true")
                    assert (
                        status.evaluate("element => getComputedStyle(element).animationName")
                        == "none"
                    )
                    accessibility = page.context.new_cdp_session(page).send(
                        "Accessibility.getFullAXTree"
                    )
                    assert any(
                        node.get("role", {}).get("value") == "status"
                        for node in accessibility["nodes"]
                    )
                    expect(
                        page.get_by_role("button", name="Descarcă MP3", exact=True)
                    ).to_be_visible(timeout=30000)
                    page.reload()
                    expect(
                        page.get_by_role("button", name="Descarcă MP3", exact=True)
                    ).to_be_visible(timeout=30000)
                    background = tmp_path / "background.mp4"
                    assert (
                        run_process(
                            [
                                shutil.which("ffmpeg"),
                                "-v",
                                "error",
                                "-f",
                                "lavfi",
                                "-i",
                                "testsrc2=size=640x360:rate=30",
                                "-t",
                                "0.5",
                                "-c:v",
                                "libx264",
                                str(background),
                            ],
                            30,
                        ).returncode
                        == 0
                    )
                    page.get_by_role("textbox", name="Text", exact=True).fill(
                        "This is a video for the browser test."
                    )
                    page.get_by_role("textbox", name="Text", exact=True).press("Tab")
                    page.get_by_role("radio", name="MP4", exact=True).locator("..").click()
                    expect(
                        page.get_by_role("slider", name="Introducere cu titlu (secunde)")
                    ).to_have_attribute("aria-valuenow", "3")
                    expect(page.get_by_text("Centru", exact=True)).to_be_visible()
                    page.locator('input[type="file"]').set_input_files(str(background))
                    page.get_by_role(
                        "checkbox", name="Accept subtitrări aproximative", exact=False
                    ).locator("..").click()
                    page.get_by_role("button", name="Previzualizează încadrarea").click()
                    expect(page.get_by_text("Încadrarea 9:16.", exact=False)).to_be_visible(
                        timeout=30000
                    )
                    page.screenshot(path=str(screenshots / "video-preview.png"), full_page=True)
                    page.get_by_role("button", name="Generează MP4", exact=True).click()
                    expect(
                        page.get_by_role("button", name="Descarcă MP4", exact=True)
                    ).to_be_visible(timeout=60000)
                    page.screenshot(path=str(screenshots / "video-result.png"), full_page=True)
                browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
