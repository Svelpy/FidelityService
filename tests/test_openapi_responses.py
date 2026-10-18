import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter

from app.domains.categoria.routes import router as categoria_router
from app.domains.negocio.routes import router as negocio_router
from app.domains.sucursal.routes import router as sucursal_router
from app.domains.vale.routes import router as vale_router


@pytest.mark.parametrize(
    ("router", "path"),
    [
        (negocio_router, "/negocios/{negocio_id}"),
        (sucursal_router, "/sucursales/{sucursal_id}"),
        (categoria_router, "/categorias/{categoria_id}"),
        (vale_router, "/vales/{vale_id}"),
    ],
)
def test_delete_con_dependencias_documenta_conflicto_409(
    router: APIRouter,
    path: str,
) -> None:
    app = FastAPI()
    app.include_router(router)

    responses = app.openapi()["paths"][path]["delete"]["responses"]

    assert "409" in responses
    assert responses["409"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
