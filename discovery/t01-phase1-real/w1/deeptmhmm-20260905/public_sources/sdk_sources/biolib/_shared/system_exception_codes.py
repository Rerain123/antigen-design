from enum import Enum


class SystemExceptionCodes(Enum):
    COMPLETED_SUCCESSFULLY = 0
    FAILED_TO_INIT_COMPUTE_PROCESS_VARIABLES = 1
    FAILED_TO_CONNECT_TO_WORKER_THREAD_SOCKET = 2
    FAILED_TO_START_SENDER_THREAD_OR_RECEIVER_THREAD = 3
    FAILED_TO_GET_ATTESTATION_DOCUMENT = 4
    FAILED_TO_CREATE_DOCKER_NETWORKS = 5
    FAILED_TO_START_REMOTE_HOST_PROXIES = 6
    FAILED_TO_REDIRECT_ENCLAVE_TRAFFIC_TO_PROXIES = 7
    FAILED_TO_CREATE_PROXY_CONTAINER = 8
    FAILED_TO_CONFIGURE_ALLOWED_REMOTE_HOST = 9
    FAILED_TO_SEND_STATUS_UPDATE = 10
    FAILED_TO_GET_REQUIRED_DATA_FOR_COMPUTE = 11
    FAILED_TO_START_RUNTIME_ZIP_DOWNLOAD_THREAD = 12
    FAILED_TO_DOWNLOAD_RUNTIME_ZIP = 13
    FAILED_TO_CONTACT_BACKEND_TO_CREATE_JOB = 14
    FAILED_TO_CREATE_NEW_JOB = 15
    FAILED_TO_START_IMAGE_PULLING_THREAD = 16
    FAILED_TO_PULL_DOCKER_IMAGE = 17
    FAILED_TO_START_COMPUTE_CONTAINER = 18
    FAILED_TO_COPY_INPUT_FILES_TO_COMPUTE_CONTAINER = 19
    FAILED_TO_COPY_RUNTIME_FILES_TO_COMPUTE_CONTAINER = 20
    FAILED_TO_RUN_COMPUTE_CONTAINER = 21
    FAILED_TO_RETRIEVE_AND_MAP_OUTPUT_FILES = 22
    FAILED_TO_SERIALIZE_AND_SEND_MODULE_OUTPUT = 23
    FAILED_TO_DESERIALIZE_SAVED_JOB = 24
    UNKNOWN_COMPUTE_PROCESS_ERROR = 25
    FAILED_TO_INITIALIZE_WORKER_THREAD = 26
    FAILED_TO_HANDLE_PACKAGE_IN_WORKER_THREAD = 27
    EXCEEDED_MAX_JOB_RUNTIME = 28
    OUT_OF_MEMORY = 29
    CANCELLED_BY_USER = 30
    COMMAND_OVERRIDE_NOT_ALLOWED = 31
    FAILED_TO_ALLOCATE_JOB_TO_COMPUTE_NODE = 32
    NO_MODULES_FOUND_ON_JOB = 33
    FAILED_TO_INITIALIZE_DOCKER_EXECUTOR = 34
    COMPUTE_NODE_SHUTDOWN = 35
    COMPUTE_NODE_SHUTDOWN_DUE_TO_HEALTH_CHECK_FAILURE = 36
    INPUT_FILE_OVERWRITES_EXISTING_FILE = 37
    FAILED_TO_ATTACH_FILE_SYSTEM = 38
    FAILED_TO_MOUNT_FILE_SYSTEM = 39
    FAILED_TO_UNMOUNT_FILE_SYSTEM = 40


# TODO: Rename to UPPER_CASE constant style (e.g. SYSTEM_EXCEPTION_CODE_MAP)
SystemExceptionCodeMap = {  # pylint: disable=invalid-name
    0: 'Job completed successfully',
    1: 'Failed to init compute process variables',
    2: 'Failed to connect to worker thread socket',
    3: 'Failed to start sender or receiver thread',
    4: 'Failed to get attestation document',
    5: 'Failed to create docker networks',
    6: 'Failed to start remote host proxies',
    7: 'Failed to redirect enclave traffic to proxies',
    8: 'Failed to create proxy container',
    9: 'Failed to configure allowed remote host',
    10: 'Failed to send status update',
    11: 'Failed to get required data for compute',
    12: 'Failed to start runtime zip download thread',
    13: 'Failed to download runtime zip',
    14: 'Failed to contact backend to create job',
    15: 'Failed to create new job',
    16: 'Failed to start image pulling thread',
    17: 'Failed to pull docker image',
    18: 'Failed to start compute container',
    19: 'Failed to copy input files to compute container',
    20: 'Failed to copy runtime files to compute container',
    21: 'Failed to run compute container',
    22: 'Failed to retrieve and map output files',
    23: 'Failed to serialize and send module output',
    24: 'Failed to deserialize job',
    25: 'Unknown Compute Process Error',
    26: 'Failed to initialize worker thread',
    27: 'Failed to handle package in worker thread',
    28: 'Job exceeded max run time',
    29: 'Container ran out of memory',
    30: 'Job was cancelled by a user or an idle timeout',
    31: 'The application does not allow the arguments to override the command',
    32: 'Failed to allocate job to compute node',
    33: 'No modules found on job',
    34: 'Failed to initialize docker executor',
    35: 'Compute node shutdown',
    36: 'Compute node shutdown due to health check failure',
    37: 'Input file would overwrite an existing file in the container',
    38: 'Failed to attach file system to compute node',
    39: 'Failed to mount file system on compute node',
    40: 'Failed to unmount file system from compute node',
}
