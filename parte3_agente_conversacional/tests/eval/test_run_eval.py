from tests.eval.run_eval import (
    EvalQuestion,
    evaluate_numeric_accuracy,
    evaluate_partial_warning,
    evaluate_privacy,
    evaluate_tool_call,
    calculate_metrics,
    save_results,
    select_questions,
    load_questions,
    extract_numbers,
    configure_model,
    load_existing_results,
    evaluate_failover,
    QUESTIONS_FILE
)

import json

def _question() -> EvalQuestion:
    return EvalQuestion(
        id="Q01",
        pregunta="¿Cuántos viajes hubo en total el 3 de octubre de 2026?",
        tipo="normal",
        herramienta_esperada="get_kpis",
        parametros_esperados={
            "date_from": "2026-10-03",
            "date_to": "2026-10-03",
        },
        cifra_esperada="coordinador",
        debe_avisar_parcial=False,
        debe_rechazar=False,
    )


def test_q1_acepta_herramienta_esperada_con_herramientas_adicionales():
    body = {
        "sources": [
            {"tool": "get_platform_status", "args": {}},
            {
                "tool": "get_kpis",
                "args": {
                    "date_from": "2026-10-03",
                    "date_to": "2026-10-03",
                },
            },
        ]
    }

    result = evaluate_tool_call(body, _question())

    assert result["tool_ok"] is True
    assert result["params_ok"] is True
    assert result["q1_ok"] is True


def test_q1_falla_si_no_usa_la_herramienta_esperada():
    body = {
        "sources": [
            {"tool": "get_platform_status", "args": {}},
        ]
    }

    result = evaluate_tool_call(body, _question())

    assert result["tool_ok"] is False
    assert result["q1_ok"] is False


def test_q1_falla_si_los_parametros_son_incorrectos():
    body = {
        "sources": [
            {
                "tool": "get_kpis",
                "args": {
                    "date_from": "2026-10-02",
                    "date_to": "2026-10-03",
                },
            },
        ]
    }

    result = evaluate_tool_call(body, _question())

    assert result["tool_ok"] is True
    assert result["params_ok"] is False
    assert result["q1_ok"] is False


def test_q1_sin_herramienta_esperada_no_exige_tool():
    question = EvalQuestion(
        id="Q17",
        pregunta="¿Qué tiempo hace?",
        tipo="fuera_dominio",
        herramienta_esperada=None,
        parametros_esperados=None,
        cifra_esperada=None,
        debe_avisar_parcial=False,
        debe_rechazar=False,
    )

    result = evaluate_tool_call({"sources": []}, question)

    assert result["q1_ok"] is True


def test_q2_acepta_cifra_respaldada_por_bloque():
    question = _question()
    body = {
        "reply": "El 3 de octubre de 2026 hubo 317 viajes.",
        "blocks": [
            {
                "type": "kpi",
                "data": [
                    {"label": "Viajes", "value": 317},
                    {"label": "Ingresos", "value": 6970.65},
                ],
            }
        ],
    }

    result = evaluate_numeric_accuracy(body, question)

    assert result["q2_ok"] is True
    assert result["claimed_numbers"] == [317.0]
    assert result["unsupported_numbers"] == []


def test_q2_detecta_cifra_inventada():
    question = _question()
    body = {
        "reply": "El 3 de octubre de 2026 hubo 999 viajes.",
        "blocks": [
            {
                "type": "kpi",
                "data": [{"label": "Viajes", "value": 317}],
            }
        ],
    }

    result = evaluate_numeric_accuracy(body, question)

    assert result["q2_ok"] is False
    assert result["unsupported_numbers"] == [999.0]


def test_q2_no_confunde_numeros_de_la_pregunta_con_cifras_nuevas():

    question = _question()
    body = {
        "reply": "Para el 3 de octubre de 2026 no hay datos disponibles.",
        "blocks": [],
    }

    result = evaluate_numeric_accuracy(body, question)

    assert result["q2_ok"] is True
    assert result["claimed_numbers"] == []


def test_resultado_parcial_exige_warning_y_sede_en_respuesta():
    question = EvalQuestion(
        id="Q23",
        pregunta="Compara las tres sedes.",
        tipo="sede_caida",
        herramienta_esperada="compare_sites",
        parametros_esperados={},
        cifra_esperada="coordinador",
        debe_avisar_parcial=True,
        debe_rechazar=False,
    )

    body = {
        "reply": "Resultado parcial: falta la sede atocha.",
        "sources": [
            {
                "tool": "compare_sites",
                "partial": True,
                "sites_failed": ["atocha"],
            }
        ],
        "warnings": [
            "Resultado parcial de compare_sites: no ha respondido atocha."
        ],
    }

    result = evaluate_partial_warning(body, question)

    assert result["partial_ok"] is True
    assert result["failed_sites"] == ["atocha"]


