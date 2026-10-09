import argparse
import os
import pathlib
import tempfile
import unittest

from scripts.md2html import convert

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "Browser checks require Playwright")
class ImageViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="doc2html-viewer-test-")
        cls.addClassCleanup(cls.workspace.cleanup)
        root = pathlib.Path(cls.workspace.name)
        (root / "large.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10371" height="3289">'
            '<rect width="10371" height="3289" fill="white"/>'
            '<path d="M0 0H10371V200H0Z" fill="teal"/>'
            '<text x="100" y="400" font-size="100">Large requirement diagram</text></svg>'
        )
        source = root / "input.md"
        source.write_text('''# Image preview fixture

## Legacy image panel

<figure class="source-panel">
<div class="source-controls"><input type="checkbox" class="original-size" checked><label>Original size</label></div>
<div class="source-viewport"><img src="large.svg" alt="Large image"></div>
<figcaption>Original image caption</figcaption>
</figure>

## Normal and linked images

![Normal image](large.svg)

<a href="https://example.com/original"><img src="large.svg" alt="Linked image"></a>

![Missing image](missing.png)

| Column | Content |
| --- | --- |
| One | Original table text |

<style>
.source-viewport{max-height:700px;overflow:auto;}
.source-panel:has(.original-size:checked) img{max-width:none;width:auto;}
</style>
''', encoding="utf-8")
        cls.output = root / "output.html"
        convert([str(source)], argparse.Namespace(
            output=str(cls.output), title=None, subtitle=None, accent="#4f46e5",
            assets_base=None, link_images=False,
        ))
        (root / "large.svg").unlink()
        cls.runtime = sync_playwright().start()
        cls.addClassCleanup(cls.runtime.stop)
        try:
            executable = os.environ.get("DOC2HTML_TEST_BROWSER")
            cls.browser = cls.runtime.chromium.launch(
                headless=True, **({"executable_path": executable} if executable else {})
            )
        except Exception as error:
            raise unittest.SkipTest(f"Chromium unavailable: {error}")
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.requests = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("request", lambda request: self.requests.append(request.url)
                     if request.url.startswith(("http:", "https:")) else None)
        self.page.goto(self.output.as_uri(), wait_until="load")
        self.page.evaluate("document.documentElement.style.scrollBehavior='auto'")
        self.addCleanup(self.check_errors)

    def check_errors(self):
        self.assertEqual(self.errors, [])
        self.assertEqual(self.requests, [])

    def open_image(self):
        self.page.locator(".image-open").first.click()
        self.page.wait_for_function("""() => {
            const dialog=document.querySelector('.image-viewer');
            const image=dialog.querySelector('.iv-image');
            return dialog.open && image.complete && image.naturalWidth && image.style.visibility==='visible';
        }""")

    def geometry(self):
        return self.page.evaluate("""() => {
            const stage=document.querySelector('.iv-stage').getBoundingClientRect();
            const image=document.querySelector('.iv-image').getBoundingClientRect();
            return {stage:{x:stage.x,y:stage.y,width:stage.width,height:stage.height},
                    image:{x:image.x,y:image.y,width:image.width,height:image.height}};
        }""")

    def assert_fitted(self):
        bounds = self.geometry()
        stage, image = bounds["stage"], bounds["image"]
        self.assertGreaterEqual(image["x"], stage["x"] - 1)
        self.assertGreaterEqual(image["y"], stage["y"] - 1)
        self.assertLessEqual(image["x"] + image["width"], stage["x"] + stage["width"] + 1)
        self.assertLessEqual(image["y"] + image["height"], stage["y"] + stage["height"] + 1)

    def test_large_image_opens_fitted_outside_the_document_frame(self):
        self.assertEqual(self.page.locator(".source-controls").count(), 0)
        self.assertEqual(self.page.locator(".image-open").count(), 2)
        self.assertEqual(self.page.locator("a .image-open").count(), 0)
        self.assertEqual(self.page.locator("a img").get_attribute("alt"), "Linked image")
        self.assertTrue(self.page.locator('.content img:not(.img-missing)').evaluate_all(
            "images=>images.every(image=>image.getAttribute('src').startsWith('data:'))"
        ))
        self.assertEqual(self.page.locator('img.img-missing').count(), 1)
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
        preview = self.page.locator(".source-panel img").bounding_box()
        self.open_image()
        self.assert_fitted()
        self.assertGreater(self.geometry()["stage"]["width"], preview["width"])
        self.page.locator('[data-action="original"]').click()
        self.assertAlmostEqual(self.geometry()["image"]["width"], 10371, delta=1)
        self.page.locator('[data-action="fit"]').click()
        self.assert_fitted()

    def test_zoom_at_cursor_and_drag_change_only_the_preview(self):
        self.open_image()
        before = self.geometry()
        point_x = before["stage"]["x"] + before["stage"]["width"] / 2 + 50
        point_y = before["stage"]["y"] + before["stage"]["height"] / 2
        self.page.mouse.move(point_x, point_y)
        self.page.mouse.wheel(0, -500)
        self.page.wait_for_function("document.querySelector('.iv-image').getBoundingClientRect().width>2000")
        after = self.geometry()
        self.assertGreater(after["image"]["width"], before["image"]["width"])
        original_point = (point_x - before["image"]["x"]) / before["image"]["width"]
        zoomed_point = (point_x - after["image"]["x"]) / after["image"]["width"]
        self.assertAlmostEqual(original_point, zoomed_point, delta=.002)
        self.page.locator('[data-action="original"]').click()
        before = self.geometry()
        self.page.mouse.move(point_x, point_y)
        self.page.mouse.down()
        self.page.mouse.move(point_x + 120, point_y + 60, steps=4)
        self.page.mouse.up()
        after = self.geometry()
        self.assertAlmostEqual(after["image"]["x"] - before["image"]["x"], 120, delta=2)
        self.assertAlmostEqual(after["image"]["y"] - before["image"]["y"], 60, delta=2)
        self.page.keyboard.press("+")
        self.assertGreater(self.geometry()["image"]["width"], after["image"]["width"])
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth<=innerWidth"))

    def test_escape_restores_reading_position_and_keyboard_focus(self):
        self.page.locator(".image-open").first.focus()
        scroll_y = self.page.evaluate("scrollY")
        self.open_image()
        self.page.keyboard.press("Tab")
        self.assertTrue(self.page.evaluate("document.querySelector('.image-viewer').contains(document.activeElement)"))
        self.page.keyboard.press("Escape")
        self.assertFalse(self.page.locator(".image-viewer").evaluate("el=>el.open"))
        self.assertFalse(self.page.locator("body").evaluate("el=>el.classList.contains('image-preview-open')"))
        self.assertAlmostEqual(self.page.evaluate("scrollY"), scroll_y, delta=1)
        self.assertTrue(self.page.locator(".image-open").first.evaluate("el=>el===document.activeElement"))
        self.open_image()
        self.assert_fitted()
        self.page.locator('[data-action="close"]').click()
        self.assertFalse(self.page.locator(".image-viewer").evaluate("el=>el.open"))

    def test_mobile_resize_keeps_fit_and_controls_in_the_viewport(self):
        self.open_image()
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.wait_for_function("document.querySelector('.iv-image').getBoundingClientRect().width<390")
        self.assert_fitted()
        for action in ("in", "out", "fit", "original", "close"):
            bounds = self.page.locator(f'[data-action="{action}"]').bounding_box()
            self.assertGreaterEqual(bounds["x"], 0)
            self.assertLessEqual(bounds["x"] + bounds["width"], 390)
            self.assertLessEqual(bounds["y"] + bounds["height"], 844)
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth<=innerWidth"))

    def test_print_hides_preview_and_removes_thumbnail_height_limit(self):
        self.open_image()
        self.page.emulate_media(media="print")
        self.assertEqual(self.page.locator(".image-viewer").evaluate("el=>getComputedStyle(el).display"), "none")
        self.assertEqual(self.page.locator(".image-open").first.evaluate("el=>getComputedStyle(el).display"), "none")
        self.assertEqual(self.page.locator(".source-panel img").evaluate("el=>getComputedStyle(el).maxHeight"), "none")


if __name__ == "__main__":
    unittest.main()
