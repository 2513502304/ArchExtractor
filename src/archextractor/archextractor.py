import os
import shutil
from typing import Literal

import patoolib
from loguru import logger
from patoolib.util import PatoolError

from .utils import is_auto_generated


class ArchExtractor:
    """
    A class for extracting archive files, which wraps the patoolib library
    """

    def __init__(
        self,
        src: str,
        dst: str,
    ):
        """
        Initialize the ArchExtractor class, set the source and destination paths

        Args:
            src (str): The source path of the archive file (only file path, not directory path)
            dst (str): The destination path of the extracted files (only directory path, not file path)
        """
        self.src = src
        self.dst = dst

    def test_archive(
        self,
        src: str | None = None,
        verbosity: int = 0,
        program: str | None = None,
        interactive: bool = False,
        password: str | None = None,
    ) -> bool:
        """
        Test if the file is a valid archive file, two steps:
        1. Preliminarily judge whether a file is a compressed package based on the file suffix (rough screening)
        2. Further check whether the compressed file exists or is a regular file (fine screening)

        Args:
            src (str | None, optional): The source path of the archive file (only file path, not directory path). If not provided, use the source path set in the constructor. Defaults to None.
            verbosity (int, optional): See `patoolib.test_archive` for more details. Defaults to 0.
            program (str | None, optional): See `patoolib.test_archive` for more details. Defaults to None.
            interactive (bool, optional): See `patoolib.test_archive` for more details. Defaults to False.
            password (str | None, optional): See `patoolib.test_archive` for more details. Defaults to None.

        Returns:
            bool: True if the file is a valid archive file, False otherwise
        """
        if src is None:
            src = self.src

        # 根据文件后缀名初步判断文件是否是压缩包（粗筛）
        if not patoolib.is_archive(src):
            logger.error(f"The file {src} is not a valid archive file")
            return False

        try:
            # 进一步检查压缩文件是否存在或者为常规文件（精筛）
            #!将会进一步排除在粗筛中未过滤的不能解压的文件类型
            #!常见的例子是，这些压缩文件以受支持的压缩文件扩展名为结尾，但本身不是压缩文件（eg. .flac）或压缩包损坏而导致无法解压
            patoolib.test_archive(
                src,
                verbosity=verbosity,
                program=program,
                interactive=interactive,
                password=password,
            )

        except PatoolError as exc:
            logger.error(
                f"Failed to test the archive file {src}: {exc.__class__.__name__}: {exc}"
            )
            return False

        return True

    def extractall(
        self,
        src: str | None = None,
        dst: str | None = None,
        mode: Literal["e", "x"] = "x",
        verbosity: int = 0,
        program: str | None = None,
        interactive: bool = False,
        password: str | None = None,
        cleanup: bool = False,
    ):
        """
        Extract all the archive files in the source path, including the nested archive files.

        If the cleanup parameter is provided as True, the source archive file will be deleted after extraction.

        Note:
            It will preserve the complete original directory structure of the extracted files.

        Args:
            src (str | None, optional): The source path of the archive file (only file path, not directory path). If not provided, use the source path set in the constructor. Defaults to None.
            dst (str | None, optional): The destination path of the extracted files (only directory path, not file path). If not provided, use the destination path set in the constructor. Defaults to None.
            mode (Literal["e", "x"], optional): The mode of the extraction. Defaults to "x". If set to "e", the extracted files will be moved to the top level directory. If set to "x", the extracted files will be kept in the original directory structure.
            verbosity (int, optional): See `patoolib.extract_archive` for more details. Defaults to 0.
            program (str | None, optional): See `patoolib.extract_archive` for more details. Defaults to None.
            interactive (bool, optional): See `patoolib.extract_archive` for more details. Defaults to False.
            password (str | None, optional): See `patoolib.extract_archive` for more details. Defaults to None.
            cleanup (bool, optional): If the cleanup parameter is provided as True, the source archive file will be deleted after extraction. Defaults to False.
        """
        if src is None:
            src = self.src
        if dst is None:
            dst = self.dst

        # 提取顶层压缩包
        self.extract(
            src=src,
            dst=dst,
            mode="x",
            verbosity=verbosity,
            program=program,
            interactive=interactive,
            password=password,
            cleanup=cleanup,
        )

        # 顶层压缩包提取后的文件目录
        extract_dir = os.path.join(dst, os.path.splitext(os.path.basename(src))[0])
        # 一般情况下压缩包提取出来的目录名称会和原始压缩包的名称一致，但不排除在创建压缩包后手动修改压缩包名称的特殊情况，这样会导致压缩包名称与解压出来的目录名称不一致
        if not os.path.exists(extract_dir) or not os.path.isdir(extract_dir):
            return

        # 解压嵌套的子压缩包
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if not patoolib.is_archive(sub_file := os.path.join(root, file)):
                    continue
                self.extractall(
                    src=sub_file,
                    dst=extract_dir,
                    mode="x",
                    verbosity=verbosity,
                    program=program,
                    interactive=interactive,
                    password=password,
                    cleanup=cleanup,
                )

        # 由于内部使用的提取函数均设置为 "x"，故只有最顶层的调用才会判断是否需要扁平化
        if mode == "x":
            pass
        elif mode == "e":
            self.flatten(dst=dst)
        else:
            raise ValueError("Incorrect mode parameter")

    def extract(
        self,
        src: str | None = None,
        dst: str | None = None,
        mode: Literal["e", "x"] = "x",
        verbosity: int = 0,
        program: str | None = None,
        interactive: bool = False,
        password: str | None = None,
        cleanup: bool = False,
    ):
        """
        Extract the archive file in the source path, but do not include nested archive files.

        If the cleanup parameter is provided as True, the source archive file will be deleted after extraction.

        Note:
            It will preserve the complete original directory structure of the extracted files.

        Args:
            src (str | None, optional): The source path of the archive file (only file path, not directory path). If not provided, use the source path set in the constructor. Defaults to None.
            dst (str | None, optional): The destination path of the extracted files (only directory path, not file path). If not provided, use the destination path set in the constructor. Defaults to None.
            mode (Literal["e", "x"], optional): The mode of the extraction. Defaults to "x". If set to "e", the extracted files will be moved to the top level directory. If set to "x", the extracted files will be kept in the original directory structure.
            verbosity (int, optional): See `patoolib.extract_archive` for more details. Defaults to 0.
            program (str | None, optional): See `patoolib.extract_archive` for more details. Defaults to None.
            interactive (bool, optional): See `patoolib.extract_archive` for more details. Defaults to False.
            password (str | None, optional): See `patoolib.extract_archive` for more details. Defaults to None.
            cleanup (bool, optional): If the cleanup parameter is provided as True, the source archive file will be deleted after extraction. Defaults to False.
        """
        if src is None:
            src = self.src
        if dst is None:
            dst = self.dst

        # 测试该压缩包是否可解压
        if not self.test_archive(
            src=src,
            verbosity=verbosity,
            program=program,
            interactive=interactive,
            password=password,
        ):
            return

        try:
            # 尝试提取该压缩文件
            patoolib.extract_archive(
                src,
                outdir=dst,
                verbosity=verbosity,
                program=program,
                interactive=interactive,
                password=password,
            )

        except PatoolError as exc:
            logger.error(
                f"Failed to extract the archive file {src}: {exc.__class__.__name__}: {exc}"
            )

        finally:
            try:
                # 删除由操作系统或工具自动生成的文件夹/文件
                for root, dirs, files in os.walk(dst):
                    for dirname in dirs:
                        dirpath = os.path.join(root, dirname)
                        if is_auto_generated(dirpath) and os.path.exists(dirpath):
                            shutil.rmtree(dirpath)
                            logger.info(
                                f"Removed the file {dirpath} because it is auto generated by the system or tool"
                            )
                    for file in files:
                        filepath = os.path.join(root, file)
                        if is_auto_generated(filepath) and os.path.exists(filepath):
                            os.remove(filepath)
                            logger.info(
                                f"Removed the file {filepath} because it is auto generated by the system or tool"
                            )

                if cleanup and os.path.exists(src):
                    os.remove(src)
                    logger.info(f"Removed the file {src} because cleanup is enabled")

                if mode == "x":
                    pass
                elif mode == "e":
                    # 顶层压缩包提取后的文件目录
                    extract_dir = os.path.join(
                        dst, os.path.splitext(os.path.basename(src))[0]
                    )
                    # 一般情况下压缩包提取出来的目录名称会和原始压缩包的名称一致，但不排除在创建压缩包后手动修改压缩包名称的特殊情况，这样会导致压缩包名称与解压出来的目录名称不一致
                    if not os.path.exists(extract_dir) or not os.path.isdir(
                        extract_dir
                    ):
                        pass
                    else:
                        self.flatten(dst=dst)
                else:
                    raise ValueError("Incorrect mode parameter")

            except OSError as exc:
                logger.error(
                    f"Failed to perform file-level operations: {exc.__class__.__name__}: {exc}"
                )

    def flatten(
        self,
        dst: str | None = None,
    ):
        """
        Flatten the extracted files, remove the original directory structure and move all files to the top level directory.

        Args:
            dst (str | None, optional): The destination path of the flattened files (only directory path, not file path). If not provided, use the destination path set in the constructor. Defaults to None.
        """
        if dst is None:
            dst = self.dst

        try:
            # 顶层目录下的所有文件夹名称
            root_dirnames = [
                dirname
                for dirname in os.listdir(dst)
                if os.path.isdir(os.path.join(dst, dirname))
            ]
            # 将所有文件夹移动到顶层目录（topdown=False，从深至浅遍历，因为文件夹会嵌套文件夹，而文件不会）
            for root, dirs, files in os.walk(dst, topdown=False):
                # 跳过已经在顶层目录的文件夹
                if root == dst:
                    continue
                for dirname in dirs:
                    # 如果目标文件夹已存在，处理文件夹名称冲突（重命名）
                    dest_dirname = dirname
                    dest_dirpath = os.path.join(dst, dest_dirname)
                    if dirname in root_dirnames:
                        counter = 1
                        while os.path.exists(dest_dirpath):
                            dest_dirname = f"{dirname}({counter})"
                            dest_dirpath = os.path.join(dst, dest_dirname)
                            counter += 1
                    shutil.move(os.path.join(root, dirname), dest_dirpath)

            # 顶层目录下的所有文件夹名称
            root_filenames = [
                filename
                for filename in os.listdir(dst)
                if os.path.isfile(os.path.join(dst, filename))
            ]
            # 将所有文件移动到顶层目录
            for root, dirs, files in os.walk(dst, topdown=True):
                # 跳过已经在顶层目录的文件
                if root == dst:
                    continue
                for filename in files:
                    # 如果目标文件已存在，处理文件名称冲突（重命名）
                    dest_filename = filename
                    dest_filepath = os.path.join(dst, dest_filename)
                    if filename in root_filenames:
                        counter = 1
                        while os.path.exists(dest_filepath):
                            basename, ext = os.path.splitext(filename)
                            dest_filename = f"{basename}({counter}){ext}"
                            dest_filepath = os.path.join(dst, dest_filename)
                            counter += 1
                    shutil.move(os.path.join(root, filename), dest_filepath)

        except OSError as exc:
            logger.error(
                f"Failed to perform file-level operations: {exc.__class__.__name__}: {exc}"
            )
