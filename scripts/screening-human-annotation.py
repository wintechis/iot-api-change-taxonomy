import json
from datetime import datetime
from typing import List, Optional

import click
import typer
from pydantic import BaseModel, Field

app = typer.Typer()



class UserAnnotation(BaseModel):
    is_api_change: bool


class Issue(BaseModel):
    number: int
    title: str
    author_annotation: Optional[UserAnnotation] = None
    
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
        extra = "allow"

class AnnotationData(BaseModel):
    issues: List[Issue]
    progress: int = Field(default=0, ge=0)

def load_json(file_path: str) -> AnnotationData:
    with open(file_path, 'r') as f:
        data = json.load(f)
        
    if isinstance(data, list):
        return AnnotationData(issues=data, progress=0)
    
    if isinstance(data, dict):
        if "search_results" in data:
            return AnnotationData(issues=data["search_results"], progress=0)
    return AnnotationData(**data)

def save_json(data: AnnotationData, file_path: str):
    with open(file_path, 'w') as f:
        json.dump(data.dict(), f, indent=2, default=str)

@app.command()
def annotate_issues(
    input_file: str = typer.Option(..., help="Path to the input JSON file"),
    output_file: str = typer.Option(..., help="Path to save the annotated JSON file")
):
    """
    Review and annotate issues with user agreement on API-related recommendations.
    Allows restarting from the last processed issue.
    """
    data = load_json(input_file)
   
    for index in range(data.progress, len(data.issues)):
        

        issue = data.issues[index]
        typer.clear()
        typer.echo(f"Issue {index + 1} of {len(data.issues)}")
        typer.echo("=" * 40)  # Separator line
        typer.echo()
        typer.echo(f"Issue Title: {issue.title}")
        typer.echo("\n")
       
        action = typer.prompt(
            "Choose an action: (a)gree, (d)isagree, (s)kip, (q)uit",
            type=click.Choice(['a', 'd', 's', 'q']),
            show_choices=False
        )
       
        if action == 'q':
            data.progress = index
            save_json(data, output_file)
            typer.echo(f"Progress saved. You can restart later from issue {index + 1}.")
            raise typer.Exit()
       
        if action != 's':
            data.issues[index].author_annotation = UserAnnotation(
                is_api_change=action == 'a'
            )
        data.progress = index + 1
        save_json(data, output_file)
   
    data.progress = 0  # Reset progress after completion
    save_json(data, output_file)
    typer.echo(f"All issues processed. Annotated data has been saved to {output_file}")

if __name__ == "__main__":
    app()