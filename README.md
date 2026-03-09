# travel-ai-costing

Simple FastAPI web app for travel quotation generation.

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Input example

```text
4 pax dubai feb
3 nights grand excelsior deluxe
desert safari
city tour
```

The app will:
- parse the request,
- calculate the quotation total from `Rates.xlsx`,
- display the total price,
- generate a downloadable PDF quotation.
