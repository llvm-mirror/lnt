"""
Report functionality centered around individual runs.
"""

from collections import namedtuple
import time
import lnt.server.reporting.analysis
import lnt.server.ui.app
import lnt.util.stats


def generate_run_data(session, run, baseurl, num_comparison_runs=0,
                      result=None, compare_to=None, baseline=None,
                      aggregation_fn=lnt.util.stats.safe_min,
                      confidence_lv=.05, styles=dict(), classes=dict()):
    """
    Generate raw data for a report on the results of the given individual
    run. They are meant as inputs to jinja templates which could create
    email reports or presentations on a web page.
    """
    assert num_comparison_runs >= 0

    start_time = time.time()

    ts = run.testsuite
    machine = run.machine
    machine_parameters = machine.parameters

    if baseline is None:
        # If a baseline has not been given, look up the run closest to
        # the default baseline revision for which this machine also
        # reported.
        baseline = machine.get_baseline_run(session)

    # If the baseline is the same as the comparison run, ignore it.
    visible_note = None
    if baseline is compare_to:
        visible_note = "Baseline and compare_to are the same: " \
                       "disabling baseline."
        baseline = None

    # Gather the runs to use for statistical data.
    comparison_start_run = compare_to or run
    comparison_window = list(ts.get_previous_runs_on_machine(
            session, comparison_start_run, num_comparison_runs))
    if baseline:
        baseline_window = list(ts.get_previous_runs_on_machine(
                session, baseline, num_comparison_runs))
    else:
        baseline_window = []

    # If we don't have an explicit baseline run or a comparison run, use the
    # previous run.
    if compare_to is None and comparison_window:
        compare_to = comparison_window[0]

    # Create the run info analysis object.
    runs_to_load = set(r.id for r in comparison_window)
    for r in baseline_window:
        runs_to_load.add(r.id)
    runs_to_load.add(run.id)
    if compare_to:
        runs_to_load.add(compare_to.id)
    if baseline:
        runs_to_load.add(baseline.id)
    sri = lnt.server.reporting.analysis.RunInfo(
        session, ts, runs_to_load, aggregation_fn, confidence_lv)

    # Get the test names, metric fields and total test counts.
    test_names = session.query(ts.Test.name, ts.Test.id).\
        order_by(ts.Test.name).\
        filter(ts.Test.id.in_(sri.test_ids)).all()
    metric_fields = list(ts.Sample.get_metric_fields())
    num_total_tests = len(metric_fields) * len(test_names)

    # Gather the run-over-run changes to report, organized by field and then
    # collated by change type.
    run_to_run_info, test_results = _get_changes_by_type(
        ts, run, compare_to, metric_fields, test_names, num_comparison_runs,
        sri)

    # If we have a baseline, gather the run-over-baseline results and
    # changes.
    if baseline:
        run_to_baseline_info, baselined_results = _get_changes_by_type(
            ts, run, baseline, metric_fields, test_names, num_comparison_runs,
            sri)
    else:
        run_to_baseline_info = baselined_results = None

    # Gather the run-over-run changes to report.

    # Collect the simplified results, if desired, for sending back to clients.
    if result is not None:
        pset_results = []
        result['test_results'] = [{'pset': (), 'results': pset_results}]
        for field, field_results in test_results:
            for _, bucket, _ in field_results:
                for name, cr, _ in bucket:
                    # FIXME: Include additional information about performance
                    # changes.
                    pset_results.append(("%s.%s" % (name, field.name),
                                         cr.get_test_status(),
                                         cr.get_value_status()))

    # Aggregate counts across all bucket types for our num item
    # display
    def aggregate_counts_across_all_bucket_types(i, name):
        num_items = sum(len(field_results[i][1])
                        for _, field_results in test_results)
        if baseline:
            num_items_vs_baseline = sum(
                len(field_results[i][1])
                for _, field_results in baselined_results)
        else:
            num_items_vs_baseline = None

        return i, name, num_items, num_items_vs_baseline

    num_item_buckets = [aggregate_counts_across_all_bucket_types(x[0], x[1][0])
                        for x in enumerate(test_results[0][1])]

    def maybe_sort_bucket(bucket, bucket_name, show_perf):
        if not bucket or bucket_name == 'Unchanged Test' or not show_perf:
            return bucket
        else:
            return sorted(
                bucket,
                key=lambda bucket_entry: -abs(bucket_entry.cr.pct_delta))

    def prioritize_buckets(test_results):
        prioritized = [(priority, field, bucket_name,
                        maybe_sort_bucket(bucket, bucket_name, show_perf),
                        [name for name, _, __ in bucket], show_perf)
                       for field, field_results in test_results
                       for priority, (bucket_name, bucket,
                                      show_perf) in enumerate(field_results)]
        prioritized.sort(key=lambda item: (item[0], item[1].name))
        return prioritized

    # Generate prioritized buckets for run over run and run over baseline data.
    prioritized_buckets_run_over_run = prioritize_buckets(test_results)
    if baseline:
        prioritized_buckets_run_over_baseline = \
            prioritize_buckets(baselined_results)
    else:
        prioritized_buckets_run_over_baseline = None

    # Prepare auxillary variables for rendering.
    # Create Subject
    subject = """%s test results""" % (machine.name,)

    # Define URLS.
    if baseurl[-1] == '/':
        baseurl = baseurl[:-1]
    ts_url = """%s/v4/%s""" % (baseurl, ts.name)
    run_url = """%s/%d""" % (ts_url, run.id)
    report_url = run_url
    url_fields = []
    if compare_to:
        url_fields.append(('compare_to', str(compare_to.id)))
    if baseline:
        url_fields.append(('baseline', str(baseline.id)))
    report_url = "%s?%s" % (run_url, "&amp;".join("%s=%s" % (k, v)
                                                  for k, v in url_fields))

    # Compute static CSS styles for elemenets. We use the style directly on
    # elements instead of via a stylesheet to support major email clients (like
    # Gmail) which can't deal with embedded style sheets.
    #
    # These are derived from the static style.css file we use elsewhere.
    #
    # These are just defaults however, and the caller can override them with
    # the 'styles' and 'classes' kwargs.
    styles_ = {
        "body": ("color:#000000; background-color:#ffffff; "
                 "font-family: Helvetica, sans-serif; font-size:9pt"),
        "h1": ("font-size: 14pt"),
        "table": "font-size:9pt; border-spacing: 0px; border: 1px solid black",
        "th": ("background-color:#eee; color:#666666; font-weight: bold; "
               "cursor: default; text-align:center; font-weight: bold; "
               "font-family: Verdana; padding:5px; padding-left:8px"),
        "td": "padding:5px; padding-left:8px",
    }
    classes_ = {
    }

    styles_.update(styles)
    classes_.update(classes)

    data = {
        'ts': ts,
        'subject': subject,
        'report_url': report_url,
        'ts_url': ts_url,
        'compare_to': compare_to,
        'run': run,
        'run_url': run_url,
        'baseline': baseline,
        'machine': machine,
        'machine_parameters': machine_parameters,
        'num_item_buckets': num_item_buckets,
        'num_total_tests': num_total_tests,
        'run_to_run_info': run_to_run_info,
        'prioritized_buckets_run_over_run': prioritized_buckets_run_over_run,
        'run_to_baseline_info': run_to_baseline_info,
        'prioritized_buckets_run_over_baseline':
            prioritized_buckets_run_over_baseline,
        'styles': styles_,
        'classes': classes_,
        'start_time': start_time,
        'sri': sri,
        'visible_note': visible_note,
    }
    return data


