from nbisession import *
import json
import logging
import re
from datetime import datetime, timedelta
from posixpath import join as urljoin
from urlparse import urlsplit, urlunsplit
from math import ceil

logger = logging.getLogger(__name__)


class CmImport(object):

    _JOBS_URI = 'jobs'

    def __init__(self, nbi_session, cli_command):
        self._session = nbi_session
        self._cli = cli_command

    def get_jobs(self, offset=0, limit=50, job_id=None, user_id=None, created_before=None, created_after=None):
        parameters = {'offset': offset, 'limit': limit, 'expand': ('summary', 'files')}
        if job_id:
            parameters['id'] = job_id
        if user_id:
            parameters['userId'] = user_id
        if created_before:
            parameters['createdBefore'] = created_before.isoformat() + 'Z'
        if created_after:
            parameters['createdAfter'] = created_after.isoformat() + 'Z'

        try:
            response = self._session.get(self._JOBS_URI, parameters=parameters)
        except NbiNoContentException:
            return []
        return self._generate_import_jobs_list_from_response(response)

    def find_jobs(self, created_start, created_end, job_name=None, user_id=None, page_size=200):
        logger.debug('starting job search...')
        jobs_found = []
        job_name_lower = job_name.lower() if job_name else ''

        def filter_by_dates(job):
            created_date = _parse_datetime(job.created())
            # logger.debug('filtering by date: %s >= %s >= %s', created_end, created_date, created_start)
            return created_end >= created_date >= created_start

        def filter_by_name(job):
            # logger.debug('filtering by name: %s in %s', job_name_lower, job.name())
            return job.name() and job_name_lower in job.name().lower()

        def filter_by_user(job):
            return job.user_id() and user_id == job.user_id()

        job_responses = self._find_job_pages_between(created_end, page_size, created_start)
        logger.debug('Found %d pages within the interval', len(job_responses))
        for response in job_responses:
            logger.debug('parsing page: %s', response)
            jobs = self._generate_import_jobs_list_from_response(response)
            jobs = filter(filter_by_dates, jobs)
            logger.debug('    %d jobs after filtering by date', len(jobs))
            if job_name:
                jobs = filter(filter_by_name, jobs)
                logger.debug('    %d jobs after filtering by name', len(jobs))
            if user_id:
                jobs = filter(filter_by_user, jobs)
                logger.debug('    %d jobs after filtering by user', len(jobs))
            jobs_found.extend(jobs)

        logger.debug('job search completed')
        return jobs_found

    def _find_job_pages_between(self, date_end, page_size, date_start=None):
        first_page_data = self._get_jobs_at_page(0, page_size, expand=True)
        if not first_page_data:
            return []

        total_jobs = int(first_page_data.get('totalCount', '0'))
        if not total_jobs:
            return []
        if total_jobs <= page_size:
            return [first_page_data]

        total_pages = int(ceil(float(total_jobs) / float(page_size)))
        page_dates = {}
        page_dates[0] = self._get_page_start_end_dates(first_page_data)
        first_page_first_date = page_dates[0][0]

        logger.debug('total-records=%d, page-size=%d, total-pages=%d', total_jobs, page_size, total_pages)

        end_page_data = None
        if date_start:
            if date_start < first_page_first_date:
                end_page_data, end_page_num = self._find_job_page_for_date(date_start, page_size, total_pages, page_dates)
            else:
                end_page_data = first_page_data
                end_page_num = 0
        else:
            end_page_num = total_pages - 1

        if not end_page_data:
            if end_page_num == 0:
                end_page_data = first_page_data
            else:
                end_page_data = self._get_jobs_at_page(end_page_num, page_size, expand=True)

        logger.debug('  end page number: %d', end_page_num)
        pages = [end_page_data]
        if 0 < end_page_num < total_pages - 1:
            for i in xrange(end_page_num - 1, -1, -1):
                page_data = first_page_data if i == 0 else self._get_jobs_at_page(i, page_size, expand=True)
                if date_end:
                    page_start_date, page_end_date = self._get_page_start_end_dates(page_data)
                    logger.debug('page %d dates: [%s][%s][%s]', i, page_start_date, date_end, page_end_date)
                    if date_end < page_start_date:
                        break
                    pages.append(page_data)
                    if date_end < page_end_date:
                        break
                else:
                    pages.append(page_data)

        pages.reverse()
        return pages

    def _find_job_page_for_date(self, date, page_size, total_pages, page_dates):
        logger.debug('searching for page of date: %s', date)
        page_data = None
        min_page = 0
        max_page = total_pages - 1
        mid = 0

        logger.debug('max page: %d', max_page)
        while min_page <= max_page:
            mid = int(min_page + (max_page - min_page) / 2)
            logger.debug('min=%d, max=%d, mid=%d', min_page, max_page, mid)
            page_data = None
            start_date, end_date = page_dates.get(mid, (None, None))
            if not start_date:
                candidate_page_data = self._get_jobs_at_page(mid, page_size)
                if candidate_page_data:
                    start_date, end_date = self._get_page_start_end_dates(candidate_page_data)
                    page_dates[mid] = (start_date, end_date)
            if not start_date:
                page_data = None
                break
            logger.debug('page date %s , btw %s-%s', str(date), str(start_date), str(end_date))
            if date > end_date:
                max_page = mid - 1
            elif date < start_date:
                min_page = mid + 1
            else:
                logger.debug('date found at page: %d', mid)
                if not page_data:
                    page_data = self._get_jobs_at_page(mid, page_size, expand=True)
                break

        logger.debug('searching for page completed at page: %d', mid)
        return page_data, mid

    def _get_jobs_at_page(self, page, page_size, expand=False):
        try:
            return self._request_jobs(limit=page_size, offset=(page * page_size), expand=expand)
        except NbiNoContentException:
            return None

    @staticmethod
    def _get_page_start_end_dates(page):
        jobs = page.get('jobs')
        if not jobs:
            return None
        end = jobs[0]['created']
        start = jobs[-1]['created']

        # logger.debug('page data range: %s   -->   %s', start, end)
        return _parse_datetime(start), _parse_datetime(end)

    def _request_jobs(self, offset=0, limit=50, expand=False):
        parameters = {'offset': offset, 'limit': limit}
        if expand:
            parameters.update({'expand': ('summary', 'files')})
        return self._session.get(self._JOBS_URI, parameters=parameters)

    def get_job(self, job_id):
        response = self._session.get(urljoin(self._JOBS_URI, job_id), parameters={'expand': ('summary', 'files')})
        return ImportJob(self._session, self._cli, **response)

    def create_job(self, validation_policy_list, error_policy_list, name=None):
        data = {}
        if name:
            data['name'] = name
        if validation_policy_list:
            data['validationPolicy'] = validation_policy_list
        if error_policy_list:
            data['executionPolicy'] = error_policy_list

        response = self._session.post(self._JOBS_URI, request_body=json.dumps(data))

        return ImportJob(self._session, self._cli, **response)

    def _generate_import_jobs_list_from_response(self, response_json):
        list_of_import_jobs = []
        for job in response_json['jobs']:
            import_job = ImportJob(self._session, self._cli, **job)  #TODO  validation/error handling on creating the Import Job(key error)
            list_of_import_jobs.append(import_job)
        return list_of_import_jobs


