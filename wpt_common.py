"""A bunch of common functions shared by wpt-{import,export}-stats.
Python 6 (2 and 3 compatible) please.
"""

# Requirements: python-dateutil, requests

from __future__ import print_function
import os
import re
import subprocess
import sys

import dateutil.parser

from csv_database import PRDB


# Only PRs after this time (UTC) will be processed. Our 2-way sync really
# started to stablize around this time. Earlier results are inaccurate.
CUTOFF = '2017-07-01T00:00:00Z'
# Change this when it is a new quarter.
QUARTER_START = '2019-07-01T00:00:00Z'

# GitHub cache. Delete the file to fetch PRs again.
PRS_FILE = 'wpt-prs.csv'

try:
    WPT_DIR = sys.argv[2]
except IndexError:
    WPT_DIR = os.path.expanduser('~/github/web-platform-tests')


def git(args, cwd):
    command = ['git'] + args
    output = subprocess.check_output(command, cwd=cwd, env={'TZ': 'UTC'})
    # Alright this only works in UTF-8 locales...
    return output.decode('utf-8').rstrip()


def wpt_git(args):
    return git(args, cwd=WPT_DIR)


def read_pr_db():
    pr_db = PRDB(PRS_FILE)
    pr_db.read()
    print('Read {} PRs from {}'.format(len(pr_db), PRS_FILE))
    return pr_db


def pr_number_from_tag(tagish):
    """Extracts the PR number as integer from a string that begins with
    merge_pr*, like merge_pr_6581 or merge_pr_6589-1-gc9db8d86f6."""
    match = re.search(r'merge_pr_(\d+)', tagish)
    if match is not None:
        return int(match.group(1))
    return None


def git_contained_pr(commit):
    """Returns the number of the latest contained PR of commit using git
    describe."""
    try:
        tag = wpt_git(['describe', '--tags', '--match', 'merge_pr_*', commit])
        return pr_number_from_tag(tag)
    except subprocess.CalledProcessError:
        return None


def pr_number(pr):
    return int(pr['PR'])


def pr_date(pr):
    return dateutil.parser.parse(pr['merged_at'])


def get_pr_latencies(prs, events=None, event_sha_func=None,
                     event_date_func=None):
    """For each PR, find the earliest event that included that PR,
    and calucate the latencies between the PR and the event.

    Args:
        prs: list of PRs from read_pr_db().values()
        events: list of events in any format
        event_sha_func: function to get a sha from an event
        event_date_func: function to get a datetime.datetime from an event

    Returns:
        A list of dictionaries in the following format:
           [{'pr': PR number (string), 'event': event,
             'latency': latency in minutes (float)}, ...]
    """

    # Sort the PRs by merge date.
    prs = sorted(prs, key=pr_date)

    # We get PR-to-event latencies by the following process:
    #  1. For each event find the latest contained PR. This is done using git
    #     describe, and after this point the git commit graph doesn't matter.
    #     Not all events necessarily have a known contained PR at all.
    #  2. Reverse to a mapping from PR to event. Some PRs won't be the latest
    #     contained PR of any event, and if there are multiple events for a
    #     single PR only the earliest is saved.
    #  3. Walk the list of PR and associated events backwards, keeping track
    #     of the earliest event encountered so far. That is the event against
    #     which the latency for the PR is measured.

    # Step 1.
    # event_contained_prs is a list of PR numbers, not dicts.
    event_contained_prs = [git_contained_pr(
        event_sha_func(event)) for event in events]

    # earliest_event allows using None as a placeholder for no event.
    def earliest_event(event1, event2):
        if event1 is None:
            return event2
        if event2 is None:
            return event1
        return min(event1, event2, key=event_date_func)

    # Step 2.
    # earliest_event_for_pr is a mapping from PR to earliest event for that
    # specific PR, implemented as a dict with PR numbers as the key.
    earliest_event_for_pr = {}
    for event, contained_pr in zip(events, event_contained_prs):
        if contained_pr is None:
            continue
        earliest_event_for_pr[contained_pr] = earliest_event(
            earliest_event_for_pr.get(contained_pr), event)

    # Step 3.
    # results is first created and then swept/updated in reverse order.
    results = [{'pr': pr, 'event': None, 'latency': None} for pr in prs]
    earliest_event_so_far = None
    for result in reversed(results):
        pr = result['pr']
        event = earliest_event_for_pr.get(pr_number(pr))
        earliest_event_so_far = earliest_event(earliest_event_so_far, event)
        if earliest_event_so_far is None:
            continue
        result['event'] = earliest_event_so_far
        result['latency'] = (event_date_func(earliest_event_so_far)
                             - pr_date(pr)).total_seconds() / 60
    return results
