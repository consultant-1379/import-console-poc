import uibind
import urwid as u
import tempfile
import itertools

from os import path
from cmimport import *
from datetime import datetime
from config import *
from collections import OrderedDict

logger = logging.getLogger(__name__)

_view_style = ('view',)
_textinput_style = ('textinput', 'focus textinput')
_heading_style = ('heading',)
_text_style = ('text',)
_error_text_style = ('error text',)
_list_style = ('list', )
_list_item_style = ('text', 'focus text')
_list_subheading_style = ('subheading', 'focus subheading')
_list_error_text_style = ('error area',)
_list_success_text_style = ('success area',)
_list_attention_text_style = ('attention area',)
_button_style = ('button', 'focus button')

_EXIT_BUTTON = '[E]xit'


class Hello(uibind.View):

    @uibind.textinput(caption='I say: ', order=0, style=('textinput', 'focus textinput'))
    def input(self):
        return 'hi'

    @input.uibind.listener
    def quittext(self, obj, value):
        if 'quit' == value:
            raise u.ExitMainLoop()

    @uibind.divider(order=1)
    def div(self):
        pass

    @uibind.text(align='center', order=1, style=('heading',))
    def description(self):
        return ' description....'

    @uibind.listbox(uibind.TextBuilder(), size=None, order=2)
    def list_of_items(self):
        return ['item - ' + str(x) for x in range(1, 200)]

    @uibind.divider(order=3, bottom=3)
    def div2(self):
        return '-'

    @uibind.buttons(labels=['Exit', 'Ok'], order=4, style=('button', 'focus button'))
    def quitbutton(self, obj, value):
        raise u.ExitMainLoop()


def print_tuple(s1, s2, s1_size=0):
    fstring = '%%-%ds: %%s' % s1_size if s1_size else '%%s : %%s'
    return fstring % (s1, s2)


class FileSelectionView(uibind.PopUpView):
    """
    Class to perform file or directory selection
    """
    def __init__(self, start_path='/', file_filter='', select_file=True, select_dir=False):
        """
        :param start_path: initial path of the file browser. This is the first directory to be listed
        :param file_filter: name filter to be applied to the start_path. It accepts usual wildcards "?", "*"
        :param select_file: indicates if the user is allowed to select files
        :param select_dir:  indicates if the user is allowed to select directories
        """
        if not select_file and not select_dir:
            raise ValueError('One of file or directory has to be allowed')
        selection = []
        if select_file:
            selection.append('file')
        if select_dir:
            selection.append('directory')
        super(FileSelectionView, self).__init__('Select %s' % ('/'.join(selection)), width=('relative', 80), height=('relative', 90), style=_view_style)
        self._select_dir = select_dir
        self._select_file = select_file
        self._file_filter = file_filter
        self._start_path = start_path
        self._selection = '/'.join(selection)

    def after_show(self):
        if self._file_filter:
            self.get_element_of(self.file_list).filter_by(self._file_filter)

    @uibind.textinput(caption='Root directory: ', order=10, style=_textinput_style)
    def search_root(self):
        return self._start_path

    @search_root.uibind.listener
    def on_search_root(self, obj, value):
        if value == 'enter':
            self._start_path = self.get_value_of(self.search_root)
            self.get_element_of(self.file_list).set_start_path(self._start_path)

    @uibind.divider(order=26)
    def div_options(self):
        pass

    @uibind.textinput(caption='Filter files: ', order=27, style=_textinput_style)
    def file_filter(self):
        return self._file_filter

    @file_filter.uibind.listener
    def on_file_filter(self, obj, value):
        if value == 'enter':
            filter_pattern = self.get_value_of(self.file_filter)
            self.get_element_of(self.file_list).filter_by(filter_pattern)

    @uibind.radios(caption='Order by    : ', labels=['Name', 'Date'], order=28, style=_textinput_style, caption_style=_text_style)
    def sort_options(self, obj, value, label):
        if value and label == 'Name':
            self.get_element_of(self.file_list).order_by(uibind.file_sort_by_name_asc)
        elif value and label == 'Date':
            self.get_element_of(self.file_list).order_by(uibind.file_sort_by_last_modified_desc)

    @uibind.divider(order=29)
    def div_filebrowser(self):
        pass

    @uibind.filebrowser(order=40, style=_list_style, item_style=_list_item_style, item_order_by=uibind.file_sort_by_name_asc)
    def file_list(self):
        return self._start_path

    @uibind.text(order=49, style=_error_text_style)
    def error_text(self):
        return ' '

    @uibind.buttons(labels=['[O]k', '[C]ancel'], align='center', order=50, style=_button_style)
    def actions(self, obj, value):
        if value == 'Ok':
            selected = self.get_value_of(self.file_list)
            if path.isfile(selected) and self._select_file:
                self.set_value(selected)
            elif path.isdir(selected) and self._select_dir:
                self.set_value(selected)
            else:
                self.get_element_of(self.error_text).set_text('Select a %s' % self._selection)
                return
        self.close()

    def after_build(self):
        self.register_shortcut('enter', 'keypress', self.get_element_of(self.actions)[0], (None, 'enter'))


class BaseImportJobExecutionView(uibind.View):
    """
    Base view which allows the user to select among the different job
    execution options
    """
    _EMPTY_LIST = []

    _validation_polices = json.loads(get_config().validation_policies, object_hook=OrderedDict)
    _execution_polices = json.loads(get_config().execution_policies, object_hook=OrderedDict)
    _execution_flow = json.loads(get_config().execution_flow, object_hook=OrderedDict)

    def _get_validation_policy_value(self, key):
        return self._get(key, self._validation_polices)

    def _get_execution_policy_value(self, key):
        return self._get(key, self._execution_polices)

    def _get_execution_flow_value(self, key):
        return self._get(key, self._execution_flow)

    @staticmethod
    def _keys(list_of_dic):
        return list(itertools.chain.from_iterable([d.keys() for d in list_of_dic]))

    @staticmethod
    def _get(key, list_of_dic):
        for d in list_of_dic:
            value = d.get(key, None)
            if value:
                return value
        return None

    @uibind.text(align='center', order=101, style=_heading_style)
    def form_intro(self):
        return 'Execution options'

    @uibind.divider(order=102)
    def div_form(self):
        pass

    @uibind.radios(caption='Validation policy: ', order=105, style=_textinput_style)
    def select_validation_policy(self):
        return [d.keys() for d in self._validation_polices]

    @uibind.divider(order=110)
    def div_exec_policy(self):
        pass

    @uibind.radios(caption='Execution policy: ', order=115, style=_textinput_style)
    def select_execution_policy(self):
        return [d.keys() for d in self._execution_polices]

    @uibind.divider(order=120)
    def div_exec_flow(self):
        pass

    @uibind.radios(caption='Execution flow: ', order=125, style=_textinput_style, size=None)
    def select_execution_flow(self):
        return [d.keys() for d in self._execution_flow]

    def get_job_execution_options(self):
        execution_flow = [value for value in [self._get_execution_flow_value(selected_label) for selected_label in
                                              self.get_value_of(self.select_execution_flow)] if value]
        execution_policy = [value for value in [self._get_execution_policy_value(selected_label) for selected_label in
                                                self.get_value_of(self.select_execution_policy)] if value]
        validation_policy = [value for value in
                             [self._get_validation_policy_value(selected_label) for selected_label in
                              self.get_value_of(self.select_validation_policy)] if value]
        if not execution_flow:
            raise ValueError('Select a valid Execution flow')

        return execution_flow[0], execution_policy, validation_policy

    @uibind.popup()
    def success_message_popup(self):
        return MessagePopup('Import job was started successfully')

    @success_message_popup.uibind.listener
    def on_popup_close(self, obj, value):
        self.get_display().back()


