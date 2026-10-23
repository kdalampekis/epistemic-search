import asyncio
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from epistemic_search.adapters import OpenAIModelProvider
from epistemic_search.campaign import estimate_campaign, load_plan
from epistemic_search.config import ExperimentSpend, RagConfig, load_config
from epistemic_search.execution import local_api_key
from epistemic_search.models import Usage
from epistemic_search.providers import ModelRequest, ProviderBudgetExceeded, ProviderError
from epistemic_search.spending import SpendLedger, SpendStopped


def settings(tmp_path: Path, **updates: object) -> ExperimentSpend:
    return ExperimentSpend.model_validate(
        {
            "ledger_path": tmp_path / "spend.sqlite3",
            "run_id": "pilot",
            "run_usd": "2",
            **updates,
        }
    )


def reserve(ledger: SpendLedger, value: str) -> str:
    return ledger.reserve(Decimal(value), Usage(model_calls=1), "gpt-6-luna", "medium")


def test_run_cap_restart_and_project_cap_across_phases(tmp_path: Path) -> None:
    cfg = settings(tmp_path, total_usd="5", validation_reserve_usd="1")
    ledger = SpendLedger(cfg)
    identifier = reserve(ledger, "1.5")
    with pytest.raises(SpendStopped, match="concurrent"):
        reserve(
            SpendLedger(
                settings(tmp_path, total_usd="5", validation_reserve_usd="1", run_id="concurrent")
            ),
            "0.1",
        )
    ledger.settle(identifier, Usage(cost_usd=Decimal("1.5")))
    with pytest.raises(SpendStopped, match="Run cost cap"):
        reserve(ledger, "0.51")
    assert SpendLedger(cfg).report()["cumulative_project_cost_usd"] == "1.5"
    next_cfg = settings(
        tmp_path, total_usd="5", validation_reserve_usd="1", run_id="phase13", run_usd="4"
    )
    next_ledger = SpendLedger(next_cfg)
    next_ledger.settle(reserve(next_ledger, "2.5"), Usage(cost_usd=Decimal("2.5")))
    with pytest.raises(SpendStopped, match="reserve protected"):
        reserve(next_ledger, "0.01")
    validation = SpendLedger(
        settings(
            tmp_path,
            total_usd="5",
            validation_reserve_usd="1",
            run_id="validation",
            run_usd="1",
            stage="validation",
        )
    )
    validation.settle(reserve(validation, "1"), Usage(cost_usd=Decimal("1")))
    with pytest.raises(SpendStopped, match="Project cost cap"):
        reserve(validation, "0.001")
    assert validation.report()["cumulative_project_cost_usd"] == "5.0"
    with pytest.raises(ValueError, match="policy differs"):
        SpendLedger(settings(tmp_path))


def test_pending_crash_reservation_and_unexpected_overcharge(tmp_path: Path) -> None:
    cfg = settings(tmp_path)
    ledger = SpendLedger(cfg)
    identifier = reserve(ledger, "1")
    restarted = SpendLedger(cfg)
    assert restarted.report()["pending_attempts"] == 1
    assert restarted.report()["cumulative_project_cost_usd"] == "1"
    assert restarted.stop_reason() is not None
    restarted.settle(identifier, Usage(cost_usd=Decimal("1.1")))
    assert "exceeded" in (restarted.stop_reason() or "")
    with pytest.raises(ValueError, match="already settled"):
        restarted.settle(identifier, Usage(cost_usd=Decimal("0")))


def paid_config(tmp_path: Path) -> RagConfig:
    config = load_config(Path("configs/hotpotqa_parity.yaml"))
    assert config.rag and config.rag.experiment_spend
    config.rag.experiment_spend.ledger_path = tmp_path / "spend.sqlite3"
    return config.rag


