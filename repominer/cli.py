import copy
import io
import json
import os

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime

from repominer.files import FixedFileEncoder, FixedFileDecoder, FailureProneFileEncoder, FailureProneFileDecoder
from repominer.metrics.ansible import AnsibleMetricsExtractor
from repominer.metrics.tosca import ToscaMetricsExtractor
from repominer.mining.base import BaseMiner
from repominer.mining.ansible import AnsibleMiner
from repominer.mining.tosca import ToscaMiner

VERSION = '0.8.11'


def valid_dir_or_url(x: str) -> str:
    """
    Check if x is a directory and exists, or a remote url
    :param x: a path
    :return: the path if exists or is a remote url; raise an ArgumentTypeError otherwise
    """
    if not (os.path.isdir(x) or x.startswith("git@") or x.startswith("https://")):
        raise ArgumentTypeError('Insert a valid path or url')

    return x


def valid_dir(x: str) -> str:
    """
    Check if x is a directory and exists
    :param x: a path
    :return: the path if exists; raise an ArgumentTypeError otherwise
    """
    if not os.path.isdir(x):
        raise ArgumentTypeError('Insert a valid path')

    return x


def valid_file(x: str) -> str:
    """
    Check if x is a file and exists
    :param x: a path
    :return: the path if exists; raise an ArgumentTypeError otherwise
    """
    if not os.path.isfile(x):
        raise ArgumentTypeError('Insert a valid path')

    return x


def set_mine_parser(subparsers):
    parser = subparsers.add_parser('mine', help='Mine fixing- and clean- files')

    parser.add_argument(action='store',
                        dest='info_to_mine',
                        type=str,
                        choices=['fixing-commits', 'fixed-files', 'failure-prone-files'],
                        help='the information to mine')

    parser.add_argument(action='store',
                        dest='host',
                        type=str,
                        choices=['github', 'gitlab'],
                        help='the source code versioning host')

    parser.add_argument(action='store',
                        dest='language',
                        type=str,
                        choices=['ansible', 'tosca'],
                        help='mine only commits modifying files of this language')

    parser.add_argument(action='store',
                        dest='repository',
                        help='the repository full name: <onwer/name> (e.g., radon-h2020/radon-repository-miner)')

    parser.add_argument(action='store',
                        dest='dest',
                        type=valid_dir,
                        help='destination folder for the reports')

    parser.add_argument('-b', '--branch',
                        action='store',
                        dest='branch',
                        type=str,
                        default='master',
                        help='the repository branch to mine (default: %(default)s)')

    parser.add_argument('--exclude-commits',
                        action='store',
                        dest='exclude_commits',
                        type=valid_file,
                        help='the path to a JSON file containing the list of commit hashes to exclude')

    parser.add_argument('--include-commits',
                        action='store',
                        dest='include_commits',
                        type=valid_file,
                        help='the path to a JSON file containing the list of commit hashes to include')

    parser.add_argument('--exclude-files',
                        action='store',
                        dest='exclude_files',
                        type=valid_file,
                        help='the path to a JSON file containing the list of FixedFiles to exclude')

    parser.add_argument('--verbose',
                        action='store_true',
                        dest='verbose',
                        default=False,
                        help='show log')


def set_extract_metrics_parser(subparsers):
    parser = subparsers.add_parser('extract-metrics', help='Extract metrics from the mined files')

    parser.add_argument(action='store',
                        dest='path_to_repo',
                        type=valid_dir_or_url,
                        help='the absolute path to a cloned repository or the url to a remote repository')

    parser.add_argument(action='store',
                        dest='src',
                        type=valid_file,
                        help='the path to report.json generated by a previous run of \'repo-miner mine\'')

    parser.add_argument(action='store',
                        dest='language',
                        type=str,
                        choices=['ansible', 'tosca'],
                        help='extract metrics for Ansible or Tosca')

    parser.add_argument(action='store',
                        dest='metrics',
                        type=str,
                        choices=['product', 'process', 'delta', 'all'],
                        help='the metrics to extract')

    parser.add_argument(action='store',
                        dest='at',
                        type=str,
                        choices=['release', 'commit'],
                        help='extract metrics at each release or commit')

    parser.add_argument(action='store',
                        dest='dest',
                        type=valid_dir,
                        help='destination folder to save the resulting csv')

    parser.add_argument('--verbose',
                        action='store_true',
                        dest='verbose',
                        default=False,
                        help='show log')


def get_parser():
    description = 'A Python library and command-line tool to mine Infrastructure-as-Code based software repositories.'

    parser = ArgumentParser(prog='repo-miner', description=description)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + VERSION)
    subparsers = parser.add_subparsers(dest='command')

    set_mine_parser(subparsers)
    set_extract_metrics_parser(subparsers)

    return parser


