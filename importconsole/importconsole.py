#!/usr/bin/env python
####################################################################
# COPYRIGHT Ericsson AB 2017
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
####################################################################
import signal
import sys
import getpass
import argparse
import ConfigParser
import time
import logging
import os
try:
    import enmscripting as enm
except ImportError:
    print '.'
    import enmscriptingembedded as enm

from lib.config import *
from lib import nbisession, MissingCredentialsException
from lib.filecleanup import FileCleaner, _30_DAYS, _1_HOUR_IN_SECONDS

signal.signal(signal.SIGINT, lambda x, y: sys.exit(1))

logger = None


def setup_logging(log, log_file_name='importconsole.log'):
    logger = logging.getLogger()
    if log:
        handler = logging.FileHandler(log_file_name, mode='w')
        if log == 'debug':
            handler.setFormatter(logging.Formatter(
                fmt='%(asctime)s; %(threadName)-10s; %(levelname)-8s; %(message)s; %(pathname)s; %(lineno)s'))
            handler.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        else:
            handler.setFormatter(logging.Formatter(fmt='%(asctime)s; %(threadName)-10s; %(levelname)-8s; %(message)s'))
            handler.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
    else:
        logging.disable(logging.CRITICAL)
    return logger


def read_args():
    parser = argparse.ArgumentParser(prog='importconsole', add_help=False, description="CM Import utility")
    optional_args = parser.add_argument_group('Optional arguments')
    optional_args.add_argument('-sp', '--search-path', help='Initial directory to search for import files', default=None)
    optional_args.add_argument('-u', '--username', help='User name to authenticate against ENM',
                               default=None)
    optional_args.add_argument('-p', '--password', help='Password to authenticate against ENM',
                               default=None)
    optional_args.add_argument('--url', help="ENM's domain url", default=None)
    optional_args.add_argument('--work-dir', help="Work directory", default=None)
    optional_args.add_argument('--file-cleanup-only', help="Indicates to just run the file cleanup procedure", action='store_true')
    optional_args.add_argument('--file-cleanup-interval', help="Interval in seconds to perform file clean-up", default='0')
    optional_args.add_argument('--file-retention-days', help="Retention days of import files for failed jobs", default='0')
    optional_args.add_argument("-h", "--help", action="help", help="show this help message and exit")

    # advanced options
    parser.add_argument('--log', help=argparse.SUPPRESS, choices=['info', 'debug'], default=None)
    parser.add_argument('--nbi-base-uri', help=argparse.SUPPRESS, default='bulk-configuration/v1/import-jobs/')
    parser.add_argument('--lic', help=argparse.SUPPRESS, default=False)
    parser.add_argument('--refresh-interval', help=argparse.SUPPRESS, default=0)

    return parser.parse_args()


def read_config_file():
    cfg_parser = ConfigParser.SafeConfigParser()
    cfg_parser.read(('importconsole.conf', os.path.join(get_user_home(), 'importconsole.conf'), '/opt/ericsson/importconsole/importconsole.conf'))
    return cfg_parser.defaults()


def get_user_home():
    username = os.environ.get('LOGNAME') or os.environ.get('SUDO_USER') or os.environ.get('USER')
    return os.path.expanduser("~"+username+"/")


_banner = """
 $$$$$$\  $$\      $$\       $$$$$$\                                              $$\     
$$  __$$\ $$$\    $$$ |      \_$$  _|                                             $$ |    
$$ /  \__|$$$$\  $$$$ |        $$ |  $$$$$$\$$$$\   $$$$$$\   $$$$$$\   $$$$$$\ $$$$$$\   
$$ |      $$\$$\$$ $$ |$$$$$$\ $$ |  $$  _$$  _$$\ $$  __$$\ $$  __$$\ $$  __$$\\_$$  _|  
$$ |      $$ \$$$  $$ |\______|$$ |  $$ / $$ / $$ |$$ /  $$ |$$ /  $$ |$$ |  \__| $$ |    
$$ |  $$\ $$ |\$  /$$ |        $$ |  $$ | $$ | $$ |$$ |  $$ |$$ |  $$ |$$ |       $$ |$$\ 
\$$$$$$  |$$ | \_/ $$ |      $$$$$$\ $$ | $$ | $$ |$$$$$$$  |\$$$$$$  |$$ |       \$$$$  |
 \______/ \__|     \__|      \______|\__| \__| \__|$$  ____/  \______/ \__|        \____/ 
                                                   $$ |                                   
                                                   $$ |                                   
                                                   \__|                                   
 $$$$$$\                                          $$\                                     
$$  __$$\                                         $$ |                                    
$$ /  \__| $$$$$$\  $$$$$$$\   $$$$$$$\  $$$$$$\  $$ | $$$$$$\                            
$$ |      $$  __$$\ $$  __$$\ $$  _____|$$  __$$\ $$ |$$  __$$\                           
$$ |      $$ /  $$ |$$ |  $$ |\$$$$$$\  $$ /  $$ |$$ |$$$$$$$$ |                          
$$ |  $$\ $$ |  $$ |$$ |  $$ | \____$$\ $$ |  $$ |$$ |$$   ____|                          
\$$$$$$  |\$$$$$$  |$$ |  $$ |$$$$$$$  |\$$$$$$  |$$ |\$$$$$$$\                           
 \______/  \______/ \__|  \__|\_______/  \______/ \__| \_______|                          

                                                                                          
"""

_TRUE_VALUES = ['yes', 'true', 'y', 't', '1']