BucketEntry = namedtuple('BucketEntry', ['name', 'cr', 'test_id'])
def _get_changes_by_type(ts, run_a, run_b, metric_fields, test_names,
                         num_comparison_runs, sri):
    comparison_results = {}
    results_by_type = []
    for field in metric_fields:
        new_failures = []
        new_passes = []
        perf_regressions = []
        perf_improvements = []
        removed_tests = []
        added_tests = []
        existing_failures = []
        unchanged_tests = []
        for name, test_id in test_names:
            cr = sri.get_run_comparison_result(
                run_a, run_b, test_id, field,
                ts.Sample.get_hash_of_binary_field())
            comparison_results[(name, field)] = cr
            test_status = cr.get_test_status()
            perf_status = cr.get_value_status()
            if test_status == lnt.server.reporting.analysis.REGRESSED:
                bucket = new_failures
            elif test_status == lnt.server.reporting.analysis.IMPROVED:
                bucket = new_passes
            elif cr.current is None and cr.previous is not None:
                bucket = removed_tests
            elif cr.current is not None and cr.previous is None:
                bucket = added_tests
            elif test_status == lnt.server.reporting.analysis.UNCHANGED_FAIL:
                bucket = existing_failures
            elif perf_status == lnt.server.reporting.analysis.REGRESSED:
                bucket = perf_regressions
            elif perf_status == lnt.server.reporting.analysis.IMPROVED:
                bucket = perf_improvements
            else:
                bucket = unchanged_tests

            bucket.append(BucketEntry(name, cr, test_id))

        results_by_type.append(
            (field, (('New Failures', new_failures, False),
                     ('New Passes', new_passes, False),
                     ('Performance Regressions', perf_regressions, True),
                     ('Performance Improvements', perf_improvements, True),
                     ('Removed Tests', removed_tests, False),
                     ('Added Tests', added_tests, False),
                     ('Existing Failures', existing_failures, False),
                     ('Unchanged Tests', unchanged_tests, False))))
    return comparison_results, results_by_type
