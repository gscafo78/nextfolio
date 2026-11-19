import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.asset import Asset
from app.models.user import User
from app.schemas.tax import AnnualTaxReportOut, IVAFEReportOut, SimulateSellOut, TaxEventOut, CarryForwardEntryOut
from app.services.market_data.updater import get_cached_price, refresh_asset_price
from app.services.tax.calculator import (
    AnnualTaxReport,
    build_annual_reports,
    compute_tax_events,
    crypto_rate,
    open_cost_pools,
    simulate_sell,
)
from app.services.tax.ivafe import compute_ivafe
from app.services.transaction import get_transactions

router = APIRouter(prefix="/tax", tags=["tax"])

# ── Colori PDF ────────────────────────────────────────────────────────────────
_BRAND      = colors.HexColor("#1D4ED8")
_BRAND_DARK = colors.HexColor("#1E40AF")
_ALT_ROW    = colors.HexColor("#F8FAFC")
_GRAY       = colors.HexColor("#6B7280")
_GREEN      = colors.HexColor("#15803D")
_ORANGE     = colors.HexColor("#C2410C")
_SKY        = colors.HexColor("#0369A1")

_ALL = 10_000


def _cf_out(entries) -> list[CarryForwardEntryOut]:
    return [CarryForwardEntryOut(year=e.year, amount=e.amount, expires_year=e.expires_year) for e in entries]


def _report_to_out(r: AnnualTaxReport, ivafe: IVAFEReportOut | None = None) -> AnnualTaxReportOut:
    special = {"events", "ivafe", "prior_carryforward_standard", "prior_carryforward_crypto"}
    data = {
        name: getattr(r, name)
        for name in AnnualTaxReportOut.model_fields
        if name not in special and hasattr(r, name)
    }
    return AnnualTaxReportOut(
        **data,
        prior_carryforward_standard=_cf_out(r.prior_carryforward_standard),
        prior_carryforward_crypto=_cf_out(r.prior_carryforward_crypto),
        events=[
            TaxEventOut(
                date=e.date,
                asset_id=e.asset_id,
                asset_name=e.asset_name,
                asset_type=e.asset_type,
                tx_type=e.tx_type,
                quantity=e.quantity,
                proceeds_eur=e.proceeds_eur,
                cost_eur=e.cost_eur,
                gain_loss_eur=e.gain_loss_eur,
                tax_bracket=e.tax_bracket,
                tax_rate=e.tax_rate,
                is_sostituto_imposta=e.is_sostituto_imposta,
                calculation_method=e.calculation_method,
            )
            for e in r.events
        ],
        ivafe=ivafe or IVAFEReportOut(year=r.year),
    )


