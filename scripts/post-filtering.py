from typing import List, Optional
from pydantic import BaseModel, Field
import json

# Constants
INPUT_BATCH_FILE_PATH = "../external/home_assistant_issue_batches/batch_1184.json"
INPUT_INTEGRATIONS_FILE_PATH = "./iot_integrations_updated.json"
OUTPUT_CHANGE_REPORTS_FILE_PATH = "./iot_api_change_reports.json"
OUTPUT_APIS_FILE_PATH = "./iot_apis.json"
INTEGRATION_BASE_URL = "https://www.home-assistant.io/integrations/"

class IntegrationInfo(BaseModel):
    """Represents information about a Home Assistant integration."""
    api: str
    introduction_version: str
    iot_class: str
    content: str
    categories: List[str]
    deployment_type: Optional[str] = Field(
        default="", description="Type of integration (local or cloud)"
    )
    communication_mechanism: Optional[str] = Field(
        default="", description="Communication mechanism used by the integration"
    )

class Comment(BaseModel):
    """Represents a comment on a change report."""
    id: int
    body: str

    class Config:
        extra = "allow"

class ChangeReport(BaseModel):
    """Represents a change report for Home Assistant integrations."""
    number: int
    title: str
    body: Optional[str]
    comments: List[Comment]
    involved_apis: List[str] = []
    tags: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"

def load_json_file(file_path: str) -> dict:
    """
    Loads and returns the content of a JSON file.

    Args:
        file_path (str): The path to the JSON file.

    Returns:
        dict: The parsed JSON content.
    """
    with open(file_path, "r") as file:
        return json.load(file)

def save_json_file(file_path: str, data: List[dict]) -> None:
    """
    Saves data to a JSON file.

    Args:
        file_path (str): The path to save the JSON file.
        data (List[dict]): The data to be saved.
    """
    with open(file_path, "w") as file:
        json.dump(data, file, indent=2)

def filter_reports_by_apis(reports: List[ChangeReport], apis: List[str]) -> List[ChangeReport]:
    """
    Filters change reports based on the APIs involved.

    Args:
        reports (List[ChangeReport]): List of change reports to filter.
        apis (List[str]): List of APIs to filter by.

    Returns:
        List[ChangeReport]: Filtered list of change reports.
    """
    return [report for report in reports if any(api in apis for api in report.involved_apis)]

def filter_integrations_by_apis(integrations: List[IntegrationInfo], apis: List[str]) -> List[IntegrationInfo]:
    """
    Filters integrations based on the APIs.

    Args:
        integrations (List[IntegrationInfo]): List of integrations to filter.
        apis (List[str]): List of APIs to filter by.

    Returns:
        List[IntegrationInfo]: Filtered list of integrations.
    """
    return [integration for integration in integrations if integration.api in apis]

def extract_integration_uris_from_tags(tags: List[str]) -> List[str]:
    """
    Extracts integration URIs from tags.

    Args:
        tags (List[str]): List of tags to process.

    Returns:
        List[str]: List of integration URIs.
    """
    return [
        f"{INTEGRATION_BASE_URL}{tag.split(': ')[1]}"
        for tag in tags
        if tag.startswith("integration:")
    ]

def main() -> None:
    """
    Main function to process Home Assistant integration data and change reports.
    """
    # Load data
    change_reports_data = load_json_file(INPUT_BATCH_FILE_PATH)
    integrations_data = load_json_file(INPUT_INTEGRATIONS_FILE_PATH)

    # Create objects
    change_reports = [ChangeReport(**report) for report in change_reports_data['issues']]
    integrations = [IntegrationInfo(**integration) for integration in integrations_data['search_results']]

    # Process data
    integration_apis = [integration.api for integration in integrations]
    
    for report in change_reports:
        report.involved_apis = extract_integration_uris_from_tags(report.tags)

    # Filter data
    filtered_change_reports = filter_reports_by_apis(change_reports, integration_apis)
    filtered_integrations = filter_integrations_by_apis(integrations, integration_apis)

    # Save results
    save_json_file(OUTPUT_CHANGE_REPORTS_FILE_PATH, [report.dict() for report in filtered_change_reports])
    save_json_file(OUTPUT_APIS_FILE_PATH, [integration.dict() for integration in filtered_integrations])

if __name__ == "__main__":
    main()