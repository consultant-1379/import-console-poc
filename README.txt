

Cm Import Utility

To be installed on the Amos vm's

Required User Roles:

	Amos_Operator
	CM_REST_Administrator
	Cmedit_Operator
	Scripting Operator

Required User Capabilities (for custom roles):

	AMOS	                    amos_em	                    read	Allows execution of the MO READ (get) commands.
	CM NBI	                    cm_config_rest_nbi	        read	Read network configuration data through REST NBI services.
	CM NBI	                    cm_config_rest_nbi	        create	Create network configuration data through REST NBI services.
	CM NBI	                    cm_config_rest_nbi          execute	Perform activate operation on network configuration data through REST NBI services.
	CM NBI	                    cm_bulk_rest_nbi	        read	Get information about bulk import export job through REST NBI services.
	CM NBI	                    cm_bulk_rest_nbi	        create	Execute bulk import export operation through REST NBI services.
	CM NBI	                    cm_bulk_rest_nbi	        delete	Delete bulk import export data through REST NBI services.
	CM-CLI	                    cm_editor	                read    Read Network Configuration Data.
	Scripting CLI scripting	    scripting_cli_scripting	    execute	Allows execution of Python scripts on scripting cluster.


Script help:

	importconsole.sh --help


	 $$$$$$\  $$\      $$\       $$$$$$\                                              $$\
	$$  __$$\ $$$\    $$$ |      \_$$  _|                                             $$ |
	$$ /  \__|$$$$\  $$$$ |        $$ |  $$$$$$\$$$$\   $$$$$$\   $$$$$$\   $$$$$$\ $$$$$$\
	$$ |      $$\$$\$$ $$ |$$$$$$\ $$ |  $$  _$$  _$$\ $$  __$$\ $$  __$$\ $$  __$$\_$$  _|
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



	usage: importconsole [-sp SEARCH_PATH] [-u USERNAME] [-p PASSWORD] [--url URL]
	                     [--work-dir WORK_DIR] [--file-cleanup-only]
	                     [--file-cleanup-interval FILE_CLEANUP_INTERVAL]
	                     [--file-retention-days FILE_RETENTION_DAYS] [-h]

	ENM CM Import utility

	Optional arguments:
	  -sp SEARCH_PATH, --search-path SEARCH_PATH
	                        Initial directory to search for import files
	  -u USERNAME, --username USERNAME
	                        User name to authenticate against ENM
	  -p PASSWORD, --password PASSWORD
	                        Password to authenticate against ENM
	  --url URL             ENM's domain url
	  --work-dir WORK_DIR   Work directory
	  --file-cleanup-only   Indicates to just run the file cleanup procedure
	  --file-cleanup-interval FILE_CLEANUP_INTERVAL
	                        Interval in seconds to perform file clean-up
	  --file-retention-days FILE_RETENTION_DAYS
	                        Retention days of import files for failed jobs
	  -h, --help            show this help message and exit


To run script:

	execute:

		importcomsole.sh	 	If you are a user logged onto ENM with valid roles and are running the script from the Amos Shell
								launched from the launcher, the script's main menu will be shown.

