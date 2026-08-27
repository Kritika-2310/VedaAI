import uuid
import base64
import asyncio
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from app.lib import gemini_client, store, pdf_utils  # noqa: E402

app = FastAPI(title="VedaAI Assessment Extraction")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/process")
async def process(question_paper: UploadFile = File(...), answer_sheet: UploadFile = File(...)):
    session_id = str(uuid.uuid4())

    qp_bytes = await question_paper.read()
    as_bytes = await answer_sheet.read()

    qp_mime = question_paper.content_type or "application/pdf"
    as_mime = answer_sheet.content_type or "application/pdf"

    questions, answers = await asyncio.gather(
        gemini_client.extract_questions_async(qp_bytes, qp_mime),
        gemini_client.extract_answers_async(as_bytes, as_mime),
    )
    mapping_result = gemini_client.map_answers(questions, answers)

    answer_sheet_pages = []
    if as_mime == "application/pdf":
        answer_sheet_pages = pdf_utils.pdf_to_page_images(as_bytes)

    store.create_session(
        session_id,
        {
            "questions": questions,
            "answers": answers,
            "mappings": mapping_result.get("mappings", []),
            "unmatched_answer_indices": mapping_result.get("unmatched_answer_indices", []),
            "question_paper_b64": base64.b64encode(qp_bytes).decode(),
            "question_paper_mime": qp_mime,
            "answer_sheet_b64": base64.b64encode(as_bytes).decode(),
            "answer_sheet_mime": as_mime,
            "answer_sheet_pages": answer_sheet_pages,
        },
    )

    return JSONResponse(
        {
            "session_id": session_id,
            "questions": questions,
            "answers": answers,
            "mappings": mapping_result.get("mappings", []),
            "unmatched_answer_indices": mapping_result.get("unmatched_answer_indices", []),
        }
    )


@app.post("/api/grade/{session_id}")
async def grade_session(session_id: str):
    session = store.get_session(session_id)
    if not session:
        return JSONResponse({"error": "session not found"}, status_code=404)

    questions = {q["number"]: q for q in session["questions"]}
    answers = session["answers"]

    pairs = []
    for m in session["mappings"]:
        q = questions.get(m["question_number"])
        if not q:
            continue
        answer_text = " ".join(
            answers[i]["text"] for i in m["answer_indices"] if i < len(answers)
        )
        pairs.append({
            "question_number": m["question_number"],
            "question_text": q["text"],
            "answer_text": answer_text or "(not attempted)",
        })

    results = gemini_client.grade_all(pairs) if pairs else []
    store.update_session(session_id, {"grading": results})
    return JSONResponse({"grading": results})


@app.get("/review/{session_id}", response_class=HTMLResponse)
async def review(request: Request, session_id: str):
    session = store.get_session(session_id)
    if not session:
        return HTMLResponse("Session not found", status_code=404)
    return templates.TemplateResponse(
        "review.html", {"request": request, "session_id": session_id, "session": session}
    )


@app.get("/api/session/{session_id}")
async def get_session_data(session_id: str):
    session = store.get_session(session_id)
    if not session:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(session)


@app.get("/api/debug/{session_id}")
async def debug_session(session_id: str):
    session = store.get_session(session_id)
    if not session:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({
        "num_questions": len(session["questions"]),
        "num_answers": len(session["answers"]),
        "sample_answers": session["answers"][:3],
        "mappings": session["mappings"],
    })
