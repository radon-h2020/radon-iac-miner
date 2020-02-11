import git
import os
import pandas as pd
import shutil
import sys

path = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.append(path)

from pathlib import Path
from pydriller.repository_mining import GitRepository, RepositoryMining

from iacminer.entities.release import Release
from iacminer.miners.commits import CommitsMiner
from iacminer.miners.metrics import MetricsMiner
from iacminer.utils import load_repositories

DESTINATION_PATH = os.path.join('data', 'metrics.csv')

class Main():

    def __init__(self, repository: str):
        
        self.repository = repository

        author = repository.split('/')[0]
        self.repo_name = repository.split('/')[1]
        self.root_path = str(Path(f'repositories/{author}'))
        self.repo_path = os.path.join(self.root_path, self.repo_name)

        self.clone_repo()

        self.commits_miner = CommitsMiner(self.__git_repo)
        self.metrics_miner = MetricsMiner()

    def delete_repo(self):
        if os.path.isdir(self.root_path):
            shutil.rmtree(self.root_path)

    def clone_repo(self):
        self.delete_repo()
        os.makedirs(self.root_path)

        git.Git(self.root_path).clone(f'https://github.com/{self.repository}.git', branch='master')
        git_repo = GitRepository(self.repo_path)

        self.__git_repo = git_repo
    
    def get_content(self, filepath):
        with open(os.path.join(self.repo_path, filepath), 'r') as f:
            return f.read()

    def save(self, filepath:str, metadata:dict, process_metrics:dict, product_metrics:dict):
        
        filepath = str(Path(filepath))
        
        metrics = metadata
        metrics.update(product_metrics)

        # Saving process metrics
        metrics['commits_count'] = process_metrics[0].get(filepath, 0)
        metrics['contributors_count'] = process_metrics[1].get(filepath, {}).get('contributors_count', 0)
        metrics['minor_contributors_count'] = process_metrics[1].get(filepath, {}).get('minor_contributors_count', 0)
        metrics['highest_experience'] = process_metrics[2].get(filepath, 0)
        metrics['history_complexity'] = process_metrics[3].get(filepath, 0)
        metrics['median_hunks_count'] = process_metrics[4].get(filepath, 0)
        metrics['total_added_loc'] = process_metrics[5].get(filepath, {}).get('added', 0)
        metrics['total_removed_loc'] = process_metrics[5].get(filepath, {}).get('removed', 0)

        dataset = pd.DataFrame()
        
        if os.path.isfile(DESTINATION_PATH):
            with open(DESTINATION_PATH, 'r') as in_file:
                dataset = pd.read_csv(in_file)

        dataset = dataset.append(metrics, ignore_index=True)

        with open(DESTINATION_PATH, 'w') as out:
            dataset.to_csv(out, mode='w', index=False)

    def run(self):
        
        releases = []
        releases_hash = []
        releases_date = []
        commits_hash = []

        for commit in RepositoryMining(self.repo_path, only_releases=True).traverse_commits():
            releases_hash.append(commit.hash)
            releases_date.append(str(commit.committer_date))

        for commit in RepositoryMining(self.repo_path, only_in_branch='master').traverse_commits():
            commits_hash.append(commit.hash)

        while releases_hash:
            hash = releases_hash.pop(0)
            date = releases_date.pop(0)
            idx = commits_hash.index(hash)
            releases.append(Release(commits_hash[0], commits_hash[idx], date))
            del commits_hash[:idx+1] 

        # Mine fixing commits
        self.commits_miner.mine()
        
        for release in releases:
            
            all_keys = set(self.commits_miner.defect_prone_files.keys()).union(set(self.commits_miner.defect_free_files.keys()))
            
            if release.end not in all_keys:
                continue
            
            process_metrics = self.metrics_miner.mine_process_metrics(self.repo_path, release.start, release.end)
            self.__git_repo.checkout(release.end)

            metadata = {
                    'repo': self.repository,
                    'release_start': release.start,
                    'release_end': release.end,
                    'release_date': release.date                    
            }

            for filepath in self.commits_miner.defect_prone_files.get(release.end, []):
                metadata['filepath'] = filepath
                metadata['defective'] = 'yes'

                try:
                    product_metrics = self.metrics_miner.mine_product_metrics(self.get_content(filepath))
                    self.save(filepath, metadata, process_metrics, product_metrics)
                except Exception:
                    print(f'An unknown error has occurred for file {self.repo_name}/{filepath}')

            for filepath in self.commits_miner.defect_free_files.get(release.end, []):
                metadata['filepath'] = filepath
                metadata['defective'] = 'no'

                try:
                    product_metrics = self.metrics_miner.mine_product_metrics(self.get_content(filepath))
                    self.save(filepath, metadata, process_metrics, product_metrics)
                except Exception:
                    print(f'An unknown error has occurred for file {self.repo_name}/{filepath}')

            self.__git_repo.reset()
        
        self.__git_repo.clear()
        self.delete_repo()

if __name__=='__main__':
    repos = load_repositories()
    
    for repo in repos:
        print(f'Mining repository: {repo}')
        Main(repo).run()