@router.get("/report", response_model=AnnualTaxReportOut)
async def get_tax_report(
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Report fiscale per l'anno richiesto, con zainetto fiscale cumulativo."""
    transactions = await get_transactions(db, current_user.id, limit=_ALL)
    events = compute_tax_events(transactions)
    reports = build_annual_reports(events)
    ivafe = await compute_ivafe(db, transactions, year)
    ivafe_out = IVAFEReportOut(
        year=ivafe.year,
        total_market_value_eur=ivafe.total_market_value_eur,
        ivafe_eur=ivafe.ivafe_eur,
        rate=ivafe.rate,
        has_foreign_accounts=ivafe.has_foreign_accounts,
        positions=[
            {
                "asset_id": p.asset_id,
                "asset_name": p.asset_name,
                "asset_type": p.asset_type,
                "quantity": p.quantity,
                "price_eur": p.price_eur,
                "market_value_eur": p.market_value_eur,
                "ivafe_eur": p.ivafe_eur,
                "price_date": p.price_date,
            }
            for p in ivafe.positions
        ],
    )

    for r in reports:
        if r.year == year:
            return _report_to_out(r, ivafe_out)

    # Anno senza eventi fiscali — restituisce comunque IVAFE se presente
    empty = AnnualTaxReport(year=year)
    empty.crypto_rate = crypto_rate(year)
    return _report_to_out(empty, ivafe_out)


@router.get("/years", response_model=list[int])
async def get_tax_years(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista degli anni con eventi fiscali (vendite, dividendi, cedole)."""
    transactions = await get_transactions(db, current_user.id, limit=_ALL)
    events = compute_tax_events(transactions)
    years = sorted({e.date.year for e in events}, reverse=True)
    return years


@router.get("/simulate", response_model=SimulateSellOut)
async def simulate_sell_endpoint(
    asset_id: int = Query(...),
    quantity: float = Query(..., gt=0),
    account_id: int | None = Query(None, description="Conto da cui vendere (default: tutti)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stima l'impatto fiscale di una vendita ipotetica al costo medio ponderato.

    Con ``account_id`` usa il pool PMC di quel conto (amministrato) o il pool
    dichiarativo; senza, la media ponderata di tutti i pool dell'asset.
    """
    result = await db.get(Asset, asset_id)
    if not result:
        raise HTTPException(404, "Asset non trovato")
    asset: Asset = result

    # Prezzo corrente in EUR
    cached = await get_cached_price(asset_id)
    if cached is None:
        try:
            cached = await refresh_asset_price(db, asset)
        except Exception:
            pass
    if cached is None:
        raise HTTPException(503, "Prezzo non disponibile")

    price_eur = cached.get("price", 0.0) * cached.get("exchange_rate", 1.0)

    transactions = await get_transactions(db, current_user.id, limit=_ALL)
    pools = open_cost_pools(transactions)
    selected = [p for k, p in pools.items() if k[-1] == asset_id]
    if account_id is not None:
        acc_tx = next((t for t in transactions if t.account_id == account_id), None)
        if acc_tx is None:
            raise HTTPException(404, "Conto non trovato")
        key = ("A", account_id, asset_id) if acc_tx.account.is_sostituto_imposta else ("D", asset_id)
        selected = [pools[key]] if key in pools else []

    available = sum(p.quantity for p in selected)
    if available < quantity - 1e-9:
        raise HTTPException(400, "Quantità disponibile insufficiente")
    avg_cost = sum(p.quantity * p.avg_cost_per_unit for p in selected) / available

    result_data = simulate_sell(asset, quantity, price_eur, avg_cost)
    return SimulateSellOut(**result_data)


# ── Export PDF fiscale ────────────────────────────────────────────────────────

@router.get("/export/pdf")
async def export_tax_pdf(
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera un PDF del riepilogo fiscale per l'anno richiesto."""
    transactions = await get_transactions(db, current_user.id, limit=_ALL)
    events = compute_tax_events(transactions)
    reports = build_annual_reports(events)
    ivafe = await compute_ivafe(db, transactions, year)

    report: AnnualTaxReport | None = next((r for r in reports if r.year == year), None)
    # report può essere None se non ci sono eventi fiscali quell'anno

    buf = BytesIO()
    styles = getSampleStyleSheet()

    title_st   = ParagraphStyle("t",  parent=styles["Normal"], fontName="Helvetica-Bold",
                                fontSize=20, textColor=_BRAND, spaceAfter=1*mm)
    sub_st     = ParagraphStyle("s",  parent=styles["Normal"], fontName="Helvetica",
                                fontSize=9,  textColor=_GRAY, spaceAfter=5*mm, alignment=TA_RIGHT)
    sec_st     = ParagraphStyle("h",  parent=styles["Normal"], fontName="Helvetica-Bold",
                                fontSize=11, textColor=_BRAND, spaceBefore=6*mm, spaceAfter=3*mm)
    note_st    = ParagraphStyle("n",  parent=styles["Normal"], fontName="Helvetica-Oblique",
                                fontSize=8,  textColor=_GRAY)
    small_st   = ParagraphStyle("sm", parent=styles["Normal"], fontName="Helvetica",
                                fontSize=8,  textColor=_GRAY, spaceAfter=2*mm)

    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_GRAY)
        w, _ = A4
        canvas.drawString(15*mm, 10*mm, f"Nextfolio — Riepilogo fiscale {year} — Documento riservato")
        canvas.drawRightString(w - 15*mm, 10*mm, f"Pagina {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=18*mm, bottomMargin=20*mm,
    )

    def _tbl(rows, col_widths, header=True):
        t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
        base = [
            ("FONTNAME",     (0, 0), (-1, 0 if header else -1), "Helvetica-Bold"),
            ("FONTNAME",     (0, 1 if header else 0), (-1, -1), "Helvetica"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, _ALT_ROW]),
            ("GRID",         (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ]
        if header:
            base.insert(0, ("BACKGROUND", (0, 0), (-1, 0), _BRAND))
            base.insert(1, ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white))
        t.setStyle(TableStyle(base))
        return t

    def _money(v: float) -> str:
        return f"EUR {v:>12,.2f}"

    elems: list = []

    # ── Intestazione ──────────────────────────────────────────────────────────
    elems.append(Paragraph("Nextfolio", title_st))
    elems.append(Paragraph(f"Riepilogo fiscale anno {year} &bull; Generato il {now_str}", sub_st))
    elems.append(HRFlowable(width="100%", color=_BRAND, thickness=1.5, spaceAfter=5*mm))

    if report is None and not ivafe.positions:
        elems.append(Paragraph(f"Nessun evento fiscale registrato per l'anno {year}.", note_st))
    else:
        r = report

        # ── Riepilogo regime ──────────────────────────────────────────────────
        def _sum(prefix: str, kind: str) -> float:
            return sum(getattr(r, f"{prefix}_{kind}_{c}") for c in ("standard", "govt", "funds", "crypto"))

        def _cg_tax(prefix: str) -> float:
            return sum(getattr(r, f"{prefix}_tax_{c}") for c in ("standard", "funds", "crypto"))

        elems.append(Paragraph("Riepilogo per regime fiscale", sec_st))
        regime_rows = [
            ["Voce", "Regime amministrato (broker)", "Regime dichiarativo (730)"],
            ["Plusvalenze (€)", _money(_sum("administered", "gains")) if r else "—",
                                _money(_sum("declaratory", "gains")) if r else "—"],
            ["Minusvalenze (€)", _money(_sum("administered", "losses")) if r else "—",
                                 _money(_sum("declaratory", "losses")) if r else "—"],
            ["Imposta capital gain (€)", _money(_cg_tax("administered")) if r else "—",
                                         _money(_cg_tax("declaratory")) if r else "—"],
            ["Redditi cedole/dividendi (€)", _money(r.administered_dividends_eur) if r else "—",
                                             _money(r.declaratory_dividends_eur) if r else "—"],
            ["Ritenuta su redditi (€)", _money(r.administered_income_tax) if r else "—",
                                        _money(r.declaratory_income_tax) if r else "—"],
        ]
        elems.append(_tbl(regime_rows, [60*mm, 55*mm, 55*mm]))

        # ── Quadri RT / RM ────────────────────────────────────────────────────
        if r and (r.has_declaratory_accounts):
            elems.append(Paragraph("Quadri RT / RM — Redditi finanziari dichiarativi (modello Redditi PF)", sec_st))
            rt_rows = [
                ["Quadro", "Descrizione", "Importo (EUR)"],
                ["RT", "Plusvalenze imponibili 26% (titoli di Stato al 48,08%)", f"{r.declaratory_taxable_gains:>12,.2f}"],
                ["RT", "Minusvalenze compensabili (titoli di Stato al 48,08%, incl. ETF)", f"{r.declaratory_taxable_losses:>12,.2f}"],
                ["RT", "Imposta sostitutiva 26%", f"{r.declaratory_tax_standard:>12,.2f}"],
                ["RT", "Plusvalenze cripto-attività", f"{r.declaratory_gains_crypto:>12,.2f}"],
                ["RT", "Minusvalenze cripto-attività", f"{r.declaratory_losses_crypto:>12,.2f}"],
                ["RT", f"Imposta cripto-attività {r.crypto_rate*100:.0f}%", f"{r.declaratory_tax_crypto:>12,.2f}"],
                ["RM", "Proventi da ETF/OICR esteri (redditi di capitale)", f"{r.declaratory_gains_funds:>12,.2f}"],
                ["RM", "Imposta 26% su proventi ETF/OICR", f"{r.declaratory_tax_funds:>12,.2f}"],
            ]
            t = _tbl(rt_rows, [20*mm, 120*mm, 35*mm])
            t.setStyle(TableStyle([("ALIGN", (2, 1), (2, -1), "RIGHT")]))
            elems.append(t)
            elems.append(Paragraph(
                "I righi esatti dipendono dal modello dell'anno: verifica le istruzioni ufficiali.", small_st,
            ))

        # ── Quadro RW / IVAFE ─────────────────────────────────────────────────
        if ivafe.positions:
            elems.append(Paragraph("Quadro RW — Attività finanziarie estere (IVAFE 0,2%)", sec_st))
            rw_rows = [["Asset", "Tipo", "Quantità", "Prezzo (EUR)", "Valore 31/12 (EUR)", "IVAFE (EUR)", "Data prezzo"]]
            for p in ivafe.positions:
                rw_rows.append([
                    (p.asset_name[:30] + "…") if len(p.asset_name) > 30 else p.asset_name,
                    p.asset_type,
                    f"{p.quantity:,.4f}",
                    f"{p.price_eur:,.4f}",
                    f"{p.market_value_eur:>12,.2f}",
                    f"{p.ivafe_eur:>10,.2f}",
                    p.price_date.strftime("%d/%m/%Y") if p.price_date else "—",
                ])
            rw_rows.append(["", "", "", "Totale", f"{ivafe.total_market_value_eur:>12,.2f}", f"{ivafe.ivafe_eur:>10,.2f}", ""])
            t = _tbl(rw_rows, [45*mm, 18*mm, 22*mm, 22*mm, 28*mm, 22*mm, 23*mm])
            t.setStyle(TableStyle([
                ("ALIGN",      (2, 1), (-1, -1), "RIGHT"),
                ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), _ALT_ROW),
            ]))
            elems.append(t)
            elems.append(Paragraph(
                f"Rigo RW5 — Valore complessivo: EUR {ivafe.total_market_value_eur:,.2f} | "
                f"Rigo RW12 — IVAFE dovuta: EUR {ivafe.ivafe_eur:,.2f}",
                small_st,
            ))

        # ── Redditi da capitale ───────────────────────────────────────────────
        if r and (r.dividends_eur + r.coupons_govt_eur + r.coupons_standard_eur + r.interests_eur) > 0.005:
            elems.append(Paragraph("Redditi da capitale", sec_st))
            rl_rows = [["Categoria", "Aliquota", "Importo lordo (EUR)", "Ritenuta stimata (EUR)"]]
            if r.dividends_eur > 0.005:
                rl_rows.append(["Dividendi azionari", "26%",
                                 f"{r.dividends_eur:>12,.2f}", f"{r.dividends_eur*0.26:>12,.2f}"])
            if r.coupons_govt_eur > 0.005:
                rl_rows.append(["Cedole titoli di Stato", "12,5%",
                                 f"{r.coupons_govt_eur:>12,.2f}", f"{r.coupons_govt_eur*0.125:>12,.2f}"])
            if r.coupons_standard_eur > 0.005:
                rl_rows.append(["Cedole obbligazioni soc.", "26%",
                                 f"{r.coupons_standard_eur:>12,.2f}", f"{r.coupons_standard_eur*0.26:>12,.2f}"])
            if r.interests_eur > 0.005:
                rl_rows.append(["Interessi", "26%",
                                 f"{r.interests_eur:>12,.2f}", f"{r.interests_eur*0.26:>12,.2f}"])
            elems.append(_tbl(rl_rows, [65*mm, 20*mm, 45*mm, 45*mm]))

        # ── Storico minusvalenze ──────────────────────────────────────────────
        if r and (r.prior_carryforward_standard or r.prior_carryforward_crypto):
            elems.append(Paragraph("Zainetto fiscale — minusvalenze disponibili", sec_st))
            cf_rows = [["Anno perdita", "Zainetto", "Disponibile (EUR)", "Scade entro"]]
            for e in r.prior_carryforward_standard:
                cf_rows.append([str(e.year), "Redditi diversi 26%",
                                 f"{e.amount:>12,.2f}", str(e.expires_year)])
            for e in r.prior_carryforward_crypto:
                cf_rows.append([str(e.year), "Cripto-attività",
                                 f"{e.amount:>12,.2f}", str(e.expires_year)])
            elems.append(_tbl(cf_rows, [30*mm, 55*mm, 50*mm, 40*mm]))

        # ── Dettaglio eventi ──────────────────────────────────────────────────
        if r and r.events:
            elems.append(Paragraph("Dettaglio eventi fiscali", sec_st))
            ev_hdr = ["Data", "Asset", "Tipo", "Quantità", "Ricavo EUR", "Costo EUR", "Gain/Loss EUR", "Aliquota", "Metodo"]
            ev_rows = [ev_hdr]
            for ev in sorted(r.events, key=lambda e: e.date):
                rate_str = f"{ev.tax_rate*100:.1f}%".replace(".0%", "%").replace(".", ",")
                ev_rows.append([
                    ev.date.strftime("%d/%m/%Y"),
                    (ev.asset_name[:22] + "…") if len(ev.asset_name) > 22 else ev.asset_name,
                    ev.tx_type,
                    f"{ev.quantity:,.2f}" if ev.quantity else "—",
                    f"{ev.proceeds_eur:>10,.2f}",
                    f"{ev.cost_eur:>10,.2f}" if ev.cost_eur is not None else "—",
                    f"{ev.gain_loss_eur:>+10,.2f}",
                    rate_str,
                    ev.calculation_method,
                ])
            ev_tbl = _tbl(ev_rows, [19*mm, 38*mm, 16*mm, 16*mm, 22*mm, 22*mm, 22*mm, 14*mm, 12*mm])
            ev_tbl.setStyle(TableStyle([("ALIGN", (4, 1), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 7)]))
            elems.append(ev_tbl)

    # ── Disclaimer ────────────────────────────────────────────────────────────
    elems.append(Spacer(1, 8*mm))
    elems.append(HRFlowable(width="100%", color=_GRAY, thickness=0.5, spaceAfter=3*mm))
    elems.append(Paragraph(
        "I valori sono calcolati al costo medio ponderato (art. 68 c.6 TUIR) a scopo informativo; "
        "plus/minus su titoli di Stato ponderate al 48,08%, plusvalenze da ETF/OICR tassate come redditi di capitale. "
        "Potrebbero differire da quanto calcolato dal tuo intermediario. "
        "Per la compilazione definitiva della dichiarazione fiscale si raccomanda di verificare con i prospetti ufficiali "
        "del broker e di consultare un commercialista.",
        note_st,
    ))

    doc.build(elems, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)

    user_slug = current_user.name.lower().replace(" ", "-")
    filename = f"{user_slug}-{datetime.date.today().strftime('%Y-%m-%d')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
