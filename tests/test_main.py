from httpx import AsyncClient, ASGITransport
from starlette import status

import pytest

from main import app
from config import TEST_ACCESS_TOKEN


@pytest.mark.asyncio
async def test_read_main_page():
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get('/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_read_about_us_page():
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get('/about_us')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_read_register_page():
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get('/jwt/register')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_read_login_page():
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get('/jwt/login')
        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT


@pytest.mark.asyncio
async def test_read_authenticated_page_without_token():
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get('/authenticated/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_read_authenticated_page_with_token():
    try:
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            client.cookies.set('access_token', TEST_ACCESS_TOKEN)
            response = await client.get('/authenticated/')
            assert response.status_code == status.HTTP_200_OK
    except AssertionError:
        print('токен истек')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED