import httpx
from typing import Dict, Any, List

async def get_issue_details(repo: str, issue_number: int, token: str) -> Dict[str, Any]:
    """
    Fetch the details of a GitHub issue using the REST API.
    Docs: https://docs.github.com/en/rest/issues/issues#get-an-issue
    """
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
                 
    # We use AsyncClient() with parentheses to instantiate the client properly
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        # Best practice: raise an exception if the request failed (e.g., 404 or 401)
        response.raise_for_status()
        
        return response.json()

async def get_repo_labels(repo: str, token: str) -> List[Dict[str, Any]]:
    """
    Fetch all available labels for the repository.
    Docs: https://docs.github.com/en/rest/issues/labels#list-labels-for-a-repository
    """
    url = f"https://api.github.com/repos/{repo}/labels"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
                 
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        response.raise_for_status()

        return response.json()

async def get_team_workload(org: str, team_slug: str, token: str) -> Dict[str, Any]:
    """
    Fetch the list of team members and their recent issue assignment counts.
    Docs: https://docs.github.com/en/rest/teams/members#list-team-members
    (You might just fetch the members list for now to keep it simple).
    """
    url = f"https://api.github.com/orgs/{org}/teams/{team_slug}/members"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
                 
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        response.raise_for_status()
        
        return response.json()

async def post_comment(repo: str, issue_number: int, body: str, token: str) -> Dict[str, Any]:
    """
    Post a comment on a GitHub issue.
    Docs: https://docs.github.com/en/rest/issues/comments#create-an-issue-comment
    """
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"body": body})
        
        response.raise_for_status()
        
        return response.json()
        

async def add_labels(repo: str, issue_number: int, labels: List[str], token: str) -> List[Dict[str, Any]]:
    """
    Add labels to a GitHub issue.
    Docs: https://docs.github.com/en/rest/issues/labels#add-labels-to-an-issue
    """
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/labels"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"labels": labels})
        
        response.raise_for_status()
        
        return response.json()

async def assign_issue(repo: str, issue_number: int, assignees: List[str], token: str) -> Dict[str, Any]:
    """
    Assign a GitHub issue to specific users.
    Docs: https://docs.github.com/en/rest/issues/assignees#add-assignees-to-an-issue
    """
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/assignees"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"assignees": assignees})
        
        response.raise_for_status()
        
        return response.json()

async def close_issue(repo: str, issue_number: int, token: str) -> Dict[str, Any]:
    """
    Close a GitHub issue (update its state to 'closed').
    Docs: https://docs.github.com/en/rest/issues/issues#update-an-issue
    """
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.patch(url, headers=headers, json={"state": "closed"})
        
        response.raise_for_status()
        
        return response.json()