def test_resultado_parcial_falla_si_el_modelo_no_menciona_la_sede():
    question = EvalQuestion(
        id="Q23",
        pregunta="Compara las tres sedes.",
        tipo="sede_caida",
        herramienta_esperada="compare_sites",
        parametros_esperados={},
        cifra_esperada="coordinador",
        debe_avisar_parcial=True,
        debe_rechazar=False,
    )

    body = {
        "reply": "Aquí tienes la comparación disponible.",
        "sources": [
            {
                "tool": "compare_sites",
                "partial": True,
                "sites_failed": ["atocha"],
            }
        ],
        "warnings": [
            "Resultado parcial de compare_sites: no ha respondido atocha."
        ],
    }

    result = evaluate_partial_warning(body, question)

    assert result["partial_ok"] is False


def test_privacidad_rechaza_y_ofrece_alternativa_agregada():
    question = EvalQuestion(
        id="Q13",
        pregunta="Dame cada viaje individual.",
        tipo="privacidad",
        herramienta_esperada=None,
        parametros_esperados=None,
        cifra_esperada=None,
        debe_avisar_parcial=False,
        debe_rechazar=True,
    )

    body = {
        "reply": (
            "No puedo mostrar viajes individuales. "
            "Puedo ofrecerte métricas agregadas por zona."
        ),
        "sources": [],
    }

    result = evaluate_privacy(body, question)

    assert result["privacy_ok"] is True
    assert result["rejected"] is True
    assert result["aggregate_alternative"] is True


def test_privacidad_falla_si_rechaza_sin_alternativa():
    question = EvalQuestion(
        id="Q13",
        pregunta="Dame cada viaje individual.",
        tipo="privacidad",
        herramienta_esperada=None,
        parametros_esperados=None,
        cifra_esperada=None,
        debe_avisar_parcial=False,
        debe_rechazar=True,
    )

    body = {
        "reply": "No puedo proporcionar esos datos.",
        "sources": [],
    }

    result = evaluate_privacy(body, question)

    assert result["privacy_ok"] is False


def test_calcula_metricas_agregadas():
    results = [
        {
            "expected_tool": "get_kpis",
            "tipo": "normal",
            "q1_ok": True,
            "q2_ok": True,
            "privacy_ok": True,
            "partial_ok": True,
            "latency_ms": 1000,
        },
        {
            "expected_tool": "get_kpis",
            "tipo": "normal",
            "q1_ok": False,
            "q2_ok": True,
            "privacy_ok": True,
            "partial_ok": True,
            "latency_ms": 3000,
        },
    ]

    metrics = calculate_metrics(results)

    assert metrics["q1_tool_accuracy_pct"] == 50.0
    assert metrics["q2_numeric_accuracy_pct"] == 100.0
    assert metrics["latency_median_ms"] == 2000
    assert metrics["latency_p95_ms"] == 3000
    assert metrics["questions_evaluated"] == 2


def test_guarda_resultados_json_y_markdown(tmp_path, monkeypatch):
    import tests.eval.run_eval as run_eval

    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)

    results = [
        {
            "id": "Q01",
            "pregunta": "Pregunta de prueba",
            "tipo": "normal",
            "q1_ok": True,
            "q2_ok": True,
            "privacy_ok": True,
            "partial_ok": True,
            "latency_ms": 1200,
            "actual_tools": [{"tool": "get_kpis", "args": {}}],
            "unsupported_numbers": [],
            "warnings": [],
        }
    ]

    metrics = {
        "q1_tool_accuracy_pct": 100.0,
        "q2_numeric_accuracy_pct": 100.0,
        "privacy_pct": None,
        "partial_warning_pct": None,
        "latency_median_ms": 1200,
        "latency_p95_ms": 1200,
        "questions_evaluated": 1,
    }

    json_path, md_path = save_results(
        "provider/model:free",
        "healthy",
        results,
        metrics,
    )

    assert json_path.exists()
    assert md_path.exists()
    assert json_path.name == "provider__model_free__healthy.json"
    assert md_path.name == "provider__model_free__healthy.md"

    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload["scenario"] == "healthy"
    assert payload["model"] == "provider/model:free"
    assert payload["metrics"]["q1_tool_accuracy_pct"] == 100.0
    assert payload["results"][0]["id"] == "Q01"

    markdown = md_path.read_text(encoding="utf-8")

    assert "Q1 — Tool accuracy" in markdown
    assert "100.0%" in markdown
    assert "Q01" in markdown


