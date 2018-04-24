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
import requests

from csv_database import PRDB


# Only PRs after this time (UTC) will be processed. Our 2-way sync really
# started to stablize around this time. Earlier results are inaccurate.
CUTOFF = '2017-07-01T00:00:00Z'
# Change this when it is a new quarter.
QUARTER_START = '2018-04-01T00:00:00Z'

# Read token from env var.
GH_TOKEN = os.environ.get('GH_TOKEN')
if GH_TOKEN is None:
    print('Warning: Provide GH_TOKEN to get full results')

# GitHub cache. Delete the file to fetch PRs again.
PRS_FILE = 'wpt-prs.csv'

try:
    CHROMIUM_DIR = sys.argv[1]
except IndexError:
    CHROMIUM_DIR = os.path.expanduser('~/chromium/src')
CHROMIUM_WPT_PATH = 'third_party/WebKit/LayoutTests/external/wpt'
try:
    WPT_DIR = sys.argv[2]
except IndexError:
    WPT_DIR = os.path.expanduser('~/github/web-platform-tests')


def git(args, cwd):
    command = ['git'] + args
    output = subprocess.check_output(command, cwd=cwd, env={'TZ': 'UTC'})
    # Alright this only works in UTF-8 locales...
    return output.decode('utf-8').rstrip()


def chromium_git(args):
    return git(args, cwd=CHROMIUM_DIR)


def wpt_git(args):
    return git(args, cwd=WPT_DIR)


def github_request(url):
    base_url = 'https://api.github.com'
    headers = None
    if GH_TOKEN is not None:
        headers = {'Authorization': 'token {}'.format(GH_TOKEN)}
    res = requests.get(base_url + url, headers=headers)
    res.raise_for_status()
    return res.json()


def fetch_all_prs(update=False):
    pr_db = PRDB(PRS_FILE)

    if update == False:
        pr_db.read()
        print('Read {} PRs from {}'.format(len(pr_db), PRS_FILE))
        return pr_db

    for pr_tag in get_merge_pr_tags():
        pr_number = pr_number_from_tag(pr_tag)
        # --iso-strict-local works because TZ=UTC is set in the environment
        info = wpt_git(['log', '--no-walk', '--format=%H%n%cd%n%B',
                        '--date=iso-strict-local', pr_tag])
        lines = info.splitlines()

        commit = lines[0]
        commit_date = lines[1][0:19] + 'Z'
        chromium_commit = ''
        for line in lines[2:]:
            match = re.match(r'Change-Id: (.+)', line)
            if match == None:
                match = re.match(r'Cr-Commit-Position: (.+)', line)
            if match != None:
                chromium_commit = match.group(1).strip()
                break

        pr_db.add({
            'PR': str(pr_number),
            'merge_commit_sha': commit,
            'merged_at': commit_date,
            'chromium_commit': chromium_commit
        })

    print('Found {} PRs'.format(len(pr_db)))

    print('Writing file', PRS_FILE)
    pr_db.write(order='asc')
    return pr_db


def is_export_pr(pr):
    return bool(pr['chromium_commit'])


def pr_number_from_tag(tagish):
    """Extracts the PR number as integer from a string that begins with
    merge_pr*, like merge_pr_6581 or merge_pr_6589-1-gc9db8d86f6."""
    match = re.search(r'merge_pr_(\d+)', tagish)
    if match is not None:
        return int(match.group(1))
    return None


def get_merge_pr_tags():
    """Gets the set of merge_pr_* tags as string."""
    # --format="%(refname:strip=2) %(objectname)" would also include SHA-1
    return wpt_git(['tag', '--list', 'merge_pr_*']).splitlines()


def git_contained_pr(commit):
    """Returns the number of the latest contained PR of commit using git describe."""
    try:
        tag = wpt_git(['describe', '--tags', '--match', 'merge_pr_*', commit])
        return pr_number_from_tag(tag)
    except subprocess.CalledProcessError:
        return None


def pr_number(pr):
    return int(pr['PR'])


def pr_date(pr):
    return dateutil.parser.parse(pr['merged_at'])


def get_pr_latencies(prs, events=None, event_sha_func=None, event_date_func=None):
    """For each PR, find the earliest event that included that PR,
    and calucate the latencies between the PR and the event.

    Args:
        prs: list of PRs from fetch_all_prs()
        events: list of events in any format
        event_sha_func: function to get a sha from an event
        event_date_func: function to get a datetime.datetime from an event

    Returns:
        A list of dictionaries in the following format:
           [{'pr': PR number (string), 'event': event,
             'latency': latency in minutes (float)}, ...]
    """

    # Sort the PRs by merge date and filter out the ones that weren't tagged,
    # since we don't know at which commit they were merged, and their computed
    # latency can therefore be higher than the real latency. (Any PR which has
    # correct merge information via the GitHub API should also have a tag:
    # https://github.com/foolip/ecosystem-infra-stats/issues/6#issuecomment-375731858)
    tagged_prs = set(pr_number_from_tag(tag) for tag in get_merge_pr_tags())
    skipped_prs = []

    def is_tagged_pr(pr):
        n = pr_number(pr)
        if n in tagged_prs:
            return True
        skipped_prs.append(n)
        return False

    prs = filter(is_tagged_pr, sorted(prs, key=pr_date))
    if len(skipped_prs) > 0:
        print('Skipped PRs (no merge_pr_* tag):', skipped_prs)

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
        result['latency'] = (event_date_func(earliest_event_so_far) -
                             pr_date(pr)).total_seconds() / 60
    return results
