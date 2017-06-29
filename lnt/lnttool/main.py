"""Implement the command line 'lnt' tool."""
import logging
import os
import sys
import json
import contextlib
import code
import werkzeug.contrib.profiler
import click

import lnt
import lnt.util.ImportData
from lnt.testing.util.commands import note, warning, error, LOGGER_NAME
import lnt.testing.profile.profile as profile
from lnt.tests.nt import NTTest
from lnt.tests.compile import CompileTest
from lnt.tests.test_suite import TestSuiteTest

from .create import action_create
from .convert import action_convert
from .import_data import action_import
from .updatedb import action_updatedb
from .viewcomparison import action_view_comparison
from .import_report import action_importreport


@click.command("runserver", short_help="start a new development server")
@click.argument("instance_path", type=click.UNPROCESSED)
@click.option("--hostname", default="localhost", show_default=True,
              help="host interface to use")
@click.option("--port", default=8000, show_default=True,
              help="local port to use")
@click.option("--reloader", is_flag=True, help="use WSGI reload monitor")
@click.option("--debugger", is_flag=True, help="use WSGI debugger")
@click.option("--profiler", is_flag=True, help="use WSGI profiler")
@click.option("--profiler-file", help="file to dump profile info to")
@click.option("--profiler-dir",
              help="pstat.Stats files are saved to this directory ")
@click.option("--shell", is_flag=True, help="load in shell")
@click.option("--show-sql", is_flag=True, help="show all SQL queries")
@click.option("--threaded", is_flag=True, help="use a threaded server")
@click.option("--processes", default=1, show_default=True,
              help="number of processes to use")
def action_runserver(instance_path, hostname, port, reloader, debugger,
                     profiler, profiler_file, profiler_dir, shell, show_sql,
                     threaded, processes):
    """start a new development server

\b
Start the LNT server using a development WSGI server. Additional options can be
used to control the server host and port, as well as useful development
features such as automatic reloading.

The command has built-in support for running the server on an instance which
has been packed into a (compressed) tarball. The tarball will be automatically
unpacked into a temporary directory and removed on exit. This is useful for
passing database instances back and forth, when others only need to be able to
view the results.
    """

    # Setup the base LNT logger.
    # Root logger in debug.
    logger = logging.getLogger(LOGGER_NAME)
    if debugger:
        logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)

    # Enable full SQL logging, if requested.
    if show_sql:
        sa_logger = logging.getLogger("sqlalchemy")
        if debugger:
            sa_logger.setLevel(logging.DEBUG)
        sa_logger.setLevel(logging.INFO)
        sa_logger.addHandler(handler)

    import lnt.server.ui.app
    app = lnt.server.ui.app.App.create_standalone(instance_path,)
    if debugger:
        app.debug = True
    if profiler:
        if profiler_dir:
            if not os.path.isdir(profiler_dir):
                os.mkdir(profiler_dir)
        app.wsgi_app = werkzeug.contrib.profiler.ProfilerMiddleware(
            app.wsgi_app, stream=open(profiler_file, 'w'),
            profile_dir=profiler_dir)
    if shell:
        from flask import current_app
        from flask import g
        ctx = app.test_request_context()
        ctx.push()

        vars = globals().copy()
        vars.update(locals())
        shell = code.InteractiveConsole(vars)
        shell.interact()
    else:
        app.run(hostname, port,
                use_reloader=reloader,
                use_debugger=debugger,
                threaded=threaded,
                processes=processes)


@click.command("checkformat")
@click.argument("file", "input_file", nargs=-1, type=click.Path(exists=True))
@click.option("--testsuite", "-s", default='nts')
def action_checkformat(input_file, testsuite):
    """check the format of an LNT test report file"""

    import lnt.server.db.v4db
    import lnt.server.config
    db = lnt.server.db.v4db.V4DB('sqlite:///:memory:',
                                 lnt.server.config.Config.dummy_instance())
    result = lnt.util.ImportData.import_and_report(
        None, None, db, input_file, 'json', testsuite, commit=True)
    lnt.util.ImportData.print_report_result(result, sys.stdout, sys.stderr,
                                            verbose=True)