@pytest.mark.parametrize(
    "mode", ["success", "input_cap", "run_cap", "timeout", "missing_usage", "overrun", "cancel"]
)
def test_paid_adapter_is_offline_and_fail_closed(tmp_path: Path, mode: str) -> None:
    cfg = paid_config(tmp_path)
    assert cfg.experiment_spend is not None
    if mode == "run_cap":
        cfg.experiment_spend.run_usd = Decimal("0.000001")
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload["model"] == "gpt-6-luna"
        assert payload["reasoning"] == {"effort": "medium"}
        if request.url.path.endswith("input_tokens"):
            return httpx.Response(200, json={"input_tokens": 100})
        assert payload["store"] is False
        assert payload["prompt_cache_options"] == {"mode": "implicit", "ttl": "30m"}
        if mode == "timeout":
            raise httpx.ReadTimeout("do not log secret-test-key")
        if mode == "cancel":
            raise asyncio.CancelledError
        body = {
            "id": "response1",
            "model": "gpt-6-luna",
            "status": "completed",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20 if mode != "overrun" else 101,
                "input_tokens_details": {"cached_tokens": 10, "cache_write_tokens": 20},
                "output_tokens_details": {"reasoning_tokens": 15},
            },
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"answer":"Paris"}'}],
                }
            ],
        }
        if mode == "missing_usage":
            del body["usage"]
        return httpx.Response(200, json=body)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAIModelProvider(client, "secret-test-key", cfg)
            request = ModelRequest(
                prompt="capital?",
                model=cfg.model,
                prompt_version="v1",
                max_output_tokens=100,
                max_input_tokens=99 if mode == "input_cap" else 100,
            )
            if mode == "success":
                result = await provider.complete(request)
                assert result.usage.cost_usd == Decimal("0.0000196")
                assert result.usage.api_calls == 2 and result.usage.preflight_calls == 1
                assert result.usage.reasoning_tokens == 15
                # A new provider/process reuses the exact request, retaining logical budget use.
                reused = await OpenAIModelProvider(client, "secret-test-key", cfg).complete(request)
                assert len(calls) == 2
                assert reused.text == result.text and reused.usage.prompt_tokens == 100
                assert reused.usage.model_calls == 1 and reused.usage.model_cache_hits == 1
                assert reused.usage.cost_usd == 0 and reused.usage.api_calls == 0
                assert reused.usage.reused_cost_usd == result.usage.cost_usd
                request.max_input_tokens = 99
                with pytest.raises(ProviderBudgetExceeded):
                    await provider.complete(request)
                assert len(calls) == 2
                request.max_input_tokens = 100
                request.seed = 43
                await provider.complete(request)
                assert len(calls) == 4  # Explicit independent replicate cannot reuse seed 0.
            elif mode == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    await provider.complete(request)
            else:
                with pytest.raises(ProviderError) as error:
                    await provider.complete(request)
                assert "secret-test-key" not in str(error.value)
                if mode in {"input_cap", "run_cap"}:
                    assert error.value.usage.api_calls == 1
                    assert error.value.usage.model_calls == 0
                    assert error.value.usage.cost_usd == 0
                    assert len(calls) == 1
            assert provider.spend
            if mode in {"timeout", "missing_usage", "cancel"}:
                assert provider.spend.report()["pending_attempts"] == 1
                assert provider.spend.stop_reason()
            if mode == "overrun":
                assert provider.spend.stop_reason()
            assert cfg.experiment_spend is not None
            assert b"secret-test-key" not in cfg.experiment_spend.ledger_path.read_bytes()

    asyncio.run(run())


def test_model_policy_and_small_plan(tmp_path: Path) -> None:
    cfg = paid_config(tmp_path).model_dump(mode="json")
    for model in ("gpt-6.1-sol", "gpt-6-astra"):
        with pytest.raises(ValueError):
            RagConfig.model_validate({**cfg, "model": model})
    with pytest.raises(ValueError):
        RagConfig.model_validate({**cfg, "reasoning_effort": "low"})
    runs = load_plan(Path("configs/phase12.yaml"))
    assert len(runs) == 6
    estimate = estimate_campaign(Path("configs/phase12.yaml"), "comparison")
    assert estimate["automatic_scaling"] is False
    assert sum(c.evaluation.limit or 0 for _, c in runs[3:] if c.evaluation) == 22


def test_dotenv_read_is_local_and_does_not_mutate_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text('IGNORED=anything\nexport OPENAI_API_KEY="fake-local-key" # comment\n')
    assert local_api_key(tmp_path) == "fake-local-key"
    import os

    assert "OPENAI_API_KEY" not in os.environ
    monkeypatch.setenv("OPENAI_API_KEY", "fake-env-key")
    assert local_api_key(tmp_path) == "fake-env-key"


def test_smoke_audit_binds_reports_and_refuses_provider_failures(tmp_path: Path) -> None:
    import yaml

    from epistemic_search.campaign import verify_smoke_audit
    from epistemic_search.decomposition import digest

    cfg = load_config(Path("configs/hotpotqa_parity.yaml"))
    assert cfg.evaluation
    cfg.evaluation.output_dir = tmp_path / "smoke"
    root = cfg.evaluation.output_dir
    trace_dir = root / "epistemic_search/traces"
    trace_dir.mkdir(parents=True)
    report = {"complete": True, "summaries": {}}
    (root / "comparison.json").write_text(json.dumps(report))
    trace = trace_dir / "000000.json"
    trace.write_text(json.dumps({"trace": [{"type": "MODEL"}]}))
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        yaml.safe_dump(
            {"smoke": ["smoke.yaml"], "comparison": ["pilot.yaml"], "smoke_audit": "audit.json"}
        )
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps(
            {
                "informative": True,
                "rationale": "Known model rejection retained",
                "comparison_report_hashes": {cfg.run_id: digest(report)},
            }
        )
    )
    runs = [(tmp_path / "smoke.yaml", cfg)]
    verify_smoke_audit(plan, runs)
    trace.write_text(json.dumps({"trace": [{"type": "MODEL_ERROR"}]}))
    with pytest.raises(ValueError, match="Provider failures"):
        verify_smoke_audit(plan, runs)
    trace.write_text(json.dumps({"trace": []}))
    (root / "comparison.json").write_text(json.dumps({**report, "changed": True}))
    with pytest.raises(ValueError, match="does not match"):
        verify_smoke_audit(plan, runs)