class NewImportJobView(BaseImportJobExecutionView):
    """
    View to create a new import job
    """
    _allowed_flows = json.loads(get_config().allowed_new_job_execution_flows)

    def __init__(self, cm_import, import_file=None, allow_file_selection=True, delete_file_on_exit=False, file_cleaner=None):
        """
        :param cm_import: reference to a instance of CmImport
        :param import_file: Optionally can pass the file to be imported
        :param allow_file_selection: if the user should be allows to select the file to be imported
        :param delete_file_on_exit: if the file should be deleted on exiting the view
        :param file_cleaner: optionally a reference to instance of FileCleaner
        """
        super(NewImportJobView, self).__init__('New import job', style=_view_style)
        self._file_cleaner = file_cleaner
        self._cm_import = cm_import
        self._import_file = import_file
        self._allow_file_selection = allow_file_selection
        self._delete_file_on_exit = delete_file_on_exit
        self._import_job = None

    @uibind.text(order=10, style=_text_style)
    def intro(self):
        return 'By selecting execute, a new import job will be created and the execution process will be started'

    @uibind.divider(order=15)
    def div_name(self):
        pass

    @uibind.textinput(caption='Job name: ', order=16, style=_textinput_style, action_on_enter=False)
    def job_name(self):
        pass

    @uibind.divider(order=17)
    def div_file(self):
        pass

    @uibind.text(order=20, style=_text_style)
    def job_file(self):
        if not self._allow_file_selection:
            return None
        return 'Import file : -- select a file --'

    @uibind.buttons(align='left', order=30, style=_button_style)
    def select_file_button(self):
        if not self._allow_file_selection:
            return None
        return ['select [F]ile']

    @select_file_button.uibind.listener
    def select_file(self, obj, value):
        self.select_file_popup.popup.show()

    @uibind.divider(order=31)
    def div_file_button(self):
        pass

    @uibind.radios(caption='File policy: ', style=_textinput_style, order=32)
    def file_clean_up_policy(self):
        if not self._has_file_policy():
            return None
        return ['Keep file', 'Remove file on job success']

    def _has_file_policy(self):
        return self._allow_file_selection and self._file_cleaner

    @uibind.divider(order=35, top=1)
    def div_exec_options(self):
        pass

    @uibind.popup()
    def select_file_popup(self):
        start_path = get_config().import_file_path if get_config() and get_config().import_file_path else '/'
        return FileSelectionView(start_path=start_path, file_filter=get_config().default_file_name_filter)

    @select_file_popup.uibind.listener
    def on_file_popup_close(self, obj, value):
        if value:
            self._import_file = value
            self.get_element_of(self.job_file).set_text('Import file : ' + value)

    @uibind.divider(char=u'_', top=1, bottom=1, order=200)
    def div_bottom(self):
        pass

    @uibind.radios(caption='Execution flow: ', order=125, style=_textinput_style, size=None)
    def select_execution_flow(self):
        return map(lambda item: item[0], itertools.ifilter(lambda item: item[1] in self._allowed_flows, itertools.chain.from_iterable([d.iteritems() for d in self._execution_flow])))

    @uibind.buttons(labels=['e[X]ecute', '[B]ack', _EXIT_BUTTON], align='right',  style=_button_style, order=201)
    def action_option(self, obj, value):
        if value == 'Exit':
            self._delete_file_if_required()
            raise u.ExitMainLoop
        if value == 'eXecute':
            self._validate_file()
            execution_flow, execution_policy, validation_policy = self.get_job_execution_options()

            if self._import_job is None:
                job_name = self.get_value_of(self.job_name) or None
                self._import_job = self._cm_import.create_job(validation_policy_list=validation_policy, error_policy_list=execution_policy, name=job_name)

            self._import_job.add_file(self._import_file)
            self._delete_file_if_required()

            if path.exists(self._import_file) and self._has_file_policy():
                file_policy = self.get_value_of(self.file_clean_up_policy)[0]
                if file_policy.startswith('Remove '):
                    self._file_cleaner.add_file(self._import_job.id(), self._import_file)

            try:
                self._import_job.execute(execution_flow, validation_policy_list=validation_policy, error_policy_list=execution_policy)
            except Exception as e:
                self.get_display().back()
                raise RuntimeError('The import job [%s] was created but the execution failed due to: %s ' % (str(self._import_job.id()), str(e)))

            self.success_message_popup.popup.show()

        else:
            self._delete_file_if_required()
            self.get_display().back()

    @uibind.propagate_exception
    def _validate_file(self):
        if not self._import_file:
            raise ValueError('Please select a file to import')

    def _delete_file_if_required(self):
        if self._delete_file_on_exit and self._import_file and path.exists(self._import_file):
            logger.debug('Deleting file [%s] as requested...', self._import_file)
            os.remove(self._import_file)

    @uibind.popup()
    def success_message_popup(self):
        return MessagePopup('Import job %s was started successfully' % (self._import_job.id() if self._import_job else ''))

    @success_message_popup.uibind.listener
    def on_popup_close(self, obj, value):
        self.get_display().back()


class ImportJobExecuteView(BaseImportJobExecutionView):
    """
    View to configure and start a import job execution
    """
    _FIELD_NAME_SIZE = 19

    def __init__(self, import_job):
        """
        :param import_job: reference to ImportJob instance
        """
        super(ImportJobExecuteView, self).__init__('Execute job', style=_view_style)
        self._import_job = import_job

    def after_build(self):
        radio_bar = self.get_element_of(self.select_validation_policy)
        for policy in self._import_job.validation_policy():
            for radio in radio_bar.get_options():
                if policy == self._get_validation_policy_value(radio.label):
                    radio.set_state(True)

        radio_bar = self.get_element_of(self.select_execution_policy)
        for policy in self._import_job.execution_policy():
            for radio in radio_bar.get_options():
                if policy == self._get_execution_policy_value(radio.label):
                    radio.set_state(True)

    @uibind.text(align='center', order=5, style=_heading_style)
    def job_id(self):
        return 'Job id %d' % (self._import_job.id() or -1)

    @uibind.text(order=10, style=_text_style)
    def job_name(self):
        if self._import_job.name():
            return print_tuple('Job name', self._import_job.name() or '', self._FIELD_NAME_SIZE)
        return None

    @uibind.text(order=15, style=_text_style)
    def job_status(self):
        return print_tuple('Status', self._import_job.status() or '', self._FIELD_NAME_SIZE)

    @uibind.text(order=20, style=_text_style)
    def job_crated(self):
        return print_tuple('Created at', self._import_job.created() or '', self._FIELD_NAME_SIZE)

    @uibind.text(order=25, style=_text_style)
    def job_last_execution(self):
        return print_tuple('Last executed at', self._import_job.executed() or '', self._FIELD_NAME_SIZE)

    @uibind.divider(order=30, bottom=2)
    def div_form_intro(self):
        pass

    @uibind.divider(char=u'_', top=1, bottom=1, order=210)
    def div_bottom(self):
        pass

    @uibind.buttons(labels=['e[X]ecute', '[B]ack', _EXIT_BUTTON], align='right',  style=_button_style, order=211)
    def action_option(self, obj, value):
        if value == 'Exit':
            raise u.ExitMainLoop
        if value == 'eXecute':

            execution_flow, execution_policy, validation_policy = self.get_job_execution_options()

            self._import_job.execute(execution_mode=execution_flow,
                                     validation_policy_list=validation_policy,
                                     error_policy_list=execution_policy)

            self.success_message_popup.popup.show()

        else:
            self.get_display().back()


