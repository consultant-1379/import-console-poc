
_config = None


def set_config(config):
    global _config
    _config = config


def get_config():
    global _config
    return _config


class Config(object):
    def __init__(self, import_file_path=None,
                 default_file_name_filter=None,
                 enable_job_filtering=False,
                 enable_job_filtering_by_userid=False,
                 enable_job_filtering_by_date=False,
                 list_buffer_size=100,
                 enable_job_undo=True,
                 execution_flow='{}',
                 execution_policies='{}',
                 validation_policies='{}',
                 allowed_new_job_execution_flows='[]',
                 work_dir=None,
                 file_cleanup_interval=None,
                 file_retention_days=None):
        self.file_retention_days = file_retention_days
        self.file_cleanup_interval = file_cleanup_interval
        self.work_dir = work_dir
        self.allowed_new_job_execution_flows = allowed_new_job_execution_flows
        self.validation_policies = validation_policies
        self.execution_policies = execution_policies
        self.execution_flow = execution_flow
        self.enable_job_filtering_by_date = enable_job_filtering_by_date
        self.enable_job_filtering_by_userid = enable_job_filtering_by_userid
        self.enable_job_undo = enable_job_undo
        self.list_buffer_size = list_buffer_size
        self.enable_job_filtering = enable_job_filtering
        self.default_file_name_filter = default_file_name_filter
        self.import_file_path = import_file_path
        self.auto_refresh_enabled = True


