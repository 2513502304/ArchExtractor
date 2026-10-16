import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import patoolib
from loguru import logger
from patoolib.util import PatoolError

from archextractor import ArchExtractor
from archextractor.utils import is_auto_generated, is_auto_generated_dir


class ArchExtractorTest(unittest.TestCase):
    def setUp(self):
        logger.disable("archextractor")
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()
        logger.enable("archextractor")

    def make_zip(self, path: Path, entries: dict[str, str]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
        return path

    def assert_tree(self, root: Path, expected: set[str]):
        actual = {
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(actual, expected)

    def assert_no_directories_below(self, root: Path):
        directories = [
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_dir()
        ]
        self.assertEqual(directories, [])

    def test_extractall_expands_nested_archive_at_extracted_root(self):
        inner = self.make_zip(self.base / "inner.zip", {"inside.txt": "nested"})
        top = self.base / "top.zip"
        with zipfile.ZipFile(top, "w") as archive:
            archive.write(inner, "inner.zip")

        out = self.base / "out"
        extractor = ArchExtractor()
        extractor.extractall(src=str(top), dst=str(out), verbosity=-1, cleanup=False)

        self.assert_tree(out, {"inner.zip", "inside.txt"})

    def test_extractall_skips_file_when_archive_detection_backend_errors(self):
        source = self.make_zip(self.base / "source.zip", {"069.jpg": "jpeg payload"})
        out = self.base / "out"

        original_is_archive = patoolib.is_archive

        def is_archive(path):
            if Path(path).name == "069.jpg":
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["/usr/bin/file", "--brief", str(path)],
                    output="ERROR: JPEG image data, Exif standard: [TIFF image data] name use count (50) exceeded",
                )
            return original_is_archive(path)

        with mock.patch(
            "archextractor.archextractor.patoolib.is_archive",
            side_effect=is_archive,
        ):
            result = ArchExtractor().extractall(
                src=str(source),
                dst=str(out),
                verbosity=-1,
                cleanup=False,
            )

        self.assertEqual(result, str(out))
        self.assert_tree(out, {"069.jpg"})

    def test_extractall_can_reuse_one_extractor_for_multiple_archives(self):
        first = self.make_zip(self.base / "first.zip", {"first.txt": "1"})
        second = self.make_zip(self.base / "second.zip", {"second.txt": "2"})
        out1 = self.base / "out1"
        out2 = self.base / "out2"

        extractor = ArchExtractor()
        extractor.extract(src=str(first), dst=str(out1), verbosity=-1)
        extractor.extract(src=str(second), dst=str(out2), verbosity=-1)

        self.assert_tree(out1, {"first.txt"})
        self.assert_tree(out2, {"second.txt"})

    def test_cleanup_does_not_delete_source_when_extraction_fails(self):
        source = self.make_zip(self.base / "source.zip", {"file.txt": "content"})
        out = self.base / "out"
        extractor = ArchExtractor()

        with mock.patch(
            "archextractor.archextractor.patoolib.extract_archive",
            side_effect=PatoolError("simulated failure"),
        ):
            result = extractor.extract(
                src=str(source),
                dst=str(out),
                verbosity=-1,
                cleanup=True,
            )

        self.assertIsNone(result)
        self.assertTrue(source.exists())

    def test_extractall_does_not_delete_source_when_nested_archive_fails(self):
        source = self.make_zip(self.base / "source.zip", {"file.txt": "content"})
        out = self.base / "out"

        def extract_archive(src, outdir, **kwargs):
            if Path(src) == source:
                (Path(outdir) / "nested.zip").write_text("not extracted yet")
                return str(outdir)
            raise PatoolError("simulated nested failure")

        with (
            mock.patch.object(ArchExtractor, "test_archive", return_value=True),
            mock.patch(
                "archextractor.archextractor.patoolib.extract_archive",
                side_effect=extract_archive,
            ),
        ):
            result = ArchExtractor().extractall(
                src=str(source),
                dst=str(out),
                verbosity=-1,
                cleanup=True,
            )

        self.assertIsNone(result)
        self.assertTrue(source.exists())
        # A failed recursive extraction is discarded as a whole: nothing it
        # produced -- the outer archive's output included -- is left in dst.
        self.assert_tree(out, set())

    def test_extractall_deletes_source_after_nested_extraction_succeeds(self):
        inner = self.make_zip(self.base / "inner.zip", {"inside.txt": "nested"})
        source = self.base / "source.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.write(inner, "inner.zip")
        out = self.base / "out"

        result = ArchExtractor().extractall(
            src=str(source),
            dst=str(out),
            verbosity=-1,
            cleanup=True,
        )

        self.assertEqual(result, str(out))
        self.assertFalse(source.exists())
        self.assertFalse((out / "inner.zip").exists())
        self.assert_tree(out, {"inside.txt"})

    def test_invalid_mode_does_not_extract_files(self):
        source = self.make_zip(self.base / "source.zip", {"file.txt": "content"})
        out = self.base / "out"
        extractor = ArchExtractor()

        with self.assertRaises(ValueError):
            extractor.extract(
                src=str(source),
                dst=str(out),
                mode="bad",  # type: ignore[arg-type]
                verbosity=-1,
            )

        self.assertFalse((out / "file.txt").exists())

    def test_flatten_keeps_file_named_like_existing_directory_at_top_level(self):
        source = self.make_zip(
            self.base / "archive.zip",
            {
                "archive/foo/root.txt": "root",
                "archive/bar/foo": "file named foo",
            },
        )
        out = self.base / "out"
        extractor = ArchExtractor()

        extractor.extractall(
            src=str(source),
            dst=str(out),
            mode="e",
            verbosity=-1,
            cleanup=False,
        )

        self.assert_tree(out, {"root.txt", "foo"})
        self.assertTrue((out / "foo").is_file())
        self.assert_no_directories_below(out)

    def test_extractall_flattens_tar_gz_without_guessing_directory_name(self):
        payload = self.base / "payload"
        payload.mkdir()
        (payload / "file.txt").write_text("content")
        source = self.base / "payload.tar.gz"
        with tarfile.open(source, "w:gz") as archive:
            archive.add(payload, arcname="payload")
        out = self.base / "out"

        ArchExtractor().extractall(
            src=str(source),
            dst=str(out),
            mode="e",
            verbosity=-1,
            cleanup=False,
        )

        self.assert_tree(out, {"file.txt"})
        self.assert_no_directories_below(out)

    def test_paxheader_directory_is_auto_generated(self):
        self.assertTrue(is_auto_generated("archive/PaxHeader"))
        self.assertTrue(is_auto_generated("archive/PaxHeader/file"))

    def test_folder_named_like_an_editor_backup_keeps_its_files(self):
        # Romanised manga titles often end in "~"; the "*~" pattern is for files.
        source = self.make_zip(
            self.base / "source.zip",
            {
                "Kaguya-sama ~Love is War~/001.jpg": "1",
                "Kaguya-sama ~Love is War~/002.jpg": "2",
            },
        )
        out = self.base / "out"

        result = ArchExtractor().extractall(
            src=str(source), dst=str(out), verbosity=-1, cleanup=False
        )

        self.assertEqual(result, str(out))
        self.assert_tree(
            out,
            {
                "Kaguya-sama ~Love is War~/001.jpg",
                "Kaguya-sama ~Love is War~/002.jpg",
            },
        )

    def test_folder_named_icon_inside_a_nested_archive_keeps_its_files(self):
        inner = self.make_zip(
            self.base / "volume.zip", {"Icon/001.jpg": "1", "Icon/002.jpg": "2"}
        )
        source = self.base / "outer.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("cover.jpg", "cover")
            archive.write(inner, "volume.zip")
        out = self.base / "out"

        ArchExtractor().extractall(
            src=str(source), dst=str(out), verbosity=-1, cleanup=True
        )

        self.assert_tree(out, {"cover.jpg", "Icon/001.jpg", "Icon/002.jpg"})

    def test_generated_directories_and_files_are_still_removed(self):
        source = self.make_zip(
            self.base / "source.zip",
            {
                "book/001.jpg": "1",
                "book/.DS_Store": "x",
                "book/notes.txt~": "backup",
                "__MACOSX/book/._001.jpg": "x",
            },
        )
        out = self.base / "out"

        ArchExtractor().extract(src=str(source), dst=str(out), verbosity=-1)

        self.assert_tree(out, {"book/001.jpg"})

    def test_extract_leaves_existing_destination_content_alone(self):
        out = self.base / "out"
        (out / "old").mkdir(parents=True)
        (out / "old" / "page.jpg").write_text("old page")
        (out / "keep~").write_text("not ours")
        (out / "Thumbs.db").write_text("not ours either")
        source = self.make_zip(self.base / "source.zip", {"new/001.jpg": "new"})

        result = ArchExtractor().extract(
            src=str(source), dst=str(out), mode="e", verbosity=-1
        )

        self.assertEqual(result, str(out))
        # Cleanup and flattening only touch what this extraction produced.
        self.assert_tree(out, {"old/page.jpg", "keep~", "Thumbs.db", "001.jpg"})

    def test_extractall_leaves_existing_destination_content_alone(self):
        out = self.base / "out"
        (out / "old").mkdir(parents=True)
        (out / "old" / "page.jpg").write_text("old page")
        inner = self.make_zip(self.base / "inner.zip", {"in/002.jpg": "2"})
        source = self.base / "source.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("a/001.jpg", "1")
            archive.write(inner, "inner.zip")

        ArchExtractor().extractall(
            src=str(source), dst=str(out), mode="e", verbosity=-1, cleanup=True
        )

        self.assert_tree(out, {"old/page.jpg", "001.jpg", "002.jpg"})

    def test_name_clash_with_existing_file_is_renamed_not_overwritten(self):
        out = self.base / "out"
        out.mkdir()
        (out / "001.jpg").write_text("existing")
        source = self.make_zip(self.base / "source.zip", {"001.jpg": "extracted"})

        ArchExtractor().extract(src=str(source), dst=str(out), verbosity=-1)

        self.assertEqual((out / "001.jpg").read_text(), "existing")
        self.assertEqual((out / "001(1).jpg").read_text(), "extracted")

    def test_failed_extraction_leaves_no_partial_output(self):
        out = self.base / "out"
        source = self.make_zip(self.base / "source.zip", {"file.txt": "content"})

        def extract_archive(src, outdir, **kwargs):
            (Path(outdir) / "half-written.txt").write_text("partial")
            raise PatoolError("simulated failure mid-extraction")

        with mock.patch(
            "archextractor.archextractor.patoolib.extract_archive",
            side_effect=extract_archive,
        ):
            result = ArchExtractor().extract(
                src=str(source), dst=str(out), verbosity=-1
            )

        self.assertIsNone(result)
        self.assert_tree(out, set())
        self.assert_no_directories_below(out)

    def test_post_processing_failure_is_reported_as_failure(self):
        out = self.base / "out"
        source = self.make_zip(self.base / "source.zip", {"a/file.txt": "content"})

        with mock.patch.object(
            ArchExtractor, "_flatten", side_effect=OSError("simulated move failure")
        ):
            result = ArchExtractor().extract(
                src=str(source), dst=str(out), mode="e", verbosity=-1, cleanup=True
            )

        self.assertIsNone(result)
        self.assertTrue(source.exists())
        self.assert_tree(out, set())

    def test_only_directory_patterns_mark_a_directory_as_generated(self):
        self.assertTrue(is_auto_generated_dir("archive/__MACOSX"))
        self.assertTrue(is_auto_generated_dir("archive/PaxHeader"))
        self.assertFalse(is_auto_generated_dir("archive/Kaguya-sama ~Love is War~"))
        self.assertFalse(is_auto_generated_dir("archive/Icon"))
        self.assertFalse(is_auto_generated_dir("archive/#01#"))
        # The file patterns are unchanged.
        self.assertTrue(is_auto_generated("archive/notes.txt~"))
        self.assertTrue(is_auto_generated("archive/Icon"))


if __name__ == "__main__":
    unittest.main()