class ImportJob(object):
    """
    Class to represent the current import job.
    All data representing a job is held here.
    This will represent the state of a particular job.
    """

    VALIDATION_INSTANCE_VALIDATION = 'instance-validation'
    VALIDATION_NO_INSTANCE_VALIDATION = 'no-instance-validation'

    ON_ERROR_STOP = 'stop-on-error'
    ON_ERROR_NEXT_OPERATION = 'continue-on-error-operation'
    ON_ERROR_NEXT_NODE = 'continue-on-error-node'

    EXECUTION_MODE_VALIDATE = 'validate'
    EXECUTION_MODE_VALIDATE_EXECUTE = 'validate-and-execute'
    EXECUTION_MODE_EXECUTE = 'execute'

    def __init__(self, nbi_session, cli, id, name='', validationPolicy=None, created=None,
                 status='', lastValidation='', lastExecution='', executionPolicy=None, totalElapsedTime='',
                 _links=None, files=None, summary=None, operations=None, userId='', failureReason='', **entries):
        self._session = nbi_session
        self._cli = cli
        self._id = id
        self._name = name
        self._validation_policy = validationPolicy
        self._created = created
        self._status = status
        self._last_validation = lastValidation
        self._last_execution = lastExecution
        self._execution_policy = executionPolicy
        self._total_elapsed_time = totalElapsedTime
        self._links = _links
        self._import_file = files
        self._operations = None
        self._job_summary = None
        self._failureReason = failureReason
        self._user_id = userId
        self._parse_operations(operations)
        self._parse_summary(summary)

    def id(self):
        return self._id

    def name(self):
        return self._name

    def status(self):
        return self._status

    def created(self):
        return self._created

    def validation_policy(self):
        return self._validation_policy

    def executed(self):
        return self._last_execution

    def execution_policy(self):
        return self._execution_policy

    def total_elapsed_time(self):
        return self._total_elapsed_time

    def links(self):
        return self._links

    def user_id(self):
        return self._user_id

    def failureReason(self):
        return self._failureReason

    def job_summary(self):
        return self._job_summary

    def set_import_job_summary(self, import_job_summary):
        self._parse_summary(import_job_summary)

    def progress(self):
        validation_progress = 0
        execution_progress = 0
        if self._job_summary:
            for summary in self._job_summary:
                if summary.type().lower() == 'total':
                    parsed = summary.parsed()
                    if parsed:
                        total_validated = summary.valid() + summary.invalid()
                        validation_progress = int(total_validated * 100 / parsed)

                        to_execute = parsed - summary.invalid()
                        if self.is_finished():
                            execution_progress = 100
                        elif to_execute > 0:
                            execution_progress = int((summary.executed() + summary.execution_errors()) * 100 / to_execute)
                    break

        return validation_progress, execution_progress

    def is_finished(self):
        return self.status().lower() in ['executed', 'execution-interrupted']

    def has_errors(self):
        if self._failureReason:
            return True

        summary = self.job_summary()
        if summary:
            for item in summary:
                try:
                    if item.invalid() and int(item.invalid()) > 0:
                        return True
                    elif item.execution_errors() and int(item.execution_errors()) > 0:
                        return True
                except ValueError:
                    continue
        return False

    def operations(self):
        if self._operations:
            return self._operations
        elif 'operations' in self._links:
            try:
                self._parse_operations(self._session.get(self._links['operations']['href'], parameters={'expand': ('attributes', 'failures')}))
            except NbiServiceUnavailableException as e:
                logger.error('Error fetching operations for job %s: %s', self._id, e)
                self._parse_operations([])
            except NbiNoContentException:
                self._operations = None

            return self._operations
        else:
            try:
                url_parts = urlsplit(self._links['self']['href'])
                operation_url = urlunsplit((url_parts[0], url_parts[1], urljoin(url_parts[2], 'operations'), '', ''))
                self._parse_operations(self._session.get(operation_url, parameters={'expand': ('attributes', 'failures')}))
            except NbiNoContentException:
                self._operations = None
            except Exception as e:
                self._operations = None
                logger.exception('Error fetching operations for job %s, %s', self._id, e)

            return self._operations

    def set_import_operations(self, import_operations):
        self._parse_operations(import_operations)

    def can_execute(self):
        return 'invocations' in self._links or str(self._status).lower() in ['validated']

    def execute(self, execution_mode, validation_policy_list=None, error_policy_list=None):
        if not self.can_execute():
            raise RuntimeError('Job %s can not be executed' % self._id)

        data = {'invocationFlow': execution_mode}
        if validation_policy_list:
            data['validationPolicy'] = validation_policy_list
        if error_policy_list:
            data['executionPolicy'] = error_policy_list

        self._session.post(self.get_invocations_url(), request_body=json.dumps(data))
        self.refresh()

    def get_invocations_url(self):
        if 'invocations' in self._links and self._links['invocations']['href']:
            return self._links['invocations']['href']

        url_parts = urlsplit(self._links['self']['href'])
        invocations_url = urlunsplit((url_parts[0], url_parts[1], urljoin(url_parts[2], 'invocations'), '', ''))
        return invocations_url

    def can_have_file(self):
        return 'files' in self._links

    def add_file(self, file_path):
        if not os.path.exists(file_path):
            raise ValueError('Path does not exist: ' + file_path)
        if not os.path.isfile(file_path):
            raise ValueError('It is not a file: ' + file_path)

        with open(file_path, 'rb') as f:
            file_name = os.path.basename(file_path)
            request = {'file': (file_name, f)}
            result = self._session.post(self._links['files']['href'], files=request, request_body={'filename': file_name})
            links = result.get('_links')
            if links and 'invocations' in links:
                self._links['invocations'] = links['invocations']

    def files(self):
        files = []
        if self._import_file:
            for item in self._import_file:
                files.append(ImportFile(**item))
        return files

    def __str__(self):
        return "id: %s\nName: %s\nStatus: %s\nCreated: %s" \
               "\nExecuted: %s\nExecution Policy: %s\nTotal Elapsed Time: %s\nLinks: %s\nImport File: %s" % \
               (self._id, self._name, self._status, self._created,
                self._last_execution, self._execution_policy, self._total_elapsed_time, self.links, self._import_file)

    def _parse_operations(self, import_operations):
        self._operations = ImportOperations(self._session, self._cli, **import_operations) if import_operations else None

    def _parse_summary(self, import_job_summary):
        self._job_summary = []
        if import_job_summary:
            for summary_data in import_job_summary.itervalues():
                self._job_summary.append(ImportJobSummary(self._session, **summary_data))

    def refresh(self):
        if 'self' in self._links:
            response = self._session.get(self._links['self']['href'], parameters={'expand': ('summary', 'files')})
            current_operations = self._operations
            self.__init__(self._session, self._cli, **response)
            if current_operations:
                self._operations = current_operations
                if current_operations.list_operations():
                    current_operations.fetch(current_operations.offset(), len(current_operations.list_operations()))


