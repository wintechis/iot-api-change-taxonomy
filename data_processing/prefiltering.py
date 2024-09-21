import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process

# Constants
ISSUES_DIRECTORY: str = "../datasets/home_assistant_issue_batches"
SEARCH_THRESHOLD: int = 60
MAX_RESULTS_TO_DISPLAY: int = 10
OUTPUT_JSON_FILENAME: str = "home_assistant_issue_prefiltered.json"
API_CHANGE_SEARCH_TERMS: List[str] = [
    "api",
    "breaking",
    "call",
    "change",
    "compatibility",
    "deprecated",
    "deprecation",
    "documentation",
    "endpoint",
    "feature",
    "function",
    "improvement",
    "integration",
    "interface",
    "method",
    "migration",
    "modification",
    "parameter",
    "refactor",
    "request",
    "response",
    "schema",
    "update",
    "version",
]


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
    tags: List[str] = Field(default_factory=list)
    comments: List[Comment] = Field(default_factory=list)


class Repository(BaseModel):
    name: str
    issues: List[Issue] = Field(default_factory=list)


class SearchResult(BaseModel):
    issue: Issue
    matches: List[Dict[str, Any]]


class Match(BaseModel):
    type: str
    matched_term: str
    score: float


class SearchResultItem(BaseModel):
    number: int
    title: str
    body: Optional[str]
    state: str
    created: datetime
    updated: datetime
    closed: Optional[datetime]
    matches: List[Match]
    comments: List[Comment]
    tags: List[str] = Field(default_factory=list)


class SearchResults(BaseModel):
    search_results: List[SearchResultItem] = Field(..., alias="search_results")


def load_issues_from_directory(directory: str) -> Repository:
    """
    Load all issues from JSON files in the specified directory.

    Args:
        directory (str): The path to the directory containing JSON files with issue data.

    Returns:
        Repository: A Repository object containing all loaded issues.

    Raises:
        FileNotFoundError: If the specified directory does not exist.
        json.JSONDecodeError: If any of the JSON files are malformed.
    """
    repository = Repository(name="")

    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".json"):
            with open(os.path.join(directory, filename), "r") as file:
                batch_data = json.load(file)
                batch_repo = Repository.parse_obj(batch_data)
                repository.issues.extend(batch_repo.issues)

    print(f"Loaded {len(repository.issues)} issues")
    if repository.issues:
        print(f"Sample issue: {repository.issues[0]}")
    return repository


def perform_fuzzy_match(
    text: str, search_terms: List[str]
) -> Tuple[Optional[str], int]:
    """
    Perform a fuzzy match of search terms against the given text.

    Args:
        text (str): The text to search within.
        search_terms (List[str]): A list of search terms to match against.

    Returns:
        Tuple[Optional[str], int]: A tuple containing the matched term (or None if no match)
                                   and the match score.
    """
    match_result = process.extractOne(
        " ".join(search_terms), [text], scorer=fuzz.partial_ratio
    )
    if match_result:
        return match_result[0], match_result[1]
    return None, 0


def search_single_issue(
    issue: Issue, search_terms: List[str], threshold: int
) -> SearchResult:
    """
    Search for matches within a single issue and its comments.

    Args:
        issue (Issue): The issue to search within.
        search_terms (List[str]): A list of search terms to match against.
        threshold (int): The minimum score for a match to be considered valid.

    Returns:
        SearchResult: A SearchResult object containing the issue and any matches found.
    """
    issue_result = SearchResult(issue=issue, matches=[])

    # Search in issue title and body
    title_match, title_score = perform_fuzzy_match(issue.title, search_terms)
    body_match, body_score = perform_fuzzy_match(issue.body or "", search_terms)

    if title_match and title_score >= threshold:
        issue_result.matches.append(
            {"type": "title", "matched_term": title_match, "score": title_score}
        )
    if body_match and body_score >= threshold:
        issue_result.matches.append(
            {"type": "body", "matched_term": body_match, "score": body_score}
        )

    # Search in comments
    for comment in issue.comments:
        comment_match, comment_score = perform_fuzzy_match(comment.body, search_terms)
        if comment_match and comment_score >= threshold:
            issue_result.matches.append(
                {
                    "type": f"comment_{comment.id}",
                    "matched_term": comment_match,
                    "score": comment_score,
                }
            )

    return issue_result


def search_issues_and_comments(
    repository: Repository, search_terms: List[str], threshold: int
) -> List[SearchResult]:
    """
    Search for matches across all issues and comments in the repository.

    Args:
        repository (Repository): The repository containing issues to search.
        search_terms (List[str]): A list of search terms to match against.
        threshold (int): The minimum score for a match to be considered valid.

    Returns:
        List[SearchResult]: A list of SearchResult objects, sorted by highest match score.
    """
    results = []

    for issue in repository.issues:
        issue_result = search_single_issue(issue, search_terms, threshold)
        if issue_result.matches:
            results.append(issue_result)

    return sorted(
        results, key=lambda x: max(match["score"] for match in x.matches), reverse=True
    )


def print_search_results(results: List[SearchResult], max_results: int) -> None:
    """
    Print the top search results to the console.

    Args:
        results (List[SearchResult]): The list of search results to print.
        max_results (int): The maximum number of results to display.

    Returns:
        None
    """
    for i, result in enumerate(results[:max_results], 1):
        print(f"{i}. Issue #{result.issue.number}: {result.issue.title}")
        for match in result.matches:
            print(f"   Match type: {match['type']}")
            print(f"   Matched term: {match['matched_term']}")
            print(f"   Score: {match['score']}")
        print(f"   Issues: /issues/{result.issue.number}")
        print()


def save_results_to_json_file(results: List[SearchResult], filename: str) -> None:
    """
    Save the search results to a JSON file using the new Pydantic model.

    Args:
        results (List[SearchResult]): The list of search results to save.
        filename (str): The name of the file to save the results to.

    Returns:
        None

    Raises:
        IOError: If there's an error writing to the file.
    """
    search_result_items = [
        SearchResultItem(
            number=result.issue.number,
            title=result.issue.title,
            body=result.issue.body,
            state=result.issue.state,
            created=result.issue.created_at,
            updated=result.issue.updated_at,
            closed=result.issue.closed_at,
            matches=[Match(**match) for match in result.matches],
            comments=result.issue.comments,
            tags=result.issue.tags,
        )
        for result in results
    ]

    search_results = SearchResults(search_results=search_result_items)

    with open(filename, "w") as file:
        json.dump(search_results.dict(by_alias=True), file, indent=4, default=str)


def main() -> None:
    """
    Main function to execute the API change search process.

    This function loads issues, performs the search, prints results,
    and saves the results to a JSON file.

    Returns:
        None
    """
    repository = load_issues_from_directory(ISSUES_DIRECTORY)

    search_results = search_issues_and_comments(
        repository, API_CHANGE_SEARCH_TERMS, SEARCH_THRESHOLD
    )

    print(f"\nTop search results for API changes:")
    print_search_results(search_results, MAX_RESULTS_TO_DISPLAY)

    save_results_to_json_file(search_results, OUTPUT_JSON_FILENAME)
    print(f"\nFull results saved to {OUTPUT_JSON_FILENAME}")

    print(
        f"\nSearch complete. Found {len(search_results)} matching issues for {len(repository.issues)} issues."
    )


if __name__ == "__main__":
    main()