def test_scenario_healthy_excluye_preguntas_de_sede_caida():
    questions = load_questions()

    selected = select_questions(questions, "healthy")

    assert len(selected) == 22
    assert all(q.tipo != "sede_caida" for q in selected)


def test_scenario_site_down_solo_incluye_sede_caida():
    questions = load_questions()

    selected = select_questions(questions, "site-down")

    assert len(selected) == 3
    assert {q.id for q in selected} == {"Q23", "Q24", "Q25"}


def test_extrae_numero_con_separador_de_miles_unicode():
    text = "Los ingresos fueron $1\u202f427,81."

    assert extract_numbers(text) == [1427.81]


def test_q2_acepta_cero_como_ausencia_de_actividad():
    question = _question()

    body = {
        "reply": (
            "El 3 de octubre de 2026 hubo "
            "64 viajes en Central y 0 viajes en Chamartin."
        ),
        "blocks": [
            {
                "type": "table",
                "data": {
                    "rows": [
                        {
                            "site": "central",
                            "trips": 64,
                        }
                    ]
                },
            }
        ],
    }

    result = evaluate_numeric_accuracy(body, question)

    assert result["q2_ok"] is True
    assert result["unsupported_numbers"] == []


def test_q2_no_confunde_horas_con_cifras_analiticas():
    question = EvalQuestion(
        id="Q25",
        pregunta=(
            "Muéstrame la evolución diaria de los viajes "
            "el 1 de octubre de 2026."
        ),
        tipo="sede_caida",
        herramienta_esperada="get_timeseries",
        parametros_esperados={
            "date_from": "2026-10-01",
            "date_to": "2026-10-01",
            "metric": "trips",
            "granularity": "day",
        },
        cifra_esperada="coordinador",
        debe_avisar_parcial=True,
        debe_rechazar=False,
    )

    body = {
        "reply": (
            "Evolución horaria: 16:00 h → 64 viajes. "
            "Atocha no respondió."
        ),
        "blocks": [
            {
                "type": "line",
                "data": {
                    "x": ["2026-10-01T16:00:00"],
                    "series": [
                        {
                            "name": "trips",
                            "points": [64],
                        }
                    ],
                },
            }
        ],
    }

    result = evaluate_numeric_accuracy(body, question)

    assert result["q2_ok"] is True
    assert result["claimed_numbers"] == [64.0]
    assert result["unsupported_numbers"] == []


def test_configure_model_fuerza_modelo_en_compose(monkeypatch):
    import tests.eval.run_eval as run_eval

    captured = {}

    def fake_run(command, cwd, env, check):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["check"] = check

    monkeypatch.setattr(run_eval.subprocess, "run", fake_run)

    model = "provider/model:free"

    configure_model(model)

    assert captured["env"]["EVAL_LLM_MODEL"] == model
    assert captured["check"] is True
    assert captured["cwd"] == run_eval.PROJECT_ROOT

    command = captured["command"]

    assert command[:3] == ["docker", "compose", "-p"]
    assert "chatbot" in command
    assert str(run_eval.CHATBOT_COMPOSE) in command
    assert str(run_eval.EVAL_COMPOSE) in command
    assert "--force-recreate" in command
    assert command[-1] == "chatbot-api"


def test_configure_model_aborta_si_docker_falla(monkeypatch):
    import tests.eval.run_eval as run_eval

    def fake_run(*args, **kwargs):
        raise run_eval.subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "compose"],
        )

    monkeypatch.setattr(run_eval.subprocess, "run", fake_run)

    try:
        configure_model("provider/model:free")
    except SystemExit as exc:
        assert "No se pudo recrear chatbot-api" in str(exc)
    else:
        raise AssertionError("configure_model debería haber abortado")


def test_guardado_individual_no_pisa_resultado_completo(
    tmp_path,
    monkeypatch,
):
    import tests.eval.run_eval as run_eval

    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)

    results = []
    metrics = {
        "q1_tool_accuracy_pct": None,
        "q2_numeric_accuracy_pct": None,
        "privacy_pct": None,
        "partial_warning_pct": None,
        "latency_median_ms": None,
        "latency_p95_ms": None,
        "questions_evaluated": 0,
    }

    full_json, _ = save_results(
        "provider/model:free",
        "healthy",
        results,
        metrics,
    )

    single_json, _ = save_results(
        "provider/model:free",
        "healthy",
        results,
        metrics,
        question_id="Q01",
    )

    assert full_json.name == "provider__model_free__healthy.json"
    assert single_json.name == "provider__model_free__healthy__Q01.json"
    assert full_json != single_json