class ImportJobSummary(object):
    """
    Class representing the import Job Summary information

    """

    def __init__(self, nbi_session, type, parsed=0, valid=0, invalid=0, executed=0, executionErrors=0, _links=None):
        self._session = nbi_session
        self._execution_errors = executionErrors
        self._executed = executed
        self._invalid = invalid
        self._valid = valid
        self._parsed = parsed
        self._type = type
        self._links = _links

    def type(self):
        return self._type

    def parsed(self):
        return self._parsed

    def valid(self):
        return self._valid

    def invalid(self):
        return self._invalid

    def executed(self):
        return self._executed

    def execution_errors(self):
        return self._execution_errors


class ImportFile(object):

    def __init__(self, id, name):
        self._name = name
        self._id = id

    def name(self):
        return self._name

    def id(self):
        return self._id


class ImportOperations(object):
    """
    Class representing all the Import Operations of an ImportJob
    """
    def __init__(self, nbi_session, cli, totalCount, operations, _links):
        self._session = nbi_session
        self._cli = cli
        self._total_count = totalCount
        self._operations = None
        self._links = _links
        self._parse_operations(operations)
        self._offset = 0
        self._attr_value_cache = {}

    def total_count(self):
        return self._total_count

    def list_operations(self):
        return self._operations

    def offset(self):
        return self._offset

    def fetch(self, offset, length, get_current_value=False):
        self_link = self._get_self_link()
        if self_link is None:
            logger.error('Can not fetch operations, no self link provided')
            self._operations = None

        try:
            operations_wrapper = self._session.get(self_link, parameters={'offset': offset, 'limit': length, 'expand': ('attributes', 'failures')})
            self._parse_operations(operations_wrapper['operations'])
            self._offset = offset
        except NbiNoContentException:
            return []
        except NbiServiceUnavailableException as e:
            logger.error('Error fetching operations for job: %s', e)
            return []
        except Exception as e:
            self._parse_operations([])
            logger.exception('Error fetching operations at %s, %s', self_link, e)
            raise e

        if get_current_value:
            self.load_attribute_values()

        for operation in self._operations:
            current_values = self._attr_value_cache.get(operation.fdn())
            if current_values:
                attributes = operation.attributes()
                if attributes:
                    for attribute in attributes:
                        if not attribute.current_value():
                            current_value = current_values.get(attribute.name(), 'not found')
                            attribute.set_current_value(current_value)

        return self.list_operations()

    def set_operations(self, operations_list):
        self._operations = operations_list

    def links(self):
        return self._links

    def _get_self_link(self):
        if 'self' not in self.links():
            return None

        url_parts = urlsplit(self.links()['self']['href'])
        operation_url = urlunsplit((url_parts[0], url_parts[1], url_parts[2], '', ''))
        return operation_url

    def _parse_operations(self, operations):
        self._operations = []
        for operation in operations:
            self._operations.append(ImportOperation(self._session, **operation))

    def load_attribute_values(self, progress_listener=None):
        self._attr_value_cache = {}
        if self._operations:
            total_of_operations = len(self._operations)
            operations_evaluated = 0
            logger.debug('operations to get the current value from: %d', total_of_operations)
            for operation in self._operations:
                if operation.type().lower() in ('update', 'create'):
                    if not operation.fdn() in self._attr_value_cache:
                        cmedit_get = 'cmedit get %s -t' % operation.fdn()
                        logger.debug('executing: %s', cmedit_get)
                        result = self._cli.execute(cmedit_get)
                        if not result.is_command_result_available():
                            logger.error('Failed to fetch current value for MO %s. Http response code: %s', operation.fdn(), result.http_response_code())
                        else:
                            output = result.get_output()
                            if output.has_groups():
                                current_values = output.groups()[0][0]
                                values_cache = {}
                                for i in xrange(len(current_values)):
                                    values_cache[current_values[i].labels()[0]] = _cli_complex_to_json_object(current_values[i].value())

                                self._attr_value_cache[operation.fdn()] = values_cache
                            elif operation.type().lower() == 'update':
                                logger.warn('MO not found %s', operation.fdn())
                if progress_listener:
                    operations_evaluated += 1
                    progress_listener(int(operations_evaluated * 100 / total_of_operations))


