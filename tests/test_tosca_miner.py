# !/usr/bin/python
# coding=utf-8

import os
import shutil
import unittest

from radonminer.files import FixingFile
from radonminer.mining.tosca import ToscaMiner


class RepositoryMinerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.path_to_tmp_dir = os.path.join(os.getcwd(), 'test_data', 'tmp')
        os.mkdir(cls.path_to_tmp_dir)
        os.environ["TMP_REPOSITORIES_DIR"] = cls.path_to_tmp_dir

        cls.repo_miner = ToscaMiner(url_to_repo='https://github.com/UoW-CPC/COLARepo.git', branch='master')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.path_to_tmp_dir)
        del os.environ["TMP_REPOSITORIES_DIR"]

    def setUp(self) -> None:
        self.repo_miner.fixing_commits = list()  # reset list of fixing-commits
        self.repo_miner.exclude_commits = set()  # reset list of commits to exclude
        self.repo_miner.exclude_fixing_files = list()  # reset list of fixing-files to exclude

    def test_get_fixing_commits_from_closed_issues(self):
        hashes = self.repo_miner.get_fixing_commits_from_closed_issues(labels={'bug'})
        assert not hashes

    def test_get_fixing_commits_from_commit_messages(self):
        self.repo_miner.get_fixing_commits_from_commit_messages(regex=r'(bug|fix|error|crash|problem|fail|defect|patch)')
        assert self.repo_miner.fixing_commits == ['3994a835f7417703810c95555bf3553b9dcaea9b',
                                                  '38b25771ff411cd05667325e8da3b68f4bb93e68']

    def test_discard_undesired_fixing_commits(self):
        fixing_commits = ['38b25771ff411cd05667325e8da3b68f4bb93e68',
                          '3994a835f7417703810c95555bf3553b9dcaea9b',
                          '31657f2047d486cb39daef9ffd0b5ec11d431b92']

        self.repo_miner.discard_undesired_fixing_commits(fixing_commits)

        assert fixing_commits == ['3994a835f7417703810c95555bf3553b9dcaea9b',
                                  '38b25771ff411cd05667325e8da3b68f4bb93e68']

    def test_get_fixing_files(self):
        self.repo_miner.get_fixing_commits_from_commit_messages(
            regex=r'(bug|fix|error|crash|problem|fail|defect|patch)')
        fixing_files = self.repo_miner.get_fixing_files()

        assert fixing_files
        assert len(fixing_files) == 8

        assert fixing_files[0].filepath == os.path.join('nodes', 'custom_types.yaml')
        assert fixing_files[0].fic == '38b25771ff411cd05667325e8da3b68f4bb93e68'

        assert fixing_files[1].filepath == os.path.join('policies', 'placement', 'requirement', 'location',
                                             'tosca_policy_Placement_Requirement_location.yaml')
        assert fixing_files[1].fic == '3994a835f7417703810c95555bf3553b9dcaea9b'

        assert fixing_files[2].filepath == os.path.join('policies', 'scalability', 'consumption',
                                                        'tosca_policy_scalability_comsumption.yaml')
        assert fixing_files[2].fic == '3994a835f7417703810c95555bf3553b9dcaea9b'

        assert fixing_files[3].filepath == os.path.join('policies', 'scalability', 'performance', 'completion',
                                             'tosca_policy_scalability_performance_completion.yaml')
        assert fixing_files[3].fic == '3994a835f7417703810c95555bf3553b9dcaea9b'

        assert fixing_files[4].filepath == os.path.join('templates', 'dataavenue.yaml')
        assert fixing_files[4].fic == '3994a835f7417703810c95555bf3553b9dcaea9b'

        assert fixing_files[5].filepath == os.path.join('templates', 'inycom.yaml')
        assert fixing_files[5].fic == '3994a835f7417703810c95555bf3553b9dcaea9b'

        assert fixing_files[6].filepath == os.path.join('templates', 'outlandish.yaml')
        assert fixing_files[6].fic == '3994a835f7417703810c95555bf3553b9dcaea9b'

        assert fixing_files[7].filepath == os.path.join('templates', 'repast.yaml')
        assert fixing_files[7].fic == '3994a835f7417703810c95555bf3553b9dcaea9b'

    def test_get_fixing_files_with_exclude_files(self):
        self.repo_miner.exclude_fixing_files = [
            FixingFile(filepath=os.path.join('policies', 'placement', 'requirement', 'location',
                                             'tosca_policy_Placement_Requirement_location.yaml'),
                       fic='3994a835f7417703810c95555bf3553b9dcaea9b',
                       bic='undefined'),
            FixingFile(filepath=os.path.join('policies', 'scalability', 'consumption',
                                             'tosca_policy_scalability_comsumption.yaml'),
                       fic='3994a835f7417703810c95555bf3553b9dcaea9b',
                       bic='undefined'),
            FixingFile(filepath=os.path.join('policies', 'scalability', 'performance', 'completion',
                                             'tosca_policy_scalability_performance_completion.yaml'),
                       fic='3994a835f7417703810c95555bf3553b9dcaea9b',
                       bic='undefined'),
            FixingFile(filepath=os.path.join('templates', 'dataavenue.yaml'),
                       fic='3994a835f7417703810c95555bf3553b9dcaea9b',
                       bic='undefined'),
            FixingFile(filepath=os.path.join('templates', 'inycom.yaml'),
                       fic='3994a835f7417703810c95555bf3553b9dcaea9b',
                       bic='undefined'),
            FixingFile(filepath=os.path.join('templates', 'repast.yaml'),
                       fic='3994a835f7417703810c95555bf3553b9dcaea9b',
                       bic='undefined')
        ]

        self.repo_miner.get_fixing_commits_from_commit_messages(r'(bug|fix|error|crash|problem|fail|defect|patch)')
        fixing_files = self.repo_miner.get_fixing_files()

        assert fixing_files
        assert len(fixing_files) == 2

        assert fixing_files[0].filepath == os.path.join('nodes', 'custom_types.yaml')
        assert fixing_files[0].fic == '38b25771ff411cd05667325e8da3b68f4bb93e68'
        assert fixing_files[0].bic == 'cf90b509825fc2f3cc87df72ce4c55b1cea909c5'

        assert fixing_files[1].filepath == os.path.join('templates', 'outlandish.yaml')
        assert fixing_files[1].fic == '3994a835f7417703810c95555bf3553b9dcaea9b'
        assert fixing_files[1].bic == 'cf90b509825fc2f3cc87df72ce4c55b1cea909c5'


if __name__ == '__main__':
    unittest.main()