"""
A module for mining repositories.
It requires that the repository to mine is cloned on the local machine.
"""
import github
import re

from typing import Generator, NewType, List, Set
from miner import filters
from miner.file import FixingFile, LabeledFile
from pydriller.domain.commit import ModificationType
from pydriller.repository_mining import GitRepository, RepositoryMining

Issue = NewType('Issue', github.Issue)

# Constants
BUG_RELATED_LABELS = {'bug', 'Bug', 'bug :bug:', 'Bug - Medium', 'Bug - Low', 'Bug - Critical', 'ansible_bug',
                      'Type: Bug', 'Type: bug', 'Type/Bug', 'type: bug 🐛', 'type:bug', 'type: bug', 'type/bug',
                      'kind/bug', 'kind/bugs', 'bug/bugfix', 'bugfix', 'critical-bug', '01 type: bug', 'bug_report',
                      'minor-bug'}


class RepositoryMiner:
    """
    This class is responsible for mining the history of a repository to collect defect-prone and defect-free blueprints.
    """

    def __init__(self,
                 access_token: str,
                 path_to_repo: str,
                 repo_owner: str,
                 repo_name: str,
                 branch: str = 'master'):
        """
        Initialize a new miner for a software repository.

        :param path_to_repo: the path to the repository to analyze;
        :param repo_owner: the repository's owner;
        :param repo_name: the name of the repository; 
        :param branch: the branch to analyze. Default 'master';
        """

        self.__github = github.Github(access_token)
        self.path_to_repo = path_to_repo
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch

        self.fixing_commits = list()
        self.fixing_files = list()

        # Get all the repository commits sorted by commit date
        self.commit_hashes = [c.hash for c in
                              RepositoryMining(self.path_to_repo,
                                               only_in_branch=self.branch,
                                               order='date-order').traverse_commits()]

    def discard_non_iac_fixing_commits(self, commits: List[str]):
        """
        Discard commits that do not touch IaC files (i.e., Ansible)
        :commits: the original list of commits
        """
        # get a sorted list of commits in ascending order of date
        self.sort_commits(commits)

        for commit in RepositoryMining(self.path_to_repo,
                                       from_commit=commits[0],  # first commit in commits
                                       to_commit=commits[-1],  # last commit in commits
                                       only_in_branch=self.branch).traverse_commits():

            if not any(filters.is_ansible_file(modified_file.new_path) for modified_file in commit.modifications):
                if commit.hash in commits:
                    commits.remove(commit.hash)

    def get_labels(self) -> Set[str]:
        """
        Collect all the repository labels
        :return: a set of labels
        """

        repo = self.__github.get_repo('/'.join([self.repo_owner, self.repo_name]))  # repo_owner/repo_name
        labels = set()
        for label in repo.get_labels():
            if type(label) == github.Label.Label:
                labels.add(label.name)

        return labels

    def get_closed_issues(self, label: str) -> List[Issue]:
        """
        Get all the closed issues with a given label

        :param label: the issue label (e.g., 'bug')
        :return: the set of closed issues with that label
        """

        repo = self.__github.get_repo('/'.join([self.repo_owner, self.repo_name]))  # repo_owner/repo_name
        label = repo.get_label(label)
        issues = list()
        for issue in repo.get_issues(state='closed', labels=[label], sort='created', direction='desc'):
            issues.append(issue)

        return issues

    def get_fixing_commits_from_closed_issues(self, labels: Set[str]) -> List[str]:
        """
        Collect fixing-commit hashes by analyzing closed issues related to bugs.
        :param labels: bug-related labels (e.g., bug, bugfix, type: bug)
        :return: the set of fixing-commit hashes
        """

        if not labels:
            labels = BUG_RELATED_LABELS

        # Get the repository labels (self.get_labels()) and keep only those matching the input labels, if any
        labels = labels.intersection(self.get_labels())

        fixes_from_issues = list()

        for label in labels:
            for issue in self.get_closed_issues(label):
                for e in issue.get_events():
                    is_merged = e.event.lower() == 'merged'
                    is_closed = e.event.lower() == 'closed'

                    if (is_merged or is_closed) and e.commit_id:
                        fixes_from_issues.append(e.commit_id)

        if fixes_from_issues:
            # Discard commits that do not touch IaC files
            self.discard_non_iac_fixing_commits(fixes_from_issues)

            # Update the list of fixing commits
            self.fixing_commits.extend(fixes_from_issues)

            # Sort fixing_commits in ascending order of date
            self.sort_commits(self.fixing_commits)

        return fixes_from_issues

    def get_fixing_commits_from_commit_messages(self, regex: str) -> List[str]:
        """
        Collect fixing-commit hashes by analyzing commit messages.
        :param regex: a regular expression to identify fixing-commit (e.g., '(bug|fix|error|crash|problem|fail)')
        :return: the set of fixing-commit hashes
        """

        if not regex:
            regex = r'(bug|fix|error|crash|problem|fail|defect|patch)'

        fixes_from_message = list()

        for commit in RepositoryMining(self.path_to_repo, only_in_branch=self.branch).traverse_commits():

            # Remove words ending with 'bug' or 'fix' (e.g., 'debug' and 'prefix') from the commit message
            p = re.compile(r'(\w+(bug|fix)\w)*', re.IGNORECASE)
            msg = commit.msg
            match = p.match(msg)
            if match:
                msg = re.sub(match.group(), '', msg)

            # Match the regular expression to the message
            if re.match(regex, msg.lower()):
                fixes_from_message.append(commit.hash)

        if fixes_from_message:
            # Discard commits that do not touch IaC files
            self.discard_non_iac_fixing_commits(fixes_from_message)

            # Update the list of fixing commits
            self.fixing_commits.extend(fixes_from_message)

            # Sort fixing_commits in ascending order of date
            self.sort_commits(self.fixing_commits)

        return fixes_from_message

    def get_fixing_files(self) -> List[FixingFile]:
        """
        Collect the IaC files involved in fixing-commits and for each of them identify the bug-inducing-commit.
        :return: the list of files
        """

        if not self.fixing_commits:
            return list()

        self.sort_commits(self.fixing_commits)

        self.fixing_files = list()
        renamed_files = dict()
        git_repo = GitRepository(self.path_to_repo)

        # Traverse commits from the latest to the first fixing-commit
        for commit in RepositoryMining(self.path_to_repo,
                                       from_commit=self.fixing_commits[-1],  # Last fixing-commit by date
                                       to_commit=self.fixing_commits[0],  # First fixing-commit by date
                                       order='reverse',
                                       only_in_branch=self.branch).traverse_commits():

            for modified_file in commit.modifications:

                # Not interested in ADDED and DELETED files
                if modified_file.change_type not in (ModificationType.MODIFY, ModificationType.RENAME):
                    continue

                # If RENAMED then handle renaming
                if modified_file.change_type == ModificationType.RENAME:

                    if modified_file.new_path in renamed_files:
                        renamed_files[modified_file.old_path] = renamed_files[modified_file.new_path]

                    elif commit.hash in self.fixing_commits:
                        renamed_files[modified_file.old_path] = modified_file.new_path

                # This is to ensure that renamed files are tracked. Then, if the commit is not a fixing-commit then
                # go to the next (previous commit in chronological order)
                if commit.hash not in self.fixing_commits:
                    continue

                # Not interested in files other than Ansible
                if not filters.is_ansible_file(modified_file.new_path):
                    continue

                # Identify bug-inducing commits. Dict[modified_file, Set[commit_hashes]]
                bug_inducing_commits = git_repo.get_commits_last_modified_lines(commit, modified_file)

                if not bug_inducing_commits.get(modified_file.new_path):
                    continue
                else:
                    bug_inducing_commits = list(bug_inducing_commits[modified_file.new_path])
                    self.sort_commits(bug_inducing_commits)
                    bic = bug_inducing_commits[0]  # bic is the oldest bug-inducing-commit

                current_fix = FixingFile(filepath=renamed_files.get(modified_file.new_path, modified_file.new_path),
                                         bic=bic,
                                         fic=commit.hash)

                if current_fix not in self.fixing_files:
                    self.fixing_files.append(current_fix)
                else:
                    idx = self.fixing_files.index(current_fix)
                    existing_fix = self.fixing_files[idx]

                    # If the current FIC is older than the existing bic, then save it as a new FixingFile.
                    # Else it means the current fix is between the existing fix bic and fic.
                    # If the current BIC is older than the existing bic, then update the bic.
                    if self.commit_hashes.index(current_fix.fic) < self.commit_hashes.index(existing_fix.bic):
                        self.fixing_files.append(current_fix)
                    elif self.commit_hashes.index(current_fix.bic) < self.commit_hashes.index(existing_fix.bic):
                        existing_fix.bic = current_fix.bic

        return self.fixing_files.copy()

    def label(self) -> Generator[LabeledFile, None, None]:
        """
        Start labeling process
        :param files: a list of FixingFile objects
        :return: yields labeled files
        """

        if not self.fixing_files:
            yield None

        labeling = dict()
        for file in self.fixing_files:
            labeling.setdefault(file.filepath, list()).append(file)

        for commit in RepositoryMining(self.path_to_repo,
                                       from_commit=self.fixing_commits[-1],
                                       to_commit=self.commit_hashes[0],
                                       order='reverse').traverse_commits():

            for files in labeling.values():
                for file in files:
                    idx_fic = self.commit_hashes.index(file.fic)
                    idx_bic = self.commit_hashes.index(file.bic)
                    idx_commit = self.commit_hashes.index(commit.hash)

                    if idx_fic > idx_commit >= idx_bic:
                        label = LabeledFile.Label.FAILURE_PRONE
                    else:
                        # label = LabeledFile.Label.CLEAN
                        # uncomment and remove continue if want to support labeling for 'clean' files.
                        # If the case, update test_mine
                        continue

                    yield LabeledFile(filepath=file.filepath,
                                      commit=commit.hash,
                                      label=label,
                                      fixing_commit=file.fic)

                    if idx_commit == idx_bic:
                        labeling[file.filepath].remove(file)

            # Handle file renaming
            for modified_file in commit.modifications:
                filepath = modified_file.new_path

                for file in list(labeling.get(filepath, list())):
                    if self.commit_hashes.index(file.fic) > self.commit_hashes.index(
                            commit.hash) >= self.commit_hashes.index(file.bic):

                        if modified_file.change_type == ModificationType.ADD:
                            labeling[filepath].remove(file)
                        elif modified_file.change_type == ModificationType.RENAME:
                            file.filepath = modified_file.old_path
                        break

    def mine(self, labels: Set[str] = None, regex: str = None) -> Generator[LabeledFile, None, None]:
        """
        Mine the repository.

        :param labels: bug-related issues labels. If None, the default set of labels is used: {'bug', 'Bug',
        'bug :bug:', 'Bug - Medium', 'Bug - Low', 'Bug - Critical', 'ansible_bug', 'Type: Bug', 'Type: bug',
        'Type/Bug', 'type: bug 🐛', 'type:bug', 'type: bug', 'type/bug', 'kind/bug', 'kind/bugs', 'bug/bugfix',
        'bugfix', 'critical-bug', '01 type: bug', 'bug_report', 'minor-bug'}
        :param regex: the regular expression used to identify fixing-commits from commits message. If None, the default
        regex is used, that is: r'(bug|fix|error|crash|problem|fail|defect|patch)'
        :return: yields LabeledFile objects
        """

        if not labels:
            labels = BUG_RELATED_LABELS

        if not regex:
            regex = r'(bug|fix|error|crash|problem|fail|defect|patch)'

        self.get_fixing_commits_from_closed_issues(labels)
        self.get_fixing_commits_from_commit_messages(regex)
        self.get_fixing_files()

        for labeled_file in self.label():
            yield labeled_file

    def sort_commits(self, commits: List[str]):
        """
        Sort fixing commits in chronological order
        :commits: the list of commits sha to order
        """
        sorted_commits = [sha for sha in self.commit_hashes if sha in commits]
        commits.clear()
        commits.extend(sorted_commits)