class ImportOperation(object):
    """
    Class representing an Import Operation
    """
    def __init__(self, nbi_session, id, type, fdn, status, _links=None, attributes=None, failures=None):
        self._session = nbi_session
        self._id = id
        self._type = type
        self._fdn = fdn
        self._status = status
        self._links = _links
        self._failures = None
        self._attributes = None
        self._parse_attributes(attributes)
        self._parse_failures(failures)

    def id(self):
        return self._id

    def type(self):
        return self._type

    def fdn(self):
        return self._fdn

    def status(self):
        return self._status

    def links(self):
        return self._links

    def set_attributes(self, attributes):
        self._parse_attributes(attributes)

    def attributes(self):
        if self._attributes:
            return self._attributes
        elif self._links and 'attributes' in self._links:
            try:
                self._parse_attributes(self._session.get(self._links['attributes']['href'], parameters={'expand': 'current-value'}))
            except NbiNoContentException:
                self._parse_attributes(None)
            except Exception as e:
                logger.exception('Error fetching attributes of operation %s, %s', self._id, e)
                self._parse_attributes(None)
            return self._attributes
        else:
            return []

    def set_failures(self, failures):
        self._parse_failures(failures)

    def failures(self):
        if self._failures:
            return self._failures
        else:
            return []

    def __str__(self):
        return "id: %s\nType: %s\nFDN: %s\nStatus: %s\nLinks: %s\nAttributes: %s\nFailures: %s" % \
               (self._id, self._type, self._fdn, self._status, self._links, self._attributes, self._failures)

    def _parse_attributes(self, attributes):
        self._attributes = []
        if attributes:
            for attribute in attributes:
                self._attributes.append(ImportOperationAttribute(self._session, **attribute))

    def _parse_failures(self, failures):
        self._failures = []
        if failures:
            for failure in failures:
                self._failures.append(ImportOperationFailure(self._session, **failure))


