from fastapi import Header


def get_actor_id(x_user_id: int = Header(...)) -> int:
    """Who is acting. No authentication, as the project rules say."""
    return x_user_id