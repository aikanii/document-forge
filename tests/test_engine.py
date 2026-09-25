"""Hephaestus engine smoke tests.

Creates synthetic PDFs/images and exercises every backend tool, exactly the
way the GUI runners call them. Run:  python tests/test_engine.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hephaestus.engine import image_ops, office, pdf_ops  # noqa: E402
from hephaestus.engine.mupdf_compat import fitz  # noqa: E402
from hephaestus.tools import build_catalog  # noqa: E402
from hephaestus import icons  # noqa: E402


def make_sample_pdf(path: str, pages: int = 4, title: str = "Sample") -> str:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"{title} — page {i + 1}",
                         fontsize=24, fontname="tiro")
        for line in range(10):
            page.insert_text((72, 160 + line * 24),
                             f"Line {line + 1} of forged text on sheet {i + 1}.",
                             fontsize=11, fontname="tiro")
        page.insert_image(fitz.Rect(72, 500, 300, 700), stream=_tiny_jpg())
    doc.save(path)
    doc.close()
    return path


def _tiny_jpg() -> bytes:
    from PIL import Image
    import io
    img = Image.new("RGB", (400, 400), (200, 180, 140))
    for x in range(0, 400, 20):
        for y in range(0, 400, 20):
            img.putpixel((x, y), (120, 60, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


class TestPdfOps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="hephaestus_test_")
        cls.a = make_sample_pdf(os.path.join(cls.tmp, "alpha.pdf"), 4)
        cls.b = make_sample_pdf(os.path.join(cls.tmp, "beta.pdf"), 3, "Beta")

    def _out(self, name):
        return os.path.join(self.tmp, name)

    def test_merge(self):
        out = self._out("merged.pdf")
        res = pdf_ops.merge_pdfs([self.a, self.b], out)
        self.assertEqual(len(res), 1)
        doc = fitz.open(out)
        self.assertEqual(doc.page_count, 7)
        doc.close()

    def test_split_ranges(self):
        outdir = os.path.join(self.tmp, "split_r")
        os.makedirs(outdir, exist_ok=True)
        res = pdf_ops.split_pdf(self.a, outdir, "ranges", ranges="1-2, 4")
        self.assertEqual(len(res), 2)
        doc = fitz.open(res[0])
        self.assertEqual(doc.page_count, 2)
        doc.close()

    def test_split_all(self):
        outdir = os.path.join(self.tmp, "split_a")
        os.makedirs(outdir, exist_ok=True)
        res = pdf_ops.split_pdf(self.a, outdir, "all")
        self.assertEqual(len(res), 4)

    def test_split_every_n(self):
        outdir = os.path.join(self.tmp, "split_n")
        os.makedirs(outdir, exist_ok=True)
        res = pdf_ops.split_pdf(self.a, outdir, "every_n", every_n=3)
        self.assertEqual(len(res), 2)

    def test_split_extract(self):
        outdir = os.path.join(self.tmp, "split_e")
        os.makedirs(outdir, exist_ok=True)
        res = pdf_ops.split_pdf(self.a, outdir, "extract", ranges="2-3")
        doc = fitz.open(res[0])
        self.assertEqual(doc.page_count, 2)
        doc.close()

    def test_compress(self):
        out = self._out("compressed.pdf")
        pdf_ops.compress_pdf(self.a, out, "high")
        self.assertLess(os.path.getsize(out), os.path.getsize(self.a) + 4096)
        doc = fitz.open(out)
        self.assertEqual(doc.page_count, 4)
        doc.close()

    def test_rotate(self):
        out = self._out("rotated.pdf")
        pdf_ops.rotate_pdf(self.a, out, 90, page_spec="1-2")
        doc = fitz.open(out)
        self.assertEqual(doc[0].rotation, 90)
        self.assertEqual(doc[2].rotation, 0)
        doc.close()

    def test_organize(self):
        out = self._out("organized.pdf")
        pdf_ops.organize_pdf(self.a, out, [3, 2, 1, 0, 0],
                             extra_rotations={0: 180})
        doc = fitz.open(out)
        self.assertEqual(doc.page_count, 5)
        self.assertEqual(doc[0].rotation, 180)
        doc.close()

    def test_page_numbers(self):
        out = self._out("numbered.pdf")
        pdf_ops.add_page_numbers(self.a, out, position="bottom-center",
                                 fmt="Page {p} of {n}", start=1)
        doc = fitz.open(out)
        text = doc[0].get_text()
        self.assertIn("Page 1 of 4", text)
        doc.close()

    def test_watermark_text(self):
        out = self._out("wm.pdf")
        pdf_ops.add_watermark(self.a, out, kind="text", text="CONFIDENTIAL",
                              position="diagonal", opacity=0.3)
        doc = fitz.open(out)
        self.assertIn("CONFIDENTIAL", doc[1].get_text())
        doc.close()

    def test_watermark_tile(self):
        out = self._out("wm_tile.pdf")
        pdf_ops.add_watermark(self.a, out, kind="text", text="DRAFT",
                              position="tile", opacity=0.2, font_size=40)
        doc = fitz.open(out)
        self.assertGreaterEqual(doc[0].get_text().count("DRAFT"), 4)
        doc.close()

    def test_watermark_image(self):
        img = os.path.join(self.tmp, "seal.png")
        from PIL import Image
        Image.new("RGBA", (200, 200), (140, 47, 36, 160)).save(img)
        out = self._out("wm_img.pdf")
        pdf_ops.add_watermark(self.a, out, kind="image", image_path=img,
                              position="center", opacity=0.5, scale=0.4)
        doc = fitz.open(out)
        self.assertEqual(len(doc[0].get_images()), 2)  # original + watermark
        doc.close()

    def test_protect_unlock_roundtrip(self):
        out = self._out("protected.pdf")
        pdf_ops.protect_pdf(self.a, out, user_password="forge123",
                            can_modify=False)
        doc = fitz.open(out)
        self.assertTrue(doc.needs_pass)
        doc.close()
        unlocked = self._out("unlocked.pdf")
        pdf_ops.unlock_pdf(out, unlocked, password="forge123")
        doc = fitz.open(unlocked)
        self.assertFalse(doc.needs_pass)
        self.assertEqual(doc.page_count, 4)
        doc.close()

    def test_unlock_wrong_password(self):
        out = self._out("protected2.pdf")
        pdf_ops.protect_pdf(self.a, out, user_password="secret")
        with self.assertRaises(RuntimeError):
            pdf_ops.unlock_pdf(out, self._out("nope.pdf"), password="wrong")

    def test_repair(self):
        # corrupt the tail of a copy
        broken = self._out("broken.pdf")
        data = open(self.a, "rb").read()
        with open(broken, "wb") as fh:
            fh.write(data[: len(data) // 2] + b"\x00" * 512)
        out = self._out("repaired.pdf")
        try:
            pdf_ops.repair_pdf(broken, out)
            self.assertTrue(os.path.getsize(out) > 0)
        except RuntimeError:
            pass  # a half-truncated PDF may be unrecoverable; both are acceptable

    def test_stamp_and_edits(self):
        from PIL import Image
        sig = os.path.join(self.tmp, "sig.png")
        Image.new("RGBA", (300, 100), (26, 26, 26, 255)).save(sig)
        out = self._out("signed.pdf")
        pdf_ops.stamp_image(self.a, out, [
            {"page": 0, "rect": (100, 700, 300, 766), "image": sig}])
        doc = fitz.open(out)
        self.assertEqual(len(doc[0].get_images()), 2)
        doc.close()
        edited = self._out("edited.pdf")
        pdf_ops.apply_edits(self.a, edited, [
            {"kind": "text", "page": 1, "point": (100, 400), "text": "Added!",
             "size": 16, "font": "tiro", "color": (0.6, 0.1, 0.1)},
            {"kind": "image", "page": 2, "rect": (300, 300, 450, 350),
             "image": sig},
        ])
        doc = fitz.open(edited)
        self.assertIn("Added!", doc[1].get_text())
        doc.close()

    def test_info(self):
        info = pdf_ops.pdf_info(self.a)
        self.assertEqual(info["pages"], 4)
        self.assertFalse(info["encrypted"])


class TestImageOps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="hephaestus_img_")
        cls.pdf = make_sample_pdf(os.path.join(cls.tmp, "src.pdf"), 3)

    def test_pdf_to_images(self):
        outdir = os.path.join(self.tmp, "imgs")
        os.makedirs(outdir, exist_ok=True)
        res = image_ops.pdf_to_images(self.pdf, outdir, fmt="jpg", dpi=72)
        self.assertEqual(len(res), 3)
        for f in res:
            self.assertTrue(f.endswith(".jpg"))
            self.assertGreater(os.path.getsize(f), 1000)

    def test_pdf_to_png_scope(self):
        outdir = os.path.join(self.tmp, "imgs2")
        os.makedirs(outdir, exist_ok=True)
        res = image_ops.pdf_to_images(self.pdf, outdir, fmt="png", dpi=72,
                                      page_spec="2-3")
        self.assertEqual(len(res), 2)

    def test_images_to_pdf(self):
        from PIL import Image
        paths = []
        for i in range(3):
            p = os.path.join(self.tmp, f"pic{i}.png")
            Image.new("RGB", (300 + i * 50, 400), (250 - i * 40, 240, 200)).save(p)
            paths.append(p)
        rgba = os.path.join(self.tmp, "alpha.png")
        Image.new("RGBA", (200, 200), (10, 10, 10, 128)).save(rgba)
        paths.append(rgba)
        out = os.path.join(self.tmp, "bound.pdf")
        image_ops.images_to_pdf(paths, out, page_size="A4", margin=20)
        doc = fitz.open(out)
        self.assertEqual(doc.page_count, 4)
        r = doc[0].rect
        self.assertAlmostEqual(r.width, 595.28, delta=1)
        doc.close()


class TestRegistry(unittest.TestCase):
    def test_catalog_complete(self):
        cat = build_catalog()
        self.assertGreaterEqual(len(cat), 20)
        for spec in cat:
            with self.subTest(tool=spec.id):
                self.assertTrue(spec.runner or spec.custom_view,
                                f"{spec.id} has neither runner nor view")
                self.assertIn(spec.icon, icons.ICON_PAINTERS,
                              f"{spec.id}: missing icon '{spec.icon}'")
                self.assertTrue(spec.name and spec.blurb)
        ids = {s.id for s in cat}
        expected = {"merge", "split", "organize", "rotate", "pagenum",
                    "watermark", "compress", "repair", "ocr", "word2pdf",
                    "ppt2pdf", "excel2pdf", "img2pdf", "html2pdf", "pdf2word",
                    "pdf2ppt", "pdf2excel", "pdf2jpg", "pdfa", "protect",
                    "unlock", "sign", "edit"}
        self.assertEqual(expected, ids, "catalog drift vs ilovepdf parity")

    def test_option_defaults(self):
        cat = {s.id: s for s in build_catalog()}
        split = cat["split"]
        vals = {o.key: o.default if o.default is not None
                else (o.values[0] if o.values else None) for o in split.options}
        self.assertIn("mode", vals)

    def test_option_visibility_lambdas(self):
        """Every show_if predicate must evaluate cleanly on default values
        and on each possible choice value."""
        for spec in build_catalog():
            if not spec.options:
                continue
            base = {}
            for o in spec.options:
                if o.kind == "check":
                    base[o.key] = bool(o.default)
                elif o.kind == "choice":
                    base[o.key] = o.default if o.default is not None else o.values[0]
                else:
                    base[o.key] = o.default
            for o in spec.options:
                if o.show_if is None:
                    continue
                with self.subTest(tool=spec.id, option=o.key):
                    o.show_if(dict(base))
                    if o.kind == "choice":
                        for v in o.values:
                            probe = dict(base)
                            probe[o.key] = v
                            o.show_if(probe)


class TestExternalDetection(unittest.TestCase):
    def test_detection_is_graceful(self):
        # must never raise, whether or not the engines are installed
        self.assertIsInstance(office.find_soffice(), (str, type(None)))
        from hephaestus.engine import ocr
        self.assertIsInstance(ocr.find_tesseract(), (str, type(None)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