def _print_result_url(results, verbose):
    result_url = results.get('result_url')
    if result_url is not None:
        if verbose:
            print "Results available at:", result_url
        else:
            print result_url
    elif verbose:
        print "Results available at: no URL available"


@click.group("runtest", context_settings=dict(
    ignore_unknown_options=True, allow_extra_args=True,))
def action_runtest():
    """run a builtin test application"""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)


action_runtest.add_command(NTTest.cli_wrapper)
action_runtest.add_command(CompileTest.cli_wrapper)
action_runtest.add_command(TestSuiteTest.cli_wrapper)


@click.command("showtests")
def action_showtests():
    """show the available built-in tests"""

    import lnt.tests

    print 'Available tests:'
    test_names = lnt.tests.get_test_names()
    max_name = max(map(len, test_names))
    for name in test_names:
        print '  %-*s - %s' % (max_name, name,
                               lnt.tests.get_test_description(name))


@click.command("submit")
@click.argument("url")
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--commit", show_default=True, type=int,
              help="number of days to show in report")
@click.option("--verbose", "-v", is_flag=True, help="show verbose test results")
def action_submit(url, files, commit, verbose):
    """submit a test report to the server"""

    if not commit:
        warning("submit called with --commit=0, your results will not be saved"
                " at the server.")

    from lnt.util import ServerUtil
    files = ServerUtil.submitFiles(url, files, commit, verbose)
    for submitted_file in files:
        if verbose:
            lnt.util.ImportData.print_report_result(
                submitted_file, sys.stdout, sys.stderr, True)
        _print_result_url(submitted_file, verbose)

@click.command("update")
@click.argument("db_path")
@click.option("--show-sql", is_flag=True, help="show all SQL queries")
def action_update(db_path, show_sql):
    """create and or auto-update the given database"""

    # Setup the base LNT logger.
    logger = logging.getLogger("lnt")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)

    # Enable full SQL logging, if requested.
    if show_sql:
        sa_logger = logging.getLogger("sqlalchemy")
        sa_logger.setLevel(logging.INFO)
        sa_logger.addHandler(handler)

    # Update the database.
    lnt.server.db.migrate.update_path(db_path)


@click.command("send-daily-report")
@click.argument("instance_path", type=click.UNPROCESSED)
@click.argument("address")
@click.option("--database", default="default", show_default=True,
              help="database to use")
@click.option("--testsuite", default="nts", show_default=True,
              help="testsuite to use")
@click.option("--host", default="localhost", show_default=True,
              help="email relay host to use")
@click.option("--from", "from_address", default=None, required=True,
              help="from email address")
@click.option("--today", is_flag=True,
              help="send the report for today (instead of most recent)")
@click.option("--subject-prefix", help="add a subject prefix")
@click.option("--dry-run", is_flag=True, help="don't actually send email")
@click.option("--days", default=3, show_default=True,
              help="number of days to show in report")
@click.option("--filter-machine-regex",
              help="only show machines that contain the regex")
