"""Tool MCP della pagina Pianifica (sola lettura: non salvano nulla)."""
from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.mcp.server import _Session, mcp
from app.services.ai.context import table

_READ = dict(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


@mcp.tool(
    name="search-securities",
    title="Search securities",
    annotations=ToolAnnotations(title="Search securities", **_READ),
    structured_output=False,
    description=(
        "Cerca titoli per nome, ticker o ISIN sia in Nextfolio sia su Yahoo Finance (anche titoli mai acquistati). "
        "Restituisce asset_id per quelli già in Nextfolio e symbol (ticker Yahoo) per gli altri: usali con "
        "simulate-purchase."
    ),
)
async def search_securities(
    ctx: Context,
    query: Annotated[str, Field(min_length=3, max_length=100, description="Nome, ticker o ISIN")],
    type: Annotated[Literal["STOCK", "ETF", "BOND", "CRYPTO", "COMMODITY", "REIT", "OTHER"] | None,
                    Field(description="Filtra per tipo")] = None,
) -> str:
    from app.api.v1.endpoints.planning import search

    async with _Session(ctx) as s:
        results = await search(q=query, type=type, external_search=True, db=s.db, current_user=s.user)
        rows = [[r.source, r.asset_id or "—", r.symbol or "—", r.name, r.isin, r.type, r.exchange_label or r.exchange,
                 "sì" if r.in_portfolio else "no"] for r in results]
        return table(["Fonte", "ID asset", "Symbol Yahoo", "Nome", "ISIN", "Tipo", "Borsa", "In portafoglio"], rows)


class PurchaseInput(BaseModel):
    asset_id: int | None = Field(None, description="ID asset Nextfolio")
    symbol: str | None = Field(None, description="Ticker Yahoo per titoli non in Nextfolio (vedi search-securities)")
    name: str | None = None
    type: Literal["STOCK", "ETF", "BOND", "CRYPTO", "COMMODITY", "REIT", "OTHER"] | None = None
    amount_eur: float | None = Field(None, gt=0, description="Importo da investire in EUR")
    quantity: float | None = Field(None, gt=0, description="In alternativa all'importo")
    account_id: int | None = None


@mcp.tool(
    name="simulate-purchase",
    title="Simulate purchase",
    annotations=ToolAnnotations(title="Simulate purchase", **_READ),
    structured_output=False,
    description=(
        "Simula uno o più acquisti senza registrarli e mostra l'effetto sul portafoglio: asset class, valute del "
        "sottostante, pesi dei titoli e regole X-Ray prima e dopo. Con use_cash=true gli acquisti sono pagati con "
        "la liquidità dei conti."
    ),
)
async def simulate_purchase(
    ctx: Context,
    purchases: Annotated[list[PurchaseInput], Field(min_length=1, max_length=20)],
    use_cash: bool = False,
) -> str:
    from app.api.v1.endpoints.planning import SimItemIn, SimulateIn, run_simulation

    async with _Session(ctx) as s:
        try:
            body = SimulateIn(use_cash=use_cash, items=[SimItemIn(**p.model_dump()) for p in purchases])
        except ValidationError as e:
            raise ToolError(e.errors()[0]["msg"]) from e
        r = await run_simulation(s.db, s.user, body)

        def cls(a):
            return {i.label: i.pct for i in a.by_asset_class}

        before, after = cls(r.allocation_before), cls(r.allocation_after)
        out = [f"Acquisti simulati: {r.invested_eur:.2f} € (commissioni {r.fees_eur:.2f} €). "
               f"Patrimonio {r.total_before_eur:.2f} € → {r.total_after_eur:.2f} €; "
               f"liquidità {r.cash_before_eur:.2f} € → {r.cash_after_eur:.2f} €."]
        out.append("#### Asset class\n" + table(
            ["Classe", "Prima %", "Dopo %"],
            [[k, before.get(k, 0.0), after.get(k, 0.0)] for k in sorted(set(before) | set(after))]))
        out.append("#### Pesi dei titoli\n" + table(
            ["Titolo", "Prima %", "Dopo %", "Δ"],
            [[w["name"] + (" (nuovo)" if w["new"] else ""), w["before_pct"], w["after_pct"], w["delta_pct"]]
             for w in r.weights]))
        out.append(f"#### X-Ray: punteggio {r.xray_before.score} → {r.xray_after.score}\n" + table(
            ["Regola", "Prima", "Dopo", "Valore prima", "Valore dopo"],
            [[c.name, c.before_status, c.after_status, c.before_actual, c.after_actual] for c in r.rule_changes]))
        if r.warnings:
            out.append("\n".join(f"- ⚠ {w}" for w in r.warnings))
        return "\n\n".join(out)


@mcp.tool(
    name="get-scenarios",
    title="Get scenarios",
    annotations=ToolAnnotations(title="Get scenarios", readOnlyHint=True, destructiveHint=False,
                                idempotentHint=True, openWorldHint=False),
    structured_output=False,
    description="Scenari di acquisto salvati nella pagina Pianifica: nome, stato (bozza/eseguito) e acquisti previsti.",
)
async def get_scenarios(ctx: Context) -> str:
    from app.models.planning import PlanningScenario

    async with _Session(ctx) as s:
        rows = (await s.db.execute(select(PlanningScenario).where(PlanningScenario.user_id == s.user.id)
                                   .order_by(PlanningScenario.updated_at.desc()))).scalars().all()
        out = []
        for sc in rows:
            items = table(["Titolo", "Importo EUR", "Quantità", "Prezzo EUR"],
                          [[i.name, i.amount_eur, i.quantity, i.price_eur] for i in sc.items])
            out.append(f"### {sc.name} (ID {sc.id}, {'eseguito' if sc.status == 'executed' else 'bozza'})\n{items}")
        return "\n\n".join(out) if out else "_Nessuno scenario salvato._"


@mcp.tool(
    name="suggest-contribution",
    title="Suggest contribution",
    annotations=ToolAnnotations(title="Suggest contribution", **_READ),
    structured_output=False,
    description=(
        "Suggerisce cosa comprare con un importo (o con la liquidità dei conti) per avvicinare il portafoglio "
        "all'allocazione obiettivo impostata nella pagina Pianifica, senza vendere. Non registra nulla."
    ),
)
async def suggest_contribution(
    ctx: Context,
    amount_eur: Annotated[float | None, Field(gt=0, description="Importo; vuoto = tutta la liquidità (con from_cash)")] = None,
    from_cash: bool = False,
    whole_units: bool = True,
) -> str:
    from fastapi import HTTPException

    from app.api.v1.endpoints.planning import ContributionIn, run_contribution

    async with _Session(ctx) as s:
        try:
            plan = await run_contribution(s.db, s.user, ContributionIn(amount_eur=amount_eur, from_cash=from_cash,
                                                                       whole_units=whole_units))
        except HTTPException as e:
            raise ToolError(str(e.detail)) from e
        out = [f"Importo da investire: {plan['amount_eur']:.2f} €"
               f"{' (dalla liquidità)' if from_cash else ''}; non investiti: {plan['uninvested_eur']:.2f} €."]
        out.append(table(["Classe", "Obiettivo %", "Prima %", "Dopo %", "Allocati €"],
                         [[c["label"], c["target_pct"], c["before_pct"], c["after_pct"], c["allocated_eur"]]
                          for c in plan["per_class"]]))
        out.append(table(["Titolo", "Classe", "Quantità", "Prezzo €", "Importo €"],
                         [[o["name"], o["asset_class"], o["quantity"], round(o["price_eur"], 2), o["amount_eur"]]
                          for o in plan["orders"]]))
        if plan["warnings"]:
            out.append("\n".join(f"- ⚠ {w}" for w in plan["warnings"]))
        return "\n\n".join(out)


@mcp.tool(
    name="project-goal",
    title="Project goal",
    annotations=ToolAnnotations(title="Project goal", **{**_READ, "openWorldHint": False}),
    structured_output=False,
    description=(
        "Proiezione Monte Carlo (5.000 scenari) del patrimonio verso un obiettivo: probabilità di raggiungerlo, "
        "valori mediano e pessimistico in euro di oggi, versamento mensile necessario per l'80% di probabilità. "
        "Rendimento e volatilità derivano dall'allocazione attuale con ipotesi di lungo periodo per asset class."
    ),
)
async def project_goal(
    ctx: Context,
    target_amount: Annotated[float, Field(gt=0, description="Obiettivo in euro di oggi")],
    target_date: Annotated[str, Field(description="Data ISO, es. 2040-12-31")],
    monthly_contribution: Annotated[float, Field(ge=0)] = 0.0,
    initial_amount: Annotated[float | None, Field(ge=0, description="Default: patrimonio attuale")] = None,
    inflation_pct: float = 2.0,
) -> str:
    import datetime

    from fastapi import HTTPException

    from app.api.v1.endpoints.planning import ProjectionIn, projection

    async with _Session(ctx) as s:
        try:
            body = ProjectionIn(target_amount=target_amount, target_date=datetime.date.fromisoformat(target_date),
                                monthly_contribution=monthly_contribution, initial_amount=initial_amount,
                                inflation_pct=inflation_pct)
            r = await projection(body=body, db=s.db, current_user=s.user)
        except (ValueError, HTTPException) as e:
            raise ToolError(str(getattr(e, "detail", e))) from e
        return (
            f"Probabilità di raggiungere {target_amount:,.0f} € (euro di oggi) entro {target_date}: "
            f"**{r['probability'] * 100:.0f}%**.\n\n"
            + table(["Voce", "Valore"], [
                ["Capitale iniziale (EUR)", r["initial_amount"]],
                ["Versamento mensile (EUR)", monthly_contribution],
                ["Rendimento atteso / volatilità annui", f"{r['expected_return_pct']}% / {r['volatility_pct']}%"],
                ["Valore mediano a scadenza (EUR di oggi)", r["median_final"]],
                ["Scenario sfavorevole, 10° percentile (EUR di oggi)", r["p10_final"]],
                ["Scenario favorevole, 90° percentile (EUR di oggi)", r["p90_final"]],
                ["Versamento mensile per l'80% di probabilità (EUR)", r["required_monthly_80"]],
            ])
            + "\n\nIpotesi di lungo periodo, non previsioni."
        )
