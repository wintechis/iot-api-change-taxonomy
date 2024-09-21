import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import openai
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()

# Configuration
INPUT_FILE_PATH: str = "../interim/home_assistant_search_results.json"
OUTPUT_FILE_PATH: str = "home_assistant_api_analysis_results_updated.json"
OPENAI_API_KEY: str = os.getenv("OPENAI_KEY")
OPENAI_MODEL: str = "gpt-4o-mini-2024-07-18"
LLM_PROMPT: str = """
Analyze the following content and determine if it's related to API changes.
Consider the following criteria for your classification:
a. Network changes:
    - Protocol modifications (adding/removing features, modifying data packet structure)
    - Addressing and identification changes (device addressing, service identifiers, path structure)
b. Device changes:
    - Data exchange patterns (communication method interface, information retrieval method)
    - Access control (altering access methods, authentication, authorization)
c. Communication changes between network and device
d. Data changes:
    - Network (changed data packet)
    - Device (altered data structures, representations)
e. Other changes:
   - Mentions of specific API endpoints, methods, or parameters
   - Discussions about versioning, deprecation, or introduction of new API features
   - Changes in request/response formats, authentication methods, or rate limits
   - Mentions of breaking changes or backward compatibility issues
   - Updates to API documentation

Return a JSON object with the following structure:
{
    \"is_api_related\": boolean,
    \"confidence\": float,
    \"explanation\": string,
}
The 'is_api_related' field should be true if the content is primarily about API changes, false otherwise.
The 'confidence' field should be a float between 0 and 1, indicating your confidence in the assessment.
The 'explanation' field should provide a brief rationale for your decision, referencing specific parts of the content if applicable.
Content to analyze:
{content}

Ensure your response is a valid JSON object.

"""

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class Comment(BaseModel):
    """Represents a comment in an issue."""
    id: int
    body: str
    created_at: datetime
    updated_at: datetime
    user: str

class Match(BaseModel):
    """Represents a match in search results."""
    type: str
    matched_term: str
    score: float

class SearchResultItem(BaseModel):
    """Represents an individual search result item."""
    issue_number: int
    issue_title: str
    issue_body: Optional[str]
    issue_state: str
    issue_created_at: datetime
    issue_updated_at: datetime
    issue_closed_at: Optional[datetime]
    matches: List[Match]
    comments: List[Comment]

class SearchResults(BaseModel):
    """Represents the overall search results."""
    search_results: List[SearchResultItem] = Field(..., alias="search_results")

class SpecificChange(BaseModel):
    """Represents a specific API change."""
    category: str
    subcategory: str
    description: str

class APIChangeAnalysisResult(BaseModel):
    """Represents the result of API change analysis."""
    is_api_related: bool
    confidence: float = Field(description="Confidence in the assessment, between 0 and 1")
    explanation: str
    categories: List[str]
    specific_changes: List[SpecificChange]

class AnalysisRecord(BaseModel):
    """Represents a complete analysis record for an issue."""
    issue_number: int
    issue_title: str
    analysis_result: APIChangeAnalysisResult
    timestamp: datetime = Field(default_factory=datetime.utcnow)

def read_search_results(file_path: str) -> SearchResults:
    """
    Read and parse search results from a JSON file.

    Args:
        file_path (str): Path to the JSON file containing search results.

    Returns:
        SearchResults: Parsed search results.
    """
    with open(file_path, 'r') as file:
        data = json.load(file)
        return SearchResults(**data)

def analyze_content(content: str) -> APIChangeAnalysisResult:
    """
    Analyze content using OpenAI's API to determine if it's related to API changes.

    Args:
        content (str): The content to analyze.

    Returns:
        APIChangeAnalysisResult: The analysis result.
    """
    prompt = LLM_PROMPT.replace("{content}", content)
    response = openai_client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are an AI assistant specialized in analyzing software development discussions, particularly those related to API changes. Your task is to accurately determine if the given content is about API changes and provide a structured analysis."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        response_format=APIChangeAnalysisResult,
    )

    result = json.loads(response.choices[0].message.content)
    return APIChangeAnalysisResult(**result)

def load_existing_results(file_path: str) -> Dict[int, AnalysisRecord]:
    """
    Load existing analysis results from a JSON file.

    Args:
        file_path (str): Path to the JSON file containing existing results.

    Returns:
        Dict[int, AnalysisRecord]: A dictionary of existing analysis records, keyed by issue number.
    """
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
            return {record['issue_number']: AnalysisRecord(**record) for record in data}
    return {}

def save_result(record: AnalysisRecord, file_path: str):
    """
    Save an analysis record to the output JSON file.

    Args:
        record (AnalysisRecord): The analysis record to save.
        file_path (str): Path to the output JSON file.
    """
    existing_results = load_existing_results(file_path)
    existing_results[record.issue_number] = record
    
    with open(file_path, 'w') as file:
        json.dump([record.dict() for record in existing_results.values()], file, default=str, indent=2)

def process_search_result(result: SearchResultItem) -> str:
    """
    Process a search result item and generate a content string for analysis.

    Args:
        result (SearchResultItem): The search result item to process.

    Returns:
        str: A formatted string containing the issue content for analysis.
    """
    issue_content = f"Title: {result.issue_title}\n\nBody: {result.issue_body or ''}\n\nComments:\n"
    for comment in result.comments:
        issue_content += f"{comment.user}: {comment.body}\n\n"
    return issue_content

def analyze_and_save_result(result: SearchResultItem, output_file_path: str):
    """
    Analyze a search result item and save the analysis.

    Args:
        result (SearchResultItem): The search result item to analyze.
        output_file_path (str): Path to the output JSON file.
    """
    issue_content = process_search_result(result)
    analysis = analyze_content(issue_content)
    
    record = AnalysisRecord(
        issue_number=result.issue_number,
        issue_title=result.issue_title,
        analysis_result=analysis
    )
    
    save_result(record, output_file_path)
    print_analysis_result(record)

def print_analysis_result(record: AnalysisRecord):
    """
    Print the analysis result to the console.

    Args:
        record (AnalysisRecord): The analysis record to print.
    """
    print(f"Issue #{record.issue_number}")
    print(f"Title: {record.issue_title}")
    print(f"Is API related: {record.analysis_result.is_api_related}")
    print(f"Confidence: {record.analysis_result.confidence}")
    print(f"Explanation: {record.analysis_result.explanation}")
    print(f"Categories: {record.analysis_result.categories}")
    print(f"Specific Changes: {record.analysis_result.specific_changes}")
    print(f"Result saved to {OUTPUT_FILE_PATH}")
    print("-" * 50)

def main():
    """
    Main function to orchestrate the API analysis workflow.
    """
    search_results = read_search_results(INPUT_FILE_PATH)
    existing_results = load_existing_results(OUTPUT_FILE_PATH)
    
    for result in search_results.search_results:
        if result.issue_number in existing_results:
            print(f"Skipping analysis for Issue #{result.issue_number} (already analyzed)")
            continue
        
        analyze_and_save_result(result, OUTPUT_FILE_PATH)
    
    print(f"All results saved to {OUTPUT_FILE_PATH}")

if __name__ == "__main__":
    main()