def action_send_daily_report(instance_path, address, database, testsuite, host,
                             from_address, today, subject_prefix, dry_run,
                             days, filter_machine_regex):
    """send a daily report email"""
    import datetime
    import email.mime.multipart
    import email.mime.text
    import smtplib

    import lnt.server.reporting.dailyreport

    # Load the LNT instance.
    instance = lnt.server.instance.Instance.frompath(instance_path)
    config = instance.config

    # Get the database.
    with contextlib.closing(config.get_database(database)) as db:

        # Get the testsuite.
        ts = db.testsuite[testsuite]

        if today:
            date = datetime.datetime.utcnow()
        else:
            # Get a timestamp to use to derive the daily report to generate.
            latest = ts.query(ts.Run).\
                order_by(ts.Run.start_time.desc()).limit(1).first()

            # If we found a run, use it's start time (rounded up to the next
            # hour, so we make sure it gets included).
            if latest:
                date = latest.start_time + datetime.timedelta(hours=1)
            else:
                # Otherwise, just use now.
                date = datetime.datetime.utcnow()

        # Generate the daily report.
        note("building report data...")
        report = lnt.server.reporting.dailyreport.DailyReport(
            ts, year=date.year, month=date.month, day=date.day,
            day_start_offset_hours=date.hour, for_mail=True,
            num_prior_days_to_include=days,
            filter_machine_regex=filter_machine_regex)
        report.build()

        note("generating HTML report...")
        ts_url = "%s/db_%s/v4/%s" \
            % (config.zorgURL, database, testsuite)
        subject = "Daily Report: %04d-%02d-%02d" % (
            report.year, report.month, report.day)
        html_report = report.render(ts_url, only_html_body=False)

        if subject_prefix is not None:
            subject = "%s %s" % (subject_prefix, subject)

        # Form the multipart email message.
        msg = email.mime.multipart.MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_address
        msg['To'] = address
        msg.attach(email.mime.text.MIMEText(html_report, "html"))

        # Send the report.
        if not dry_run:
            s = smtplib.SMTP(host)
            s.sendmail(from_address, [address],
                       msg.as_string())
            s.quit()
        else:
            out = sys.stdout
            out.write("From: %s\n" % msg['From'])
            out.write("To: %s\n" % msg['To'])
            out.write("Subject: %s\n" % msg['Subject'])
            out.write("=== html report\n")
            out.write(html_report + "\n")


@click.command("send-run-comparison")
@click.argument("instance_path", type=click.UNPROCESSED)
@click.argument("run_a_id")
@click.argument("run_b_id")
@click.option("--database", default="default", show_default=True,
              help="database to use")
@click.option("--testsuite", default="nts", show_default=True,
              help="testsuite to use")
@click.option("--host", default="localhost", show_default=True,
              help="email relay host to use")
@click.option("--from", "from_address", default=None, required=True,
              help="from email address")
@click.option("--to", "to_address", default=None, required=True,
              help="to email address")
@click.option("--subject-prefix", help="add a subject prefix")
@click.option("--dry-run", is_flag=True, help="don't actually send email")
def action_send_run_comparison(instance_path, run_a_id, run_b_id, database,
                               testsuite, host, from_address, to_address,
                               subject_prefix, dry_run):
    """send a run-vs-run comparison email"""
    import email.mime.multipart
    import email.mime.text
    import smtplib
    import lnt.server.reporting.dailyreport

    # Setup the base LNT logger.
    logger = logging.getLogger("lnt")
    logger.setLevel(logging.ERROR)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)

    # Load the LNT instance.
    instance = lnt.server.instance.Instance.frompath(instance_path)
    config = instance.config

    # Get the database.
    with contextlib.closing(config.get_database(database)) as db:

        # Get the testsuite.
        ts = db.testsuite[testsuite]

        # Lookup the two runs.
        run_a_id = int(run_a_id)
        run_b_id = int(run_b_id)
        run_a = ts.query(ts.Run).\
            filter_by(id=run_a_id).first()
        run_b = ts.query(ts.Run).\
            filter_by(id=run_b_id).first()
        if run_a is None:
            error("invalid run ID %r (not in database)" % (run_a_id,))
        if run_b is None:
            error("invalid run ID %r (not in database)" % (run_b_id,))

        # Generate the report.
        data = lnt.server.reporting.runs.generate_run_data(
            run_b, baseurl=config.zorgURL, result=None, compare_to=run_a,
            baseline=None, aggregation_fn=min)

        env = lnt.server.ui.app.create_jinja_environment()
        text_template = env.get_template('reporting/runs.txt')
        text_report = text_template.render(data)
        data['only_html_body'] = False
        html_template = env.get_template('reporting/runs.html')
        html_report = html_template.render(data)

        subject = data['subject']
        if subject_prefix is not None:
            subject = "%s %s" % (subject_prefix, subject)

        # Form the multipart email message.
        msg = email.mime.multipart.MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_address
        msg['To'] = to_address
        msg.attach(email.mime.text.MIMEText(text_report, 'plain'))
        msg.attach(email.mime.text.MIMEText(html_report, 'html'))

        # Send the report.
        if not dry_run:
            mail_client = smtplib.SMTP(host)
            mail_client.sendmail(
                from_address,
                [to_address],
                msg.as_string())
            mail_client.quit()
        else:
            out = sys.stdout
            out.write("From: %s\n" % from_address)
            out.write("To: %s\n" % to_address)
            out.write("Subject: %s\n" % subject)
            out.write("=== text/plain report\n")
            out.write(text_report + "\n")
            out.write("=== html report\n")
            out.write(html_report + "\n")


