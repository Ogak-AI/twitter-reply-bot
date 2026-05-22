import logging
from typing import Any
import requests

logger = logging.getLogger(__name__)


def post_to_buffer(
    tweet: str,
    channel_id: str,
    api_key: str,
    api_url: str = "https://api.buffer.com",
    mode: str = "addToQueue"
) -> dict[str, Any]:
    """
    Posts a tweet to Buffer using the new GraphQL API.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess {
          post {
            id
            dueAt
          }
        }
        ... on MutationError {
          message
        }
        ... on UnexpectedError {
          message
        }
      }
    }
    """

    save_to_draft = False
    graphql_mode = mode

    if mode == "draft":
        save_to_draft = True
        graphql_mode = "addToQueue"
    elif mode not in ["addToQueue", "customScheduled", "shareNow"]:
        graphql_mode = "addToQueue"

    variables = {
        "input": {
            "text": tweet,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": graphql_mode,
            "saveToDraft": save_to_draft
        }
    }

    try:
        response = requests.post(
            api_url.rstrip('/'),
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=15
        )
        
        # Try to parse the JSON body to handle any GraphQL validation/top-level errors
        body = {}
        try:
            body = response.json()
        except ValueError:
            pass

        if body and "errors" in body:
            error_msg = body["errors"][0].get("message", "Unknown GraphQL error")
            logger.error(f"GraphQL top-level errors: {body['errors']}")
            return {
                "success": False,
                "post_id": None,
                "due_at": None,
                "error": error_msg,
            }

        response.raise_for_status()
    except Exception as exc:
        logger.exception("Buffer GraphQL API request failed")
        return {
            "success": False,
            "post_id": None,
            "due_at": None,
            "error": str(exc),
        }

    create_post_data = body.get("data", {}).get("createPost")
    if not create_post_data:
        logger.error(f"Empty createPost data. Full body: {body}")
        return {
            "success": False,
            "post_id": None,
            "due_at": None,
            "error": "No createPost data in GraphQL response",
        }

    typename = create_post_data.get("__typename")
    
    if typename == "PostActionSuccess":
        post_info = create_post_data.get("post", {})
        return {
            "success": True,
            "post_id": post_info.get("id"),
            "due_at": post_info.get("dueAt"),
            "error": None,
        }

    # Extract error message for any other type (MutationError, UnexpectedError, etc.)
    error_msg = create_post_data.get("message")
    if not error_msg:
        error_msg = f"Unexpected response type: {typename} (Payload: {create_post_data})"
    else:
        error_msg = f"{typename}: {error_msg}"

    logger.error(f"Buffer post creation failed: {error_msg}")
    
    return {
        "success": False,
        "post_id": None,
        "due_at": None,
        "error": error_msg,
    }
