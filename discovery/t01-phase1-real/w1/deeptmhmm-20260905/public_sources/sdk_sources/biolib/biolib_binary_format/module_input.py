from pathlib import Path

from biolib._shared.types.typing import Dict, Iterator, List, Mapping, Optional, Tuple, TypedDict, Union
from biolib.biolib_binary_format.base_bbf_package import BioLibBinaryFormatBasePackage
from biolib.biolib_errors import BioLibError
from biolib.biolib_logging import logger


class ModuleInputDict(TypedDict):
    stdin: bytes
    files: Dict[str, bytes]
    arguments: List[str]


ModuleInputFileSource = Union[bytes, Path]


class LazyModuleInputDict(TypedDict):
    stdin: bytes
    files: Dict[str, ModuleInputFileSource]
    arguments: List[str]


class LazyModuleInput:
    _FILE_READ_CHUNK_SIZE_IN_BYTES = 8_000_000
    _VERSION = 1
    _PACKAGE_TYPE = 1
    _HEADER_SIZE_IN_BYTES = 22  # version, package type, stdin length, argument data length, files data length
    _ARGUMENT_HEADER_SIZE_IN_BYTES = 2  # argument length
    _FILE_HEADER_SIZE_IN_BYTES = 12  # path length, file size

    def __init__(
        self,
        _module_input: Optional[LazyModuleInputDict] = None,
        _serialized: Optional[bytes] = None,
    ):
        self._module_input: Optional[LazyModuleInputDict] = _module_input
        self._serialized: Optional[bytes] = _serialized
        self._file_sizes: Dict[str, int] = {}
        self._data_lengths: Optional[Tuple[int, int]] = None

    @classmethod
    def from_module_input(
        cls,
        stdin: bytes,
        arguments: List[str],
        files: Mapping[str, ModuleInputFileSource],
    ) -> 'LazyModuleInput':
        for path in files:
            if '//' in path:
                raise ValueError(f"File path '{path}' contains double slashes which are not allowed")

        return cls(_module_input=LazyModuleInputDict(stdin=stdin, files=dict(files), arguments=list(arguments)))

    @classmethod
    def from_serialized(cls, serialized: bytes) -> 'LazyModuleInput':
        return cls(_serialized=serialized)

    @property
    def size_in_bytes(self) -> int:
        if self._serialized is not None:
            return len(self._serialized)

        argument_data_len, files_data_len = self._get_data_lengths()
        return self._HEADER_SIZE_IN_BYTES + len(self._get_module_input()['stdin']) + argument_data_len + files_data_len

    def iter_chunks(self, chunk_size_in_bytes: int) -> Iterator[bytes]:
        if chunk_size_in_bytes <= 0:
            raise ValueError('Chunk size must be greater than zero')

        if self._serialized is not None:
            for start in range(0, self.size_in_bytes, chunk_size_in_bytes):
                yield self._serialized[start : start + chunk_size_in_bytes]
            return

        chunk = bytearray()
        for piece in self._iter_serialized_pieces():
            chunk.extend(piece)
            while len(chunk) >= chunk_size_in_bytes:
                yield bytes(chunk[:chunk_size_in_bytes])
                del chunk[:chunk_size_in_bytes]

        if chunk:
            yield bytes(chunk)

    def to_bytes(self) -> bytes:
        return b''.join(self.iter_chunks(max(self.size_in_bytes, 1)))

    def deserialize(self) -> ModuleInputDict:
        serialized = self._serialized if self._serialized is not None else self.to_bytes()
        return ModuleInput(serialized).deserialize()

    def _get_module_input(self) -> LazyModuleInputDict:
        if self._module_input is None:
            raise BioLibError('Module input is already serialized')

        return self._module_input

    def _get_data_lengths(self) -> Tuple[int, int]:
        if self._data_lengths is None:
            module_input = self._get_module_input()
            self._file_sizes = {
                path: len(source) if isinstance(source, bytes) else source.stat().st_size
                for path, source in module_input['files'].items()
            }
            self._data_lengths = (
                sum(
                    len(argument.encode('utf-8')) + self._ARGUMENT_HEADER_SIZE_IN_BYTES
                    for argument in module_input['arguments']
                ),
                sum(
                    self._FILE_HEADER_SIZE_IN_BYTES + len(path.encode('utf-8')) + size
                    for path, size in self._file_sizes.items()
                ),
            )

        return self._data_lengths

    def _iter_serialized_pieces(self) -> Iterator[bytes]:
        argument_data_len, files_data_len = self._get_data_lengths()
        module_input = self._get_module_input()

        stdin = module_input['stdin']
        yield self._VERSION.to_bytes(1, 'big')
        yield self._PACKAGE_TYPE.to_bytes(1, 'big')
        yield len(stdin).to_bytes(8, 'big')
        yield argument_data_len.to_bytes(4, 'big')
        yield files_data_len.to_bytes(8, 'big')
        yield stdin

        for argument in module_input['arguments']:
            encoded_argument = argument.encode('utf-8')
            yield len(encoded_argument).to_bytes(2, 'big')
            yield encoded_argument

        for path, source in module_input['files'].items():
            encoded_path = path.encode('utf-8')
            file_size = self._file_sizes[path]
            yield len(encoded_path).to_bytes(4, 'big')
            yield file_size.to_bytes(8, 'big')
            yield encoded_path
            if isinstance(source, bytes):
                yield source
            else:
                yield from self._iter_file(source, file_size)

    @classmethod
    def _iter_file(cls, path: Path, expected_size: int) -> Iterator[bytes]:
        bytes_read = 0
        with open(path, 'rb') as file_object:
            while bytes_read < expected_size:
                data = file_object.read(min(cls._FILE_READ_CHUNK_SIZE_IN_BYTES, expected_size - bytes_read))
                if not data:
                    break
                bytes_read += len(data)
                yield data

            has_extra_data = bool(file_object.read(1))

        if bytes_read != expected_size or has_extra_data:
            raise BioLibError(f"File '{path}' changed while streaming module input: expected {expected_size} bytes")