def mine_fixing_commits(miner: BaseMiner, verbose: bool, dest: str, exclude_commits: str = None, include_commits: str = None):

    if exclude_commits:
        with open(exclude_commits, 'r') as f:
            commits = json.load(f)
            miner.exclude_commits = set(commits)

    if include_commits:
        with open(include_commits, 'r') as f:
            commits = json.load(f)
            miner.fixing_commits = commits

    if verbose:
        print('Identifying fixing-commits from closed issues related to bugs')

    from_issues = miner.get_fixing_commits_from_closed_issues(labels=None)

    if verbose:
        print('Identifying fixing-commits from commit messages')

    from_msg = miner.get_fixing_commits_from_commit_messages(regex=None)

    if verbose:
        print(f'Saving {len(miner.fixing_commits)} fixing-commits ({len(from_issues)} from closed issue, {len(from_msg)} from commit messages) [{datetime.now().hour}:{datetime.now().minute}]')

    filename_json = os.path.join(dest, 'fixing-commits.json')

    with io.open(filename_json, "w") as f:
        json.dump(miner.fixing_commits, f)

    if verbose:
        print(f'JSON created at {filename_json}')


def mine_fixed_files(miner: BaseMiner, verbose: bool, dest: str, exclude_files: str = None):

    if exclude_files:
        with open(exclude_files, 'r') as f:
            files = json.load(f, cls=FixedFileDecoder)
            miner.exclude_fixed_files = files

    if verbose:
        language = 'Ansible' if isinstance(miner, AnsibleMiner) else 'Tosca'
        print(f'Identifying {language} files modified in fixing-commits')

    fixed_files = miner.get_fixed_files()

    if verbose:
        print(f'Saving {len(fixed_files)} fixed-files [{datetime.now().hour}:{datetime.now().minute}]')

    filename_json = os.path.join(dest, 'fixed-files.json')
    json_files = []
    for file in fixed_files:
        json_files.append(FixedFileEncoder().default(file))

    with io.open(filename_json, "w") as f:
        json.dump(json_files, f)

    if verbose:
        print(f'JSON created at {filename_json}')


def mine_failure_prone_files(miner: BaseMiner, verbose: bool, dest: str):
    if verbose:
        print('Identifying and labeling failure-prone files')

    failure_prone_files = [copy.deepcopy(file) for file in miner.label()]

    if verbose:
        print('Saving failure-prone files')

    filename_json = os.path.join(dest, 'failure-prone-files.json')

    json_files = []
    for file in failure_prone_files:
        json_files.append(FailureProneFileEncoder().default(file))

    with open(filename_json, "w") as f:
        json.dump(json_files, f)

    if verbose:
        print(f'JSON created at {filename_json}')


def mine(args: Namespace):
    url_to_repo = None

    if args.host == 'github':
        url_to_repo = f'https://github.com/{args.repository}'
    elif args.host == 'gitlab':
        url_to_repo = f'https://gitlab.com/{args.repository}'

    if args.verbose:
        print(f'Mining {args.repository} [started at: {datetime.now().hour}:{datetime.now().minute}]')

    if args.language == 'ansible':
        miner = AnsibleMiner(url_to_repo=url_to_repo, branch=args.branch)
    else:
        miner = ToscaMiner(url_to_repo=url_to_repo, branch=args.branch)

    mine_fixing_commits(miner, args.verbose, args.dest, args.exclude_commits, args.include_commits)

    if args.info_to_mine in ('fixed-files', 'failure-prone-files'):
        mine_fixed_files(miner, args.verbose, args.dest, args.exclude_files)

    if args.info_to_mine == 'failure-prone-files':
        mine_failure_prone_files(miner, args.verbose, args.dest)

    exit(0)


def extract_metrics(args: Namespace):
    global extractor

    if args.verbose:
        print(
            f'Extracting metrics from {args.path_to_repo} using report {args.src} [started at: {datetime.now().hour}:{datetime.now().minute}]')

    with open(args.src, 'r') as f:
        labeled_files = json.load(f, cls=FailureProneFileDecoder)

    if args.verbose:
        print(f'Setting up {args.language} metrics extractor')

    if args.language == 'ansible':
        extractor = AnsibleMetricsExtractor(args.path_to_repo, at=args.at)
    elif args.language == 'tosca':
        extractor = ToscaMetricsExtractor(args.path_to_repo, at=args.at)

    if args.verbose:
        print(f'Extracting {args.metrics} metrics')

    assert extractor
    extractor.extract(labeled_files=labeled_files,
                      process=args.metrics in ('process', 'all'),
                      product=args.metrics in ('product', 'all'),
                      delta=args.metrics in ('delta', 'all'))

    extractor.to_csv(os.path.join(args.dest, 'metrics.csv'))

    if args.verbose:
        print(f'Metrics saved at {args.dest}/metrics.csv [completed at: {datetime.now().hour}:{datetime.now().minute}]')


def main():
    args = get_parser().parse_args()
    if args.command == 'mine':
        mine(args)
    elif args.command == 'extract-metrics':
        extract_metrics(args)
