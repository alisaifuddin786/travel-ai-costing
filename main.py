from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app import build_quote_and_pdf_from_input


app = FastAPI(title="Travel AI Costing")
templates = Jinja2Templates(directory="templates")

PDF_DIR = Path("generated_quotes")
PDF_DIR.mkdir(exist_ok=True)

SAMPLE_RATES_COLUMNS = ["Segment", "MinPax", "MaxPax", "Rate", "Currency"]


def _build_sample_rates_workbook() -> BytesIO:
    sample_df = pd.DataFrame(
        [
            {
                "Segment": "Airport Transfer",
                "MinPax": 1,
                "MaxPax": 3,
                "Rate": 120,
                "Currency": "AED",
            },
            {
                "Segment": "City Tour",
                "MinPax": 1,
                "MaxPax": 6,
                "Rate": 95,
                "Currency": "AED",
            },
        ]
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sample_df.to_excel(writer, index=False, sheet_name="ServiceRates")
    output.seek(0)
    return output


def _validate_uploaded_rates(df: pd.DataFrame) -> list[str]:
    columns = {str(column).strip().lower() for column in df.columns}
    required = {column.lower() for column in SAMPLE_RATES_COLUMNS}
    return sorted(required - columns)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"input_text": "", "result": None, "error": None},
    )


@app.post("/quote", response_class=HTMLResponse)
def quote(request: Request, input_text: str = Form(...)) -> HTMLResponse:
    try:
        output_filename = f"quotation_{uuid4().hex}.pdf"
        output_path = PDF_DIR / output_filename

        quote_result = build_quote_and_pdf_from_input(
            user_input=input_text,
            output_path=output_path,
        )

        result = {
            "pax": quote_result["pax"],
            "month": str(quote_result["month"]).title(),
            "nights": quote_result["nights"],
            "hotel": str(quote_result["hotel"]).title(),
            "room": str(quote_result["room"]).title(),
            "services": [str(item).title() for item in quote_result["services"]],
            "total_cost": f"AED {float(quote_result['total_cost']):,.2f}",
            "pdf_filename": output_filename,
        }

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"input_text": input_text, "result": result, "error": None},
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"input_text": input_text, "result": None, "error": str(exc)},
        )


@app.get("/download/{filename}")
def download_pdf(filename: str) -> FileResponse:
    file_path = PDF_DIR / filename
    if not file_path.exists() or file_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
    )


@app.get("/download-sample-rates")
@app.get("/api/download-sample-rates")
def download_sample_rates() -> StreamingResponse:
    workbook = _build_sample_rates_workbook()
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="service_rates_sample.xlsx"'},
    )


@app.post("/upload-service-rates")
@app.post("/api/upload-service-rates")
async def upload_service_rates(request: Request) -> JSONResponse:
    form = await request.form()
    upload = form.get("file")

    if upload is None:
        return JSONResponse(status_code=400, content={"error": "Missing file in form data (key: file)."})

    filename = str(getattr(upload, "filename", ""))
    if not filename.lower().endswith((".xlsx", ".xls")):
        return JSONResponse(status_code=400, content={"error": "Please upload an Excel file (.xlsx or .xls)."})

    content = await upload.read()
    if not content:
        return JSONResponse(status_code=400, content={"error": "Uploaded file is empty."})

    try:
        rates_df = pd.read_excel(BytesIO(content))
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Unable to read Excel content."})

    missing_columns = _validate_uploaded_rates(rates_df)
    if missing_columns:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid template columns.",
                "missing_columns": missing_columns,
                "expected_columns": SAMPLE_RATES_COLUMNS,
            },
        )

    destination = Path("rates.xlsx")
    destination.write_bytes(content)

    return JSONResponse(
        content={
            "message": "Service rates uploaded successfully.",
            "filename": filename,
            "rows": int(len(rates_df)),
        }
    )
