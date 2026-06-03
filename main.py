from archextractor import ArchExtractor

if __name__ == "__main__":
    extractor = ArchExtractor()

    extractor.extractall(
        src="./Data/top_compress.zip",
        dst="./Data/",
        verbosity=-1,
        mode="e",
        cleanup=False,
    )
