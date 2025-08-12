def search_documentation(query: str, category: str = None, max_results: int = 10) -> str:
    """
    Search for documentation based on a query string.
    
    Args:
        query (str): The search query to find relevant documentation
        category (str, optional): Filter results by documentation category 
        max_results (int): Maximum number of results to return (default: 10)
    
    Returns:
        str: Mock response indicating the search was performed
    """
    return f"Documentation search performed for query: '{query}' in category: '{category}' with max_results: {max_results}"


def create_feature_request(title: str, description: str, priority: str = "medium", assignee: str = None) -> str:
    """
    Create a new feature request in the system.
    
    Args:
        title (str): Brief title describing the feature request
        description (str): Detailed description of the requested feature
        priority (str): Priority level - "low", "medium", "high", or "critical" (default: "medium")
        assignee (str, optional): User to assign the feature request to
    
    Returns:
        str: Mock response indicating the feature request was created
    """
    return f"Feature request created: '{title}' with priority: '{priority}' assigned to: '{assignee}'"


def file_bug_report(title: str, description: str, severity: str = "medium", steps_to_reproduce: str = None, environment: str = None) -> str:
    """
    File a bug report in the system.
    
    Args:
        title (str): Brief title describing the bug
        description (str): Detailed description of the bug
        severity (str): Bug severity - "low", "medium", "high", or "critical" (default: "medium")
        steps_to_reproduce (str, optional): Steps needed to reproduce the bug
        environment (str, optional): Environment information where bug occurs
    
    Returns:
        str: Mock response indicating the bug report was filed
    """
    return f"Bug report filed: '{title}' with severity: '{severity}' in environment: '{environment}'"