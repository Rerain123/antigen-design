from biolib import utils
from biolib._experiment.experiment import Experiment
from biolib._internal.utils.auth import exchange_azure_oauth_token_for_biolib_refresh_token
from biolib._internal.utils.experiment import fetch_experiment_by_uri
from biolib._internal.utils.job_url import parse_result_id_or_url
from biolib._result.result import Result
from biolib._shared.types.typing import Optional
from biolib.api.client import ApiClient, ApiClientInitDict
from biolib.app import BioLibApp
from biolib.biolib_errors import BioLibError


class Session:
    def __init__(self, _init_dict: ApiClientInitDict, _experiment: Optional[str] = None) -> None:
        self._api = ApiClient(_init_dict=_init_dict)
        self._experiment = _experiment

    @staticmethod
    def get_session(
        refresh_token: Optional[str] = None,
        base_url: Optional[str] = None,
        client_type: Optional[str] = None,
        experiment: Optional[str] = None,
        azure_oauth_access_token: Optional[str] = None,
    ) -> 'Session':
        if refresh_token and azure_oauth_access_token:
            raise BioLibError('Only one of refresh_token or azure_oauth_access_token can be provided, not both')

        resolved_base_url = base_url or utils.load_base_url_from_env()

        if not refresh_token:
            if not azure_oauth_access_token:
                raise BioLibError('Please provide refresh_token or azure_oauth_access_token to authenticate')

            refresh_token = exchange_azure_oauth_token_for_biolib_refresh_token(
                azure_oauth_access_token=azure_oauth_access_token,
                base_url=resolved_base_url,
            )

        return Session(
            _init_dict=ApiClientInitDict(
                refresh_token=refresh_token,
                base_url=resolved_base_url,
                client_type=client_type,
            ),
            _experiment=experiment,
        )

    def load(self, uri: str, suppress_version_warning: bool = False) -> BioLibApp:
        r"""Load a BioLib application by its URI or website URL.

        Args:
            uri (str): The URI or website URL of the application to load. Can be either:
                - App URI (e.g., 'biolib/myapp:1.0.0')
                - Website URL (e.g., 'https://biolib.com/biolib/myapp/')
            suppress_version_warning (bool): If True, don't print a warning when no version is specified.
                Defaults to False.

        Returns:
            BioLibApp: The loaded application object

        Example::

            >>> # Load by URI
            >>> app = biolib.load('biolib/myapp:1.0.0')
            >>> # Load by website URL
            >>> app = biolib.load('https://biolib.com/biolib/myapp/')
            >>> result = app.cli('--help')
        """
        return BioLibApp(
            uri=uri,
            _api_client=self._api,
            suppress_version_warning=suppress_version_warning,
            _experiment=self._experiment,
        )

    def get_experiment(self, uri: str) -> Experiment:
        resource_dict = fetch_experiment_by_uri(uri=uri, api_client=self._api)
        return Experiment(uri=resource_dict['uri'], _resource_dict=resource_dict, _api_client=self._api)

    def get_job(self, job_id: str, job_token: Optional[str] = None) -> Result:
        r"""Get a job by its ID or full URL using this session's credentials.

        Args:
            job_id (str): The UUID of the job to retrieve, or a full URL to the job.
                Can be either:
                - Job UUID (e.g., 'abc123')
                - Full URL (e.g., 'https://biolib.com/result/abc123/?token=xyz789')
                - Full URL with token parameter (e.g., 'biolib.com/result/abc123/token=xyz789')
            job_token (str, optional): Authentication token for accessing the job.
                Only needed for jobs that aren't owned by the current user.
                If the URL contains a token, this parameter is ignored.

        Returns:
            Result: The job object

        Example::

            >>> session = biolib.sdk.get_session(refresh_token='...')
            >>> job = session.get_job('abc123')
        """
        uuid, token = parse_result_id_or_url(job_id, job_token, base_url=self._api.base_url)
        return Result.create_from_uuid(uuid=uuid, auth_token=token, _api_client=self._api)

    def get_result(self, result_id: str, result_token: Optional[str] = None) -> Result:
        r"""Get a result by its ID or full URL using this session's credentials.

        Args:
            result_id (str): The UUID of the result to retrieve, or a full URL to the result.
                Can be either:
                - Result UUID (e.g., 'abc123')
                - Full URL (e.g., 'https://biolib.com/result/abc123/?token=xyz789')
                - Full URL with token parameter (e.g., 'biolib.com/result/abc123/token=xyz789')
            result_token (str, optional): Authentication token for accessing the result.
                Only needed for results that aren't owned by the current user.
                If the URL contains a token, this parameter is ignored.

        Returns:
            Result: The result object

        Example::

            >>> session = biolib.sdk.get_session(refresh_token='...')
            >>> result = session.get_result('abc123')
        """
        uuid, token = parse_result_id_or_url(result_id, result_token, base_url=self._api.base_url)
        return Result.create_from_uuid(uuid=uuid, auth_token=token, _api_client=self._api)

    def show_jobs(self, count: int = 25) -> None:
        r"""Display a table of recent jobs for this session's user.

        Args:
            count (int): Maximum number of jobs to display. Defaults to 25.

        Example::

            >>> session = biolib.sdk.get_session(refresh_token='...')
            >>> session.show_jobs()
            >>> session.show_jobs(100)
        """
        Result.show_jobs(count=count, _api_client=self._api)

    def show_results(self, count: int = 25) -> None:
        r"""Display a table of recent results for this session's user.

        Args:
            count (int): Maximum number of results to display. Defaults to 25.

        Example::

            >>> session = biolib.sdk.get_session(refresh_token='...')
            >>> session.show_results()
            >>> session.show_results(100)
        """
        Result.show_jobs(count=count, _api_client=self._api)
