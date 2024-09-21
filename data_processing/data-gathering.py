import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from github import Github
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()

# Constants
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME", "home-assistant/core")
BATCH_SIZE = 100
ISSUE_BATCHES_DIR = "home_assistant_issue_batches"


# Pydantic models
class Comment(BaseModel):
    id: int
    body: str
    created_at: datetime
    updated_at: datetime
    user: str


class Issue(BaseModel):
    number: int
    title: str
    body: Optional[str]
    state: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    comments: List[Comment] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class Repository(BaseModel):
    name: str
    issues: List[Issue] = Field(default_factory=list)


def initialize_github_client() -> Github:
    """
    Initialize and return a PyGitHub client.

    Returns:
        Github: An authenticated PyGitHub client.

    Raises:
        ValueError: If GITHUB_TOKEN is not found in the environment or .env file.
    """
    if not GITHUB_TOKEN:
        raise ValueError(
            "GITHUB_TOKEN not found. Please set it in your environment or .env file."
        )
    return Github(GITHUB_TOKEN)


def get_stored_issue_numbers() -> Set[int]:
    """
    Retrieve the set of issue numbers that have already been stored.

    Returns:
        Set[int]: A set of issue numbers that have been previously stored.
    """
    stored_issues = set()
    for filename in os.listdir(ISSUE_BATCHES_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(ISSUE_BATCHES_DIR, filename), "r") as f:
                batch_data = json.load(f)
                stored_issues.update(issue["number"] for issue in batch_data["issues"])
    return stored_issues


def get_file_number() -> int:
    """
    Retrieve a new file number for the next batch of issues.

    Returns:
        int: The next file number to use for storing issues.
    """
    stored_number = []
    for filename in os.listdir(ISSUE_BATCHES_DIR):
        if filename.endswith(".json"):
            stored_number.append(int(filename.split("_")[1].split(".")[0]))
    return max(stored_number) + 1


def create_comment_model(comment: Any) -> Comment:
    """
    Create a Comment model from a GitHub comment object.

    Args:
        comment (Any): A GitHub comment object.

    Returns:
        Comment: A Comment model instance.
    """
    return Comment(
        id=comment.id,
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        user=comment.user.login,
    )


def create_issue_model(issue: Any, comments: List[Comment]) -> Issue:
    """
    Create an Issue model from a GitHub issue object and its comments.

    Args:
        issue (Any): A GitHub issue object.
        comments (List[Comment]): A list of Comment model instances.

    Returns:
        Issue: An Issue model instance.
    """
    return Issue(
        number=issue.number,
        title=issue.title,
        body=issue.body,
        state=issue.state,
        tags=[label.name for label in issue.get_labels()],
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        closed_at=issue.closed_at,
        comments=comments,
    )


def fetch_issue_comments(issue: Any) -> List[Comment]:
    """
    Fetch and create Comment models for all comments of an issue.

    Args:
        issue (Any): A GitHub issue object.

    Returns:
        List[Comment]: A list of Comment model instances.
    """
    return [create_comment_model(comment) for comment in issue.get_comments()]


def store_issue_batch(repository: Repository, batch_number: int) -> None:
    """
    Store a batch of issues as a JSON file.

    Args:
        repository (Repository): A Repository model instance containing the issues to store.
        batch_number (int): The current batch number.
    """
    filename = f"{ISSUE_BATCHES_DIR}/batch_{batch_number}.json"
    with open(filename, "w") as f:
        json.dump(repository.dict(), f, default=str)
    print(f"Stored batch {batch_number} with {len(repository.issues)} issues")


def fetch_and_store_issues(repo_name: str) -> None:
    """
    Fetch issues from a GitHub repository and store them in batches.

    This function fetches issues that haven't been stored yet, creates Issue models
    for them (including their comments), and stores them in batch files.

    Args:
        repo_name (str): The name of the GitHub repository to fetch issues from.
    """
    github_client = initialize_github_client()
    repo = github_client.get_repo(repo_name)
    issues = repo.get_issues(state="all")

    os.makedirs(ISSUE_BATCHES_DIR, exist_ok=True)

    stored_issues = get_stored_issue_numbers()
    batch_number = 1

    while True:
        repository = Repository(name=repo_name)
        for issue in issues:
            if issue.number in stored_issues:
                print(f"Skipping issue #{issue.number}")
                continue

            print(f"Fetching issue #{issue.number}")
            comments = fetch_issue_comments(issue)
            issue_model = create_issue_model(issue, comments)
            repository.issues.append(issue_model)

            if len(repository.issues) >= BATCH_SIZE:
                break

        if not repository.issues:
            break  # No more issues to fetch

        number = get_file_number()
        print(f"Storing new batch {number} with {len(repository.issues)} issues")
        store_issue_batch(repository, number)
        stored_issues.update(issue.number for issue in repository.issues)
        batch_number += 1
        break


def load_all_issues(repo_name: str) -> Repository:
    """
    Load all stored issues for a repository from batch files.

    Args:
        repo_name (str): The name of the GitHub repository.

    Returns:
        Repository: A Repository model instance containing all stored issues.
    """
    repository = Repository(name=repo_name)

    for filename in sorted(os.listdir(ISSUE_BATCHES_DIR)):
        if filename.endswith(".json"):
            with open(os.path.join(ISSUE_BATCHES_DIR, filename), "r") as f:
                batch_data = json.load(f)
                batch_repo = Repository.parse_obj(batch_data)
                repository.issues.extend(batch_repo.issues)

    return repository


def main() -> None:
    """
    Main function to orchestrate the fetching, storing, and loading of GitHub issues.
    """
    try:
        fetch_and_store_issues(REPO_NAME)
        repository = load_all_issues(REPO_NAME)

        print(f"Total issues retrieved: {len(repository.issues)}")

        # Example: Print titles of first 5 issues and their comment counts
        for issue in repository.issues[:5]:
            print(
                f"Issue #{issue.number}: {issue.title} (Comments: {len(issue.comments)})"
            )

    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