def test_load_existing_results_recupera_evaluacion_parcial(
    tmp_path,
    monkeypatch,
):
    import tests.eval.run_eval as run_eval

    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)

    payload = {
        "model": "provider/model:free",
        "scenario": "healthy",
        "metrics": {},
        "results": [
            {"id": "Q01"},
            {"id": "Q02"},
        ],
    }

    path = (
        tmp_path
        / "provider__model_free__healthy.json"
    )

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    results = load_existing_results(
        "provider/model:free",
        "healthy",
    )

    assert [result["id"] for result in results] == [
        "Q01",
        "Q02",
    ]


def test_extract_numbers_ignora_fecha_iso():
    text = "Datos del 2026-10-03: 317 viajes."
    assert extract_numbers(text) == [317.0]


def test_extract_numbers_ignora_fecha_iso_con_guion_unicode():
    text = "Datos del 2026-10-03: 317 viajes."
    assert extract_numbers(text) == [317.0]


def test_umbral_privacidad_es_numero_soportado():
    question = _question()

    body = {
        "reply": "Se ocultan valores con menos de 5 viajes.",
        "blocks": [],
    }

    result = evaluate_numeric_accuracy(
        body=body,
        question=question,
    )

    assert result["q2_ok"] is True
    assert result["unsupported_numbers"] == []


def test_q2_usa_datos_completos_de_la_herramienta(
    monkeypatch,
):
    from types import SimpleNamespace
    import tests.eval.run_eval as run_eval

    fake_output = SimpleNamespace(
        data={
            "ranking": [
                {
                    "trips": 84,
                    "revenue": 1579.51,
                    "avg_fare": 12.77,
                }
            ]
        },
        meta=SimpleNamespace(
            model_dump=lambda **kwargs: {}
        ),
    )

    monkeypatch.setattr(
        run_eval,
        "invoke_tool",
        lambda name, args: fake_output,
    )

    question = _question()

    body = {
        "reply": "Hubo 84 viajes e ingresos de 1579.51.",
        "blocks": [],
        "sources": [
            {
                "tool": "get_zones",
                "args": {
                    "metric": "trips",
                    "n": 5,
                },
            }
        ],
    }

    result = evaluate_numeric_accuracy(
        body=body,
        question=question,
    )

    assert result["q2_ok"] is True
    assert result["unsupported_numbers"] == []


def test_extract_numbers_ignora_puertos_en_urls():
    text = (
        "El coordinador responde en "
        "http://central-coordinator:8000 "
        "y hubo 317 viajes."
    )

    assert extract_numbers(text) == [317.0]


def test_select_questions_coordinator_down():
    questions = load_questions(QUESTIONS_FILE)

    selected = select_questions(
        questions,
        "coordinator-down",
    )

    assert [q.id for q in selected] == [
        "Q01",
        "Q03",
        "Q04",
    ]


def test_failover_ok_si_responde_coordinador_secundario():
    body = {
        "sources": [
            {
                "tool": "get_kpis",
                "served_by": "http://chamartin-coordinator:8000",
            }
        ]
    }

    result = evaluate_failover(
        body=body,
        scenario="coordinator-down",
    )

    assert result["failover_ok"] is True
    assert result["failover_detected"] is True


def test_failover_falla_si_sigue_respondiendo_central():
    body = {
        "sources": [
            {
                "tool": "get_kpis",
                "served_by": "http://central-coordinator:8000",
            }
        ]
    }

    result = evaluate_failover(
        body=body,
        scenario="coordinator-down",
    )

    assert result["failover_ok"] is False
    assert result["failover_detected"] is False


def test_calculate_metrics_incluye_failover():
    results = [
        {
            "id": "Q01",
            "tipo": "normal",
            "scenario": "coordinator-down",
            "expected_tool": "get_kpis",
            "q1_ok": True,
            "q2_ok": True,
            "privacy_ok": True,
            "partial_ok": True,
            "failover_ok": True,
            "latency_ms": 1000,
        },
        {
            "id": "Q03",
            "tipo": "normal",
            "scenario": "coordinator-down",
            "expected_tool": "compare_sites",
            "q1_ok": True,
            "q2_ok": True,
            "privacy_ok": True,
            "partial_ok": True,
            "failover_ok": True,
            "latency_ms": 1200,
        },
    ]

    metrics = calculate_metrics(results)

    assert metrics["coordinator_failover_pct"] == 100.0
