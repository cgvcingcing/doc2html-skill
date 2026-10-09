import base64
from html.parser import HTMLParser
import pathlib
import tempfile
import unittest

from scripts.md2html import embed_images


class ImageParser(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.images = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(attrs)


class EmbeddedImageTests(unittest.TestCase):
    def test_local_images_embed_with_different_attribute_order_and_quotes(self):
        with tempfile.TemporaryDirectory(prefix="doc2html-images-") as directory:
            root = pathlib.Path(directory)
            data = (pathlib.Path(__file__).resolve().parents[1] / "samples/demo.png").read_bytes()
            (root / "a&b.png").write_bytes(data)
            for tag in (
                '<img alt="A &gt; B" src="a&amp;b.png" title="Diagram" />',
                "<img src='a&amp;b.png' class='diagram' alt='A &gt; B'>",
            ):
                with self.subTest(tag=tag):
                    attrs = dict(ImageParser(embed_images(tag, root, True)).images[0])
                    self.assertEqual(base64.b64decode(attrs["src"].split(",", 1)[1]), data)
                    self.assertEqual(attrs["alt"], "A > B")

    def test_missing_image_preserves_attributes_and_has_one_missing_class(self):
        with tempfile.TemporaryDirectory(prefix="doc2html-images-") as directory:
            tag = '<img alt="Original description" class="diagram" src="missing.png">'
            attrs = ImageParser(embed_images(tag, pathlib.Path(directory), True)).images[0]
            self.assertEqual(sum(name == "alt" for name, _ in attrs), 1)
            self.assertEqual(sum(name == "class" for name, _ in attrs), 1)
            values = dict(attrs)
            self.assertEqual(values["alt"], "Original description")
            self.assertEqual(values["class"].split(), ["diagram", "img-missing"])

    def test_external_and_explicitly_linked_images_keep_their_source(self):
        for tag, embed in (
            ('<img alt="External" src="https://example.com/diagram.png">', True),
            ('<img alt="Linked" src="diagram.png">', False),
            ('<img alt="Embedded" src="data:image/png;base64,AA==">', True),
        ):
            with self.subTest(tag=tag):
                self.assertEqual(embed_images(tag, pathlib.Path("."), embed), tag)


if __name__ == "__main__":
    unittest.main()
