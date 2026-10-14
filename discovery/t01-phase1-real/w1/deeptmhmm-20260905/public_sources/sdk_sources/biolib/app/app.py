import copy
import io
import json
import os
import random
import string
from pathlib import Path

from biolib import utils
from biolib._app.app_version_sdk import AppVersionSdk
from biolib._experiment.experiment import Experiment
from biolib._internal.file_utils import add_path_to_files_dict, path_to_renamed_path
from biolib._result.result import Result
from biolib._runtime.runtime import Runtime
from biolib._shared.types import MountPoint
from biolib._shared.types.typing import Dict, List, Optional, Union
from biolib._shared.utils import parse_resource_uri
from biolib.api.client import ApiClient
from biolib.biolib_api_client.app_types import AppDict, AppVersion
from biolib.biolib_api_client.biolib_app_api import BiolibAppApi
from biolib.biolib_binary_format import LazyModuleInput
from biolib.biolib_errors import BioLibError, JobResultNonZeroExitCodeError
from biolib.biolib_logging import logger


class JsonStringIO(io.StringIO):
    pass


class BioLibApp:
    def __init__(
        self,
        uri: str,
        _api_client: Optional[ApiClient] = None,
        suppress_version_warning: bool = False,
        _experiment: Optional[str] = None,
    ):
        self._api_client: Optional[ApiClient] = _api_client
        self._experiment = _experiment
        self._input_uri = uri
        self._parsed_input_uri = parse_resource_uri(uri)

        app_response = BiolibAppApi.get_by_uri(uri=uri, api_client=self._api_client)
        self._app: AppDict = app_response['app']
        self._app_uri = app_response['app_uri']
        self._app_version: AppVersion = app_response['app_version']

        if (
            not suppress_version_warning
            and self._parsed_input_uri['version'] is None
            and Runtime.check_is_environment_biolib_app()
        ):
            logger.warning(
                f"No version specified in URI '{uri}'. This will use the default version, "
                f'which may change behaviour over time. Consider locking down the exact version, '
                f"e.g. '{uri}:1.2.3'"
            )

        if self._parsed_input_uri['tag']:
            semantic_version = f'{self._app_version["major"]}.{self._app_version["minor"]}.{self._app_version["patch"]}'
            logger.info(f'Loaded {self._input_uri} (resolved to {semantic_version})')
        else:
            logger.info(f'Loaded {self._app_uri}')

    def __str__(self) -> str:
        return self._app_uri

    @property
    def uri(self) -> str:
        return self._app_uri

    @property
    def uuid(self) -> str:
        return self._app['public_id']

    @property
    def version(self) -> AppVersion:
        return self._app_version

    @property
    def sdk(self) -> AppVersionSdk:
        return AppVersionSdk(app_version=self._app_version, _api_client=self._api_client)

    def cli(
        self,
        args=None,
        stdin=None,
        files=None,
        override_command=False,
        machine='',
        blocking: bool = True,
        experiment_id: Optional[str] = None,
        result_prefix: Optional[str] = None,
        timeout: Optional[int] = None,
        notify: bool = False,
        max_workers: Optional[int] = None,
        experiment: Optional[str] = None,
        temporary_client_secrets: Optional[Dict[str, str]] = None,
        check: bool = False,
        stream_logs: bool = False,
        mount_points: Optional[List[MountPoint]] = None,
    ) -> Result:
        if experiment_id and experiment:
            raise ValueError('Only one of experiment_id and experiment can be specified')

        if check and not blocking:
            raise ValueError('The argument "check" cannot be True when blocking is False')

        if not experiment_id:
            experiment_to_use = experiment if experiment is not None else self._experiment
            experiment_instance: Optional[Experiment]
            if experiment_to_use:
                experiment_instance = Experiment(experiment_to_use, _api_client=self._api_client)
            else:
                experiment_instance = Experiment.get_experiment_in_context()
            experiment_id = experiment_instance.uuid if experiment_instance else None

        module_input = self._get_module_input(args, stdin, files)

        if machine == 'local':
            raise BioLibError('Running applications locally with machine="local" is no longer supported.')

        job = Result._start_job_in_cloud(  # pylint: disable=protected-access
            app_uri=self._app_uri,
            app_version_uuid=self._app_version['public_id'],
            experiment_id=experiment_id,
            machine=machine,
            module_input=module_input,
            notify=notify,
            override_command=override_command,
            result_prefix=result_prefix,
            timeout=timeout,
            requested_machine_count=max_workers,
            temporary_client_secrets=temporary_client_secrets,
            mount_points=mount_points,
            api_client=self._api_client,
        )
        if utils.IS_RUNNING_IN_NOTEBOOK:
            logger.info(f'View the result in your browser at: {utils.BIOLIB_BASE_URL}/results/{job.id}/')
        if blocking:
            # TODO: Deprecate utils.STREAM_STDOUT and always stream logs by simply calling job.stream_logs()
            if utils.IS_RUNNING_IN_NOTEBOOK:
                utils.STREAM_STDOUT = True

            enable_print = bool(
                (utils.STREAM_STDOUT or stream_logs)
                and (self._app_version.get('main_output_file') or self._app_version.get('stdout_render_type') == 'text')
            )
            job._stream_logs(enable_print=enable_print)  # pylint: disable=protected-access

            if check:
                exit_code = job.get_exit_code()
                if exit_code != 0:
                    raise JobResultNonZeroExitCodeError(exit_code)

        return job

    def exec(self, args=None, stdin=None, files=None, machine=''):
        return self.cli(args, stdin, files, override_command=True, machine=machine)

    def __call__(self, *args, **kwargs):
        if not args and not kwargs:
            self.cli()

        else:
            raise BioLibError("""
Calling an app directly with app() is currently being reworked.
To use the previous functionality, please call app.cli() instead.
Example: "app.cli('--help')"
""")

    @staticmethod
    def _get_module_input(args=None, stdin=None, files=None) -> LazyModuleInput:
        args = [] if args is None else copy.copy(args)

        if stdin is None:
            stdin = b''

        if isinstance(args, str):
            args = list(filter(lambda p: p != '', args.split(' ')))

        if not isinstance(args, list):
            raise Exception('The given input arguments must be list or str')

        if isinstance(stdin, str):
            stdin = stdin.encode('utf-8')

        if files is None:
            files = []

        files_dict: Dict[str, Union[bytes, Path]] = {}
        if isinstance(files, list):
            for file_path in files:
                path = Path(file_path)
                add_path_to_files_dict(files_dict, path)
        elif isinstance(files, dict):
            files_dict = {}
            for key, value in files.items():
                if '//' in key:
                    raise BioLibError(f"File path '{key}' contains double slashes which are not allowed")
                if not key.startswith('/'):
                    key = '/' + key
                files_dict[key] = value
        else:
            raise Exception('The given files input must be list or dict or None')

        for idx, arg in enumerate(args):
            if isinstance(arg, str):
                if os.path.isfile(arg) or os.path.isdir(arg):
                    add_path_to_files_dict(files_dict, Path(arg))
                    args[idx] = path_to_renamed_path(arg, prefix_with_slash=False)

                # support --myarg=file.txt
                elif os.path.isfile(arg.split('=')[-1]) or os.path.isdir(arg.split('=')[-1]):
                    file_path = arg.split('=')[-1]
                    add_path_to_files_dict(files_dict, Path(file_path))
                    args[idx] = arg.split('=')[0] + '=' + path_to_renamed_path(file_path, prefix_with_slash=False)
                else:
                    pass  # a normal string arg was given
            else:
                tmp_filename = f'input_{"".join(random.choices(string.ascii_letters + string.digits, k=7))}'
                if isinstance(arg, JsonStringIO):
                    file_data = arg.getvalue().encode()
                    tmp_filename += '.json'
                elif isinstance(arg, io.StringIO):
                    file_data = arg.getvalue().encode()
                elif isinstance(arg, io.BytesIO):
                    file_data = arg.getvalue()
                else:
                    raise Exception(f'Unexpected type of argument: {arg}')
                files_dict[f'/{tmp_filename}'] = file_data
                args[idx] = tmp_filename

        return LazyModuleInput.from_module_input(
            stdin=stdin,
            arguments=args,
            files=files_dict,
        )

    def run(self, **kwargs) -> Result:
        args = []
        biolib_kwargs = {}
        for key, value in kwargs.items():
            if key.startswith('biolib_'):
                biolib_kwarg_key = key.replace('biolib_', '')
                biolib_kwargs[biolib_kwarg_key] = value
                continue

            if isinstance(value, dict):
                value = JsonStringIO(json.dumps(value))
            elif isinstance(value, (int, float)):  # Cast numeric values to strings
                value = str(value)

            if not key.startswith('--'):
                key = f'--{key}'

            args.append(key)
            if isinstance(value, list):
                # TODO: only do this if argument key is of type file list
                args.extend(value)
            else:
                args.append(value)

        # Set check=True by default if not explicitly provided and not in non-blocking mode
        if 'check' not in biolib_kwargs and biolib_kwargs.get('blocking', True) is not False:
            biolib_kwargs['check'] = True

        return self.cli(args, **biolib_kwargs)

    def start(self, **kwargs) -> Result:
        return self.run(biolib_blocking=False, **kwargs)
