"""Tests de serializacion de los contratos de /chat (P3-01)."""

import pytest
from pydantic import ValidationError

from src.api.schemas import Block, ChatRequest, ChatResponse, Source


def test_chat_request_valida_longitud_mensaje():
    with pytest.raises(ValidationError):
        ChatRequest(session_id="s", message="")  # vacio
    with pytest.raises(ValidationError):
        ChatRequest(session_id="s", message="x" * 2001)  # demasiado largo
    ok = ChatRequest(session_id="s", message="hola")
    assert ok.message == "hola"


def test_chat_response_roundtrip():
    resp = ChatResponse(
        request_id="r1",
        reply="Central tuvo 10 viajes.",
        blocks=[
            Block(
                type="kpi",
                title="Viajes",
                data=[{"label": "Viajes", "value": 10}],
                unit="viajes",
            )
        ],
        sources=[
            Source(
                tool="get_kpis",
                args={"sites": ["central"]},
                served_by="central",
                sites_ok=["central"],
                sites_failed=[],
                partial=False,
                latency_ms=12,
            )
        ],
        warnings=["Resultado parcial: falta atocha."],
        latency_ms=100,
    )
    # dict round-trip
    back = ChatResponse.model_validate(resp.model_dump())
    assert back == resp
    # json round-trip
    back2 = ChatResponse.model_validate_json(resp.model_dump_json())
    assert back2.blocks[0].type == "kpi"
    assert back2.sources[0].served_by == "central"


def test_block_rechaza_tipo_desconocido():
    with pytest.raises(ValidationError):
        Block(type="pie", title="x", data={})


def test_chat_response_valores_por_defecto():
    resp = ChatResponse(request_id="r2", reply="hola")
    assert resp.blocks == []
    assert resp.sources == []
    assert resp.warnings == []
    assert resp.latency_ms == 0
