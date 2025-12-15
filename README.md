# **ArchExtractor**

A module for extracting archive files, which wraps the patoolib library, can recursively process nested compressed package files.

## **Installation**

- **On Ubuntu**

```zsh
# Install the necessary decompression backend
>>> sudo apt-get install unzip unrar p7zip-full

# Install using pip
>>> python3 -m pip install archextractor

# or uv
>>> uv add archextractor
```

- **On MacOS**

```zsh
# Install the necessary decompression backend
>>> brew install 7zip rar

# Install using pip
>>> python3 -m pip install archextractor

# or uv
>>> uv add archextractor
```

# **Usage**

```python
from archextractor import ArchExtractor

# Initialize the ArchExtractor class, set the source and destination paths
extractor = ArchExtractor(
    src="/data/archive.tar",  # The source path of the archive file (only file path, not directory path)
    dst="/data/unpacked",  # The destination path of the extracted files (only directory path, not file path)
)

# Extract all the archive files in the source path, including the nested archive files
extractor.extractall(
    mode="e",   # The mode of the extraction. If set to "e", the extracted files will be moved to the top level directory. If set to "x", the extracted files will be kept in the original directory structure
    verbosity=-1,  # See patoolib.extract_archive for more details
    cleanup=True,  # The source archive file will be deleted after extraction
)
```