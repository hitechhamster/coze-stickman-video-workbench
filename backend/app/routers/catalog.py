from fastapi import APIRouter

from app.services.jianying_catalog import get_catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("")
def get_catalog_route():
    return get_catalog()