def main():

    print _banner

    args = read_args()
    config_file = read_config_file()

    global logger
    logger = setup_logging(args.log or config_file.get('log'))

    config = Config()
    config.import_file_path = args.search_path or config_file.get('search-path') or get_user_home()
    config.default_file_name_filter = config_file.get('default-file-filter', '')
    config.enable_job_filtering = config_file.get('enable-job-filtering', 'false').lower() in _TRUE_VALUES
    config.enable_job_filtering_by_date = config_file.get('enable-job-filtering-by-date', 'false').lower() in _TRUE_VALUES
    config.enable_job_filtering_by_userid = config_file.get('enable-job-filtering-by-userid', 'false').lower() in _TRUE_VALUES
    config.enable_job_undo = config_file.get('enable-job-undo', 'true').lower() in _TRUE_VALUES
    config.list_buffer_size = config_file.get('list-buffer-size', 100)
    config.validation_policies = config_file.get('validation-policies', '[{"perform MO instance validation":"", "SKIP MO instance validation":"no-instance-validation"}]')
    config.execution_policies = config_file.get('execution-policies', '[{"stop":"stop-on-error", "continue next operation":"continue-on-error-operation", "continue next node":"continue-on-error-node"}]')
    config.execution_flow = config_file.get('execution-flow', '[{"execute":"execute", "validate":"validate"}]')
    config.allowed_new_job_execution_flows = config_file.get('allowed-new-job-execution-flows', '["validate", "validate-and-execute"]')
    config.max_days_interval_in_search = int(config_file.get('max-days-interval-in-search', '20'))
    config.file_cleanup_interval = int(args.file_cleanup_interval) or int(config_file.get('file-cleanup-interval', '0')) or _1_HOUR_IN_SECONDS
    config.file_retention_days = int(args.file_retention_days) or int(config_file.get('file-retention-days', '0')) or _30_DAYS
    config.work_dir = args.work_dir or config_file.get('work-dir', None)

    set_config(config)

    from lib import uibind, CmImport, CmImportUndo

    if args.lic:
        uibind.disable_catch_view_exceptions()

    print 'Connecting to ENM...\n'
    session = _auth_open_session(args.url or config_file.get('url'), args.username, args.password, args.nbi_base_uri or config_file.get('nbi-base-uri'))

    cli_session = enm.open(session.host(), session.username(), session.password())

    cm_import = CmImport(session, cli_session.command())
    cm_undo = CmImportUndo(session)

    print 'Testing service...\n'
    cm_import.get_jobs(limit=1)

    print '   ... all looking good\n'

    time.sleep(1)

    if args.file_cleanup_only:
        _clean_files_and_exit(cm_import, config)

    if config.file_cleanup_interval > 0:
        file_cleaner = FileCleaner(config.work_dir, cm_import, config.file_cleanup_interval, config.file_retention_days)
    else:
        file_cleaner = None

    palette = [
        (None,  'light gray', 'dark gray', None, '#ff0', '#66d'),
        ('view',  'light gray', 'dark gray', None, '#000', 'g78'),
        ('heading', 'black', 'dark cyan', None, '#ff0', '#006'),
        ('subheading', 'dark cyan,underline', 'dark gray', None, '#06f,underline', 'g78'),
        ('focus subheading', 'dark cyan,underline', 'dark gray', None, '#6d6,underline', 'white'),
        ('text', 'light gray', 'dark gray', None, '#000', 'g78'),
        ('error text', 'dark red', 'dark gray', None, 'dark red', 'g78'),
        ('success area', 'white', 'dark green'),
        ('attention area', 'black', 'yellow', None, 'white', '#d60'),
        ('error area', 'white', 'dark red'),
        ('button', 'white', 'dark blue', None, '#000', 'g70'),
        ('list', 'light cyan', 'dark gray', None, '#000', 'g52'),
        ('textinput', 'white', 'dark gray', None, '#000', '#88d'),
        ('pg normal', 'white', 'black', 'standout', 'black', 'g85'),
        ('pg complete', 'white', 'dark magenta', None, 'black', '#8aa'),
        ('pg smooth', 'dark magenta', 'black', None, 'g85', '#8aa'),
        ('focus text', 'dark gray', 'white', None, '#006', 'white'),
        ('focus button', 'white', 'dark red', None, '#fff', '#600'),
        ('focus textinput', 'white', 'brown', None, '#ff0', '#66d')]

    try:
        refresh_interval = int(args.refresh_interval) or int(config_file.get('refresh-interval', '0')) or 18

        from lib.ui import error_handler, MainMenuView
        display = uibind.Display(palette=palette)
        display.exception_handler = error_handler
        display.set_update_interval(refresh_interval)
        display.start(MainMenuView(cm_import, cm_undo, file_cleaner))
    except Exception as e:
        logger.exception('Exiting application due to error %s', e)
        print 'Error: %s' % str(e)
    finally:
        if cli_session:
            enm.close(cli_session)


def _clean_files_and_exit(cm_import, config):
    file_cleaner = FileCleaner(config.work_dir, cm_import, -1)
    print 'Starting file clean up'
    file_cleaner.clean_files()
    print 'File clean up ended successfully'
    exit(0)


def _auth_open_session(enm_url, username, password, nbi_uri):
    if username:
        session = nbisession.NbiSession(nbi_uri, username=username, password=password, host=enm_url)
        session.open_session()
        return session
    else:
        try:
            session = nbisession.NbiSession(nbi_uri, username=username, password=password, host=enm_url)
            session.open_session()
        except MissingCredentialsException:
            while True:
                username = raw_input("username: ")
                password = getpass.getpass()

                session = nbisession.NbiSession(nbi_uri, username=username, password=password, host=enm_url)
                try:
                    session.open_session()
                    return session
                except (ValueError, MissingCredentialsException):
                    print 'Invalid username/password combination.'
        return session


if __name__ == "__main__":
    main()