class ImportOperationAttribute(object):
    """
    Class representing an import operation attribute.
    Has the current state of the attribute value in ENM and the attribute value in the import file
    Used to facilitate users to view the differences the import file will apply to the system.
    Name is the attribute name, value is the attribute value in the import job and current_value is the
    actual value of the attribute currently in the system.
    """
    def __init__(self, nbi_session, name, suppliedValue, currentValue=''):
        self._session = nbi_session
        self._name = name
        self._value = self._print_attribute_value(suppliedValue)
        self._current_value = currentValue

    def name(self):
        return self._name

    def value(self):
        return self._value

    def current_value(self):
        return self._current_value

    def set_current_value(self, new_value):
        self._current_value = self._print_attribute_value(new_value)

    def __str__(self):
        return "Name: %s\nValue: %s\nCurrent Value: %s\n" % \
               (self._name, self._value, self._current_value)

    @staticmethod
    def _print_attribute_value(value, level=0, item_sep=','):
        tab = ' ' * level
        if isinstance(value, basestring):
            return tab + value

        formatted = ''
        if isinstance(value, dict):
            items = []
            for k, v in value.iteritems():
                if isinstance(v, (dict, list, tuple)):
                    items.append(tab + '%s:\n%s' % (k, ImportOperationAttribute._print_attribute_value(v, level + 3, item_sep)))
                else:
                    items.append(tab + '%s: %s' % (k, ImportOperationAttribute._print_attribute_value(v, item_sep=item_sep)))
            formatted += '\n'.join(items)
        elif isinstance(value, (list, tuple)):
            formatted += (item_sep + '\n').join([ImportOperationAttribute._print_attribute_value(x, level, item_sep=item_sep) for x in value])
        else:
            formatted += tab + str(value)

        return formatted