class ModuleInput(BioLibBinaryFormatBasePackage):
    def __init__(self, bbf=None):
        super().__init__(bbf)
        self.package_type = 1

    def serialize(self, stdin, arguments, files) -> bytes:
        for path in files:
            if '//' in path:
                raise ValueError(f"File path '{path}' contains double slashes which are not allowed")

        bbf_data = bytearray()
        bbf_data.extend(self.version.to_bytes(1, 'big'))
        bbf_data.extend(self.package_type.to_bytes(1, 'big'))

        bbf_data.extend(len(stdin).to_bytes(8, 'big'))

        argument_len = sum([len(arg.encode()) for arg in arguments]) + (2 * len(arguments))
        bbf_data.extend(argument_len.to_bytes(4, 'big'))

        file_data_len = sum([len(data) + len(path.encode()) for path, data in files.items()]) + (12 * len(files))
        bbf_data.extend(file_data_len.to_bytes(8, 'big'))

        bbf_data.extend(stdin)

        for argument in arguments:
            encoded_argument = argument.encode()
            bbf_data.extend(len(encoded_argument).to_bytes(2, 'big'))
            bbf_data.extend(encoded_argument)

        for path, data in files.items():
            encoded_path = path.encode()
            bbf_data.extend(len(encoded_path).to_bytes(4, 'big'))
            bbf_data.extend(len(data).to_bytes(8, 'big'))

            bbf_data.extend(encoded_path)
            bbf_data.extend(data)

        return bytes(bbf_data)

    def deserialize(self) -> ModuleInputDict:
        version = self.get_data(1, output_type='int')
        package_type = self.get_data(1, output_type='int')
        self.check_version_and_type(version=version, package_type=package_type, expected_package_type=self.package_type)

        stdin_len = self.get_data(8, output_type='int')
        argument_data_len = self.get_data(4, output_type='int')
        files_data_len = self.get_data(8, output_type='int')
        stdin = self.get_data(stdin_len)

        end_of_arguments = self.pointer + argument_data_len
        arguments = []
        while self.pointer != end_of_arguments:
            argument_len = self.get_data(2, output_type='int')
            argument = self.get_data(argument_len, output_type='str')
            arguments.append(argument)

        end_of_files = self.pointer + files_data_len
        files = {}
        while self.pointer < end_of_files:
            path_len = self.get_data(4, output_type='int')
            data_len = self.get_data(8, output_type='int')
            path = self.get_data(path_len, output_type='str')
            data = self.get_data(data_len)
            if '//' in path:
                # TODO: Raise ValueError here once backwards compatibility period is over
                logger.warning(f"File path '{path}' contains double slashes which are not allowed")
            files[path] = bytes(data)

        return ModuleInputDict(stdin=stdin, arguments=arguments, files=files)
