"""Selective redaction preserves every pixel outside detected rectangles."""

import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException
from PIL import Image

from hackyeah import photo_privacy, photos


class PhotoPrivacyTests(unittest.TestCase):
    def test_only_detected_regions_change_and_png_is_lossless(self):
        for mode in ("RGB", "RGBA"):
            with self.subTest(mode=mode):
                image = Image.new(mode, (20, 20))
                image.putdata(
                    [
                        (x * 10, y * 10, (x + y) * 5, (x * 13) % 256)
                        if mode == "RGBA"
                        else (x * 10, y * 10, (x + y) * 5)
                        for y in range(20)
                        for x in range(20)
                    ]
                )
                boxes = [(2, 3, 8, 12), (12, 10, 20, 20)]
                with patch.object(photo_privacy, "detect_regions", return_value=boxes):
                    result = photo_privacy.anonymize(image)
                output = BytesIO()
                result.save(output, format="PNG")
                with Image.open(BytesIO(output.getvalue())) as saved:
                    self.assertEqual(saved.mode, mode)
                    self.assertEqual(saved.size, image.size)
                    for y in range(20):
                        for x in range(20):
                            inside = any(
                                a <= x < c and b <= y < d for a, b, c, d in boxes
                            )
                            if not inside:
                                self.assertEqual(
                                    saved.getpixel((x, y)), image.getpixel((x, y))
                                )
                    for box in boxes:
                        self.assertEqual(len(set(saved.crop(box).getdata())), 1)
                self.assertNotEqual(result.tobytes(), image.tobytes())

    def test_no_detections_preserves_all_pixels(self):
        image = Image.new("RGBA", (5, 5), (15, 20, 25, 30))
        with patch.object(photo_privacy, "detect_regions", return_value=[]):
            result = photo_privacy.anonymize(image)
        self.assertEqual(result.tobytes(), image.tobytes())

    def test_detection_failure_rejects_upload_before_storage(self):
        output = BytesIO()
        Image.new("RGB", (10, 10)).save(output, format="PNG")
        with (
            patch.object(
                photo_privacy, "detect_regions", side_effect=RuntimeError("offline")
            ),
            patch.object(photos, "_file_path") as storage,
            self.assertLogs(photos.logger, level="ERROR"),
            self.assertRaises(HTTPException) as caught,
        ):
            photos.create("user_test", output.getvalue())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail, "PHOTO_ANALYSIS_UNAVAILABLE")
        storage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
