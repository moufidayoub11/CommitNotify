#!/bin/python3

import os
import requests
import time
from plyer import notification

# Constants
STATE_FILE = os.path.expanduser("~/.commitnotify_state.txt")
CRED_FILE = os.path.expanduser("~/.github_credentials.txt")
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"

class GitHubCommitNotifier:
	def __init__(self):
		self.github_username = None
		self.repo_name = None
		self.access_token = None
		self.running = True

	def printf_with_color(self, text, color):
			print(f"{color}{text}{RESET}")

	def read_credentials(self):
		if os.path.isfile(CRED_FILE):
			with open(CRED_FILE, "r") as state_file:
				credentials = dict(line.strip().split("=") for line in state_file)
			return credentials
		else:
			return None

	def write_credentials(self, credentials):
		with open(CRED_FILE, "w") as state_file:
			for key, value in credentials.items():
				state_file.write(f"{key}={value}\n")

	def setup_github_credentials(self):
		existing_credentials = self.read_credentials()

		if existing_credentials:
			use_existing = (
				input("Do you want to use the existing credentials (yes/no)? ")
				.strip()
				.lower()
			)
			if use_existing in ["no", "n"]:
				self.github_username = input("Enter your new GitHub username: ")
				self.repo_name = input("Enter the new repository name: ")
				self.access_token = input("Enter your new GitHub access token: ")

				existing_credentials = {
					"GITHUB_USERNAME": self.github_username,
					"REPO_NAME": self.repo_name,
					"ACCESS_TOKEN": self.access_token,
				}
				self.write_credentials(existing_credentials)

			else:
				# Use existing credentials
				self.github_username = existing_credentials.get("GITHUB_USERNAME", "")
				self.repo_name = existing_credentials.get("REPO_NAME", "")
				self.access_token = existing_credentials.get("ACCESS_TOKEN", "")
		else:
			self.github_username = input("Enter your GitHub username: ")
			self.repo_name = input("Enter the repository name: ")
			self.access_token = input("Enter your GitHub access token: ")

			# Write the credentials to the state file
			credentials = {
				"GITHUB_USERNAME": self.github_username,
				"REPO_NAME": self.repo_name,
				"ACCESS_TOKEN": self.access_token,
			}
			self.write_credentials(credentials)

		if os.name == "nt":
			_ = os.system("cls")
		else:
			_ = os.system("clear")

	def fetch_commits_branch(self, branch):
		url = f"https://api.github.com/repos/{self.github_username}/{self.repo_name}/commits/{branch}"
		headers = {"Authorization": f"token {self.access_token}"}
		response = requests.get(url, headers=headers)

		if response.status_code != 200:
			self.printf_with_color("Failed to fetch commit information. Exiting...", RED)
			exit(response.status_code)

		result = response.json()
		if not isinstance(result, list):
			result = [result]
		return result

	def fetch_branch(self):
		url = f"https://api.github.com/repos/{self.github_username}/{self.repo_name}/branches"
		headers = {"Authorization": f"token {self.access_token}"}
		response = requests.get(url, headers=headers)
		if response.status_code != 200:
			self.printf_with_color("Failed to fetch commit information. Exiting...", RED)
			exit(response.status_code)
		branches_data = response.json()

		return branches_data

	def fetch_all_commits(self):
		branches = self.fetch_branch()
		all_commits = []

		for branch in branches:
			branch_name = branch['name']
			commits = self.fetch_commits_branch(branch_name)

			for commit in commits:
				commit['branch'] = branch_name

			all_commits.extend(commits)

		all_commits.sort(key=lambda x: x['commit']['committer']['date'], reverse=True)

		return all_commits

	def fetch_commit_info(self, commit_sha):
		url = f"https://api.github.com/repos/{self.github_username}/{self.repo_name}/commits/{commit_sha}"
		headers = {"Authorization": f"token {self.access_token}"}
		response = requests.get(url, headers=headers)

		if response.status_code != 200:
			self.printf_with_color(f"Failed to fetch commit details for {commit_sha}. Skipping...", RED)
			return None

		return response.json()

	def read_state_file(self, file_path):
		try:
			with open(file_path, "r") as state_file:
				return state_file.read().strip()
		except FileNotFoundError:
			# If the file doesn't exist, create it with an empty string as the content
			with open(file_path, "w") as state_file:
				state_file.write("")
			return ""

	def get_newest_commits(self, commits):
		newest = []
		for commit in commits:
			commit_sha = commit["sha"]

			if commit_sha == self.last_commit_sha:
				break

			newest.append(commit)

		return newest[::-1]

	def send_notification(self, message):
		title = "New Commit Alert"
		notification.notify(title=title, message=message, app_name="CommitNotify")

	def run(self):
		self.setup_github_credentials()
		first = 1
		while self.running:
			all_commits = self.fetch_all_commits()
			self.last_commit_sha = self.read_state_file(STATE_FILE)

			newest_commit_sha = all_commits[0]["sha"]
			if self.last_commit_sha == "" or first:
				self.printf_with_color("Started recording commits ;)", GREEN)
				first = 0
				self.last_commit_sha = newest_commit_sha

			commits = self.get_newest_commits(all_commits)
			for commit in commits:
				commit_sha = commit["sha"]

				commit_message = commit["commit"]["message"]
				committer_name = commit["commit"]["committer"]["name"]
				branch_name = commit["branch"]

				commit_info = self.fetch_commit_info(commit_sha)
				if not commit_info:
					continue

				files_info = commit_info["files"]

				message = f"New commit by {committer_name} in {branch_name} branch:\n{commit_message}"
				self.send_notification(message)

				self.printf_with_color("=" * 50, CYAN)
				self.printf_with_color(
					f"New commit is made to {branch_name}"
					if branch_name
					else "New commit is made", MAGENTA
				)
				self.printf_with_color(f"Committer: {committer_name}", BLUE)
				self.printf_with_color(f"Commit message: {commit_message}", YELLOW)
				print("Changed files:")

				for file_info in files_info:
					file_status = file_info["status"]
					file_name = file_info["filename"]
					changes_url = file_info["blob_url"]

					color = RESET
					if file_status == 'added':
						color = GREEN
					elif file_status == 'modified':
						color = BLUE
					elif file_status == 'removed':
						color = RED
					self.printf_with_color(f"({file_status}) - {file_name}:", color)
					print(f"View changes: {changes_url}")

			with open(STATE_FILE, "w") as state_file:
				state_file.write(newest_commit_sha)

			time.sleep(10)

	def stop(self):
		self.running = False


if __name__ == "__main__":
	try:
		notifier = GitHubCommitNotifier()
		notifier.run()
	except KeyboardInterrupt:
		notifier.stop()
		exit(0)