# **ArchExtractor**

A Python module for extracting archive files, with support for recursively unpacking nested archives.

`ArchExtractor` wraps [patool](https://github.com/wummel/patool) with a small, reusable API for archive validation, single archive extraction, recursive extraction, output flattening, and cleanup of common system/tool-generated files.

## **Feature**

- Archive test: Validate whether a file is a processable archive before extraction.
- Extract one: Extract a single archive without processing nested archives.
- Extract all: Recursively extract nested archive files found in the output directory.
- Output mode: Preserve the original directory tree with `mode="x"` or flatten files into the destination directory with `mode="e"`; duplicate flattened file names are renamed with suffixes such as `(1)` to avoid overwrites.
- Generated file cleanup: Remove common system/tool-generated files such as `__MACOSX`, `.DS_Store`, `PaxHeader`, and `Thumbs.db`.
- Source cleanup: Delete source archives only after successful extraction when `cleanup=True`.
- Backend options: Pass `program`, `interactive`, `password`, and `verbosity` to `patool`.

> [!IMPORTANT]
> Supported archive formats depend on `patool` and the archive programs installed on your system. Install the required backend programs before processing formats such as `7z` or `rar`.

## **QuickStart**

Install the Python package:

```bash
# pip
python3 -m pip install archextractor

# uv
uv add archextractor
```

Install common archive backends:

```bash
# Ubuntu / Debian
sudo apt-get install p7zip-full unrar

# macOS
brew install 7zip rar
```

## API

| Method | Description | Return |
| --- | --- | --- |
| `test_archive(src, ...)` | Test whether `src` is a readable archive supported by `patool`. | `bool` |
| `extract(src, dst, ...)` | Extract one archive without recursively processing nested archives. | `str \| None` |
| `extractall(src, dst, ...)` | Extract one archive and recursively extract nested archives found under `dst`. | `str \| None` |

> [!NOTE]
> `extract()` and `extractall()` return `None` when validation or extraction fails. Passing a `mode` other than `"x"` or `"e"` raises `ValueError`.

## **Usage**

```python
from archextractor import ArchExtractor

# Initialize one reusable extractor
extractor = ArchExtractor()

# Test whether ``src`` is a readable archive supported by patool
is_valid = extractor.test_archive(
    src="/data/archive.tar",  # The source path of the archive file (only file path, not directory path)
    verbosity=-1,  # Larger values print more information. 0 is the default, -1 or lower means no output, values >= 1 prints command output
    program=None,  # Select a specific archive program, or let patool search for a suitable program in PATH
    interactive=False,  # If True, wait for user input when the backend program asks for it
    password=None,  # Password for encrypted archives, passed to the backend program when supported
)

print(is_valid)

# Extract a single archive without recursively processing nested archives
result = extractor.extract(
    src="/data/archive.tar",  # The source path of the archive file (only file path, not directory path)
    dst="/data/unpacked",  # The destination path of the extracted files (only directory path, not file path)
    mode="x",  # "x" preserves the original directory structure; "e" flattens files and renames duplicate file names with suffixes such as "(1)" to avoid overwrites
    verbosity=-1,  # Larger values print more information. 0 is the default, -1 or lower means no output, values >= 1 prints command output
    program=None,  # Select a specific archive program, or let patool search for a suitable program in PATH
    interactive=False,  # If True, wait for user input when the backend program asks for it
    password=None,  # Password for encrypted archives, passed to the backend program when supported
    cleanup=False,  # Delete the source archive file after successful extraction
)

if result is None:
    print("Extraction failed")
else:
    print(f"Extracted to: {result}")

# Extract ``src`` and recursively extract nested archives found under ``dst``
result = extractor.extractall(
    src="/data/archive.tar",  # The source path of the archive file (only file path, not directory path)
    dst="/data/unpacked",  # The destination path of the extracted files (only directory path, not file path)
    mode="e",  # "e" flattens extracted files and renames duplicate file names with suffixes such as "(1)" to avoid overwrites; "x" preserves the original directory structure
    verbosity=-1,  # Larger values print more information. 0 is the default, -1 or lower means no output, values >= 1 prints command output
    program=None,  # Select a specific archive program, or let patool search for a suitable program in PATH
    interactive=False,  # If True, wait for user input when the backend program asks for it
    password=None,  # Password for encrypted archives, passed to the backend program when supported
    cleanup=True,  # Delete source archive files after successful extraction
)

if result is None:
    print("Extraction failed")
else:
    print(f"Extracted to: {result}")
```
