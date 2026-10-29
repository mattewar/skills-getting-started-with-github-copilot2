from copy import deepcopy

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import activities, app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def restore_activities():
    original_activities = deepcopy(activities)
    yield
    activities.clear()
    activities.update(original_activities)


@pytest.fixture
async def client(anyio_backend, restore_activities):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.mark.anyio
async def test_signup_adds_participant_and_is_visible_in_activity_list(client):
    email = "new-student@mergington.edu"

    response = await client.post(
        "/activities/Art Club/signup",
        params={"email": email},
    )

    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for Art Club"}

    activities_response = await client.get("/activities")
    assert activities_response.headers["cache-control"] == "no-store"
    assert email in activities_response.json()["Art Club"]["participants"]


@pytest.mark.anyio
async def test_signup_rejects_duplicate_participant(client):
    email = activities["Art Club"]["participants"][0]

    response = await client.post(
        "/activities/Art Club/signup",
        params={"email": email},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Student already signed up for this activity"
    assert activities["Art Club"]["participants"].count(email) == 1


@pytest.mark.anyio
async def test_signup_rejects_full_activity(client):
    activity = activities["Art Club"]
    activity["participants"] = [
        f"student{number}@mergington.edu"
        for number in range(activity["max_participants"])
    ]

    response = await client.post(
        "/activities/Art Club/signup",
        params={"email": "new-student@mergington.edu"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Activity is full"


@pytest.mark.anyio
async def test_signup_rejects_unknown_activity(client):
    response = await client.post(
        "/activities/Unknown Club/signup",
        params={"email": "new-student@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


@pytest.mark.anyio
async def test_unregister_removes_participant_and_updates_activity_list(client):
    email = "registered-student@mergington.edu"
    activities["Art Club"]["participants"].append(email)

    response = await client.delete(
        "/activities/Art Club/participants",
        params={"email": email},
    )

    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Art Club"}

    activities_response = await client.get("/activities")
    assert email not in activities_response.json()["Art Club"]["participants"]


@pytest.mark.anyio
async def test_unregister_rejects_unregistered_participant(client):
    response = await client.delete(
        "/activities/Art Club/participants",
        params={"email": "not-registered@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Student is not signed up for this activity"


@pytest.mark.anyio
async def test_unregister_rejects_unknown_activity(client):
    response = await client.delete(
        "/activities/Unknown Club/participants",
        params={"email": "registered-student@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"