class CurrentValueProgressPopup(uibind.PopUpView):

    def __init__(self, import_job):
        super(CurrentValueProgressPopup, self).__init__('Current value update', style=_view_style, height=15)
        self._import_job = import_job

    @uibind.divider(top=2, order=1)
    def description_div(self):
        pass

    @uibind.text(align='center', order=5, style=_text_style)
    def description(self):
        return 'Fetching current values for attributes...'

    @uibind.divider(top=2, order=10)
    def progress_div(self):
        pass

    @uibind.progressbar(align='center', style_normal='pg normal', style_complete='pg complete', width=('relative', 90), size=None, order=20)
    def progress_bar(self):
        return 0

    def after_show(self):
        pbar = self.get_element_of(self.progress_bar)
        job_operations = self._import_job.operations()
        if job_operations:
            def progress_listener(p):
                pbar.set_completion(p)
                self.get_display().redraw_ui()
            job_operations.load_attribute_values(progress_listener)

        self.close()


class JobOperationsListItemBuilder(uibind.WidgetBuilder):
    """
    Builder that creates the ui-componentes for each JobOperation item
    in the job operations list
    """
    def __init__(self, **kwargs):
        super(JobOperationsListItemBuilder, self).__init__(**kwargs)

    def do_build(self, instance, binder):
        index, job_operation = binder.source
        icon = u.SelectableIcon(str(index+1))
        type_text = u.AttrMap(u.Text(str(job_operation.type())), *_heading_style)
        fdn_text = u.AttrMap(u.Text(job_operation.fdn()), *_text_style)
        status_text = u.Text(job_operation.status(), align='center')

        attribute_list_content = []
        for attribute in job_operation.attributes():
            row_content = [u.Text(attribute.name()), u.Text(attribute.value()), u.Text(attribute.current_value())]
            attribute_list_content.append(u.Columns(row_content, dividechars=1))
        if len(attribute_list_content) > 0:
            heading = u.Columns((u.Text('attribute'),
                                 u.Text('new value'),
                                 u.Text('current value')), dividechars=1)
            heading = u.AttrMap(heading, *_list_subheading_style)

            attribute_list_content.insert(0, heading)
            attribute_list_content.insert(0, u.Divider())

        attribute_list = u.Padding(u.Pile(attribute_list_content), left=3)

        failures_list_content = []

        for failure in job_operation.failures():
            failures_list_content.append(u.Text(failure.failure_reason()))
        if len(failures_list_content) > 0:
            heading = u.Text('errors:', align='left')
            heading = u.AttrMap(heading, *_list_error_text_style)

            failures_list_content.insert(0, heading)
            failures_list_content.insert(0, u.Divider())

        failures_list = u.Padding(u.Pile(failures_list_content), left=3)

        operation_details = u.Pile((('pack', type_text), ('pack', fdn_text), attribute_list, failures_list))
        operation_and_status = u.Columns((('pack', icon), (20, status_text), operation_details), dividechars=1)
        item_div = u.Divider(div_char=u' ')

        top = u.AttrMap(u.Pile((operation_and_status, ('pack', item_div))), *_list_item_style)

        return top


class ImportJobDetailsView(uibind.View):
    """
    View of detailed information of the job
    """
    _EMPTY_LIST = []
    _FIELD_NAME_SIZE = 19

    class CmImportOperationsDataSource(uibind.NavigableDataSource):

        def __init__(self, import_job):
            self._import_job = import_job
            self._operations = import_job.operations()
            self._fetch_current_value = False

        def fetch(self, start, size):
            data = self._operations.fetch(start, size, self._fetch_current_value) if self._operations else None
            if data:
                data = [(start + i, data[i]) for i in xrange(len(data))]

            return data

        def set_fetch_current_value(self, flag):
            self._fetch_current_value = flag

    def __init__(self, import_job, cm_import, cm_undo):
        """
        :param import_job: a reference to a instance of ImportJob
        :param cm_import: a reference to a instance of CmImport
        :param cm_undo:  a reference to a instance of CmUndo
        """
        super(ImportJobDetailsView, self).__init__('Import job details', style=_view_style)
        self._cm_undo = cm_undo
        self._cm_import = cm_import
        self._import_job = import_job
        self._refresh_work = None
        self._operations_ds = ImportJobDetailsView.CmImportOperationsDataSource(self._import_job)
        self._refresh_on_show = False

    def after_show(self):
        if self._refresh_on_show:
            status = self.get_element_of(self.job_status)
            if status:
                self._import_job.refresh()
                status.set_text(self.job_status())
            self._refresh_on_show = False

    @uibind.text(align='center', order=5, style=_heading_style)
    def job_id(self):
        return 'Job id %d' % (self._import_job.id() or -1)

    @uibind.text(order=10, style=_text_style)
    def job_name(self):
        if not self._import_job.name():
            return None

        return print_tuple('Job name', self._import_job.name() or '', self._FIELD_NAME_SIZE)

    @uibind.divider(order=11)
    def name_div(self):
        pass

    @uibind.text(order=15, style=_text_style)
    def job_status(self):
        return print_tuple('Status', self._import_job.status() or '', self._FIELD_NAME_SIZE)

    @uibind.text(order=18, style=_text_style)
    def job_user_id(self):
        if not self._import_job.user_id():
            return None

        return print_tuple('Created by', self._import_job.user_id(), self._FIELD_NAME_SIZE)

    @uibind.text(order=20, style=_text_style)
    def job_crated(self):
        return print_tuple('Created at', self._import_job.created() or '', self._FIELD_NAME_SIZE)

    @uibind.text(order=25, style=_text_style)
    def job_last_execution(self):
        return print_tuple('Last executed at', self._import_job.executed() or '', self._FIELD_NAME_SIZE)

    @uibind.text(order=30, style=_text_style)
    def validation_policy(self):
        return print_tuple('Validation policy', ', '.join(self._import_job.validation_policy() or self._EMPTY_LIST), self._FIELD_NAME_SIZE)

    @uibind.text(order=35, style=_text_style)
    def execution_policy(self):
        return print_tuple('Execution policy', ', '.join(self._import_job.execution_policy() or self._EMPTY_LIST), self._FIELD_NAME_SIZE)

    @uibind.divider(order=36)
    def div_failure_reason(self):
        if not self._import_job.failureReason():
            return None

        return u' '

    @uibind.text(align='center', order=37, style=_list_error_text_style)
    def failure_reason(self):
        if not self._import_job.failureReason():
            return None

        return self._import_job.failureReason()

    @uibind.divider(top=1, order=38)
    def summary_div(self):
        pass

    @uibind.text(align='center', style=_heading_style, order=39)
    def summary_intro(self):
        return 'Execution summary:'

    @uibind.texttable(order=40, style=_text_style, size=None)
    def job_summary(self):

        class CmImportSummaryDataSource(uibind.NavigableDataSource):

            def __init__(self, import_job):
                self._import_job = import_job

            def fetch(self, start, size):
                data = self._get_summary_data()
                if not data:
                    return None
                end = min(start + size, len(data))
                return data[start:end]

            def _get_summary_data(self):
                summary = self._import_job.job_summary()
                if not summary:
                    return None

                table = []
                title = ('', 'parsed', 'valid', 'invalid', 'executed', 'errors')
                total_line = None

                table.append(title)
                for item in summary:
                    line = (item.type(), item.parsed(), item.valid(), item.invalid(), item.executed(), item.execution_errors())
                    if item.type() == 'total':
                        total_line = line
                    else:
                        table.append(line)
                if total_line:
                    table.append(total_line)

                return table

        return CmImportSummaryDataSource(self._import_job)

    @uibind.divider(top=1, order=45)
    def operations_div(self):
        pass

    @uibind.text(align='center', style=_heading_style, order=50)
    def operations_intro(self):
        return 'Operations:'

    @uibind.listbox(JobOperationsListItemBuilder(), size=('weight', 3), order=55)
    def operations_list(self):
        return self._operations_ds

    @uibind.popup()
    def select_file_popup(self):
        start_path = get_config().import_file_path if get_config() and get_config().import_file_path else '/'
        return FileSelectionView(start_path=start_path, file_filter=get_config().default_file_name_filter)

    @select_file_popup.uibind.listener
    def on_file_popup_close(self, obj, value):
        if value:
            self._import_job.add_file(value)
            self.success_file_popup.popup.show()

    @uibind.popup()
    def success_file_popup(self):
        return MessagePopup('Import file was added successfully')

    @success_file_popup.uibind.listener
    def on_popup_close(self, obj, value):
        self._import_job.refresh()
        self.get_display().rebuild_ui()

    @uibind.popup()
    def current_value_progress_popup(self):
        return CurrentValueProgressPopup(self._import_job)

    @current_value_progress_popup.uibind.listener
    def on_current_value_progress_popup_close(self, obj, value):
        operations = self.get_element_of(self.operations_list)
        if operations:
            operations.refresh()

    @uibind.divider(char=u'_', bottom=1, order=65)
    def div_bottom(self):
        pass

    @uibind.buttons(align='right',  style=_button_style, order=70)
    def action_option(self):
        actions = []
        if self._import_job.can_execute():
            actions.append('e[X]ecute')
        if self._import_job.can_have_file():
            actions.append('add [F]ile')
        if self._import_job.is_finished() and get_config().enable_job_undo:
            actions.append('[U]ndo')

        actions += ['current [V]alues', '[B]ack', _EXIT_BUTTON]
        return actions

    @action_option.uibind.listener
    def perform_action(self, obj, value):
        if value == 'Exit':
            raise u.ExitMainLoop
        if value == 'Back':
            self.get_display().back()
        elif value == 'eXecute':
            self._refresh_on_show = True
            self.get_display().show_view(ImportJobExecuteView(self._import_job))
        elif value == 'add File':
            self.select_file_popup.popup.show()
        elif value == 'Undo':
            self.get_display().show_view(BrowseUndosView(self._cm_import, self._cm_undo, self._import_job))
        elif value == 'current Values':
            self.current_value_progress_popup.popup.show()

    def _refresh_import_job(self):
        self._import_job.refresh()
        self._import_job.job_summary()
        self._import_job.operations()

    def update_interval(self):
        logger.debug('Job detail got update interval request...')
        if not get_config().auto_refresh_enabled:
            return

        if self._refresh_work:
            work = self.get_display().get_work(self._refresh_work)
            if work and work.is_ended():
                summary = self.get_element_of(self.job_summary)
                if summary:
                    summary.refresh()

                operations = self.get_element_of(self.operations_list)
                if operations:
                    operations.refresh()

                status = self.get_element_of(self.job_status)
                if status:
                    status.set_text(self.job_status())

                last_exec = self.get_element_of(self.job_last_execution)
                if last_exec:
                    last_exec.set_text(self.job_last_execution())

            if work is None or work.is_ended():
                self._refresh_work = None
        else:
            logger.debug('... generating refresh work')
            self._refresh_work = self.get_display().request_work(self._refresh_import_job)


