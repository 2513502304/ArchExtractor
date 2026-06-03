import tempfile
import tarfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from loguru import logger
from patoolib.util import PatoolError

from archextractor import ArchExtractor
from archextractor.utils import is_auto_generated


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


if __name__ == "__main__":
    unittest.main()