Views:

	NOTE:	hot keys denoted with []

	1.	Main Menu

		View [I]mports				-	view all import jobs on the system
		View [J]ob					-	view one particular import job (by jobId)
		[S]earch import 			-	search for import jobs by date or name
		Create [N]ew import 		-	create a new import job
		View [U]ndos				- 	view the undo jobs list.

		[E]xit						-	exit the script


	2.	View [I]mports

		Shows a list of all the import jobs in reverse chronological order.

		Each job will have the following details:
			jobId				-	the job Id
			jobName				-	the job Name
			created at:			-	date the job was initially created
			last executed at:	-	time job last executed (blank if not executed)
			status				-	the job status, one of [PARSING, PARSED, VALIDATING, VALIDATED, EXECUTING, EXECUTED]
			<Details> tag		- 	to view the job details
			<Execute> tag		- 	visible if the job status is VALIDATED only
			Job 'Message'  		-	message about the current state of the job, e.g.:
										-	'** Job Completed **'
										-	'There are invalid operations. View Job operations for more information.' if there are errors in the job
										-	Progress indicators for Validation and Execution if the job is not complete

		Navigation Options:
			[B]ack				-	return to previous view
			[E]xit				-	exit script


		2.1	Import Job Details 		-	sub view of View Imports

			Shows the details of a particular import job.

			There are 3 sections for each job:
			2.1.1	General Job Info:
					Job Name:
					Status:
					Created at:
					Last Executed at:
					Validation Policy:
					Execution Policy:

				Optional:	Error message if there are errors in the job

			2.1.2	Execution Summary

				A summary of the Import job operations.
				Can include:

				parsed, valid, invalid, executed and errors for each import operation type [create, update, action and delete] and a total of each.

			2.1.3	Operations list

				A numbered list of all the import operations in the import job.

				Each operation will have:
					Status
					Operation Type
					FDN
					A list of attribute names and attribute values for the operation
					(Optional) the current Value of the attribute on the ENM system

			Navigation Options:
				e[X]execute 		-	execute the job (if possible)
				add [F]ile 			-  	add file (if not already added)
				[U]ndo 				-	opens the Undo jobs list view for a particular import job (see below for details)
				current [V]alues 	-	show current Values for the operation attributes on the current page.
										(when scrolling through operations list, a new invocation will be required)
				[B]ack				-	return to previous view
				[E]xit				-	exit script


		2.2		Undo jobs list view (for a particular import job) 	-	sub View of Import Job Details

				Shows a list of undo jobs for a particular import job

				For each undo job details there are the following options:
					1.	Import undo file 	-	imports this particular undo file (creating a new import job)
					2.	Save file as 		-	opens a dialog box to allow the user to save this particular undo file
												Fields/Options:
													Directory:			directory to store the undo file in (default is configured root directory)
													select [D]irectory:	opens select directory view to allow user to select a different directory
													file name:			shows the particular undo default file filename, this can be changed
													[S]ave: 			save the undo file to the chosen directory
													[C]ancel:			exit window

				Navigation Options:
					[N]ew Undo Job 		-	creates a new undo job for this import job
					[B]ack				-	return to previous view
					[E]xit				-	exit script


	3.	View Job

		Shows a dialog box to enter a jobId.

		Shows that job's Import Job Details view.

		Navigation Options:
			[O]k 		 		-	show the job details
			[C]ancel  			-  	back to Main Menu

	4.	Search Import Job

		Shows a view to filter jobs by date and by job name.
		There is a max. number of days that can be viewed at any given time as a limit is required for performance reasons.
		This value is configurable with a default value of 20 days.


		Fields available:
			Created from (dd/mm/yyyy)	-	the start date to view jobs from
			Created to (dd/mm/yyyy)		-	the end date to view jobs to
			Job name 					-	the name of the job to view

		Behaviour:
		UC1		Enter a value only for 'Created from'
				Will show all jobs from that date to the present date if the date is within the max range
				Number of Import Jobs found indicated at bottom left of the view
				Error message if the date is invalid

		UC2		Enter a value for 'Created from' and 'Created to'
				Will show all jobs between the supplied dates if the interval is less than the maximum range
				Number of Import Jobs found indicated at bottom left of the view
				Error message if the dates are invalid or the maximum number of days is exceeded

		UC3		Filter by job name
				Shows job(s) who's job name contains a particular string, e.g. 'delete' will show all jobs containing 'delete' in any position in the name
				Must provide a start date for the search
				Number of Import Jobs found indicated at bottom left of the view


		Navigation Options:
			Search 		 		-	execute the search and view the results
			[B]ack				-	return to previous view
			[E]xit				-	exit script

	5.	Create New Import

		Shows a view to create a new Import Job.
		Flow to create a new import job:
			1.	Supply a job name (optional - default name will be given if not supplied)
			2.	Select an import file to use.
			3.	Select a file policy (optional)
			4.	Select Execution Options:
					Select validation policy
					Select execution policy
					Select Execution flow
			5.	Execute create import job

		Fields/options available:

		Job Name:		enter a name for the new job (optional)
		select file:	opens the file selection view (see below for description)
		File Policy:	Keep file 					-	select to keep the import file after job creation
						Remove file on job success	-	import file will be deleted after job is successfully executed
		Execution Options:
			Validation Policy:	perform MO instance validation
								skip MO instance validation
			Execution policy:	continue next node			-	on error when executing, will skip to the next node and continue execution
								stop						-	on error when executing, will stop the import job
								continue next operation 	-	on error when executing, will continue to the next operation (even on the same node)
			Execution Flow:		options depend on the current status of the import job.

		Navigation Options:
			e[X]ecute 	 		-	create the new import job
			[B]ack				-	return to previous view
			[E]xit				-	exit script


		5.1		File Selection View

				View to select the import file for new job creation

				Fields/options available:

				Root Directory:		directory to select import file from (default is configurable)
				Filter Files:		filename filters for the files view
				Order by:			Name 	-	show files in the root directory in alphabetical order
									Date	-	show files in the root directory in chronological order

				Navigation Options:
					[O]k 		 		-	show the job details
					[C]ancel  			-  	back to Main Menu



	6.	View [U]ndos

		View all the undo jobs for every import job.

		For each undo job details there are the following options:
					1.	Import undo file 	-	imports this particular undo file (creating a new import job)
					2.	Save file as 		-	opens a dialog box to allow the user to save this particular undo file
												Fields/Options:
													Directory:			directory to store the undo file in (default is configured root directory)
													select [D]irectory:	opens select directory view to allow user to select a different directory
													file name:			shows the particular undo default file filename, this can be changed
													[S]ave: 			save the undo file to the chosen directory
													[C]ancel:			exit window

		Navigation Options:
			[B]ack				-	return to previous view
			[E]xit				-	exit script



Configurable options for importconsole.conf:

default-file-filter 			-	default filters for the select file view

search-path						-	default folder for select file view		(default is the user's home directory)

max-days-interval-in-search		-	maximum number of days allowed when using search by filter view (default is 20)

work-dir						-	folder to store the file clean-up configuration	(default is current folder)

file-cleanup-interval			-	interval (secs) to perform the file clean-up	(default is 1 hour)

file-retention-days				-	time-to-die (days) for files from failed import jobs 	(default is 30 days)

enable-job-undo					-	enable the undo feature (true by default)


Sample usage:

default-file-filter=*.txt;*.xml
search-path=/var/tmp/dibbler
max-days-interval-in-search=20
work-dir=/home/shared/common/importconsole
file-cleanup-interval=3600
file-retention-days=30
enable-job-undo=true