class ImportListFilterView(uibind.PopUpView):
    """
    View for selection of filters to be applied to the list of import jobs
    """

    _INPUT_TIME_FORMAT_FULL = '%d/%m/%Y %H:%M'
    _INPUT_DATE_FORMAT_8 = '%d%m%Y'
    _INPUT_DATE_FORMAT_10 = '%d/%m/%Y'
    _INPUT_TIME_FORMAT_13 = '%d%m%Y %H%M'
    _INPUT_TIME_FORMAT_14 = '%d%m%Y %H:%M'

    _size_to_format = {8: _INPUT_DATE_FORMAT_8,
                       10: _INPUT_DATE_FORMAT_10,
                       13: _INPUT_TIME_FORMAT_13,
                       14: _INPUT_TIME_FORMAT_14}

    def __init__(self, job_id, user_id, created_before, created_after):
        super(ImportListFilterView, self).__init__('Filter by', style=_view_style, height=15)
        self._job_id = job_id or ''
        self._created_after = created_after.strftime(self._INPUT_TIME_FORMAT_FULL) if created_after else ''
        self._created_before = created_before.strftime(self._INPUT_TIME_FORMAT_FULL) if created_before else ''
        self._user_id = user_id or ''

    @uibind.textinput('Job id: ', order=5, style=_textinput_style, action_on_enter=True)
    def job_id(self):
        return self._job_id

    @job_id.uibind.listener
    def on_job_id(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Ok')
        self._job_id = value

    @uibind.divider(order=6, top=1)
    def job_div(self):
        pass

    @uibind.textinput('User id: ', order=10, style=_textinput_style, action_on_enter=True, disable_on_none=True)
    def user_id(self):
        if not get_config().enable_job_filtering_by_userid:
            return None

        return self._user_id

    @user_id.uibind.listener
    def on_user_id(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Ok')
        self._user_id = value

    @uibind.divider(order=11, top=1)
    def user_div(self):
        pass

    @uibind.textinput('Created after (dd/mm/yyyy HH:MM): ', order=20, style=_textinput_style, action_on_enter=True, disable_on_none=True)
    def created_after(self):
        if not get_config().enable_job_filtering_by_date:
            return None
        return self._created_after

    @created_after.uibind.listener
    def on_created_after(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Ok')
        self._created_after = value

    @uibind.text(style=_error_text_style, order=21)
    def created_after_error_text(self):
        return ''

    @uibind.divider(order=22)
    def after_div(self):
        pass

    @uibind.textinput('Created before (dd/mm/yyyy HH:MM): ', order=30, style=_textinput_style, action_on_enter=True, disable_on_none=True)
    def created_before(self):
        if not get_config().enable_job_filtering_by_date:
            return None
        return self._created_before

    @created_before.uibind.listener
    def on_created_before(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Ok')
        self._created_before = value

    @uibind.text(valign='top', style=_error_text_style, order=31, size=None)
    def created_before_error_text(self):
        return ''

    @uibind.buttons(labels=['[O]k', '[C]ancel'], align='center', order=50, style=_button_style)
    def actions(self, obj, value):
        if value == 'Ok':
            created_after = None
            created_before = None
            if self._created_after:
                error_text = self.get_element_of(self.created_after_error_text)
                try:
                    created_after = datetime.strptime(self._created_after, self._size_to_format.get(len(self._created_after), self._INPUT_TIME_FORMAT_FULL))
                except ValueError:
                    error_text.set_text('Invalid date/time format')
                    return
                else:
                    error_text.set_text('')

            if self._created_before:
                error_text = self.get_element_of(self.created_before_error_text)
                try:
                    created_before = datetime.strptime(self._created_before, self._size_to_format.get(len(self._created_before), self._INPUT_TIME_FORMAT_FULL))
                    if len(self._created_before) <= 10:
                        created_before = created_before.replace(hour=23, minute=59, second=59)
                    else:
                        created_before = created_before.replace(second=59)
                except ValueError:
                    error_text.set_text('Invalid date/time format')
                    return
                else:
                    error_text.set_text('')

            logger.debug('Returning filters: %s, %s, %s', self._user_id, created_after, created_before)
            self.set_value((self._job_id, self._user_id, created_after, created_before))

        self.close()


class ImportListItemBuilder(uibind.WidgetBuilder):
    """
    Builder to build the ui-componentes for each job item in the list
    of import jobs
    """
    def __init__(self, action_listener=None, **kwargs):
        super(ImportListItemBuilder, self).__init__(**kwargs)
        self.action_listener = action_listener

    def do_build(self, instance, binder):
        import_job = binder.source
        icon = u.SelectableIcon(u'-')
        id_text = u.AttrMap(u.Text(str(import_job.id()), align='right'), *_heading_style)
        name_text = u.Text(import_job.name())
        if import_job.has_errors():
            status_text = u.Columns((('pack', u.Text('status: ')), u.AttrMap(u.Text(import_job.status(), align='center'), *_list_error_text_style)))
        elif import_job.status().lower() == 'executed':
            status_text = u.Columns((('pack', u.Text('status: ')), u.AttrMap(u.Text(import_job.status(), align='center'), *_list_success_text_style)))
        else:
            status_text = u.Columns((('pack', u.Text('status: ')), u.AttrMap(u.Text(import_job.status(), align='center'), *_list_attention_text_style)))

        first_row = u.Columns((('pack', icon),(10, id_text), ('weight', 2, name_text), (30, status_text)), dividechars=1)

        created_elements = [u.Text('created at: %s' % import_job.created())]
        if import_job.user_id():
            created_elements.append(u.Text('created by: %s' % import_job.user_id()))
        created_row = u.Columns(created_elements, dividechars=1)

        executed_date_text = u.Text('last executed at: %s' % import_job.executed())
        if not import_job.job_summary():
            progress = u.Text(' ')
        elif import_job.is_finished():
            progress_message = import_job.failureReason() if import_job.failureReason() else ' ** Job completed. ** '
            progress = u.Text(progress_message, align='center')
        else:
            validation_progress, execution_progress = import_job.progress()
            progress = u.Columns((u.Text('Validation: ', align='right'),
                                  (18, u.ProgressBar('pg normal', 'pg complete', validation_progress)),
                                  u.Text('  Execution: ', align='right'),
                                  (18, u.ProgressBar('pg normal', 'pg complete', execution_progress))),
                                 dividechars=1)
        data_column = u.Padding(u.Pile((first_row, created_row, executed_date_text, progress)), left=1, right=1)

        details_button = u.AttrMap(u.Button('Details'), *_button_style)
        execute_button = u.AttrMap(u.Button('Execute'), *_button_style) if import_job.can_execute() and import_job.status().lower() in ['validated'] else None
        actions_bar = u.Pile((details_button, execute_button) if execute_button else (details_button, ))

        item_div = u.Divider(div_char=u' ')
        top = u.AttrMap(u.Pile((u.Columns((data_column, (11, actions_bar))), item_div)), *_list_item_style)
        top.get_value = lambda: import_job

        if callable(self.action_listener):
            connect_args = (details_button.base_widget, "click", self.action_listener, details_button.base_widget.label, None, [instance])
            u.connect_signal(*connect_args)
            self.add_connected_signal(instance, connect_args)

            if execute_button:
                connect_args = (execute_button.base_widget, "click", self.action_listener, execute_button.base_widget.label, None, [instance])
                u.connect_signal(*connect_args)
                self.add_connected_signal(instance, connect_args)

        return top


class BrowseImportView(uibind.View):
    """
    View that lists import jobs and theirs status
    """
    class CmImportDataSource(uibind.NavigableDataSource):

        def __init__(self, cm_import, job_id=None, user_id=None, created_before=None, created_after=None):
            self.job_id = job_id
            self.created_after = created_after
            self.created_before = created_before
            self.user_id = user_id
            self._cm_import = cm_import

        def fetch(self, start, size):
            logger.debug('asking for import-jobs: start=%d, size=%d, user_id=%s, before=%s, after=%s' % (start, size, self.user_id, self.created_before, self.created_after))
            return self._cm_import.get_jobs(start, size,
                                            job_id=self.job_id,
                                            user_id=self.user_id,
                                            created_before=self.created_before,
                                            created_after=self.created_after)

    def __init__(self, cm_import, cm_undo):
        super(BrowseImportView, self).__init__('Import jobs list', style=_view_style)
        self._cm_undo = cm_undo
        self._cm_import = cm_import
        self._first_shown = True
        self._refresh_work = None
        self._data_source = self.CmImportDataSource(self._cm_import)

    def after_show(self):
        if not self._first_shown:
            self.get_display().rebuild_ui()

        self._first_shown = False

    @uibind.buttons(align='right', style=_button_style, order=5)
    def filters_option(self):
        if not get_config().enable_job_filtering:
            return None

        num_filters = len([x for x in (self._data_source.job_id, self._data_source.user_id, self._data_source.created_after, self._data_source.created_before) if x is not None])
        return '[F]ilters (%02d)' % num_filters if num_filters else '  [F]ilters   '

    @filters_option.uibind.listener
    def filters_option_action(self, obj, value):
        self.filters_popup.popup.show()

    @uibind.popup()
    def filters_popup(self):
        return ImportListFilterView(self._data_source.job_id, self._data_source.user_id, self._data_source.created_before, self._data_source.created_after)

    @filters_popup.uibind.listener
    def on_filters_popup_close(self, obj, value):
        if value:
            job_id, user_id, created_after, created_before = value
            self._data_source.job_id = job_id if job_id else None
            self._data_source.user_id = user_id if user_id else None
            self._data_source.created_after = created_after
            self._data_source.created_before = created_before
            self.get_element_of(self.import_list).refresh()

            self.get_element_of(self.filters_option).set_label(self.filters_option())

    @uibind.divider(order=10)
    def div_filter(self):
        pass

    def import_list_item_action_listener(self, obj, value):
        import_job = self.get_value_of(self.import_list)
        if value == 'Details' and import_job:
            view = ImportJobDetailsView(import_job, self._cm_import, self._cm_undo)
            self.get_display().show_view(view)
        elif value == 'Execute' and import_job:
            view = ImportJobExecuteView(import_job)
            self.get_display().show_view(view)

    @uibind.listbox(ImportListItemBuilder(action_listener=import_list_item_action_listener), size=None, order=15, buffer_size=get_config().list_buffer_size)
    def import_list(self):

        return self._data_source

    @uibind.divider(char=u'_', bottom=1, order=20)
    def div_bottom(self):
        pass

    @uibind.buttons(labels=['[B]ack', _EXIT_BUTTON], align='right',  style=_button_style, order=30)
    def back_option(self, obj, value):
        if value == 'Exit':
            raise u.ExitMainLoop
        self.get_display().back()

    def refresh(self):
        import_list = self.get_element_of(self.import_list)
        self._cm_undo.get_jobs()
        if import_list:
            logger.debug('Refreshing job list...')
            import_list.refresh()
            self.get_display().redraw_ui()

    def update_interval(self):
        logger.debug('Job list got update interval request...')
        if not get_config().auto_refresh_enabled:
            return

        if self._refresh_work:
            work = self.get_display().get_work(self._refresh_work)
            if work is None or work.is_ended():
                self._refresh_work = None
        else:
            logger.debug('... generating refresh work')
            self._refresh_work = self.get_display().request_work(self.refresh)


class ImportSearchView(uibind.View):
    """
    View for searching import jobs
    """

    class CmImportDataSource(uibind.NavigableDataSource):

        def __init__(self, cm_import, job_name=None, user_id=None, created_from=None, created_to=None):
            self.job_name = job_name
            self.created_from = created_from
            self.created_to = created_to
            self.user_id = user_id
            self._cm_import = cm_import
            self._last_created_from = None
            self._last_created_to = None
            self._last_user_id = None
            self._last_job_name = None
            self._last_result = None

        def size(self):
            return len(self._last_result) if self._last_result else 0

        def fetch(self, start, size):
            if not self.created_from:
                logger.debug('No dates, nothing to search for....')
                return []

            if self._last_created_from == self.created_from \
                    and self._last_created_to == self.created_to \
                    and self._last_user_id == self.user_id \
                    and self._last_job_name == self.job_name:
                result = self._last_result
            else:
                result = self._cm_import.find_jobs(self.created_from, self.created_to, job_name=self.job_name,
                                                   user_id=self.user_id)
                logger.debug('Search result len: %d', len(result))
                self._last_created_from = self.created_from
                self._last_created_to = self.created_to
                self._last_user_id = self.user_id
                self._last_job_name = self.job_name
                self._last_result = result

            return result[start: min(start + size, len(result))]

    _INPUT_TIME_FORMAT_FULL = '%d/%m/%Y %H:%M'
    _INPUT_DATE_FORMAT_8 = '%d%m%Y'
    _INPUT_DATE_FORMAT_10 = '%d/%m/%Y'
    _INPUT_TIME_FORMAT_13 = '%d%m%Y %H%M'
    _INPUT_TIME_FORMAT_14 = '%d%m%Y %H:%M'

    _size_to_format = {8: _INPUT_DATE_FORMAT_8,
                       10: _INPUT_DATE_FORMAT_10,
                       13: _INPUT_TIME_FORMAT_13,
                       14: _INPUT_TIME_FORMAT_14}

    def __init__(self, cm_import, cm_undo):
        super(ImportSearchView, self).__init__('Search import Job', style=_view_style)
        self._cm_import = cm_import
        self._cm_undo = cm_undo
        self._job_name = ''
        self._created_from = None
        self._created_to = None
        self._user_id = None
        self._data_source = ImportSearchView.CmImportDataSource(cm_import)

    @uibind.divider(order=5)
    def initial_div(self):
        pass

    @uibind.textinput('Created from (dd/mm/yyyy): ', order=10, style=_textinput_style, action_on_enter=True)
    def created_from(self):
        return self._created_from

    @created_from.uibind.listener
    def on_created_from(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Search')
        else:
            self._created_from = value

    @uibind.text(style=_error_text_style, order=11)
    def created_from_error_text(self):
        return ''

    @uibind.divider(order=12)
    def from_div(self):
        pass

    @uibind.textinput('Created to (dd/mm/yyyy): ', order=20, style=_textinput_style, action_on_enter=True)
    def created_to(self):
        return self._created_to

    @created_to.uibind.listener
    def on_created_to(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Search')
        else:
            self._created_to = value

    @uibind.text(valign='top', style=_error_text_style, order=21)
    def created_to_error_text(self):
        return ''

    @uibind.divider(order=22)
    def to_div(self):
        pass

    @uibind.textinput('Job name: ', order=30, style=_textinput_style, action_on_enter=True)
    def job_name(self):
        return self._job_name

    @job_name.uibind.listener
    def on_job_name(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Search')
        else:
            self._job_name = value

    @uibind.divider(order=31, top=1)
    def job_div(self):
        pass

    @uibind.textinput('User id: ', order=40, style=_textinput_style, action_on_enter=True, disable_on_none=True)
    def user_id(self):
        if not get_config().enable_job_filtering_by_userid:
            return None

        return self._user_id

    @user_id.uibind.listener
    def on_user_id(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Search')
        self._user_id = value

    @uibind.divider(order=40, top=1)
    def user_div(self):
        if not get_config().enable_job_filtering_by_userid:
            return ''
        return ' '

    @uibind.buttons(labels=['Search'], align='center', order=50, style=_button_style)
    def actions(self, obj, value):
        if value == 'Search':
            created_from = None
            created_to = None
            error_text = self.get_element_of(self.created_from_error_text)
            error_text.set_text('')
            if self._created_from:
                try:
                    created_from = datetime.strptime(self._created_from, self._size_to_format.get(len(self._created_from), self._INPUT_TIME_FORMAT_FULL))
                except ValueError:
                    error_text.set_text('Invalid date/time format')
                    return
                else:
                    error_text.set_text('')
            else:
                error_text.set_text('Please provide an start date')
                return

            error_text = self.get_element_of(self.created_to_error_text)
            error_text.set_text('')
            if self._created_to:
                try:
                    created_to = datetime.strptime(self._created_to, self._size_to_format.get(len(self._created_to), self._INPUT_TIME_FORMAT_FULL))
                    if len(self._created_to) <= 10:
                        created_to = created_to.replace(hour=23, minute=59, second=59)
                    else:
                        created_to = created_to.replace(second=59)
                except ValueError:
                    error_text.set_text('Invalid date/time format')
                    return
            else:
                created_to = datetime.now()

            if created_to < created_from:
                error_text.set_text('End date cannot be before start date.')
                return

            max_delta = timedelta(days=get_config().max_days_interval_in_search + 1)
            if (created_to - created_from) >= max_delta:
                error_text.set_text('Maximum interval allowed is %d days' % get_config().max_days_interval_in_search)
                return

            logger.debug('Searching for: %s, %s, %s, %s', created_from, created_to, self._job_name, self._user_id)
            self._data_source.created_from = created_from
            self._data_source.created_to = created_to
            self._data_source.job_name = self._job_name
            self._data_source.user_id = self._user_id
            list = self.get_element_of(self.import_list)
            list.refresh()

            self.get_element_of(self.total_text).set_text('Found %d import job(s)' % self._data_source.size())

    @uibind.divider(order=60, top=1)
    def result_div(self):
        pass

    @uibind.text(align='center', order=61, style=_heading_style)
    def result_title(self):
        return 'Search results'

    def import_list_item_action_listener(self, obj, value):
        import_job = self.get_value_of(self.import_list)
        if value == 'Details' and import_job:
            view = ImportJobDetailsView(import_job, self._cm_import, self._cm_undo)
            self.get_display().show_view(view)
        elif value == 'Execute' and import_job:
            view = ImportJobExecuteView(import_job)
            self.get_display().show_view(view)

    @uibind.listbox(ImportListItemBuilder(action_listener=import_list_item_action_listener), size=None, order=63, buffer_size=2000)
    def import_list(self):
        return self._data_source

    @uibind.text(align='left', order=64, style=_text_style)
    def total_text(self):
        return ''

    @uibind.buttons(labels=['[B]ack', _EXIT_BUTTON], align='right',  style=_button_style, order=70)
    def back_option(self, obj, value):
        if value == 'Exit':
            raise u.ExitMainLoop
        self.get_display().back()


class DirectorySelectionView(FileSelectionView):
    """
    Extension to the FileSelectionView that only allows directories to be selected
    """
    @uibind.filebrowser(order=40, style=_list_style, item_style=_list_item_style, item_order_by=uibind.file_sort_by_name_asc, show_files=False)
    def file_list(self):
        return self._start_path


class SaveAsView(uibind.PopUpView):
    """
    View so select a destination folder and file name to save a import-file
    """
    def __init__(self, undo_job, file_name='', ):
        super(SaveAsView, self).__init__('Save as', style=_view_style)
        self._file_name = file_name
        self._undo_job = undo_job
        self._directory = get_config().import_file_path if get_config() and get_config().import_file_path else '/'

    @uibind.text(order=20, style=_text_style)
    def target_directory(self):
        return 'Directory : %s' % self._directory

    @uibind.buttons(align='left', order=30, style=_button_style)
    def select_directory_button(self):
        return ['select [D]irectory']

    @select_directory_button.uibind.listener
    def select_directory(self, obj, value):
        self.select_directory_popup.popup.show()

    @uibind.divider(order=35, top=1)
    def div_file_name(self):
        pass

    @uibind.textinput('file name: ', order=40, style=_textinput_style, size=None)
    def file_name_input(self):
        return self._file_name

    @file_name_input.uibind.listener
    def on_file_name_input(self, obj, value):
        if value == 'enter':
            self.action_option(None, 'Save')
        else:
            self._file_name = value

    @uibind.popup()
    def select_directory_popup(self):
        start_path = get_config().import_file_path if get_config() and get_config().import_file_path else '/'
        return DirectorySelectionView(start_path=start_path, select_dir=True, select_file=False)

    @select_directory_popup.uibind.listener
    def on_directory_popup_close(self, obj, value):
        if value:
            self._directory = value
            self.get_element_of(self.target_directory).set_text('Directory : %s' % self._directory)

    @uibind.divider(char=u'_', top=1, bottom=1, order=60)
    def div_bottom(self):
        pass

    @uibind.buttons(labels=['[S]ave', '[C]ancel'], align='right',  style=_button_style, order=201)
    def action_option(self, obj, value):
        if value == 'Save':
            self._validate_file()

            with open(path.join(self._directory, self._file_name), 'wb') as f_handler:
                self._undo_job.save_file(f_handler)

            self.success_message_popup.popup.show()

        else:
            self.get_display().back()

    def after_build(self):
        self.register_shortcut('enter', 'keypress', self.get_element_of(self.action_option)[0], (None, 'enter'))

    @uibind.propagate_exception
    def _validate_file(self):
        if not self._directory:
            raise ValueError('Please select the destinaiton directory')
        if not self._file_name:
            raise ValueError('Please input a file name')

    @uibind.popup()
    def success_message_popup(self):
        return MessagePopup('File was saved successfully')

    @success_message_popup.uibind.listener
    def on_popup_close(self, obj, value):
        self.get_display().back()


class UndoListItemBuilder(uibind.WidgetBuilder):

    def __init__(self, action_listener=None, **kwargs):
        super(UndoListItemBuilder, self).__init__(**kwargs)
        self.action_listener = action_listener

    def do_build(self, instance, binder):
        undo_job = binder.source
        icon = u.SelectableIcon(u'-')
        id_text = u.AttrMap(u.Text(str(undo_job.id()), align='right'), *_heading_style)
        status_text = u.Text('status: %s' % undo_job.status())
        import_id_text = u.Text('source import job: %s' % undo_job.job_id())
        first_row_items = [('pack', icon), (10, id_text), status_text, import_id_text]
        if undo_job.status_reason() and not undo_job.status_reason() == undo_job.status():
            first_row_items.append(u.Text('reason: %s' % undo_job.status_reason()))
        first_row = u.Columns(first_row_items, dividechars=1)

        total_op_text = u.Text('original operations: %s' % undo_job.total_operations())
        undo_op_text = u.Text('undo operations: %s' % undo_job.undo_operations())
        user_text = u.Text('user: %s' % undo_job.user_id())
        second_row = u.Columns((total_op_text, undo_op_text, user_text), dividechars=1)

        created_date_text = u.Text('created at: %s' % undo_job.creation_time())
        started_date_text = u.Text('stared at: %s' % undo_job.start_time())
        ended_date_text = u.Text('ended at: %s' % undo_job.end_time())
        third_row = u.Columns((created_date_text, started_date_text, ended_date_text))

        data_column = u.Padding(u.Pile((first_row, second_row, third_row)), left=1, right=1)

        import_button = None
        save_button = None
        if undo_job.is_successful() and undo_job.file_uri():
            import_button = u.AttrMap(u.Button('Import undo file'), *_button_style)
            save_button = u.AttrMap(u.Button('Save file as'), *_button_style)
            actions_bar = u.Pile((import_button, save_button))
        else:
            actions_bar = u.Text(' ')

        item_div = u.Divider(div_char=u' ')
        top = u.AttrMap(u.Pile((u.Columns((data_column, (20, actions_bar))), item_div)), *_list_item_style)
        top.get_value = lambda: undo_job

        if callable(self.action_listener):
            if import_button:
                connect_args = (import_button.base_widget, "click", self.action_listener, import_button.base_widget.label, None, [instance])
                u.connect_signal(*connect_args)
                self.add_connected_signal(instance, connect_args)

            if save_button:
                connect_args = (save_button.base_widget, "click", self.action_listener, save_button.base_widget.label, None, [instance])
                u.connect_signal(*connect_args)
                self.add_connected_signal(instance, connect_args)

        return top


class BrowseUndosView(uibind.View):

    def __init__(self, cm_import, cm_undo, import_job=None):
        title = 'Undo jobs list'
        if import_job:
            title += ' for import %s' % import_job.id()
        super(BrowseUndosView, self).__init__(title, style=_view_style)
        self._import_job = import_job
        self._cm_import = cm_import
        self._cm_undo = cm_undo
        self._first_shown = True
        self._refresh_work = None
        self._job_list = []
        self._undo_job = None
        self._new_undo_id = ''

    def before_build(self):
        self.reload_jobs()

    def after_show(self):
        if not self._first_shown:
            self.get_display().rebuild_ui()

        self._first_shown = False

    def undo_list_item_action_listener(self, obj, value):
        self._undo_job = self.get_value_of(self.undo_list)
        if value == 'Import undo file' and self._undo_job:
            self._import_undo_job(self._undo_job)
        elif value == 'Save file as' and self._undo_job:
            self.save_as_popup.popup.show()

    @uibind.text(align='center', style=_text_style, order=5)
    def description(self):
        return """List of jobs which generate a configuration file (Bulk CM import file) 
        containing the reverse of the operations from the 'source import job' """

    @uibind.divider(order=6)
    def description_div(self):
        pass

    @uibind.listbox(UndoListItemBuilder(action_listener=undo_list_item_action_listener), size=None, order=15)
    def undo_list(self):
        return uibind.NavigableDataSource(self._job_list)

    @uibind.popup()
    def save_as_popup(self):
        if self._undo_job:
            return SaveAsView(self._undo_job, file_name='undo_for_import_%s-%s' % (self._undo_job.job_id(), datetime.now().strftime('%Y-%m-%d_%H%M%S.txt')))

    @uibind.divider(char=u'_', bottom=1, order=20)
    def div_bottom(self):
        pass

    @uibind.buttons(align='right',  style=_button_style, order=30)
    def action_options(self):
        actions = ['[B]ack', _EXIT_BUTTON]
        if self._import_job:
            actions.insert(0, '[N]ew undo job')
        return actions

    @action_options.uibind.listener
    def on_action_options(self, obj, value):
        if value == 'Exit':
            raise u.ExitMainLoop
        if value == 'New undo job':
            self._new_undo_id = self._cm_undo.undo_import_job(self._import_job.id())
            self.new_undo_success_message_popup.popup.show()
        else:
            self.get_display().back()

    @uibind.popup()
    def new_undo_success_message_popup(self):
        return MessagePopup('New undo job %s stared successfully' % self._new_undo_id)

    @new_undo_success_message_popup.uibind.listener
    def on_popup_close(self, obj, value):
        self.reload_jobs()

    def reload_jobs(self):
        del self._job_list[:]
        if self._import_job:
            self._job_list += self._cm_undo.get_jobs(for_import_job=str(self._import_job.id()))
        else:
            self._job_list += self._cm_undo.get_jobs()

    def refresh(self):
        import_list = self.get_element_of(self.undo_list)
        if import_list:
            logger.debug('Refreshing undo job list...')
            import_list.refresh()

    def update_interval(self):
        logger.debug('Undo job list got update interval request...')
        if not get_config().auto_refresh_enabled:
            return

        if self._refresh_work:
            work = self.get_display().get_work(self._refresh_work)
            if work and work.is_ended():
                self.refresh()
            if work is None or work.is_ended():
                self._refresh_work = None
        else:
            logger.debug('... generating refresh work')
            self._refresh_work = self.get_display().request_work(self.reload_jobs)

    def _import_undo_job(self, undo_job):
        f_handler, f_name = tempfile.mkstemp(prefix='undo_for_import_job_%s_' % undo_job.job_id(), suffix='.xml')
        logger.debug('created temporary file [%s] to hold import data', f_name)
        try:
            with os.fdopen(f_handler, 'wb') as import_file:
                undo_job.save_file(import_file)

            self.get_display().show_view(NewImportJobView(self._cm_import, import_file=f_name, allow_file_selection=False, delete_file_on_exit=True))
        except IOError as e:
            logger.exception('Error saving file from undo job %s:%s', undo_job.id(), e)
            if path.exists(f_name):
                try:
                    os.remove(f_name)
                except:
                    logger.exception('Could not remove temporary file %s', f_name)


class MessagePopup(uibind.PopUpView):

    def __init__(self, message):
        super(MessagePopup, self).__init__(style=_view_style)
        self._message = message

    @uibind.text(align='center', valign='middle', size=None, order=0, style=_text_style)
    def message_text(self):
        return self._message

    @uibind.buttons(labels='[O]k', align='center', order=10, style=_button_style)
    def ok(self, obj, value):
        self.close()


class ConnectionErrorPopup(uibind.PopUpView):

    def __init__(self, message):
        super(ConnectionErrorPopup, self).__init__(style=_view_style)
        self._message = message

    @uibind.text(align='center', valign='middle', size=None, order=0, style=_text_style)
    def message_text(self):
        return self._message

    @uibind.buttons(labels=('[O]k', _EXIT_BUTTON), align='center', order=10, style=_button_style)
    def ok(self, obj, value):
        if value == 'Ok':
            self.close()
        else:
            raise u.ExitMainLoop


class GetJobIdPopup(uibind.PopUpView):

    def __init__(self):
        super(GetJobIdPopup, self).__init__('Open Job', style=_view_style, height=10)
        self._job_id = ''

    @uibind.textinput('Job id: ', order=5, style=_textinput_style, action_on_enter=True)
    def job_id(self):
        pass

    @uibind.text(order=10, style=_error_text_style, size=None)
    def job_id_error(self):
        return ''

    @job_id.uibind.listener
    def on_job_id(self, obj, value):
        if value == 'enter':
            self.actions(None, 'Ok')
        else:
            self._job_id = value

    @uibind.buttons(labels=['[O]k', '[C]ancel'], align='center', order=20, style=_button_style)
    def actions(self, obj, value):
        if value == 'Ok':
            if self._job_id:
                if self._job_id.isdigit():
                    self.set_value(self._job_id)
                else:
                    self.get_element_of(self.job_id_error).set_text('Invalid job id format. It must be a number.')
                    return

        self.close()


class MainMenuView(uibind.View):

    def __init__(self, cm_import, cm_undo, file_cleaner):
        super(MainMenuView, self).__init__('Main menu', height=30, width=60, valign='middle', style=_view_style)
        self._cm_undo = cm_undo
        self._cm_import = cm_import
        self._file_cleaner = file_cleaner

    @uibind.text(align='center', style=_text_style, order=0)
    def description(self):
        return u'CM Import utility'

    @uibind.divider(top=1, bottom=2, order=5)
    def div_one(self):
        return '-'

    @uibind.text(style=_text_style, order=10)
    def select_text(self):
        return u'Please select one of the following options: '

    @uibind.divider(top=3, order=15)
    def div_two(self):
        pass

    @uibind.buttons(labels='   View [I]mports  ', align='center', style=_button_style, order=20)
    def browse_import_option(self, obj, value):
        self.get_display().show_view(BrowseImportView(cm_import=self._cm_import, cm_undo=self._cm_undo))

    @uibind.divider(order=21)
    def div_open_job(self):
        pass

    @uibind.popup()
    def get_job_id_popup(self):
        return GetJobIdPopup()

    @get_job_id_popup.uibind.listener
    def get_job_id_popup_listener(self, obj, value):
        if value:
            job = self._cm_import.get_job(value)
            self.get_display().show_view(ImportJobDetailsView(job, self._cm_import, self._cm_undo))

    @uibind.buttons(labels='     View [J]ob    ', align='center', style=_button_style, order=22)
    def open_job(self, obj, value):
        self.get_job_id_popup.popup.show()

    @uibind.divider(order=23)
    def div_three(self):
        pass

    @uibind.buttons(labels='  [S]earch Import  ', align='center', style=_button_style, order=30)
    def search_job(self, obj, value):
        self.get_display().show_view(ImportSearchView(self._cm_import, self._cm_undo))

    @uibind.divider(order=31)
    def div_search(self):
        pass

    @uibind.buttons(labels='Create [N]ew Import', align='center',  style=_button_style, order=40)
    def new_import_option(self, obj, value):
        self.get_display().show_view(NewImportJobView(self._cm_import, file_cleaner=self._file_cleaner))

    @uibind.divider(order=41)
    def div_four(self):
        pass

    @uibind.buttons(align='center',  style=_button_style, order=50)
    def browse_undos_option(self):
        if get_config().enable_job_undo:
            return '   View [U]ndos    '

        return None

    @browse_undos_option.uibind.listener
    def browse_undos_action(self, obj, value):
        self.get_display().show_view(BrowseUndosView(self._cm_import, self._cm_undo))

    @uibind.divider(top=2, bottom=2, order=51)
    def div_five(self):
        pass

    @uibind.buttons(labels='       %s      ' % _EXIT_BUTTON, align='center',  style=_button_style, order=60, size=None)
    def exit_option(self, obj, value):
        raise u.ExitMainLoop()


def error_handler(exception, view):
    if view and view.get_display():
        if isinstance(exception, u.ExitMainLoop):
            raise exception
        elif isinstance(exception, NbiConnectionException):
            view.show_popup(ConnectionErrorPopup(get_error_message(exception)))
        else:
            view.show_popup(MessagePopup(get_error_message(exception)))
    else:
        raise exception


def get_error_message(exception):
    msg = ''
    if isinstance(exception, NbiRequestException):
        if exception.json and 'errors' in exception.json:
            for error in exception.json.get('errors'):
                if msg:
                    msg += '\n\n'
                msg += '%s\nError code: %s' % (error.get('message'), error.get('code', 'none'))
        elif exception.json and exception.json.get('userMessage'):
            msg = '%s\nError code: %s' % (exception.json.get('userMessage'), exception.json.get('internalErrorCode', 'none'))
        elif exception.response_text:
            msg = exception.response_text
        else:
            msg = str(exception)
        msg += '\n[http code: %s]' % str(exception.status_code)
    else:
        msg = str(exception)

    logger.exception(msg + '\n%s', exception)
    return msg
