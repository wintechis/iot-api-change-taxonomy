import json
import os
from enum import Enum
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Constants
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL: str = "gpt-4o-mini-2024-07-18"
INPUT_FILE_PATH: str = (
    "../datasets/interim/iot_integrations_filtered.json"  # Replace with actual input file path
)
OUTPUT_FILE_PATH: str = (
    "../datasets/interim/IoT-IP-dataset_api_integrations.json"  # Replace with actual output file path
)


class APIType(str, Enum):
    """Enumeration of API types."""

    DEVICE_API = "DeviceApi"
    GATEWAY_API = "GatewayApi"
    PLATFORM_API = "PlatformApi"
    UNKNOWN_API = "UnknownApi"


# Fix to allow the enum to be serialized for the structured output of chatgpt
IoTAPITypes = [
    APIType.DEVICE_API,
    APIType.GATEWAY_API,
    APIType.PLATFORM_API,
    APIType.UNKNOWN_API,
]


class APITypeClassification(BaseModel):
    """Model for API type classification results."""

    api_type: str = Field(
        description="The detected api_type", json_schema_extra={"enum": IoTAPITypes}
    )
    confidence: float = Field(
        alias="api_taxonomy_class_confidence",
        description="Confidence of the classification",
        example=0.9,
    )
    explanation: str = Field(
        alias="api_taxonomy_class_explanation",
        description="Explanation of the classification",
        example="The issue is related to the configuration of the integration",
    )


class IntegrationInfo(BaseModel):
    """Model for integration information."""

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
    integration_type: Optional[APITypeClassification] = None


INTEGRATION_TYPE_PROMPT = """
Please repeat the prompt back as you understand it.
Specifics:
1. Determine if the API is a DeviceApi by identifying direct communication with a device, device-specific protocols, or local network access.
2. Identify a GatewayApi if the API interacts through a gateway, referencing a hub/bridge/gateway device, vendor-specific ecosystem, or local network communication.
3. Classify as PlatformApi if the API supports multiple devices across different vendors using a shared API, cloud services, OAuth authentication, or REST APIs.
4. Use UnknownApi if none of the above categories apply.

Return a JSON object with the following structure:
{
"api_type": string,
"confidence": float,
"explanation": string
}

The 'api_type' field should be one of 'DeviceApi', 'GatewayApi', 'PlatformApi', or 'UnknownApi'.
The 'confidence' field should be a float between 0 and 1, indicating your confidence in the assessment.
The 'explanation' field should provide a brief rationale for your decision, referencing specific parts of the content if applicable.

Content to analyze:
{content}
Ensure your response is a valid JSON object and nothing else.
"""


def create_openai_client() -> OpenAI:
    """Create and return an OpenAI client."""
    return OpenAI(api_key=OPENAI_API_KEY)


def analyze_content(content: str, client: OpenAI) -> APITypeClassification:
    """
    Analyze the content and classify the API type using OpenAI.

    Args:
        content (str): The content to analyze.
        client (OpenAI): The OpenAI client.

    Returns:
        APITypeClassification: The classified API type.
    """
    prompt = INTEGRATION_TYPE_PROMPT.replace("{content}", content)
    response = client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are an AI tasked with classifying APIs into four categories based on the content provided. The categories are DeviceApi, GatewayApi, PlatformApi, and UnknownApi.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        response_format=APITypeClassification,
    )

    result = json.loads(response.choices[0].message.content)
    return APITypeClassification(**result)


def load_integrations(file_path: str) -> List[IntegrationInfo]:
    """
    Load integrations from a JSON file.

    Args:
        file_path (str): Path to the JSON file.

    Returns:
        List[IntegrationInfo]: List of loaded integrations.
    """
    with open(file_path, "r") as f:
        data = json.load(f)
    return [IntegrationInfo(**integration) for integration in data["search_results"]]


def save_integrations(integrations: List[IntegrationInfo], file_path: str):
    """
    Save integrations to a JSON file.

    Args:
        integrations (List[IntegrationInfo]): List of integrations to save.
        file_path (str): Path to the output JSON file.
    """
    data = {"search_results": [integration.dict() for integration in integrations]}
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def process_integrations(
    integrations: List[IntegrationInfo], client: OpenAI
) -> List[IntegrationInfo]:
    """
    Process integrations by analyzing their content and classifying API types.

    Args:
        integrations (List[IntegrationInfo]): List of integrations to process.
        client (OpenAI): The OpenAI client.

    Returns:
        List[IntegrationInfo]: List of processed integrations.
    """
    for integration in integrations:
        integration.integration_type = analyze_content(integration.content, client)
        print(f"Processed {integration.api}: {integration.integration_type}")
    return integrations


def main():
    """Main function to orchestrate the API classification workflow."""
    client = create_openai_client()
    integrations = load_integrations(INPUT_FILE_PATH)
    processed_integrations = process_integrations(integrations, client)
    save_integrations(processed_integrations, OUTPUT_FILE_PATH)
    print(
        f"Processed {len(processed_integrations)} integrations. Results saved to {OUTPUT_FILE_PATH}"
    )


if __name__ == "__main__":
    main()
