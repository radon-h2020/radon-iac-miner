# !/usr/bin/python
# coding=utf-8

import os
import unittest

from dotenv import load_dotenv

from pydriller import GitRepository
from radonminer.files import FixingFile, FailureProneFile
from radonminer.mining.ansible import AnsibleMiner

ROOT = os.path.realpath(__file__).rsplit(os.sep, 2)[0]
PATH_TO_REPO = os.path.join(ROOT, 'test_data', 'adriagalin', 'ansible.motd')


class RepositoryMinerTestCase(unittest.TestCase):

    git_repo = None

    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.git_repo = GitRepository(PATH_TO_REPO)
        cls.git_repo.reset()
        cls.git_repo.checkout('3a8d9b7ed430a3367d8d8616e0ba5d2bddb07b9e')
        cls.repo_miner = AnsibleMiner(access_token=os.getenv('GITHUB_ACCESS_TOKEN'),
                                      path_to_repo=PATH_TO_REPO,
                                      host='github',
                                      full_name_or_id='adriagalin/ansible.motd',
                                      branch='master')

    @classmethod
    def tearDownClass(cls):
        if cls.git_repo:
            cls.git_repo.reset()

    def setUp(self) -> None:
        self.repo_miner.fixing_commits = list()  # reset list of fixing-commits
        self.repo_miner.exclude_commits = set()  # reset list of commits to exclude
        self.repo_miner.exclude_fixing_files = list()  # reset list of fixing-files to exclude

    def test_get_fixing_commits_from_closed_issues(self):
        hashes = self.repo_miner.get_fixing_commits_from_closed_issues({'bug'})
        assert not hashes

    def test_get_fixing_commits_from_commit_messages(self):
        hashes = self.repo_miner.get_fixing_commits_from_commit_messages(regex=r'(bug|fix|error|crash|problem|fail'
                                                                               r'|defect|patch)')
        assert self.repo_miner.fixing_commits == ['72377bb59a484ac7c6c6954ce6bf796eb6143f86',
                                                  'be34c67e75c2788742f3e87313a0b646af1006db',
                                                  'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703']

        assert set(hashes) == {'be34c67e75c2788742f3e87313a0b646af1006db',
                               'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703',
                               '72377bb59a484ac7c6c6954ce6bf796eb6143f86'}

    def test_get_fixing_commits_from_commit_messages_with_exclude_commits(self):
        self.repo_miner.exclude_commits = {'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'}

        hashes = self.repo_miner.get_fixing_commits_from_commit_messages(regex=r'(bug|fix|error|crash|problem|fail'
                                                                               r'|defect|patch)')

        assert self.repo_miner.fixing_commits == ['72377bb59a484ac7c6c6954ce6bf796eb6143f86',
                                                  'be34c67e75c2788742f3e87313a0b646af1006db']

        assert set(hashes) == {'be34c67e75c2788742f3e87313a0b646af1006db',
                               '72377bb59a484ac7c6c6954ce6bf796eb6143f86'}

    def test_discard_non_iac_fixing_commits(self):
        fixing_commits = ['9cf96c3670b65b825d3ebc2575b0aa300f3e7bf8',
                          '72377bb59a484ac7c6c6954ce6bf796eb6143f86',
                          'be34c67e75c2788742f3e87313a0b646af1006db',
                          'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703']

        self.repo_miner.discard_undesired_fixing_commits(fixing_commits)

        assert set(fixing_commits) == {'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703',
                                       '72377bb59a484ac7c6c6954ce6bf796eb6143f86',
                                       'be34c67e75c2788742f3e87313a0b646af1006db'}

    def test_get_fixing_files(self):
        self.repo_miner.get_fixing_commits_from_commit_messages(
            regex=r'(bug|fix|error|crash|problem|fail|defect|patch)')
        fixing_files = self.repo_miner.get_fixing_files()

        assert fixing_files
        assert len(fixing_files) == 3

        assert fixing_files[0].filepath == os.path.join('meta', 'main.yml')
        assert fixing_files[0].fic == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'  # Jun 27, 2019
        assert fixing_files[0].bic == 'e3a4420937cd9061a6525d541d525ac2167d7322'  # Aug 26, 2016

        assert fixing_files[1].filepath == os.path.join('tasks', 'main.yml')
        assert fixing_files[1].fic == 'be34c67e75c2788742f3e87313a0b646af1006db'  # Jun 20, 2019
        assert fixing_files[1].bic == '033cd106f8c3f552d98438bf06cb38e7b8f4fbfd'  # Aug 13, 2015

        assert fixing_files[2].filepath == os.path.join('meta', 'main.yml')
        assert fixing_files[2].fic == '72377bb59a484ac7c6c6954ce6bf796eb6143f86'  # Aug 15, 2015
        assert fixing_files[2].bic == '033cd106f8c3f552d98438bf06cb38e7b8f4fbfd'  # Aug 13, 2015

    def test_get_fixing_files_with_exclude_commits(self):
        self.repo_miner.exclude_commits = {'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'}

        self.repo_miner.get_fixing_commits_from_commit_messages(
            regex=r'(bug|fix|error|crash|problem|fail|defect|patch)')
        fixing_files = self.repo_miner.get_fixing_files()

        assert fixing_files
        assert len(fixing_files) == 2

        assert fixing_files[0].filepath == os.path.join('tasks', 'main.yml')
        assert fixing_files[0].fic == 'be34c67e75c2788742f3e87313a0b646af1006db'  # Jun 20, 2019
        assert fixing_files[0].bic == '033cd106f8c3f552d98438bf06cb38e7b8f4fbfd'  # Aug 13, 2015

        assert fixing_files[1].filepath == os.path.join('meta', 'main.yml')
        assert fixing_files[1].fic == '72377bb59a484ac7c6c6954ce6bf796eb6143f86'  # Aug 15, 2015
        assert fixing_files[1].bic == '033cd106f8c3f552d98438bf06cb38e7b8f4fbfd'  # Aug 13, 2015

    def test_get_fixing_files_with_exclude_files(self):

        self.repo_miner.exclude_fixing_files = [
            FixingFile(filepath=os.path.join('meta', 'main.yml'),
                       fic='f9ac8bbc68dedb742e5825c5cf47bca8e6f71703',
                       bic='e3a4420937cd9061a6525d541d525ac2167d7322')
        ]

        self.repo_miner.get_fixing_commits_from_commit_messages(r'(bug|fix|error|crash|problem|fail|defect|patch)')
        fixing_files = self.repo_miner.get_fixing_files()

        assert fixing_files
        assert len(fixing_files) == 2

        assert fixing_files[0].filepath == os.path.join('tasks', 'main.yml')
        assert fixing_files[0].fic == 'be34c67e75c2788742f3e87313a0b646af1006db'  # Jun 20, 2019
        assert fixing_files[0].bic == '033cd106f8c3f552d98438bf06cb38e7b8f4fbfd'  # Aug 13, 2015

        assert fixing_files[1].filepath == os.path.join('meta', 'main.yml')
        assert fixing_files[1].fic == '72377bb59a484ac7c6c6954ce6bf796eb6143f86'  # Aug 15, 2015
        assert fixing_files[1].bic == '033cd106f8c3f552d98438bf06cb38e7b8f4fbfd'  # Aug 13, 2015

    def test_mine(self):
        self.repo_miner.fixing_commits = list()  # reset list of fixing-commits
        labeled_files = [labeled_file for labeled_file in
                         self.repo_miner.mine(labels={'bug'}, regex=r'(bug|fix|error|crash|problem|fail|defect|patch)')]

        assert labeled_files
        assert len(labeled_files) == 37

        # First meta/main
        assert labeled_files[0].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[0].commit == '84c7e12d2510db7e0ee20cc343c0e1676de41bc2'
        assert labeled_files[0].fixing_commit == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'

        assert labeled_files[1].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[1].commit == '4e5c8866ae7ce49fdb07d9f0306a7467cec175fb'
        assert labeled_files[1].fixing_commit == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'

        assert labeled_files[2].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[2].commit == 'be34c67e75c2788742f3e87313a0b646af1006db'
        assert labeled_files[2].fixing_commit == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'

        assert labeled_files[3].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[3].commit == '5a23742e4f2cc3cc579773b96dfc29ffcd7f6ab4'
        assert labeled_files[3].fixing_commit == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'

        # First tasks/main
        assert labeled_files[4].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[4].commit == '5a23742e4f2cc3cc579773b96dfc29ffcd7f6ab4'
        assert labeled_files[4].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'

        assert labeled_files[5].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[5].commit == '9cf96c3670b65b825d3ebc2575b0aa300f3e7bf8'
        assert labeled_files[5].fixing_commit == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'

        assert labeled_files[6].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[6].commit == '9cf96c3670b65b825d3ebc2575b0aa300f3e7bf8'
        assert labeled_files[6].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'

        assert labeled_files[7].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[7].commit == '81dfa955dfa0dfe3e72a0c77a057be256894c6a1'
        assert labeled_files[7].fixing_commit == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'

        assert labeled_files[8].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[8].commit == '81dfa955dfa0dfe3e72a0c77a057be256894c6a1'
        assert labeled_files[8].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'

        assert labeled_files[9].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[9].commit == '0253259a2e0c39202d56e2f45f19d6878de07404'
        assert labeled_files[9].fixing_commit == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'

        assert labeled_files[10].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[10].commit == '0253259a2e0c39202d56e2f45f19d6878de07404'
        assert labeled_files[10].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'

        # Last meta/main
        assert labeled_files[11].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[11].commit == 'e3a4420937cd9061a6525d541d525ac2167d7322'
        assert labeled_files[11].fixing_commit == 'f9ac8bbc68dedb742e5825c5cf47bca8e6f71703'

        assert labeled_files[12].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[12].commit == 'e3a4420937cd9061a6525d541d525ac2167d7322'
        assert labeled_files[12].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'

        # ...

        assert labeled_files[31].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[31].commit == 'b0e8f1f7c7f4412d8f389cbd68d52b0090be8620'
        assert labeled_files[31].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'

        assert labeled_files[32].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[32].commit == '72377bb59a484ac7c6c6954ce6bf796eb6143f86'
        assert labeled_files[32].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'

        # First meta/main
        assert labeled_files[33].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[33].commit == 'be90e54c969797b7d92594a92126df9bd8f8683a'
        assert labeled_files[33].fixing_commit == '72377bb59a484ac7c6c6954ce6bf796eb6143f86'

        assert labeled_files[34].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[34].commit == 'be90e54c969797b7d92594a92126df9bd8f8683a'
        assert labeled_files[34].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'

        # Last meta/main
        assert labeled_files[35].filepath == os.path.join('meta', 'main.yml')
        assert labeled_files[35].commit == '033cd106f8c3f552d98438bf06cb38e7b8f4fbfd'
        assert labeled_files[35].fixing_commit == '72377bb59a484ac7c6c6954ce6bf796eb6143f86'

        # Last tasks/main
        assert labeled_files[36].filepath == os.path.join('tasks', 'main.yml')
        assert labeled_files[36].commit == '033cd106f8c3f552d98438bf06cb38e7b8f4fbfd'
        assert labeled_files[36].fixing_commit == 'be34c67e75c2788742f3e87313a0b646af1006db'


if __name__ == '__main__':
    unittest.main()