@click.group("profile")
def action_profile():
    """tools to extract information from profiles"""
    return


@action_profile.command("upgrade")
@click.argument("input", type=click.Path(exists=True))
@click.argument("output", type=click.Path(exists=True))
def command_update(input, output):
    """upgrade a profile to the latest version"""
    profile.Profile.fromFile(input).upgrade().save(filename=output)


@action_profile.command("getVersion")
@click.argument("input", type=click.Path(exists=True))
def command_get_version(input):
    """print the version of a profile"""
    print profile.Profile.fromFile(input).getVersion()


@action_profile.command("getTopLevelCounters")
@click.argument("input", type=click.Path(exists=True))
def command_top_level_counters(input):
    """print the whole-profile counter values"""
    print json.dumps(profile.Profile.fromFile(input).getTopLevelCounters())


@action_profile.command("getFunctions")
@click.argument("input", type=click.Path(exists=True))
def command_get_functions(input):
    """print the functions in a profile"""
    print json.dumps(profile.Profile.fromFile(input).getFunctions())


@action_profile.command("getCodeForFunction")
@click.argument("input", type=click.Path(exists=True))
@click.argument('fn')
def command_code_for_function(input, fn):
    """print the code/instruction for a function"""
    print json.dumps(
        list(profile.Profile.fromFile(input).getCodeForFunction(fn)))


def _version_check():
    """
    Check that the installed version of the LNT is up-to-date with the running
    package.

    This check is used to force users of distribute's develop mode to reinstall
    when the version number changes (which may involve changing package
    requirements).
    """
    import pkg_resources

    # Get the current distribution.
    installed_dist = pkg_resources.get_distribution("LNT")
    installed_dist_name = "%s %s" % (installed_dist.project_name,
                                     installed_dist.version)
    current_dist_name = "LNT %s" % (lnt.__version__,)
    if pkg_resources.parse_version(installed_dist_name) != \
       pkg_resources.parse_version(current_dist_name):
        raise SystemExit("""\
error: installed distribution %s is not current (%s), you may need to reinstall
LNT or rerun 'setup.py develop' if using development mode.""" % (
                         installed_dist_name, current_dist_name))

def show_version(ctx, param, value):
    """print LNT version"""
    if not value or ctx.resilient_parsing:
        return
    if lnt.__version__:
        print "LNT %s" % (lnt.__version__,)
    ctx.exit()


@click.group(invoke_without_command=True, no_args_is_help=True)
@click.option('--version', is_flag=True, callback=show_version,
              expose_value=False, is_eager=True, help=show_version.__doc__)
def main():
    """LNT command line tool

\b
Use ``lnt <command> --help`` for more information on a specific command.
    """
    _version_check()


main.add_command(action_checkformat)
main.add_command(action_create)
main.add_command(action_convert)
main.add_command(action_import)
main.add_command(action_importreport)
main.add_command(action_profile)
main.add_command(action_runserver)
main.add_command(action_runtest)
main.add_command(action_send_daily_report)
main.add_command(action_send_run_comparison)
main.add_command(action_showtests)
main.add_command(action_submit)
main.add_command(action_update)
main.add_command(action_updatedb)
main.add_command(action_view_comparison)

if __name__ == '__main__':
    main()