class ImportOperationFailure(object):
    """
    Class representing a failure for a particular Import Operation.
    Includes the failure Reason for that operation.
    """
    def __init__(self, nbi_session, failureReason):
        self._nbi_session = nbi_session
        self._failure_reason = failureReason

    def failure_reason(self):
        return self._failure_reason

    def __str__(self):
        return "Failure Reason: %s\n" % self._failure_reason


_CLI_KV_RE = re.compile(r'(\w+)\s*=([^{},]*)')
_CLI_KV_ARRAY_RE = re.compile(r'(\w+)\s*=\s*\[')
_CLI_KV_ARRAY_ELEMENT_RE = re.compile(r'\[([^\]]+)\]')


def _cli_complex_to_json_object(value):
    if value.startswith('{'):
        replace = re.sub(_CLI_KV_RE, r'"\1": "\2"', value).replace('""{', '{')
        replace = re.sub(_CLI_KV_ARRAY_RE, r'"\1":[', replace)
        parts = re.split(_CLI_KV_ARRAY_ELEMENT_RE, replace)
        replace = ''.join([parts[i] if i % 2 == 0 else '[' + ', '.join(map(lambda e: '"'+e.strip()+'"', parts[i].split(','))) + ']' for i in xrange(len(parts))])
        try:
            return json.loads(replace)
        except Exception as e:
            logger.error('Error converting value to json: %s\n%s', value, e)
            return value
    else:
        return value


def _parse_datetime(timestamp):
    # this regex removes all colons and all
    # dashes EXCEPT for the dash indicating + or - utc offset for the timezone
    conformed_timestamp = re.sub(r"[:]|([-](?!((\d{2}[:]\d{2})|(\d{4}))$))", '', timestamp)

    # split on the offset to remove it. use a capture group to keep the delimiter
    split_timestamp = re.split(r"[+|-]",conformed_timestamp)
    main_timestamp = split_timestamp[0]
    if len(split_timestamp) == 3:
        sign = split_timestamp[1]
        offset = split_timestamp[2]
    else:
        sign = None
        offset = None

    # generate the datetime object without the offset at UTC time
    if not main_timestamp.endswith('Z'):
        main_timestamp = main_timestamp + 'Z'
    if '.' in main_timestamp:
        output_datetime = datetime.strptime(main_timestamp, "%Y%m%dT%H%M%S.%fZ")
    else:
        output_datetime = datetime.strptime(main_timestamp, "%Y%m%dT%H%M%SZ")

    if offset:
        # create timedelta based on offset
        offset_delta = timedelta(hours=int(sign+offset[:-2]), minutes=int(sign+offset[-2:]))
        # offset datetime with timedelta
        output_datetime = output_datetime + offset_delta

    return output_datetime
