from archextractor import ArchExtractor

if __name__ == "__main__":
    extractor = ArchExtractor(
        src="./Data/top_compress.zip",
        dst="./Data/",
    )

    extractor.extractall(
        verbosity=-1,
        mode="e",
        cleanup=False,
    )
