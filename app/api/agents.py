from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.models.models import User
from typing import List
import os
from pathlib import Path

router = APIRouter()

# Agent prompts directory
PROMPTS_DIR = Path("app/agents/prompts")

# Define all available agents
AVAILABLE_AGENTS = [
    {"id": "validation", "name": "Validation Agent", "file": "validation.md", "description": "High-speed plate validation and OCR verification"},
    {"id": "auditor", "name": "Forensic Auditor", "file": "auditor.md", "description": "Quality control and semantic validation"},
    {"id": "orchestrator", "name": "Orchestrator", "file": "prompts.py", "description": "Case management and workflow routing"},
]

@router.get("/agents")
async def list_agents(current_user: User = Depends(get_current_user)):
    """
    Get list of all available agents with their metadata.
    """
    agents = []
    for agent_def in AVAILABLE_AGENTS:
        agent_path = PROMPTS_DIR / agent_def["file"]
        
        # Check if file exists
        exists = agent_path.exists()
        
        # Read prompt content if exists
        prompt_content =  ""
        if exists and agent_path.suffix == ".md":
            try:
                prompt_content = agent_path.read_text(encoding="utf-8")
            except:
                prompt_content = "Error reading prompt file"
        
        agents.append({
            **agent_def,
            "exists": exists,
            "prompt_length": len(prompt_content),
            "editable": agent_path.suffix == ".md"  # Only allow editing .md files
        })
    
    return {"agents": agents}

@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, current_user: User = Depends(get_current_user)):
    """
    Get detailed information about a specific agent including full prompt.
    """
    # Find agent definition
    agent_def = next((a for a in AVAILABLE_AGENTS if a["id"] == agent_id), None)
    if not agent_def:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent_path = PROMPTS_DIR / agent_def["file"]
    
    if not agent_path.exists():
        raise HTTPException(status_code=404, detail="Agent prompt file not found")
    
    # Only allow reading .md files
    if agent_path.suffix != ".md":
        raise HTTPException(status_code=400, detail="This agent's prompt is not editable via UI")
    
    try:
        prompt_content = agent_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading prompt: {str(e)}")
    
    return {
        **agent_def,
        "prompt": prompt_content
    }

@router.put("/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    prompt: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Update an agent's prompt. Only markdown prompts can be edited.
    Returns updated agent data.
    """
    # Find agent definition
    agent_def = next((a for a in AVAILABLE_AGENTS if a["id"] == agent_id), None)
    if not agent_def:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent_path = PROMPTS_DIR / agent_def["file"]
    
    # Validate file is editable
    if agent_path.suffix != ".md":
        raise HTTPException(status_code=400, detail="This agent's prompt cannot be edited via UI")
    
    # Get new prompt content
    new_prompt = prompt.get("prompt", "")
    if not new_prompt or not new_prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt content cannot be empty")
    
    # Backup existing prompt
    backup_path = agent_path.with_suffix(".md.backup")
    try:
        if agent_path.exists():
            agent_path.read_text(encoding="utf-8")  # Test read first
            import shutil
            shutil.copy2(agent_path, backup_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating backup: {str(e)}")
    
    # Write new prompt
    try:
        agent_path.write_text(new_prompt, encoding="utf-8")
    except Exception as e:
        # Restore backup on error
        if backup_path.exists():
            import shutil
            shutil.copy2(backup_path, agent_path)
        raise HTTPException(status_code=500, detail=f"Error writing prompt: {str(e)}")
    
    return {
        "success": True,
        "message": f"Agent '{agent_def['name']}' updated successfully",
        "agent": {
            **agent_def,
            "prompt": new_prompt
        }
    }
