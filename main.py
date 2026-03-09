from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app import build_quote_and_pdf_from_input


app = FastAPI(title="Travel AI Costing")
templates = Jinja2Templates(directory="templates")

PDF_DIR = Path("generated_quotes")
PDF_DIR.mkdir(exist_ok=True)


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
